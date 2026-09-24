#!/usr/bin/env bash
# Стійка для показу — окремо від print3d-parts/make.sh (набір, модель, BOM і аркуші
# не чіпаються): дві STL у stl/, перевірка друкованості тим самим ../check_print.py,
# дві числові перевірки посадки плит колони і прев'ю preview.png.
set -eu
cd "$(dirname "$0")"
mkdir -p stl
ERR=/tmp/stand_err.txt

render() {   # render <what> <файл> [ще -D …]  — з порожнім результатом OpenSCAD 2026 пише STL без трикутників
    what=$1; out=$2; shift 2
    rm -f "$out"
    openscad -o "$out" --export-format binstl -D "what=\"$what\"" "$@" stand.scad 2>"$ERR" \
        || { echo "  ПОМИЛКА рендера: $what $*"; cat "$ERR"; exit 1; }
    grep -E 'ERROR|WARNING:' "$ERR" | grep -v 'top.level' | sed 's/^/    /' || true
}

echo "== STL"
render base stl/stand_base.stl
render peg  stl/stand_peg.stl
render post stl/stand_post.stl
# Прищепки на циліндри: 0 — стріли (шток Ø8, гільза Ø15.2), 1 — рукояті й ковша (Ø5, Ø12);
# розміри stand.scad бере з моделі
render clip stl/clip_boom.stl         -D CLIP_I=0
render clip stl/clip_stick_bucket.stl -D CLIP_I=1
for f in stl/*.stl; do
    [ -s "$f" ] || { echo "  ПОМИЛКА: $f порожній або не створений"; exit 1; }
done
echo "  файлів: $(ls stl/*.stl | wc -l | tr -d ' ')"

echo "== перевірка друку (стіл 250×250×250, межа нависання 45°)"
python3 ../check_print.py stl/*.stl --bed 250 --angle 45

echo "== посадка плит колони"
vol() { [ -s "$1" ] && python3 ../../tools/stl_volume.py "$1" || echo 0.000; }   # см³
render fit /tmp/stand_fit.stl
v=$(vol /tmp/stand_fit.stl)
[ "$v" = "0.000" ] || { echo "  ПОМИЛКА: плити перетинають стійку — $v см³"; exit 1; }
echo "  плити не перетинають стійку: так (перетин 0.000 см³)"
render seat /tmp/stand_seat.stl
v=$(vol /tmp/stand_seat.stl)
[ "$v" != "0.000" ] || { echo "  ПОМИЛКА: плити не торкаються тіла стійки — виїмки не там"; exit 1; }
echo "  плити в об'ємі виїмок: $v см³ (дві виїмки по 0.5 мм, має бути > 0)"

echo "== посадка прищепки на циліндрі стріли (шток висунутий на 40 % ходу)"
render clip_fit /tmp/stand_clip_fit.stl
v=$(vol /tmp/stand_clip_fit.stl)
[ "$v" = "0.000" ] || { echo "  ПОМИЛКА: прищепка перетинає гільзу або шток — $v см³"; exit 1; }
echo "  з гільзою і штоком не перетинається: так (перетин 0.000 см³)"
render clip_seat /tmp/stand_clip_seat.stl
v=$(vol /tmp/stand_clip_seat.stl)
[ "$v" != "0.000" ] || { echo "  ПОМИЛКА: штуцер не входить в отвір прищепки — отвір не там"; exit 1; }
echo "  штуцер в отворі рукава: так (без отвору перетин $v см³)"

echo "== прев'ю"
# --viewall: уся сцена в кадрі (плити колони здіймаються на 130 мм над стійкою),
# потім зайві поля зрізає trim_png; звіт у кінці каже, чи нічого не вилізло за кадр
openscad --preview -o preview.png --imgsize=900,900 --projection=p --viewall --autocenter --camera=0,0,0,62,0,35,600 stand.scad 2>/dev/null
python3 ../../tools/trim_png.py --margin 3 preview.png >/dev/null
openscad --preview -o clips.png --imgsize=1200,700 --projection=p --viewall --autocenter --camera=0,0,0,62,0,35,300 -D 'what="clips"' stand.scad 2>/dev/null
python3 ../../tools/trim_png.py --margin 3 clips.png >/dev/null
python3 ../../tools/trim_png.py --report --edges preview.png clips.png | tail -2
