#!/usr/bin/env bash
# Друкований набір 1:5: КОЖЕН компонент окремо (як ріжуть з металу), перевірка друкованості,
# BOM.md, DRIVE.md, аркуші розкладки — у build/print3d/, а коли все зібралось — у latest/print3d/
# новою підверсією VNNN.K. Попередня підверсія переїжджає в latest/print3d-history/ (git mv).
#
# Використання: print3d-parts/make.sh ["що змінено"]
#
# Модель не змінюється: parts.scad підключає її як бібліотеку з part="none".
# Склад набору — print3d-parts/parts.tsv (єдине джерело правди). Тут лише джерела; усе
# згенероване живе в latest/print3d/ (і в архіві versions/ разом із машиною).
# Перевірка (check_print.py) і генератор BOM (make_bom.py) лежать тут же: цей набір самодостатній.
set -eu
cd "$(dirname "$0")/.."
DESC="${1:-}"
SCAD=print3d-parts/parts.scad
TSV=print3d-parts/parts.tsv

# 0. Набір — частина версії машини: він збирається лише з тієї моделі, що лежить у latest/scad/.
#    Інакше V006.3 вийшов би з геометрії, якої у V006 немає.
[ -f latest/VERSION.md ] || { echo "ПОМИЛКА: latest/ немає — спершу tools/build_version.sh"; exit 1; }
MACHINE=$(sed -n '1s/^# //p' latest/VERSION.md)
if ! cmp -s scad/excavator_boom.scad latest/scad/excavator_boom.scad || ! diff -rq scad/brand latest/scad/brand >/dev/null 2>&1; then
    echo "ПОМИЛКА: модель змінилась після збирання $MACHINE — спершу tools/build_version.sh (він збере й набір)"
    exit 1
fi
BASE=${MACHINE%%-*}                                          # V006
# K — наступний після найбільшого серед поточного набору й історії цієї версії машини
k=$( { [ -f latest/print3d/VERSION.md ] && sed -n '1s/^# //p' latest/print3d/VERSION.md; ls latest/print3d-history 2>/dev/null; } \
     | sed -n "s/^$BASE\.\([0-9][0-9]*\).*/\1/p" | sort -n | tail -1 || true)
NAME="$BASE.$(( ${k:-0} + 1 ))-$(date +%Y-%m-%d-%H%M)"
LABEL=${NAME%%-*}                                            # V006.1 — підпис у BOM і на аркушах
OUT=build/print3d; WORK=build/print3d-work                   # проміжне — у WORK, у набір не йде
rm -rf "$OUT" "$WORK"; mkdir -p "$OUT/stl" "$WORK"
echo "== набір $LABEL (машина $MACHINE) → $OUT"

echo "== звіт параметрів друку"
openscad -o "$WORK/parts_report.echo" -D 'part="none"' -D 'pp="none"' "$SCAD" 2>/dev/null
sed -n '/=== друк/,$p' "$WORK/parts_report.echo" | sed 's/^ECHO: \"/  /; s/\"$//'

echo
echo "== рендер"
n=0
# Без конвеєра: `grep | while` крутиться в підоболонці, і exit 1 звідти не зупиняє скрипт.
# Порожнє поле в TSV не годиться: zsh злипає послідовні табуляції, тому «нема вузла» = «-».
while IFS=$'\t' read -r pp own ori pre file qty _; do
    case "$pp" in ''|'#'*) continue ;; esac
    [ "$own" = "-" ] && own=""
    f="$OUT/stl/${file}_x${qty}.stl"
    openscad -o "$f" --export-format binstl -D 'part="none"' -D "pp=\"$pp\"" -D "own=\"$own\"" -D "ori=\"$ori\"" -D "pre=$pre" "$SCAD" 2>"$WORK/scad_err.txt" || {
        echo "  ПОМИЛКА рендера: $pp"; cat "$WORK/scad_err.txt"; exit 1; }
    if grep -qE 'ERROR|WARNING:' "$WORK/scad_err.txt"; then
        echo "  УВАГА у компоненті $pp:"; grep -E 'ERROR|WARNING:' "$WORK/scad_err.txt" | sed 's/^/    /'
    fi
    [ -s "$f" ] || { echo "  ПОМИЛКА: $f порожній або не створений"; exit 1; }
    n=$((n + 1))
done < "$TSV"
echo "  компонентів: $n"

