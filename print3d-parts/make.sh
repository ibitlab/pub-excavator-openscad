#!/usr/bin/env bash
# Збирає КОЖЕН компонент окремо (як ріжуть з металу) у print3d-parts/stl/,
# перевіряє друкованість і пише BOM.md.
#
# Модель не змінюється: parts.scad підключає її як бібліотеку з part="none".
# Склад набору — print3d-parts/parts.tsv (єдине джерело правди).
# Перевірка (check_print.py) і генератор BOM (make_bom.py) лежать тут же: цей набір самодостатній.
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
python3 print3d-parts/check_print.py "$OUT"/*.stl --bed 250 --angle 45 || true
python3 print3d-parts/check_print.py "$OUT"/*.stl --bed 250 --angle 45 --json > /tmp/parts_check.json

echo
echo "== BOM"
python3 print3d-parts/make_bom.py "$TSV" /tmp/parts_check.json /tmp/parts_report.echo \
    "Специфікація компонентів під зварювання" "$VER" так > print3d-parts/BOM.md
echo "  print3d-parts/BOM.md"

echo
echo "== креслення прив'язок"
# Вежа F і вилка D стають посеред пластини — словами це не пояснити.
mkdir -p print3d-parts/img
tools/.venv/bin/python print3d-parts/make_pos_drawing.py print3d-parts/img/positions.png \
    print3d-parts/img/positions.json /tmp/parts_report.echo

echo
echo "== інструкція складання"
# Зупиняє збирання навмисно: деталь без кроку складання — це деталь, яку нікуди
# не приклеїти, і краще дізнатися про це тут, ніж із надрукованим набором у руках.
python3 print3d-parts/make_assembly.py "$TSV" print3d-parts/assembly.tsv \
    /tmp/parts_check.json "$VER" print3d-parts/img/positions.json > print3d-parts/ASSEMBLY.md
echo "  print3d-parts/ASSEMBLY.md"

echo
echo "== інструкція складання на папері"
# Біля принтера зручніше з аркушем, ніж із екраном: ескізи деталей у PDF стоять
# у тексті картинками, а не посиланнями. Потрібні лише python з Pillow і Chrome.
tools/.venv/bin/python print3d-parts/make_assembly_pdf.py || echo "  PDF не зібрано (потрібен Chrome) — ASSEMBLY.md на місці"

echo
echo "== аркуші розкладки 1:1"
# Папір проти купи схожих деталей: контур кожної у масштабі 1:1 на аркуші свого вузла,
# рендери з виносками, кроки склеювання. Читає STL з stl/, assembly.tsv і parts.tsv.
tools/.venv/bin/python print3d-parts/sheets/make_sheets.py --png || echo "  аркуші не зібрано (потрібен Chrome) — SHEETS.pdf лишився попередній"

echo
echo "== розкладка по завданнях друку"
# Рендер завжди кладе STL у корінь stl/, а друкуються вони з тек «одне завдання
# слайсера» (колір, висота шару, підпори). Тому розкладка — останній крок збирання:
# структура однакова після кожного запуску, дублікатів у корені не лишається.
# Скрипт зупиняє збирання, якщо деталь не потрапила в жодну групу: нову деталь
# треба вписати і в parts.tsv, і в stl/group.sh.
"$OUT/group.sh"
