#!/bin/sh
# Prepares the repository on a new machine. Idempotent: safe to run again.
# macOS / Linux: bash setup.sh. Windows: Git Bash with native Python and Node.js.
cd "$(dirname "$0")" || exit 1
ok()   { printf '  ok      %s\n' "$1"; }
miss() { printf '  missing %s - %s\n' "$1" "$2"; MISSING=1; }
MISSING=0
PY=""

# An activated environment is an explicit selection; never silently install elsewhere.
if [ -n "${VIRTUAL_ENV:-}" ]; then
  for c in "$VIRTUAL_ENV/bin/python" "$VIRTUAL_ENV/Scripts/python.exe"; do
    if [ -x "$c" ]; then PY="$c"; break; fi
  done
else
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY="$c"; break; fi
  done
fi

echo "Tools:"
command -v git >/dev/null 2>&1 && ok git || miss git "install git"
if [ -n "$PY" ] && "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  ok "Python $("$PY" -c 'import platform; print(platform.python_version())')"
else
  miss python "Python 3.10+ is required; check the activated environment, if any"
fi
command -v ffmpeg >/dev/null 2>&1 && ok ffmpeg || miss ffmpeg "macOS: brew install ffmpeg; Linux: apt install ffmpeg; Windows: winget install ffmpeg"
command -v ffprobe >/dev/null 2>&1 && ok ffprobe || miss ffprobe "install the complete ffmpeg package and add it to PATH"
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
  [ "$NODE_MAJOR" -ge 22 ] 2>/dev/null && ok "node $(node -v)" || miss "node $(node -v)" "Node.js 22+ is required (nodejs.org)"
else
  miss node "Node.js 22+ (nodejs.org)"
fi
command -v npx >/dev/null 2>&1 && ok npx || miss npx "comes with Node.js"
if [ "$MISSING" != 0 ]; then
  echo "Setup stopped. Install the missing tools, then run bash setup.sh again."
  exit 1
fi

echo "Python environment:"
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ ! -d .venv ]; then
    "$PY" -m venv .venv || { miss .venv "install Python's venv support and retry"; exit 1; }
  fi
  PY=""
  for c in .venv/bin/python .venv/Scripts/python.exe; do
    if [ -x "$c" ]; then PY="$c"; break; fi
  done
fi
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix and sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  miss "virtual environment" "use a Python 3.10+ venv; dependencies are never installed globally"
  exit 1
fi
case "$PY" in
  /*) ;;
  *) PY="$PWD/$PY" ;;
esac
ok "$PY"
# Make child commands use the same Python environment.
PATH="$(dirname "$PY"):$PATH"
export PATH
if "$PY" -m pip install -r requirements.txt; then
  ok requirements.txt
else
  miss requirements.txt "check pip/network access in the selected virtual environment and retry"
  exit 1
fi

echo "Config:"
if [ -f .env ]; then
  ok .env
else
  cp .env.example .env || exit 1
  ok ".env created - add ELEVENLABS_API_KEY for speech services"
fi
[ ! -f style/visual.md ] || ok "style/ (say 'set up my style' in Claude Code)"

echo "Isolated rendering browser:"
# The wrapper downloads a dedicated headless browser; it never selects personal Chrome.
# Installation only: this command does not launch a browser or call a speech API.
if ! node engine/hf.mjs browser ensure; then
  miss "dedicated browser" "check the error above; set CHROME_PATH to chrome-headless-shell if needed"
  exit 1
fi
if ! "$PY" engine/common.py chrome; then
  miss "dedicated browser" "browser lookup failed; set CHROME_PATH to the dedicated executable"
  exit 1
fi
ok "dedicated browser ready"
echo "Done. Activate the selected virtual environment before running engine scripts."
echo "Default: source .venv/bin/activate (Windows Git Bash: source .venv/Scripts/activate)."
echo "Open this folder in Claude Code and say what you want to make."
