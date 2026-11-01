"""Browser isolation and failure handling without launching a real browser."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import common
import check


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aef-browser-test-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {k: "" for k in (
            "CHROME_PATH", "HYPERFRAMES_BROWSER_PATH", "PRODUCER_HEADLESS_SHELL_PATH", "PUPPETEER_CACHE_DIR")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def binary(self, body, name="chrome-headless-shell"):
        path = self.folder / name
        path.write_text(f"#!{sys.executable}\n{body}\n")
        path.chmod(0o755)
        return path

    def test_desktop_browser_rejected_before_launch(self):
        browser = self.binary("raise SystemExit('must never run')", "Google Chrome")
        with patch.dict(os.environ, {"CHROME_PATH": str(browser)}), patch("common.subprocess.Popen") as start:
            with self.assertRaisesRegex(RuntimeError, "dedicated"):
                common.run_chrome("--dump-dom")
            start.assert_not_called()

    def test_symlink_to_desktop_browser_rejected(self):
        if os.name == "nt":
            self.skipTest("Symlink permission differs on Windows")
        desktop = self.binary("pass", "Google Chrome")
        shell = self.folder / "chrome-headless-shell"
        shell.symlink_to(desktop)
        with patch.dict(os.environ, {"CHROME_PATH": str(shell)}):
            with self.assertRaisesRegex(RuntimeError, "dedicated"):
                common.chrome()

    def test_no_system_browser_fallback(self):
        with patch("common.Path.home", return_value=self.folder), patch("common.shutil.which") as lookup:
            with self.assertRaisesRegex(RuntimeError, "Dedicated browser not found"):
                common.chrome()
            lookup.assert_not_called()

    def test_managed_headless_cache_selected(self):
        browser = self.folder / ".cache/hyperframes/chrome/chrome-headless-shell/mac_arm-1/shell/chrome-headless-shell"
        browser.parent.mkdir(parents=True)
        browser.write_text("fake binary")
        browser.chmod(0o755)
        with patch("common.Path.home", return_value=self.folder):
            self.assertEqual(common.chrome(), str(browser.resolve()))

    @unittest.skipIf(os.name == "nt", "Executable script fixture uses a POSIX shebang")
    def test_profile_removed_on_success(self):
        browser = self.binary("import json,sys\nprint(json.dumps(sys.argv[1:]))")
        with patch.dict(os.environ, {"CHROME_PATH": str(browser)}):
            result = common.run_chrome("--dump-dom")
        args = json.loads(result.stdout)
        profile = next(a.split("=", 1)[1] for a in args if a.startswith("--user-data-dir="))
        self.assertFalse(Path(profile).exists())
        self.assertIn("--disable-crash-reporter", args)

    @unittest.skipIf(os.name == "nt", "Executable script fixture uses a POSIX shebang")
    def test_failed_browser_is_an_error(self):
        browser = self.binary("import sys\nprint('failed to launch',file=sys.stderr)\nsys.exit(7)")
        with patch.dict(os.environ, {"CHROME_PATH": str(browser)}):
            with self.assertRaisesRegex(RuntimeError, "failed.*7.*failed to launch"):
                common.run_chrome("--dump-dom")

    @unittest.skipIf(os.name == "nt", "Executable script fixture uses a POSIX shebang")
    def test_timeout_cleans_profile(self):
        marker = self.folder / "profile.txt"
        browser = self.binary("import sys,time,pathlib\np=next(a.split('=',1)[1] for a in sys.argv if a.startswith('--user-data-dir='))\n"
                              f"pathlib.Path({str(marker)!r}).write_text(p)\ntime.sleep(30)")
        with patch.dict(os.environ, {"CHROME_PATH": str(browser)}):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                common.run_chrome(timeout=0.3)
        self.assertFalse(Path(marker.read_text()).exists())

    def test_empty_dom_fails_instead_of_ok(self):
        with patch("check.dom", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "did not finish"):
                check.check("missing")

    def test_script_error_reported(self):
        with patch("check.dom", return_value='<html data-err="ReferenceError: TL is not defined">'):
            self.assertEqual(check.check("bad")[0], "ReferenceError: TL is not defined")

    def test_finished_composition_counts_actual_scenes(self):
        html = ('<html data-scenes="[[0,1],[1,2]]"><div id="root" data-composition-id="test"></div>'
                '<script id="cues">[{"name":"tap"}]</script></html>')
        with patch("check.dom", return_value=html):
            self.assertEqual(check.check("good"), (None, 1, 2))

    def test_unknown_project_is_not_success(self):
        with patch.object(check, "HERE", self.folder), patch.object(sys, "argv", ["check.py", "--project", "none"]):
            with self.assertRaisesRegex(SystemExit, "No compositions"):
                check.main()

    def test_real_ffmpeg_error_not_hidden_by_legacy_fallback(self):
        error = subprocess.CompletedProcess([], 1, "", "Stream specifier ':v' matches no streams")
        with patch("common.subprocess.run", return_value=error) as run:
            with self.assertRaisesRegex(SystemExit, "matches no streams"):
                common.ffmpeg_filter_file([], "filters.txt", [])
            self.assertEqual(run.call_count, 1)

    def test_legacy_ffmpeg_fallback_only_for_unknown_option(self):
        results = [subprocess.CompletedProcess([], 1, "", "Unrecognized option '/filter_complex'"),
                   subprocess.CompletedProcess([], 0, "", "")]
        with patch("common.subprocess.run", side_effect=results) as run:
            common.ffmpeg_filter_file([], "filters.txt", [])
            self.assertEqual(run.call_count, 2)

    @unittest.skipIf(os.name == "nt", "Fake npx uses a POSIX shebang")
    def test_hf_disables_background_daemon_and_overrides_browser(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not in PATH")
        browser = self.binary("raise SystemExit('must not launch')")
        marker = self.folder / "env.json"
        npx = self.binary("import os,json,pathlib\n"
                          f"pathlib.Path({str(marker)!r}).write_text(json.dumps(dict(os.environ)))", "npx")
        env = {**os.environ, "CHROME_PATH": str(browser), "PATH": str(npx.parent) + os.pathsep + os.environ["PATH"],
               "HYPERFRAMES_BROWSER_PATH": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
        result = subprocess.run([node, str(common.HERE / "hf.mjs"), "check", "dummy"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(marker.read_text())
        self.assertEqual(actual["CI"], "1")
        self.assertEqual(actual["HF_NO_BROWSER"], "1")
        self.assertEqual(actual["BROWSER"], "none")
        self.assertEqual(actual["HYPERFRAMES_BROWSER_PATH"], str(browser.resolve()))

    @unittest.skipIf(os.name == "nt", "Fake npx uses a POSIX shebang")
    def test_ensure_reuses_explicit_shell_without_launch_or_download(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not in PATH")
        marker = self.folder / "called.txt"
        fail = f"import pathlib,sys\npathlib.Path({str(marker)!r}).write_text('called')\nsys.exit(1)"
        browser = self.binary(fail)
        self.binary(fail, "npx")
        env = {**os.environ, "CHROME_PATH": str(browser), "PATH": str(self.folder) + os.pathsep + os.environ["PATH"]}
        r = subprocess.run([node, str(common.HERE / "hf.mjs"), "browser", "ensure"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(marker.exists())
        self.assertIn(str(browser.resolve()), r.stdout)


if __name__ == "__main__":
    unittest.main()
