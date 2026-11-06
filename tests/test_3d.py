"""3D and shader kit offline: vendored files, pure timing, render planning and the example builds. No GPU, no browser."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))
import beats
import build
import common
import review_cache
import vertical

NODE = shutil.which("node")
THREE_FILES = {"LICENSE", "three.core.js", "three.module.js", "addons/environments/RoomEnvironment.js",
               "addons/geometries/RoundedBoxGeometry.js"}
NEW_FILES = ["lib/three3d.mjs", "lib/shader.mjs", "lib/motion.mjs", "render3d.mjs", "beats.py", "scenes/sketch/s1.js",
             "scenes/sketch/s1.mjs", "scenes/shader-example/index.html", "scenes/shader-example/scene.mjs"]


def node(code):
    """Run an ES module snippet from engine/ and return its printed JSON."""
    done = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=ENGINE, capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


class VendorTests(unittest.TestCase):
    def test_three_is_vendored_minimal_licensed_and_tracked(self):
        folder = ENGINE / "lib/vendor/three"
        self.assertEqual({p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}, THREE_FILES)
        self.assertIn("MIT License", (folder / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn("REVISION = '181'", (folder / "three.core.js").read_text(encoding="utf-8"))
        if not (ROOT / ".git").exists():
            return
        ignored = subprocess.run(["git", "check-ignore", "-q", "engine/lib/vendor/three/three.module.js"], cwd=ROOT)
        self.assertEqual(ignored.returncode, 1)
        generated = subprocess.run(["git", "check-ignore", "-q", "engine/lib/vendor/gsap.min.js"], cwd=ROOT)
        self.assertEqual(generated.returncode, 0)

    def test_every_addon_import_is_vendored(self):
        text = (ENGINE / "lib/three3d.mjs").read_text(encoding="utf-8")
        for name in re.findall(r'from "three/addons/([^"]+)"', text):
            self.assertTrue((ENGINE / "lib/vendor/three/addons" / name).is_file(), name)


class NeutralityTests(unittest.TestCase):
    def test_new_code_has_no_style_of_its_own(self):
        for name in NEW_FILES:
            text = (ENGINE / name).read_text(encoding="utf-8")
            self.assertNotRegex(text.lower(), r"maxouni|concrete|бетон", name)
            if name.startswith(("lib/", "scenes/")):
                self.assertNotRegex(text, r"#[0-9a-fA-F]{3,8}\b|0x[0-9a-fA-F]{6}\b", name)
                self.assertNotRegex(text, r"\bDate\.now\(|\bMath\.random\(", name)


@unittest.skipUnless(NODE, "node is needed")
class MotionTests(unittest.TestCase):
    def test_halton_matches_known_values(self):
        self.assertEqual(node('import { halton } from "./lib/motion.mjs"; console.log(JSON.stringify([1, 2, 3].map((i) => halton(i, 2))))'),
                         [0.5, 0.25, 0.75])

    def test_mouth_follows_words_and_stays_closed_between_them(self):
        got = node("""import { mouth, speakerWords } from "./lib/motion.mjs";
            const blocks = { "1.1": [{ who: "boss", words: [{ w: "budget", s: 1, e: 1.6 }] }, { who: "dev", words: [{ w: "no", s: 2, e: 2.2 }] }] };
            const open = mouth(speakerWords(blocks, "boss"));
            const samples = [...Array(61).keys()].map((i) => open(1 + i / 100));
            console.log(JSON.stringify({ before: open(0.5), after: open(1.9), other: open(2.1), peak: Math.max(...samples), again: open(1.2) === open(1.2),
              closes: samples.slice(5, 55).some((v) => v < 0.2) }));""")
        self.assertEqual((got["before"], got["after"], got["other"]), (0, 0, 0))
        self.assertGreater(got["peak"], 0.8)
        self.assertTrue(got["again"])
        self.assertTrue(got["closes"], "two syllables must close between them")

    def test_talking_bridges_short_pauses_and_fades(self):
        got = node("""import { talking } from "./lib/motion.mjs";
            const on = talking([{ s: 1, e: 2 }, { s: 2.2, e: 3 }, { s: 6, e: 7 }]);
            console.log(JSON.stringify([on(0), on(2.1), on(4.5), on(6.5)]));""")
        self.assertEqual(got, [0, 1, 0, 1])

    def test_marks_timeline(self):
        got = node("""import { count, markTimes, pulse, since } from "./lib/motion.mjs";
            const hits = markTimes({ marks: [{ t: 2, name: "hit" }, { t: 1, name: "hit" }, { t: 1.5, name: "drop" }] }, "hit");
            console.log(JSON.stringify({ hits, n: [count(hits, 0), count(hits, 1), count(hits, 3)], s: since(hits, 2.5), on: pulse(hits, 1), off: pulse(hits, 0) }));""")
        self.assertEqual(got, {"hits": [1, 2], "n": [0, 1, 2], "s": 0.5, "on": 1, "off": 0})


@unittest.skipUnless(NODE, "node is needed")
class RenderPlanTests(unittest.TestCase):
    def plan(self, expression):
        return node(f'import * as r from "./render3d.mjs"; console.log(JSON.stringify({expression}));')

    def test_stretch_in_frames(self):
        self.assertEqual(self.plan('r.frameRange({}, 60, 6)'), {"total": 360, "first": 0, "last": 360})
        self.assertEqual(self.plan('r.frameRange({ from: "1", to: "2.5" }, 60, 6)'), {"total": 360, "first": 60, "last": 150})
        self.assertEqual(self.plan('r.frameRange({ from: "5", to: "99" }, 25, 6)')["last"], 150)
        with self.assertRaises(AssertionError):
            self.plan('r.frameRange({ from: "3", to: "2" }, 25, 6)')

    def test_output_options_follow_every_input(self):
        args = self.plan('r.encodeArgs("frames", 60, 120, 30, "out.mp4", "track.wav")')
        self.assertEqual(args.count("-i"), 2)
        self.assertLess(len(args) - args[::-1].index("-i"), args.index("-frames:v"))
        self.assertEqual(args[args.index("-ss") + 1], "2")
        self.assertEqual(args[-1], "out.mp4")
        self.assertNotIn("-ss", self.plan('r.encodeArgs("frames", 60, 0, 30, "out.mp4")'))

    def test_page_spec_and_names(self):
        spec = self.plan('r.pageSpec(`<div class="x" id="root" data-start="0" data-duration="6.40" data-fps="25" data-width="1080" data-height="1920">`)')
        self.assertEqual(spec, {"width": 1080, "height": 1920, "fps": 25, "duration": 6.4})
        with self.assertRaises(AssertionError):
            self.plan('r.pageSpec("<div>")')
        page = self.plan('r.locate("scenes/shader-example/index.html")')
        self.assertEqual((page["path"], page["name"], page["project"]), ("scenes/shader-example/index.html", "shader-example", "shader-example"))
        self.assertEqual(self.plan('r.locate("scenes/shader-example")')["name"], "shader-example")
        with self.assertRaises(AssertionError):
            self.plan('r.locate("no-such-composition")')

    def test_clear_error_without_a_video_card(self):
        self.assertIn("No WebGL2", self.plan('r.gpuProblem({ webgl2: false })'))
        soft = {"webgl2": True, "floatTargets": True, "renderer": "ANGLE (Google, Vulkan (SwiftShader Device), SwiftShader driver)"}
        self.assertIn("No video card", self.plan(f"r.gpuProblem({json.dumps(soft)})"))
        self.assertIsNone(self.plan(f"r.gpuProblem({json.dumps(soft)}, true)"))
        self.assertIsNone(self.plan('r.gpuProblem({ webgl2: true, floatTargets: true, renderer: "ANGLE Metal Renderer: Apple M4" })'))

    def test_shader_example_declares_itself(self):
        html = (ENGINE / "scenes/shader-example/index.html").read_text(encoding="utf-8")
        spec = node('import { pageSpec } from "./render3d.mjs"; import { readFileSync } from "node:fs";'
                    'console.log(JSON.stringify(pageSpec(readFileSync("scenes/shader-example/index.html", "utf8"))));')
        self.assertEqual(spec["fps"], 60)
        self.assertIn("../../lib/tokens.css", html)
        marks = json.loads((ENGINE / "scenes/shader-example/beats.json").read_text(encoding="utf-8"))["marks"]
        self.assertEqual(sum(m["name"] == "drop" for m in marks), 1)


class CompositionTests(unittest.TestCase):
    def test_module_joins_only_when_the_scene_has_one(self):
        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder)
            (here / "template-v.html").write_text("{{ID}} {{DUR}} {{TIMING}} {{WORLD}} {{OVERLAY}} {{EXTRA}} {{SCENE}}")
            (here / "scenes/a").mkdir(parents=True)
            (here / "scenes/a/s1.js").write_text("")
            with patch.object(build, "HERE", here):
                build.composition("flat", 1, {}, "scenes/a/s1.js", template="template-v.html")
                (here / "scenes/a/s1.mjs").write_text("")
                build.composition("deep", 1, {}, "scenes/a/s1.js", template="template-v.html")
            self.assertNotIn("importmap", (here / "flat.html").read_text())
            deep = (here / "deep.html").read_text()
            self.assertIn('"three": "./lib/vendor/three/three.module.js"', deep)
            self.assertIn('<script type="module" src="scenes/a/s1.mjs">', deep)

    def test_sketch_builds_on_estimated_timing_without_tags_in_text(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            shutil.copy(ENGINE / "template-v.html", temp / "template-v.html")
            shutil.copytree(ENGINE / "scenes/sketch", temp / "scenes/sketch")
            with patch.object(vertical, "BUILD", temp / "build"), patch.object(vertical, "SCENES", temp / "scenes"), \
                    patch.object(vertical, "sync_style"), patch.object(build, "HERE", temp):
                vertical.cmd_build(str(ROOT / "vertical/sketch.md"), "1", "yt", "--estimate")
            html = (temp / "sketch-s1-yt.html").read_text(encoding="utf-8")
        timing = json.loads(re.search(r"window\.TIMING = (.*?);</script>", html).group(1))
        lines = [p for block in timing["blocks"].values() for p in block]
        self.assertEqual({p["who"] for p in lines}, {"boss", "dev"})
        self.assertNotRegex(" ".join([p["text"] for p in lines] + [w["w"] for p in lines for w in p["words"]]), r"[{}]|boss:|dev:")
        self.assertIn("scenes/sketch/s1.mjs", html)

    def test_review_fingerprint_follows_the_import_map(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            here = root / "engine"
            (here / "lib/vendor/three").mkdir(parents=True)
            (root / "style").mkdir()
            (root / ".agents/skills/review").mkdir(parents=True)
            for name in ("package.json", "requirements.txt", ".agents/skills/review/SKILL.md"):
                (root / name).write_text("x")
            for name in review_cache.CODE:
                (here / name).write_text("x")
            for name in ("template.html", "template-v.html", "hyperframes.json"):
                (here / name).write_text("x")
            (here / "lib/three3d.mjs").write_text('import * as T from "three"; import { R } from "three/addons/x.js";')
            (here / "lib/vendor/three/three.module.js").write_text("image.src = url;")
            (here / "a-s1-yt.html").write_text('<div id="root" data-duration="1"></div><script type="module" src="lib/three3d.mjs"></script>')
            with patch.object(common, "HERE", here), patch.object(common, "ROOT", root), \
                    patch.object(review_cache, "browser_identity", return_value={}):
                result = review_cache.fingerprint("a-s1-yt")
            self.assertEqual(result["reasons"], [])


class BeatsTests(unittest.TestCase):
    def track(self):
        sr, rng = beats.SR, np.random.default_rng(1)
        x = np.zeros(10 * sr, dtype=np.float32)
        hits = [0.5 * i for i in range(1, 20)]
        for t in hits:
            n = int(0.08 * sr)
            loud = 1.0 if t >= 6 else 0.35
            burst = rng.normal(0, 0.1, n) * np.linspace(1, 0, n)
            x[int(t * sr):int(t * sr) + n] += (loud * burst).astype(np.float32)
        t = np.arange(4 * sr) / sr
        x[6 * sr:] += (0.5 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)
        return x, hits

    def test_finds_hits_tempo_and_drop_of_a_synthetic_track(self):
        x, hits = self.track()
        bpm, marks = beats.analyse(x)
        found = [m["t"] for m in marks if m["name"] == "hit"]
        near = sum(any(abs(a - b) < 0.05 for a in found) for b in hits)
        self.assertGreaterEqual(near, len(hits) - 2)
        self.assertAlmostEqual(bpm, 120, delta=4)
        self.assertAlmostEqual(next(m["t"] for m in marks if m["name"] == "drop"), 6.0, delta=0.15)

    def test_writes_sheet_and_click_track(self):
        x, _ = self.track()
        with tempfile.TemporaryDirectory() as folder:
            marks = [{"t": 1.0, "name": "hit"}, {"t": 6.0, "name": "drop"}]
            beats.sheet(x, marks, Path(folder) / "m.png")
            beats.clicks(x, marks, Path(folder) / "c.wav")
            rate, audio = wavfile.read(Path(folder) / "c.wav")
            self.assertEqual((rate, len(audio)), (beats.SR, len(x)))
            self.assertGreater((Path(folder) / "m.png").stat().st_size, 0)


class SkillTests(unittest.TestCase):
    def test_skill_is_routed_everywhere(self):
        self.assertTrue((ROOT / ".agents/skills/3d/SKILL.md").is_file())
        self.assertIn("`3d`", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        for name in ("README.md", "README.ru.md", "engine/README.md"):
            self.assertIn("render3d.mjs", (ROOT / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
