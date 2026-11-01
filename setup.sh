#!/bin/sh
# Prepares the repository on a new machine. Idempotent: safe to run again.
#   bash setup.sh
# macOS and Linux: any shell. Windows: run from Git Bash.
cd "$(dirname "$0")" || exit 1
ok()   { printf '  ok      %s\n' "$1"; }
miss() { printf '  missing %s - %s\n' "$1" "$2"; MISSING=1; }
MISSING=0

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done

echo "Tools:"
command -v git >/dev/null 2>&1 && ok git || miss git "install git"
[ -n "$PY" ] && ok "$PY ($("$PY" -c 'import platform; print(platform.python_version())'))" || miss python "Python 3.10+ (python.org or your package manager)"
command -v ffmpeg >/dev/null 2>&1 && ok ffmpeg || miss ffmpeg "macOS: brew install ffmpeg; Linux: apt install ffmpeg; Windows: winget install ffmpeg"
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
  [ "$NODE_MAJOR" -ge 22 ] 2>/dev/null && ok "node $(node -v)" || miss "node $(node -v)" "Node.js 22+ is required (nodejs.org)"
else
  miss node "Node.js 22+ (nodejs.org)"
fi
command -v npx >/dev/null 2>&1 && ok npx || miss npx "comes with Node.js"

# Chrome: CHROME_PATH, then the usual places on each OS. HyperFrames can download its own
# browser for rendering, but the frame tools (check, shots, cues) want a system Chrome.
CHROME=""
for c in "$CHROME_PATH" \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium" \
  "$(command -v google-chrome 2>/dev/null)" "$(command -v google-chrome-stable 2>/dev/null)" \
  "$(command -v chromium 2>/dev/null)" "$(command -v chromium-browser 2>/dev/null)" \
  "/c/Program Files/Google/Chrome/Application/chrome.exe" \
  "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
  "$LOCALAPPDATA/Google/Chrome/Application/chrome.exe"; do
  if [ -n "$c" ] && [ -x "$c" ]; then CHROME="$c"; break; fi
done
[ -n "$CHROME" ] && ok "Chrome: $CHROME" || miss "Chrome" "install Google Chrome or Chromium, or set CHROME_PATH in .env"

echo "Python packages:"
if [ -n "$PY" ]; then
  if "$PY" -m pip install -q -r requirements.txt >/dev/null 2>&1 || "$PY" -m pip install -q --user -r requirements.txt >/dev/null 2>&1; then
    ok "requirements.txt"
  else
    miss "requirements.txt" "run: $PY -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
  fi
fi

echo "Config:"
if [ -f .env ]; then ok ".env"; else cp .env.example .env && ok ".env created from .env.example - add ELEVENLABS_API_KEY if you use voice cloning or speech-to-text"; fi
[ -f style/visual.md ] && ok "style/ (fill it with the style skill: say 'set up my style' in Claude Code)"

echo "HyperFrames:"
HF=$(node -p 'require("./package.json").config.hyperframes' 2>/dev/null)
[ -n "$HF" ] && ok "pinned at $HF (downloads on first run of node engine/hf.mjs)" || miss "package.json" "config.hyperframes is missing"

if [ "$MISSING" = 0 ]; then
  echo "Done. Open this folder in Claude Code and say what you want to make."
else
  echo "Done with missing pieces above. The rest works without them."
fi
