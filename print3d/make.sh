#!/usr/bin/env bash
# Збирає всі друковані деталі з print_parts.scad у print3d/stl/, перевіряє їх і пише BOM.md.
#
# Модель не змінюється: print_parts.scad підключає її як бібліотеку з part="none".
# Склад набору — у print3d/parts.tsv (єдине джерело правди).
# Запускати з будь-де:  print3d/make.sh
set -eu
cd "$(dirname "$0")/.."
OUT=print3d/stl
SCAD=print3d/print_parts.scad
TSV=print3d/parts.tsv
mkdir -p "$OUT"

echo "== звіт параметрів друку"
openscad -o /tmp/print_report.echo -D 'part="none"' -D 'pp="none"' "$SCAD" 2>/dev/null
sed -n '/=== друк/,$p' /tmp/print_report.echo | sed 's/^ECHO: \"/  /; s/\"$//'

echo
echo "== рендер"
# Без конвеєра: `grep | while` крутиться в підоболонці, і exit 1 звідти не зупиняє скрипт
while IFS=$'\t' read -r pp file qty group desc; do
    case "$pp" in ''|'#'*) continue ;; esac
    f="$OUT/${file}_x${qty}.stl"
    rm -f "$f"                       # OpenSCAD не пише файл, якщо результат порожній: інакше зміряємо попередній запуск
    # binstl обов'язковий: типовий текстовий STL перевірки не читають
    openscad -o "$f" --export-format binstl -D 'part="none"' -D "pp=\"$pp\"" "$SCAD" 2>/tmp/scad_err.txt || {
        echo "  ПОМИЛКА рендера: $pp"; cat /tmp/scad_err.txt; exit 1; }
    if grep -qE 'ERROR|WARNING:' /tmp/scad_err.txt; then
        echo "  УВАГА у деталі $pp:"; grep -E 'ERROR|WARNING:' /tmp/scad_err.txt | sed 's/^/    /'
    fi
    [ -s "$f" ] || { echo "  ПОМИЛКА: $f порожній або не створений"; exit 1; }
    printf '  %-34s %s\n' "$(basename "$f")" "$desc"
done < "$TSV"

echo
echo "== перевірка (стіл 250×250×250, межа нависання 45°)"
python3 print3d/check_print.py "$OUT"/*.stl --bed 250 --angle 45 || true
python3 print3d/check_print.py "$OUT"/*.stl --bed 250 --angle 45 --json > /tmp/print_check.json

echo
echo "== BOM"
python3 print3d/make_bom.py "$TSV" /tmp/print_check.json /tmp/print_report.echo > print3d/BOM.md
echo "  print3d/BOM.md"
