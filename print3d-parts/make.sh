#!/usr/bin/env bash
# Збирає КОЖЕН компонент окремо (як ріжуть з металу) у print3d-parts/stl/,
# перевіряє друкованість і пише BOM.md.
#
# Модель не змінюється: parts.scad підключає її як бібліотеку з part="none".
# Склад набору — print3d-parts/parts.tsv (єдине джерело правди).
# Перевірка й генератор BOM спільні з print3d/ — не дублюються.
set -eu
cd "$(dirname "$0")/.."
OUT=print3d-parts/stl
SCAD=print3d-parts/parts.scad
TSV=print3d-parts/parts.tsv
mkdir -p "$OUT"
# Тека версії — для підпису геометрії в BOM і для посилань на аркуші ескізів.
# Набори читають ЖИВУ модель, тож це підпис, а не залежність; беремо найбільший номер.
VER=$(ls -d versions/V* 2>/dev/null | sort | tail -1)
[ -n "$VER" ] || echo "  versions/ порожня — BOM буде без підпису версії й без ескізів"

echo "== звіт параметрів друку"
openscad -o /tmp/parts_report.echo -D 'part="none"' -D 'pp="none"' "$SCAD" 2>/dev/null
sed -n '/=== друк/,$p' /tmp/parts_report.echo | sed 's/^ECHO: \"/  /; s/\"$//'

echo
echo "== рендер"
n=0
# Без конвеєра: `grep | while` крутиться в підоболонці, і exit 1 звідти не зупиняє скрипт.
# Порожнє поле в TSV не годиться: zsh злипає послідовні табуляції, тому «нема вузла» = «-».
while IFS=$'\t' read -r pp own ori pre file qty group desc; do
    case "$pp" in ''|'#'*) continue ;; esac
    [ "$own" = "-" ] && own=""
    f="$OUT/${file}_x${qty}.stl"
    rm -f "$f"                       # OpenSCAD не пише файл, якщо результат порожній: інакше зміряємо попередній запуск
    openscad -o "$f" --export-format binstl -D 'part="none"' -D "pp=\"$pp\"" -D "own=\"$own\"" -D "ori=\"$ori\"" -D "pre=$pre" "$SCAD" 2>/tmp/scad_err.txt || {
        echo "  ПОМИЛКА рендера: $pp"; cat /tmp/scad_err.txt; exit 1; }
    if grep -qE 'ERROR|WARNING:' /tmp/scad_err.txt; then
        echo "  УВАГА у компоненті $pp:"; grep -E 'ERROR|WARNING:' /tmp/scad_err.txt | sed 's/^/    /'
    fi
    [ -s "$f" ] || { echo "  ПОМИЛКА: $f порожній або не створений"; exit 1; }
    n=$((n + 1))
done < "$TSV"
echo "  компонентів: $n"

echo
echo "== перевірка (стіл 250×250×250, межа нависання 45°)"
python3 print3d/check_print.py "$OUT"/*.stl --bed 250 --angle 45 || true
python3 print3d/check_print.py "$OUT"/*.stl --bed 250 --angle 45 --json > /tmp/parts_check.json

echo
echo "== BOM"
python3 print3d/make_bom.py "$TSV" /tmp/parts_check.json /tmp/parts_report.echo \
    "Специфікація компонентів під зварювання" "$VER" так > print3d-parts/BOM.md
echo "  print3d-parts/BOM.md"

echo
echo "== інструкція складання"
# Зупиняє збирання навмисно: деталь без кроку складання — це деталь, яку нікуди
# не приклеїти, і краще дізнатися про це тут, ніж із надрукованим набором у руках.
python3 print3d-parts/make_assembly.py "$TSV" print3d-parts/assembly.tsv \
    /tmp/parts_check.json "$VER" > print3d-parts/ASSEMBLY.md
echo "  print3d-parts/ASSEMBLY.md"
