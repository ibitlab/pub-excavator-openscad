#!/usr/bin/env bash
# Стійка для показу — окремо від print3d-parts/make.sh (набір, модель, BOM і аркуші
# не чіпаються): дві STL у stl/, перевірка друкованості тим самим ../check_print.py,
# дві числові перевірки посадки плит колони і прев'ю preview.png.
set -eu
cd "$(dirname "$0")"
mkdir -p stl
ERR=/tmp/stand_err.txt

render() {   # render <what> <файл>  — з порожнім результатом OpenSCAD 2026 пише STL без трикутників
    rm -f "$2"
    openscad -o "$2" --export-format binstl -D "what=\"$1\"" stand.scad 2>"$ERR" \
        || { echo "  ПОМИЛКА рендера: $1"; cat "$ERR"; exit 1; }
    grep -E 'ERROR|WARNING:' "$ERR" | grep -v 'top.level' | sed 's/^/    /' || true
}

echo "== STL"
render base stl/stand_base.stl
render peg  stl/stand_peg.stl
render post stl/stand_post.stl
for f in stl/stand_base.stl stl/stand_peg.stl stl/stand_post.stl; do
    [ -s "$f" ] || { echo "  ПОМИЛКА: $f порожній або не створений"; exit 1; }
done

echo "== перевірка друку (стіл 250×250×250, межа нависання 45°)"
python3 ../check_print.py stl/stand_base.stl stl/stand_peg.stl stl/stand_post.stl --bed 250 --angle 45

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

echo "== прев'ю"
# --viewall: уся сцена в кадрі (плити колони здіймаються на 130 мм над стійкою),
# потім зайві поля зрізає trim_png; звіт у кінці каже, чи нічого не вилізло за кадр
openscad --preview -o preview.png --imgsize=900,900 --projection=p --viewall --autocenter --camera=0,0,0,62,0,35,600 stand.scad 2>/dev/null
python3 ../../tools/trim_png.py --margin 3 preview.png >/dev/null
python3 ../../tools/trim_png.py --report --edges preview.png | tail -1
