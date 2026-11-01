#!/usr/bin/env node
/* The single entry point to HyperFrames. The version is pinned once, in package.json
   ("config.hyperframes"); every script and skill runs `node engine/hf.mjs <command> ...` instead of
   spelling the version out. Works the same on macOS, Linux and Windows.

     node engine/hf.mjs check engine
     node engine/hf.mjs render -c engine/example-ch1.html -o engine/renders/example/ch1.mp4 --fps 25
     node engine/hf.mjs --version      # prints the pinned version and exits */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const version = JSON.parse(readFileSync(join(root, "package.json"), "utf8")).config.hyperframes;
const args = process.argv.slice(2);
if (args[0] === "--version") { console.log(version); process.exit(0); }

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const r = spawnSync(npx, ["--yes", `hyperframes@${version}`, ...args], { stdio: "inherit", shell: process.platform === "win32" });
process.exit(r.status ?? 1);
