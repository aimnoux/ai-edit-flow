#!/usr/bin/env node
/* Pinned HyperFrames CLI. All browser commands use a dedicated headless shell;
   CI disables HyperFrames' detached warm-check daemon. No desktop browser fallback. */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { constants } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const version = JSON.parse(readFileSync(join(root, "package.json"), "utf8")).config.hyperframes;
const args = process.argv.slice(2);
if (args[0] === "--version") { console.log(version); process.exit(0); }
const timeoutSeconds = Number(process.env.AEF_HF_TIMEOUT_SECONDS || "1800");
if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 86400) {
  console.error("AEF_HF_TIMEOUT_SECONDS must be a positive number up to 86400"); process.exit(1);
}

let selectedPython;
function pythonCandidates() {
  const envs = [process.env.VIRTUAL_ENV, join(root, ".venv")].filter(Boolean);
  const candidates = envs.flatMap((p) => process.platform === "win32"
    ? [join(p, "Scripts", "python.exe")] : [join(p, "bin", "python3"), join(p, "bin", "python")]);
  candidates.push("python3", "python");
  return candidates;
}
function browserPath() {
  for (const py of pythonCandidates()) {
    if (py.includes("/") && !existsSync(py)) continue;
    const r = spawnSync(py, [join(root, "engine", "common.py"), "chrome"], { encoding: "utf8", windowsHide: true });
    if (r.error?.code === "ENOENT") continue;
    if (r.status !== 0) throw new Error((r.stderr || "Dedicated browser lookup failed").trim());
    selectedPython = py;
    return r.stdout.trim();
  }
  throw new Error("Python 3.11-3.13 is required; run bash setup.sh first");
}
function guardianPython() {
  if (selectedPython) return selectedPython;
  for (const py of pythonCandidates()) {
    const r = spawnSync(py, ["-c", "import sys; sys.exit(0 if (3,11) <= sys.version_info < (3,14) else 1)"], { windowsHide: true });
    if (r.status === 0) return py;
  }
  throw new Error("Python 3.11-3.13 is required; run bash setup.sh first");
}

// Never let HyperFrames infer a system Chrome, open a browser window or keep a warm daemon.
const env = { ...process.env, CI: "1", HF_NO_BROWSER: "1", BROWSER: "none" };
delete env.HYPERFRAMES_BROWSER_PATH;
delete env.PRODUCER_HEADLESS_SHELL_PATH;
const ensure = args[0] === "browser" && args[1] === "ensure";
const pathOnly = args[0] === "browser" && args[1] === "path";
const help = args.includes("--help") || !args.length || args[0] === "help";
try {
  if (ensure) {
    if (!args.includes("--force")) {
      try {
        console.log(`Dedicated browser: ${browserPath()}`);
        process.exit(0);
      } catch (error) {
        if (!error.message.includes("Dedicated browser not found")) throw error;
      }
    }
    // The upstream Linux ARM installer falls back to system Chromium/apt-get.
    // This kit requires an explicitly supplied headless shell on that platform.
    if (process.platform === "linux" && process.arch === "arm64") {
      console.log(browserPath());
      process.exit(0);
    }
    // ensure downloads the managed shell without launching it; ignore outside browser overrides.
  } else if (!help) {
    const browser = browserPath();
    if (pathOnly) { console.log(browser); process.exit(0); }
    env.HYPERFRAMES_BROWSER_PATH = browser;
    env.PRODUCER_HEADLESS_SHELL_PATH = browser;
  }
  selectedPython = guardianPython();
} catch (error) {
  console.error(error.message);
  process.exit(1);
}

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const child = spawn(npx, ["--no-install", `hyperframes@${version}`, ...args], {
  stdio: "inherit", env, detached: process.platform !== "win32",
  shell: process.platform === "win32", windowsHide: true,
});
// A pipe guardian also reaps the group if the wrapper is killed without a signal handler.
// The pipe has no other writers, so only this wrapper can keep its child group alive.
let guard;
if (process.platform !== "win32" && child.pid && selectedPython) {
  guard = spawn(selectedPython, [join(root, "engine", "process_guard.py"), String(child.pid)], {
    stdio: ["pipe", "ignore", "ignore"], detached: true,
  });
  guard.on("error", (error) => { console.error(`Process guard failed: ${error.message}`); stop(); });
}
function stop(signal = "SIGKILL") {
  if (!child.pid) return;
  try {
    if (process.platform === "win32") {
      if (child.exitCode === null) spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    } else process.kill(-child.pid, signal);
  } catch (error) { if (error.code !== "ESRCH") console.error(error.message); }
}
let interrupted;
let timedOut = false;
const deadline = setTimeout(() => {
  timedOut = true;
  console.error(`HyperFrames timed out after ${timeoutSeconds}s`);
  stop("SIGTERM");
  setTimeout(() => stop(), 3000).unref();
}, timeoutSeconds * 1000).unref();
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => { interrupted = signal; stop(signal); setTimeout(() => stop(), 3000).unref(); });
}
child.on("error", (error) => { console.error(error.message); stop(); process.exitCode = 1; });
child.on("close", (code, signal) => {
  clearTimeout(deadline);
  stop();
  guard?.stdin.end();
  if (code === 0 && ensure) {
    try { console.log(`Dedicated browser: ${browserPath()}`); }
    catch (error) { console.error(error.message); process.exitCode = 1; return; }
  }
  process.exitCode = timedOut ? 124 : interrupted ? 128 + (constants.signals[interrupted] ?? 1)
    : code ?? (128 + (constants.signals[signal] ?? 1));
});
