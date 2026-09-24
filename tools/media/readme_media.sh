#!/usr/bin/env bash
# Медіа для README, одним запуском (≈ 5 хв):
#   docs/img/page_tour.gif, page_tour.uk.gif — «тур» 3D-сторінки (WASM, свіжа збірка) у кількох
#       режимах і ракурсах: щоб з першого погляду було видно, що за посиланням на живу сторінку;
#   docs/img/pdf_sheets.png, pdf_assembly.png, pdf_parts.png — прев'ю PDF, на які README посилається.
# Запускати після змін у 3D-сторінці, у моделі (вигляд машини) чи в будь-якому з трьох PDF.
# Потрібні: node з puppeteer-core у tools/media, Chrome, ffmpeg, poppler, tools/.venv (Pillow).
set -eu
cd "$(dirname "$0")/../.."
PY=tools/.venv/bin/python
PORT=8799
TMP=$(mktemp -d)
cleanup() { [ -n "${VP:-}" ] && kill "$VP" 2>/dev/null; rm -rf "$TMP"; }
trap cleanup EXIT

echo "== 3D-сторінка: збірка і локальний сервер"
(cd tools/viewer-wasm && npx vite build >/dev/null)
(cd tools/viewer-wasm && exec npx vite preview --port "$PORT" --strictPort >/dev/null 2>&1) & VP=$!
for i in $(seq 1 50); do curl -s -o /dev/null "http://localhost:$PORT/" && break; sleep 0.3; done

for lang in en uk; do
    echo "== тур сторінки ($lang)"
    node tools/media/page_tour.mjs "http://localhost:$PORT/?lang=$lang" --lang "$lang" --frames "$TMP/tour_$lang" --fps 10
    out=docs/img/page_tour.gif; [ "$lang" = uk ] && out=docs/img/page_tour.uk.gif
    # палітра на весь ролик (stats_mode=diff — під рухомі частини), 960 px: ≈ 3 МБ
    ffmpeg -v error -y -framerate 10 -i "$TMP/tour_$lang/f%04d.png" \
        -vf "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
        "$out"
    echo "  $out: $(( $(wc -c < "$out") / 1024 )) КБ"
done

echo "== прев'ю PDF"
VER=$(ls -d versions/V* | sort | tail -1)
$PY tools/media/pdf_preview.py print3d-parts/sheets/SHEETS.pdf 1,9,10,12 docs/img/pdf_sheets.png
$PY tools/media/pdf_preview.py print3d-parts/ASSEMBLY.pdf 1,6,9,14 docs/img/pdf_assembly.png
$PY tools/media/pdf_preview.py "$VER/drawings/parts.pdf" 1,3,12,17 docs/img/pdf_parts.png --height 300 --overlap 0.3
