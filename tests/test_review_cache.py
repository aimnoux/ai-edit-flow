"""Offline evidence/conclusion cache regression checks: no browser or paid API calls."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import common
import review
import review_cache as cache


class ReviewCacheTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="aef-review-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.here = self.root / "engine"
        self.out = self.root / "review"
        self.browser = {"path": "/mock/chrome-headless-shell", "version": "123", "sha256": "fake"}
        for name in cache.CODE:
            self.write("engine/" + name, "# fixture checker\n")
        for name in ("template.html", "template-v.html", "hyperframes.json"):
            self.write("engine/" + name, "{}")
        self.write("engine/lib/finish.js", "// finish\n")
        self.write("engine/lib/tokens.css", "body {color: white}")
        self.write("style/tokens.css", "body {color: white}")
        self.write(".agents/skills/review/SKILL.md", "Review all sheets")
        self.write(".agents/skills/review/references/checklist.md", "Check contrast")
        self.write("package.json", '{"config":{"hyperframes":"1"}}')
        self.write("package-lock.json", "{}")
        self.write("requirements.txt", "Pillow>=10")
        self.write("videos/demo/script.md", "# spoken script")
        self.write("videos/demo/video.json", '{"fps":25}')
        self.write("engine/scenes/demo/one.js", 'import "./nested.js";')
        self.write("engine/scenes/demo/nested.js", "// nested")
        self.write("engine/assets/image.png", "asset bytes")
        self.write("engine/demo-ch1.html", '<div id="root" data-duration="10"></div>'
                   '<script src="scenes/demo/one.js"></script><img src="assets/image.png">')
        patches = [patch.object(common, "ROOT", self.root), patch.object(common, "HERE", self.here),
                   patch.object(review, "BUILD", self.here / "build"),
                   patch.object(cache, "browser_identity", side_effect=lambda: dict(self.browser)),
                   patch.object(review, "_generate", side_effect=self.generate)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.generations = 0

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def generate(self, cid, out, chap, video, name):
        self.generations += 1
        (out / "REVIEW-INPUT.md").write_text("Evidence " + name)
        (out / "beats-1.jpg").write_bytes(b"fake image")
        return {"sheets": ["beats-1.jpg"], "findings": [],
                "runtime": {"duration": 10, "scenes": 2, "vertical": False}}

    def reviewer(self, text="Verdict: PASS"):
        return self.write("reviewer.md", text + "\nFingerprint: " + cache.fingerprint("demo-ch1")["fingerprint"])

    def run_review(self, **kwargs):
        return review.run_review("demo-ch1", out=self.out, **kwargs)

    def test_unchanged_hit_no_generation_or_snapshots(self):
        first = self.run_review()
        with patch.object(review, "snap", side_effect=AssertionError("no snapshots on hit")):
            second = self.run_review()
        self.assertEqual((first["status"], second["status"], self.generations), ("generated", "cached", 1))
        self.assertEqual(second["conclusion"], {"status": "pending", "path": None, "verdict": None})
        self.assertTrue(Path(second["input"]).is_absolute())
        self.assertTrue(all(Path(p).is_absolute() for p in second["sheets"]))

    def test_local_font_face_can_be_approved_and_font_changes_invalidate_review(self):
        css = self.write("engine/lib/tokens.css", '@font-face {font-family: "Pilot"; src: url("fonts/pilot.woff2");}')
        font = self.write("engine/lib/fonts/pilot.woff2", "first font bytes")
        composition = self.here / "demo-ch1.html"
        composition.write_text(composition.read_text() + '<link rel="stylesheet" href="lib/tokens.css">')
        first = cache.fingerprint("demo-ch1")
        self.assertTrue(first["reusable"], first["reasons"])
        self.run_review()
        approved = self.run_review(record_review=self.reviewer())
        self.assertEqual(approved["conclusion"]["verdict"], "pass")
        font.write_text("changed font bytes")
        self.assertNotEqual(first["fingerprint"], cache.fingerprint("demo-ch1")["fingerprint"])
        changed = self.run_review()
        self.assertEqual(changed["conclusion"]["status"], "pending")

    def test_root_relative_resource_does_not_assume_the_project_directory(self):
        path = self.here / "demo-ch1.html"
        path.write_text(path.read_text() + '<img src="/assets/image.png">')
        result = cache.fingerprint("demo-ch1")
        self.assertFalse(result["reusable"])
        self.assertTrue(any("root-relative" in reason for reason in result["reasons"]))

    def test_content_changes_invalidate_every_input_category(self):
        self.run_review()
        paths = ["engine/demo-ch1.html", "engine/scenes/demo/one.js", "engine/scenes/demo/nested.js",
                 "engine/assets/image.png", "engine/lib/finish.js", "style/tokens.css",
                 "videos/demo/script.md", "videos/demo/video.json", "engine/template.html",
                 "engine/check.py", "engine/review_cache.py", "engine/hf.mjs", "engine/common.py",
                 "engine/process_guard.py", "engine/compare.py", "package.json", "package-lock.json", "requirements.txt",
                 ".agents/skills/review/references/checklist.md"]
        for name in paths:
            with self.subTest(name=name):
                p = self.root / name
                # Preserve mtime to prove freshness is content based.
                old = p.stat()
                p.write_bytes(p.read_bytes() + b"\n ")
                os.utime(p, ns=(old.st_atime_ns, old.st_mtime_ns))
                self.assertEqual(self.run_review()["status"], "generated")
                self.assertEqual(self.run_review()["status"], "cached")

    def test_unrelated_scene_and_project_do_not_invalidate(self):
        first = self.run_review()
        self.write("engine/scenes/other/scene.js", "changed")
        self.write("engine/scenes/demo/ch2.js", "changed different chapter")
        self.write("videos/other/script.md", "changed")
        self.assertEqual(self.run_review()["fingerprint"], first["fingerprint"])
        self.assertEqual(self.generations, 1)

    def test_mtime_only_change_keeps_hit(self):
        self.run_review()
        os.utime(self.here / "lib/finish.js", (1, 1))
        self.assertEqual(self.run_review()["status"], "cached")

    def test_runtime_package_identity_invalidates(self):
        self.run_review()
        with patch.object(cache, "runtime_identity", return_value={"python": "changed", "packages": {"Pillow": "new"}}):
            self.assertEqual(self.run_review()["status"], "generated")
            self.assertEqual(self.run_review()["status"], "cached")

    def test_browser_and_video_contents_invalidate(self):
        video = self.write("render.mp4", "media")
        first = self.run_review(video=video)
        self.browser["version"] = "124"
        self.assertNotEqual(self.run_review(video=video)["fingerprint"], first["fingerprint"])
        video.write_bytes(b"new media")
        self.assertEqual(self.run_review(video=video)["status"], "generated")
        self.assertEqual(self.run_review(video=video)["status"], "cached")

    def test_exact_ranges_and_validation(self):
        a = review.run_review("demo-ch1", chapter=[0.1, 1.1])
        b = review.run_review("demo-ch1", chapter=[0.2, 1.2])
        self.assertNotEqual(a["input"], b["input"])
        self.assertNotEqual(a["fingerprint"], b["fingerprint"])
        self.assertEqual(review.run_review("demo-ch1", chapter=[0.1, 1.1])["status"], "cached")
        for bounds in ((1, 1), (-1, 2), (0, 11), (float("nan"), 2), (0, float("inf"))):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                self.run_review(chapter=bounds)

    def test_backtick_resource_asset_change_invalidates_approved_evidence(self):
        p = self.here / "demo-ch1.html"
        p.write_text(p.read_text() + '<script>const img=new Image(); img.src = `assets/second.png`;</script>')
        asset = self.write("engine/assets/second.png", "first")
        self.run_review()
        self.run_review(record_review=self.reviewer())
        asset.write_text("changed")
        result = self.run_review()
        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["conclusion"]["status"], "pending")

    def test_backtick_fetch_and_import_dependencies_are_hashed(self):
        p = self.here / "demo-ch1.html"
        p.write_text(p.read_text() + '<script>fetch(`assets/data.json`); import(`scenes/demo/dynamic.js`);</script>')
        self.write("engine/assets/data.json", "{}")
        imported = self.write("engine/scenes/demo/dynamic.js", "// loaded")
        self.run_review()
        imported.write_text("// changed")
        self.assertEqual(self.run_review()["status"], "generated")

    def test_svg_object_href_is_tracked_and_computed_attributes_fail_closed(self):
        p = self.here / "scenes/demo/nested.js"
        p.write_text("svg('image', {href:'assets/second.png'}, parent);")
        asset = self.write("engine/assets/second.png", "first")
        self.run_review()
        self.run_review(record_review=self.reviewer())
        asset.write_text("changed")
        result = self.run_review()
        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["conclusion"]["status"], "pending")
        for source in ("svg('image', {href:path}, parent);", "svg('image', {[key]:path}, parent);"):
            with self.subTest(source=source):
                p.write_text(source)
                self.assertFalse(self.run_review()["reusable"])

    def test_vertical_known_avatar_empty_asset_and_escape(self):
        self.write("engine/lib/vertical.js", 'const avatar = ch.avatar ? `style="background-image:url(lib/${ch.avatar})"` : "";')
        p = self.here / "demo-ch1.html"
        original = p.read_text() + '<script src="lib/vertical.js"></script>'
        def channel(avatar):
            p.write_text(original + '<script>window.TIMING = ' + json.dumps({"channel": {"avatar": avatar}}) + ';</script>')
        channel("")
        self.assertTrue(self.run_review()["reusable"])
        channel("assets/avatar.png")
        asset = self.write("engine/lib/assets/avatar.png", "first")
        self.run_review()
        asset.write_text("changed")
        self.assertEqual(self.run_review()["status"], "generated")
        channel("../../private.png")
        self.assertFalse(self.run_review()["reusable"])
        channel("https://host/avatar.png")
        self.assertFalse(self.run_review()["reusable"])

    def test_unresolved_template_or_setattribute_cannot_be_approved(self):
        p = self.here / "demo-ch1.html"
        original = p.read_text()
        for source in ('img.src = `assets/${name}.png`;',
                       'img.setAttribute("src", "assets/image.png");',
                       'fetch(`https://host/${name}`);',
                       'img["src"] = "assets/image.png";',
                       'img.setAttributeNS(null,"href","assets/image.png");'):
            with self.subTest(source=source):
                p.write_text(original + "<script>" + source + "</script>")
                result = self.run_review()
                self.assertFalse(result["reusable"])
                with self.assertRaisesRegex(RuntimeError, "existing current"):
                    self.run_review(record_review=self.reviewer())

    def test_missing_dependency_fails_closed(self):
        self.run_review()
        (self.here / "assets/image.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_review()

    def test_external_and_dynamic_dependency_never_reused(self):
        for reference in ('<script src="https://host/app.js"></script>', '<script>fetch(dynamicURL)</script>'):
            with self.subTest(reference=reference):
                p = self.here / "demo-ch1.html"
                p.write_text(p.read_text() + reference)
                result = self.run_review()
                self.assertFalse(result["reusable"])
                self.assertTrue(result["cache_notes"])
                self.assertEqual(self.run_review()["status"], "generated")
                self.assertFalse((self.out / cache.MANIFEST).exists())

    def test_missing_corrupt_and_changed_artifacts_regenerate(self):
        self.run_review()
        for name, contents in (("beats-1.jpg", None), ("beats-1.jpg", b"changed"),
                               ("REVIEW-INPUT.md", b"changed"), (cache.MANIFEST, b"invalid json")):
            with self.subTest(name=name, contents=contents):
                path = self.out / name
                path.unlink() if contents is None else path.write_bytes(contents)
                self.assertEqual(self.run_review()["status"], "generated")

    def test_human_conclusion_explicit_binding_and_corruption(self):
        reviewer = self.reviewer("Verdict: PASS\nReviewed every sheet")
        with self.assertRaisesRegex(RuntimeError, "existing current"):
            self.run_review(record_review=reviewer)
        self.run_review()
        result = self.run_review(record_review=reviewer)
        self.assertEqual(result["status"], "cached")
        self.assertEqual(result["conclusion"]["verdict"], "pass")
        self.assertEqual(self.run_review()["conclusion"]["status"], "current")
        for changed in ("Verdict: PASS\nmodified", None):
            p = self.out / "REVIEW.md"
            p.unlink() if changed is None else p.write_text(changed)
            self.assertEqual(self.run_review()["conclusion"]["status"], "pending")
            self.run_review(record_review=reviewer)
        reviewer = self.reviewer("Verdict: FAIL\nNeeds revision")
        self.assertEqual(self.run_review(record_review=reviewer)["conclusion"]["verdict"], "fail")
        self.write("engine/lib/finish.js", "// changed")
        self.assertEqual(self.run_review()["conclusion"]["status"], "pending")
        self.assertFalse((self.out / "REVIEW.md").exists())

    def test_empty_missing_ambiguous_conclusion_rejected(self):
        self.run_review()
        for text in ("", "Looks good", "Verdict: PASS\nVerdict: FAIL"):
            reviewer = self.write("reviewer.md", text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.run_review(record_review=reviewer)
        with self.assertRaises(FileNotFoundError):
            self.run_review(record_review=self.root / "missing.md")

    def test_stale_reviewer_file_cannot_approve_new_evidence(self):
        self.run_review()
        reviewer = self.reviewer()
        self.run_review(record_review=reviewer)
        self.write("style/tokens.css", "changed")
        result = self.run_review()
        self.assertIn("Fingerprint: " + result["fingerprint"], Path(result["input"]).read_text())
        with self.assertRaisesRegex(ValueError, "current Fingerprint"):
            self.run_review(record_review=reviewer)
        self.assertEqual(self.run_review()["conclusion"]["status"], "pending")
        reviewer = self.reviewer()
        self.assertEqual(self.run_review(record_review=reviewer)["conclusion"]["status"], "current")

    def test_force_resets_human_conclusion(self):
        self.run_review()
        reviewer = self.reviewer()
        self.run_review(record_review=reviewer)
        result = self.run_review(force=True)
        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["conclusion"]["status"], "pending")
        self.assertEqual(self.generations, 2)

    def test_failure_and_input_race_never_publish_success_manifest(self):
        self.run_review()
        with patch.object(review, "_generate", side_effect=RuntimeError("failed snapshot")):
            with self.assertRaises(RuntimeError):
                self.run_review(force=True)
        self.assertFalse((self.out / cache.MANIFEST).exists())
        def race(*args):
            result = self.generate(*args)
            self.write("style/tokens.css", "changed during generation")
            return result
        with patch.object(review, "_generate", side_effect=race):
            with self.assertRaisesRegex(RuntimeError, "changed during"):
                self.run_review()
        self.assertFalse((self.out / cache.MANIFEST).exists())

    def test_video_metrics_are_cropped_and_failures_propagate(self):
        with patch("review.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            review.dead("video.mp4", chapter=[2.1, 4.2])
            review.lulls("video.mp4", chapter=[2.1, 4.2])
        for call in run.call_args_list:
            args = call.args[0]
            self.assertEqual(args[args.index("-ss") + 1], "2.1")
            self.assertEqual(args[args.index("-t") + 1], "2.1")
            self.assertTrue(call.kwargs["check"])

    def test_process_death_releases_lock(self):
        self.out.mkdir()
        engine = str(Path(cache.__file__).resolve().parent)
        program = ("import sys,time;sys.path.insert(0,sys.argv[1]);"
                   "from pathlib import Path;import review_cache;"
                   "lock=review_cache.review_lock(Path(sys.argv[2]));lock.__enter__();"
                   "print('locked',flush=True);time.sleep(60)")
        child = subprocess.Popen([sys.executable, "-c", program, engine, str(self.out)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "locked")
            with self.assertRaisesRegex(RuntimeError, "Another review"):
                with cache.review_lock(self.out):
                    self.fail("Concurrent process must own the lock")
            child.kill()
            child.wait(timeout=10)
            with cache.review_lock(self.out):
                pass
            self.assertEqual(self.run_review()["status"], "generated")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
            child.stdout.close()
            child.stderr.close()

    def test_json_cli_has_no_progress_stdout(self):
        stream = io.StringIO()
        with patch.object(sys, "argv", ["review.py", "demo-ch1", "--json", "-o", str(self.out)]):
            with contextlib.redirect_stdout(stream):
                code = review.main()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stream.getvalue())["status"], "generated")


if __name__ == "__main__":
    unittest.main()
