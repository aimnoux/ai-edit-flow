"""Unified verification reports: offline checker stubs and synthetic final-file metadata."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import review
import review_cache
import verify

HTML = '<div id="root" data-duration="1" data-fps="25" data-width="320" data-height="180"></div>'


class VerifyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="aef-verify-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.engine = self.root / "engine"
        self.engine.mkdir()
        (self.engine / "example-ch1.html").write_text(HTML)
        for name, value in (("BUILD", self.engine / "build"), ("HERE", self.engine)):
            context = patch.object(verify, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.result = {"status": "generated", "fingerprint": "abc", "input": str(self.root / "REVIEW-INPUT.md"),
                       "sheets": [str(self.root / "beats.jpg")], "findings": [],
                       "conclusion": {"status": "pending", "path": None, "verdict": None}}
        self.runner = patch.object(review, "run_review", return_value=self.result, create=True)
        self.run_review = self.runner.start()
        self.addCleanup(self.runner.stop)
        identity = patch.object(review_cache, "fingerprint", return_value={"fingerprint": "abc"})
        identity.start()
        self.addCleanup(identity.stop)

    def metadata(self, **overrides):
        v = {"codec_type": "video", "width": 320, "height": 180, "avg_frame_rate": "25/1"}
        v.update(overrides)
        return {"streams": [v, {"codec_type": "audio"}], "format": {"duration": "1.0"}}

    def probe(self, data):
        result = subprocess.CompletedProcess([], 0, json.dumps(data), "")
        with patch("verify.subprocess.run", return_value=result):
            return verify.probe_video(self.root / "out.mp4", self.engine / "example-ch1.html")

    def test_automated_success_does_not_approve_visuals(self):
        result = verify.verify(["example-ch1"])
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["ready_to_show"])
        self.assertEqual(result["items"][0]["conclusion"]["status"], "pending")
        self.assertEqual(json.loads(Path(result["report"]).read_text()), result)

    def test_current_pass_can_be_reused_without_separate_browser_checks(self):
        self.result.update(status="cached", conclusion={"status": "current", "path": "REVIEW.md", "verdict": "pass"})
        with patch("common.run_chrome") as browser:
            result = verify.verify(["example-ch1"])
        browser.assert_not_called()
        self.assertTrue(result["ready_to_show"])
        self.assertEqual(result["items"][0]["cache"], "cached")
        self.run_review.assert_called_once()

    def test_current_fail_is_not_success(self):
        self.result["conclusion"] = {"status": "current", "path": "REVIEW.md", "verdict": "fail"}
        result = verify.verify(["example-ch1"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["ready_to_show"])

    def test_untracked_dependency_is_not_silently_approved(self):
        self.result.update(reusable=False, cache_notes=["external dependency"])
        result = verify.verify(["example-ch1"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["ready_to_show"])
        self.assertIn("Untracked dependencies", result["items"][0]["error"])

    def test_changed_inputs_during_metadata_check_cannot_pass(self):
        with patch.object(review_cache, "fingerprint", return_value={"fingerprint": "changed"}):
            result = verify.verify(["example-ch1"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["ready_to_show"])

    def test_force_is_forwarded_and_needs_new_visual_review(self):
        result = verify.verify(["example-ch1"], chapter=[0, 1], force=True)
        self.assertTrue(self.run_review.call_args.kwargs["force"])
        self.assertEqual(self.run_review.call_args.kwargs["chapter"], [0, 1])
        self.assertFalse(result["ready_to_show"])

    def test_warnings_are_reported_and_strict_fails(self):
        self.result["findings"] = ["- t=0.2s · craft/short_hold (warning) · hold the text"]
        self.assertEqual(verify.verify(["example-ch1"])["status"], "passed")
        result = verify.verify(["example-ch1"], strict=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["items"][0]["warnings"], 1)

    def test_exception_and_verbose_output_go_to_log(self):
        def fail(*args, **kwargs):
            print("very long checker output")
            raise RuntimeError("composition missing")
        self.run_review.side_effect = fail
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = verify.verify(["example-ch1"])
        self.assertEqual(stdout.getvalue(), "")
        item = result["items"][0]
        self.assertEqual(item["status"], "failed")
        self.assertIn("very long checker output", Path(item["log"]).read_text())
        self.assertIn("Traceback", Path(item["log"]).read_text())

    def test_json_cli_contains_only_json(self):
        def noisy(*args, **kwargs):
            print("extra logs")
            return self.result
        self.run_review.side_effect = noisy
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["verify.py", "example-ch1", "--json"]), redirect_stdout(stdout):
            code = verify.main()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "passed")
        self.assertNotIn("extra logs", stdout.getvalue())

    def test_stdout_json_limits_findings_but_keeps_full_report(self):
        self.result["findings"] = ["warning: " + str(i) + "x" * 500 for i in range(100)]
        result = verify.verify(["example-ch1"])
        brief = verify.compact_report(result)
        self.assertLess(len(json.dumps(brief)), 2500)
        self.assertEqual(len(brief["items"][0]["findings_preview"]), 3)
        stored = json.loads(Path(result["report"]).read_text())
        self.assertEqual(len(stored["items"][0]["findings"]), 100)

    def test_unknown_project_fails(self):
        with patch.object(sys, "argv", ["verify.py", "--project", "absent"]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                verify.main()
        self.assertNotEqual(error.exception.code, 0)

    def test_video_and_range_require_a_single_composition(self):
        with patch.object(sys, "argv", ["verify.py", "one", "two", "--video", "out.mp4"]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                verify.main()

    def test_missing_audio_is_not_a_valid_final_file(self):
        d = self.metadata()
        d["streams"].pop()
        with self.assertRaisesRegex(ValueError, "no audio"):
            self.probe(d)

    def test_wrong_dimensions_fail(self):
        with self.assertRaisesRegex(ValueError, "width"):
            self.probe(self.metadata(width=640))

    def test_wrong_fps_fails(self):
        with self.assertRaisesRegex(ValueError, "frame rate"):
            self.probe(self.metadata(avg_frame_rate="30/1"))

    def test_wrong_duration_fails(self):
        d = self.metadata()
        d["format"]["duration"] = "2.5"
        with self.assertRaisesRegex(ValueError, "duration"):
            self.probe(d)

    def test_matching_video_passes(self):
        result = self.probe(self.metadata())
        self.assertEqual(result["width"], 320)
        self.assertEqual(result["audio_streams"], 1)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
    def test_real_final_file_streams(self):
        video = self.root / "final.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=s=320x180:r=25:d=1",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-preset", "ultrafast",
                        "-c:a", "aac", "-shortest", str(video)], check=True, capture_output=True)
        result = verify.probe_video(video, self.engine / "example-ch1.html")
        self.assertEqual(result["fps"], 25)
        self.assertAlmostEqual(result["duration"], 1, delta=.05)


if __name__ == "__main__":
    unittest.main()