echo
echo "== перевірка (стіл 250×250×250, межа нависання 45°)"
python3 print3d-parts/check_print.py "$OUT"/stl/*.stl --bed 250 --angle 45 || true
python3 print3d-parts/check_print.py "$OUT"/stl/*.stl --bed 250 --angle 45 --json > "$WORK/parts_check.json"

echo
echo "== BOM"
# Посилання «с. N» ведуть на ескізи машини в latest/drawings/ — BOM.md ляже в latest/print3d/
python3 print3d-parts/make_bom.py "$TSV" "$WORK/parts_check.json" "$WORK/parts_report.echo" \
    "Специфікація компонентів під зварювання" latest так "$LABEL" > "$OUT/BOM.md"
echo "  $OUT/BOM.md"

echo
echo "== привід циліндрів гвинтом M5"
# Оберти гайки M5×0.8 під «реальні» швидкості циліндрів і моторедуктор під вагу набору —
# маса береться з щойно зібраних STL.
python3 print3d-parts/model_drive.py --stl "$OUT/stl" --out "$OUT/DRIVE.md"

echo
echo "== циліндри на шпильці M5 з моторедуктором N20"
# Робочий варіант циліндрів (гайка в шестерні, мотор збоку, енкодер і кінцевики на датчиках
# Холла) — окремі деталі поруч із друкованими «глухими» циліндрами набору, не замість них у
# parts.tsv. Перетин власних деталей чи зіткнення з машиною зупиняє збирання. Маса решти
# машини для розрахунку — з щойно зібраних STL набору.
print3d-parts/m5_cylinders/make.sh --out "$OUT/m5_cylinders" --kit-stl "$OUT/stl"

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
# рендери з виносками, кроки склеювання. Без аркушів набір неповний — тому зупиняє збирання.
tools/.venv/bin/python print3d-parts/sheets/make_sheets.py --stl "$OUT/stl" --dir "$OUT/sheets" --version "$LABEL" --png \
    || { echo "  ПОМИЛКА: аркуші не зібрано (потрібен Chrome) — latest/print3d не змінено"; exit 1; }
# Прев'ю сторінок — у build/ (не комітиться): номер і дата в шапці робили б кожне новим файлом
# з кожною підверсією, а вміст і так є в SHEETS.pdf. Аркуш ковша показує TECHNICAL — його копія в docs/img/,
# і з тієї ж причини вона оновлюється, лише якщо змінився сам аркуш, а не шапка чи підвал.
rm -rf build/sheets-png; mv "$OUT/sheets/png" build/sheets-png
tools/.venv/bin/python tools/copy_if_changed.py build/sheets-png/3_bucket.png docs/img/sheet_bucket.png

echo
echo "== розкладка по завданнях друку"
# Тека = одне завдання слайсера (колір, висота шару, підпори). Скрипт зупиняє збирання,
# якщо деталь не потрапила в жодну групу: нову деталь треба вписати і в parts.tsv, і в group.sh.
print3d-parts/group.sh "$OUT/stl"

{
    echo "# $NAME"; echo
    echo "> Друкований набір 1:5 машини \`$MACHINE\`. Згенеровано \`print3d-parts/make.sh\` — руками не правити."
    echo "> Масштабна модель, не іграшка і не проєктна документація; див. \`SAFETY.md\`."; echo
    echo "- Дата: $(date '+%Y-%m-%d %H:%M')"
    echo "- Git (база на момент збирання): $(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))$([ -n "$(git status --porcelain)" ] && echo ' + незакомічені зміни робочого дерева')"
    [ -n "$DESC" ] && echo "- Зміни: $DESC"; echo
    echo "- \`stl/<тека>/\` — одна тека = одне завдання слайсера (колір · висота шару · підпори), пояснення — у \`print3d-parts/README.md\`"
    echo "- \`BOM.md\` — специфікація з виміряних STL; \`DRIVE.md\` — привід циліндрів гвинтом M5"
    echo "- \`m5_cylinders/\` — циліндри на шпильці M5 з моторедуктором N20: \`stl/\`, \`img/\`, \`CALC.md\`, \`WIRING.svg\`, \`SENSORS.svg\` (як влаштовано — \`print3d-parts/m5_cylinders/README.md\`)"
    echo "- \`sheets/SHEETS.pdf\` — аркуші розкладки 1:1 для сортування й склеювання; \`sheets/sheets.json\` — усі числа (прев'ю сторінок — у \`build/sheets-png/\`, не в git)"
    echo; echo '---'; echo "<sub>$(head -1 AUTHORS)</sub>"
} > "$OUT/VERSION.md"

echo
echo "== порівняння з поточним набором"
# OpenSCAD іноді віддає ті самі трикутники в іншому порядку — файл «змінений», деталь та сама.
# Такі STL беруться з попередньої підверсії байт-у-байт, у git іде лише справжня зміна геометрії.
python3 tools/compare_build.py latest/print3d "$OUT" --settle || true


# Попередня підверсія — в історію цієї версії машини; git mv, щоб git бачив перейменування
if [ -d latest/print3d ]; then
    PREV=$(sed -n '1s/^# //p' latest/print3d/VERSION.md)
    mkdir -p latest/print3d-history
    if git ls-files --error-unmatch latest/print3d/VERSION.md >/dev/null 2>&1; then git mv latest/print3d "latest/print3d-history/$PREV"
    else mv latest/print3d "latest/print3d-history/$PREV"; fi
    # Історія лежить на рівень глибше: посилання, що виходять за межі набору (BOM.md → ../drawings/
    # машини), дістають ще один «../» — інакше архівна підверсія посилається в порожнечу.
    for f in "latest/print3d-history/$PREV"/*.md; do sed -i '' 's#](\.\./#](../../#g' "$f"; done
    echo "  $PREV → latest/print3d-history/"
fi
mv "$OUT" latest/print3d
rm -rf "$WORK"
echo "== готово: latest/print3d = $NAME"
