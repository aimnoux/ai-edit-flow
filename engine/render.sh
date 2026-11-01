#!/bin/bash
# Full render of a horizontal video: chapters -> mix -> final MP4 with subtitles next to it.
#   bash engine/render.sh <slug>                # every chapter from build/<slug>/timing.json
#   bash engine/render.sh <slug> ch2 ch3        # re-render only these chapters, then reassemble
#   MUSIC=track.mp3 bash engine/render.sh <slug>  # music under the voice (see the sound skill)
# Run build.py first. On Windows run from Git Bash. Logs: engine/build/<slug>/render-<chapter>.log.
set -e
SLUG=${1:-}
[ -n "$SLUG" ] || { echo "usage: bash engine/render.sh <slug> [ch1 ch2 ...]"; exit 1; }
shift
PY=$(command -v python || command -v python3)
# MUSIC is supplied relative to the caller's repository root, before we enter engine/.
if [ -n "${MUSIC:-}" ]; then
  MUSIC=$("$PY" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$MUSIC")
fi
cd "$(dirname "$0")"
B="build/$SLUG"; R="renders/$SLUG"
[ -f "$B/timing.json" ] || { echo "no $B/timing.json: run python3 engine/build.py $SLUG first"; exit 1; }
ALL=$("$PY" -c "import json,sys;print(' '.join(c['id'] for c in json.load(open(sys.argv[1]))['chapters']))" "$B/timing.json")
[ "$#" -gt 0 ] || set -- $ALL
FPS=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['fps'])" "$B/timing.json")
mkdir -p "$R"
for ch in "$@"; do
  echo "== render $SLUG-$ch (log: $B/render-$ch.log)"
  # a chapter that broke off resumes from its last segment with --resume (same command)
  HF_SEGMENTED_CAPTURE=true "$PY" render.py "$SLUG-$ch" "$R/$ch.mp4" --fps "$FPS" --quiet >"$B/render-$ch.log" 2>&1 \
    || { tail -20 "$B/render-$ch.log"; echo "render of $ch failed; retry the same command with --resume: see the log"; exit 1; }
done
"$PY" mix.py "$SLUG" ${MUSIC:+--music "$MUSIC"}
: > "$B/concat.txt"
for ch in $ALL; do echo "file '$PWD/$R/$ch.mp4'" >> "$B/concat.txt"; done
ffmpeg -v error -y -f concat -safe 0 -i "$B/concat.txt" -c copy "$B/video.mp4"
ffmpeg -v error -y -i "$B/video.mp4" -i "$B/mix.wav" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart "$R/$SLUG.mp4"
cp "$B/subtitles.srt" "$R/$SLUG.srt"
echo "done: engine/$R/$SLUG.mp4 (+ .srt)"
