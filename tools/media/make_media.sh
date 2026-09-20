#!/usr/bin/env bash
# Набір зображень і відео для публікацій (LinkedIn тощо) з поточної моделі → temp/media/ (тека temp/ не комітиться).
# Використання: tools/media/make_media.sh [ТЕКА]        потрібні: openscad, Chrome, ffmpeg, node; puppeteer-core ставиться сам (--no-save)
set -e -o pipefail
cd "$(dirname "$0")/../.."
OUT="${1:-temp/media}"; RAW="$OUT/raw"; PORT=8793; URL="http://127.0.0.1:$PORT/"; PY=tools/.venv/bin/python; SHOT="node tools/media/page_shot.mjs"
mkdir -p "$RAW"
grep -qx "temp/" .git/info/exclude 2>/dev/null || echo "temp/" >> .git/info/exclude        # щоб build_version.sh --commit (git add -A) не підхопив
[ -d tools/media/node_modules/puppeteer-core ] || npm i --no-save --no-audit --no-fund --prefix tools/media puppeteer-core >/dev/null
[ -x $PY ] || tools/bom_drawings.sh --out build >/dev/null                                  # створює tools/.venv
python3 tools/viewer.py --port $PORT >/dev/null 2>&1 & SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 30); do curl -s -o /dev/null "$URL" && break; sleep 0.3; done

$SHOT "$URL" --out "$OUT/01_hero.png" --size 1200x1200 --dsf 2 --clean --angles -12,92,48 --view "Ізометрія"
for pose in "reach -5,156,-17" "deep -38,90,60" "height 58,156,0" "transport 58,51,139"; do
  name="${pose%% *}"; ang="${pose#* }"                                                        # без set -- $pose: у zsh/bash рядок з пробілом розбивається по-різному
  $SHOT "$URL" --out "$RAW/pose_$name.png" --meta "$RAW/pose_$name.json" --size 1400x1400 --dsf 2 --clean --ortho --angles "$ang" --view "Збоку"
done
$PY tools/media/compose.py poses "$OUT/02_poses.png" "$RAW"
$SHOT "$URL" --out "$OUT/03_viewer_ui.png" --size 1600x1000 --dsf 2 --angles -20,100,55 --toggle "робоча зона" --view "Збоку"
openscad -o "$RAW/bucket_a.png" --imgsize=1800,1500 --camera=900,-900,500,250,0,120 --projection=p --colorscheme=Tomorrow --viewall --autocenter -D 'part="bucket"' scad/excavator_boom.scad >/dev/null 2>&1
openscad -o "$RAW/bucket_b.png" --imgsize=1800,1500 --camera=-500,-800,350,250,0,120 --projection=p --colorscheme=Tomorrow --viewall --autocenter -D 'part="bucket"' scad/excavator_boom.scad >/dev/null 2>&1
$PY tools/media/compose.py grid "$OUT/04_bucket.png" --cols 2 --cell 1200x1000 --bg f8f8f8 "$RAW/bucket_a.png" "$RAW/bucket_b.png"
$PY tools/media/compose.py drawings "$RAW/draw" | tail -1
D="$RAW/draw/drawings/png"; $PY tools/media/compose.py grid "$OUT/05_drawings.png" --cols 2 --cell 1300x920 --bg ffffff "$D"/*_cheek.png "$D"/*_bk_shell.png "$D"/*_stick.png "$D"/*_bk_ear.png
$PY tools/media/compose.py clearances "$OUT/06_clearances.png"
$SHOT "$URL" --cycle "$RAW/frames" --size 1080x1080 --dsf 1 --clean --angles 12,145,0 --view "Ізометрія"
ffmpeg -y -loglevel error -framerate 25 -i "$RAW/frames/f%04d.png" -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart "$OUT/07_dig_cycle.mp4"
$SHOT "$URL" --cycle "$RAW/frames_ui" --size 1280x720 --dsf 1.5 --toggle "робоча зона" --view "Ззаду-збоку" --wheel 11
ffmpeg -y -loglevel error -framerate 25 -i "$RAW/frames_ui/f%04d.png" -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart "$OUT/08_dig_cycle_ui.mp4"
rm -rf "$RAW/frames" "$RAW/frames_ui"
echo "== готово: $OUT"; ls -la "$OUT" | awk 'NR>1 && $9 !~ /^\.|raw/ {printf "  %8.0f КБ  %s\n", $5/1024, $9}'
