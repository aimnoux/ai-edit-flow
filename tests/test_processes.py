"""Owned process cleanup with fake executables only; never launches a browser or npx."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipIf(os.name == "nt", "POSIX process groups and signals")
class ProcessCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aef-process-test-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.marker = self.folder / "ready.json"
        self.groups = []
        self.launchers = []
        # Register last so processes are stopped before the fixtures disappear.
        self.addCleanup(self.cleanup_processes)

    def cleanup_processes(self):
        for group in self.groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for launcher in self.launchers:
            if launcher.poll() is None:
                launcher.kill()
            launcher.communicate(timeout=5)

    def executable(self, name, source):
        path = self.folder / name
        path.write_text(f"#!{sys.executable}\n{source}\n")
        path.chmod(0o755)
        return path

    def sleeping_process(self, name):
        """One group leader and worker; the leader exits successfully on TERM."""
        return self.executable(name, """
import json, os, pathlib, signal, subprocess, sys, time
worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
pathlib.Path(os.environ['FAKE_READY']).write_text(json.dumps({'leader': os.getpid(), 'worker': worker.pid}))
while True:
    time.sleep(.1)
""")

    def launch(self, argv, env):
        proc = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        self.launchers.append(proc)
        return proc

    def ready(self, launcher):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                pids = json.loads(self.marker.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                if launcher.poll() is not None:
                    _, stderr = launcher.communicate(timeout=5)
                    self.fail(f"Launcher exited before its fake child was ready: {stderr}")
                time.sleep(.01)
                continue
            self.groups.append(pids["leader"])
            return pids
        self.fail("Fake process did not become ready")

    def assert_processes_dead(self, pids):
        def alive(pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            # A killed orphan can briefly remain a zombie until the OS reaps it.
            try:
                state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                       capture_output=True, text=True, check=False).stdout.strip()
            except PermissionError:
                # Restricted runners may deny ps; keep polling kill(pid, 0).
                return True
            return bool(state) and not state.startswith("Z")

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            remaining = [pid for pid in pids.values() if alive(pid)]
            if not remaining:
                return
            time.sleep(.02)
        self.fail(f"Owned processes survived launcher termination: {remaining}")

    def browser_launcher(self):
        browser = self.sleeping_process("chrome-headless-shell")
        script = self.folder / "browser_parent.py"
        script.write_text(f"import sys\nsys.path.insert(0, {str(ROOT / 'engine')!r})\n"
                          "import common\ncommon.run_chrome(timeout=30)\n")
        env = {**os.environ, "CHROME_PATH": str(browser), "FAKE_READY": str(self.marker)}
        return self.launch([sys.executable, str(script)], env)

    def hf_launcher(self):
        browser = self.executable("chrome-headless-shell", "raise SystemExit('must never launch')")
        self.sleeping_process("npx")
        # Supply a working Python for the wrapper's resolver and pipe guardian.
        venv = self.folder / "venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/python3").symlink_to(sys.executable)
        env = {**os.environ, "CHROME_PATH": str(browser), "FAKE_READY": str(self.marker),
               "VIRTUAL_ENV": str(venv), "PATH": str(self.folder) + os.pathsep + os.environ.get("PATH", "")}
        return self.launch([NODE, str(ROOT / "engine/hf.mjs"), "check", "fake-project"], env)

    def test_browser_parent_sigterm_reaps_owned_group(self):
        launcher = self.browser_launcher()
        pids = self.ready(launcher)
        launcher.terminate()
        launcher.wait(timeout=5)
        self.assert_processes_dead(pids)

    def test_browser_parent_sigkill_reaps_owned_group(self):
        launcher = self.browser_launcher()
        pids = self.ready(launcher)
        launcher.kill()
        launcher.wait(timeout=5)
        self.assert_processes_dead(pids)

    @unittest.skipUnless(NODE, "Node required for the fake npx wrapper test")
    def test_hf_parent_sigkill_reaps_owned_group(self):
        launcher = self.hf_launcher()
        pids = self.ready(launcher)
        launcher.kill()
        launcher.wait(timeout=5)
        self.assert_processes_dead(pids)

    @unittest.skipUnless(NODE, "Node required for the fake npx wrapper test")
    def test_hf_sigterm_with_successful_child_is_not_success(self):
        launcher = self.hf_launcher()
        pids = self.ready(launcher)
        launcher.terminate()
        _, stderr = launcher.communicate(timeout=5)
        self.assertEqual(launcher.returncode, 128 + signal.SIGTERM, stderr)
        self.assert_processes_dead(pids)


if __name__ == "__main__":
    unittest.main()
