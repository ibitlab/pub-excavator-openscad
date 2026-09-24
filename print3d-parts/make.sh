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
echo "== кроки складання"
# Зупиняє збирання навмисно: деталь без кроку в assembly.tsv мовчки випала б з аркушів
# розкладки — це деталь, яку нікуди не приклеїти, і краще дізнатися про це тут, ніж із
# надрукованим набором у руках. Кожен ключ parts.tsv — рівно один раз, чужих немає.
python3 - "$TSV" print3d-parts/assembly.tsv <<'PY'
import sys
rows = lambda f: [l.split('\t') for l in open(f, encoding='utf-8') if l.strip() and not l.startswith('#')]
parts = [r[0] for r in rows(sys.argv[1])]
steps = [r[2] for r in rows(sys.argv[2])]
bad = [f'без кроку: {k}' for k in parts if k not in steps] + [f'крок для невідомої деталі: {k}' for k in steps if k not in parts] \
    + [f'кілька кроків: {k}' for k in sorted(set(steps)) if steps.count(k) > 1]
if bad:
    sys.exit('  ПОМИЛКА assembly.tsv:\n    ' + '\n    '.join(bad))
print(f'  кроків: {len(steps)}, деталей: {len(parts)} — кожна рівно в одному кроці')
PY

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
