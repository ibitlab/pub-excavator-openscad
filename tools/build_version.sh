#!/usr/bin/env bash
# Збирання версії машини: STL кожного вузла, рендери, звіти, BOM/DXF/PDF, знімок моделі — у latest/.
# Використання: tools/build_version.sh [--new] [--no-kit] [--commit] ["короткий опис змін"]
#   Збирається в build/version/; лише коли всі перевірки пройшли, результат іде в latest/.
#   Змінились геометрія чи числа звітів (tools/compare_build.py) — нова версія VNNN: попередній
#   latest/ переїжджає в versions/<його назва> через git mv, після чого збирається набір (VNNN.1).
#   Не змінились (кольори, рендери, стиль PDF) — latest/ оновлюється на місці з тим самим номером.
#   --new     — нова версія навіть без змін по суті;  --no-kit — не збирати набір після нової версії
#   --commit  — закомітити: архів окремим комітом (щоб git бачив перейменування), нове — другим
set -e -o pipefail
cd "$(dirname "$0")/.."
COMMIT=0; FORCE_NEW=0; KIT=1; DESC=""
for a in "$@"; do case "$a" in --commit) COMMIT=1 ;; --new) FORCE_NEW=1 ;; --no-kit) KIT=0 ;; -h|--help) sed -n '2,9p' "$0"; exit 0 ;; *) DESC="$a" ;; esac; done
SCAD=scad/excavator_boom.scad
# Авторство — дрібно внизу кожного згенерованого документа; джерело — AUTHORS у корені
AUTHOR="$(head -1 AUTHORS)"
# Звіти й VERSION.md читають окремо від README — застереження (з авторством, як tools/author.py made_with) має бути в кожному з них.
WHO="${AUTHOR% · *} (${AUTHOR#* · })"; [ "$WHO" = "$AUTHOR ($AUTHOR)" ] && WHO="$AUTHOR"   # «Ім'я · @нік» → «Ім'я (@нік)»
WARN="> **УВАГА:** автор — ${WHO}: ідея, задачі, рішення; виконання — ШІ (Claude Code). Кваліфікований інженер не перевіряв, машину за цією моделлю не збудовано й не випробувано.
> Використання — на власний ризик і відповідальність; відомі недоробки конструкції — у \`SAFETY.md\`."
GIT_BASE="$(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))"
[ -n "$(git status --porcelain)" ] && GIT_BASE="$GIT_BASE + незакомічені зміни робочого дерева"
# Номер — наступний після найбільшого з трьох джерел: теки versions/, latest/ і git-теги VNNN
# (версії, прибрані з дерева, лишаються тегами — їхні номери не можна видати вдруге).
OLD_NAME=$( [ -f latest/VERSION.md ] && sed -n '1s/^# //p' latest/VERSION.md || true )
last=$( { ls versions 2>/dev/null; echo "$OLD_NAME"; git tag -l 'V[0-9][0-9][0-9]'; } \
        | sed -n 's/^V\([0-9][0-9][0-9]\).*/\1/p' | sort -n | tail -1)
N=$(printf "%03d" $((10#${last:-0} + 1)))
NAME="V${N}-$(date +%Y-%m-%d-%H%M)"
DIR=build/version; rm -rf "$DIR"
mkdir -p "$DIR/stl" "$DIR/renders" "$DIR/docs" "$DIR/scad"   # bom/, dxf/, drawings/ створює bom_drawings.sh
# Проміжне, що цілком іде у VERSION.md (список STL, echo моделі), — у тимчасову теку, не у версію:
# окремим файлом поруч воно було б лише дублем.
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
echo "== $NAME → $DIR"

# 1. Перевірка перетинів пластин (зупиняє збирання, якщо є перекриття)
./tools/check_overlaps.sh | tee "$DIR/docs/overlaps.txt"
# 1а. Перевірка рухомих пар на всьому ході циліндрів (ківш/коромисло/тяга/рукоять/циліндри ↔ кронштейни)
./tools/check_motion.sh | tee "$DIR/docs/motion.txt"

# 2. STL: збірка + зварні вузли + кожна група деталей. Логотип — наліпка, не метал:
#    у STL (і в їхніх об'ємах) його немає, на рендерах нижче — є.
PARTS="assembly boom boom_tubes boom_gussets boom_bracket_D boom_bracket_F boom_foot_boss boom_fork_B stick stick_tube stick_cheeks stick_bracket_H stick_tip rocker link bucket bucket_sides bucket_shell bucket_top bucket_edge bucket_ears bucket_wear post"
for p in $PARTS; do
  openscad -o "$DIR/stl/$p.stl" --export-format binstl -D "part=\"$p\"" -D show_ground=false -D show_envelope=false -D show_brand=false "$SCAD" >/dev/null 2>&1
  printf "  stl/%-22s %8s байт  об'єм %s см³\n" "$p.stl" "$(wc -c < "$DIR/stl/$p.stl" | tr -d ' ')" "$(python3 tools/stl_volume.py "$DIR/stl/$p.stl")"
done | tee "$WORK/stl_list.txt"

# 3. Рендери: робочі положення + вузли окремо
# venv потрібен уже тут: ним підрізаються поля рендерів (Pillow)
[ -x tools/.venv/bin/python ] || { python3 -m venv tools/.venv; tools/.venv/bin/pip install --quiet matplotlib shapely; }
tools/.venv/bin/python -c "import shapely" 2>/dev/null || tools/.venv/bin/pip install --quiet shapely
# --render=cgal ОБОВ'ЯЗКОВИЙ: у режимі прев'ю (OpenCSG) поверхні деталей, що дотикаються,
# пробивають одна одну. Саме `=cgal`, а не голий --render: прапорець бере НЕОБОВ'ЯЗКОВИЙ
# аргумент і, стоячи останнім перед іменем файлу, з'їдає його — openscad друкує usage
# і мовчки нічого не робить.
# пробивають одна одну — труба малювалася поверх накладки, і вежа F виглядала так,
# наче стоїть у повітрі. Геометрія при цьому ціла. З Manifold це майже безкоштовно.
CAM="--camera=1400,-6000,200,0,0,0 --projection=o --colorscheme=Tomorrow --viewall --autocenter --render=cgal"
render() { openscad -o "$DIR/renders/$1.png" --imgsize=2400,1500 $CAM -D "boom_angle=$2" -D "stick_angle=$3" -D "bucket_angle=$4" -D show_ground=false "$SCAD" >/dev/null 2>&1; }
render side_default 15 100 60
render folded 58 51 133
render max_reach -5 155 -16
render dig_deep -38 90 60
render max_height 58 155 0
# --viewall --autocenter обов'язкові: з фіксованою камерою кадр обрізав ківш і колону при зміні геометрії
openscad -o "$DIR/renders/iso_default.png" --imgsize=2400,1650 --camera=2500,-3500,1800,900,0,-100 --projection=p --viewall --autocenter --colorscheme=Tomorrow --render=cgal -D boom_angle=20 -D stick_angle=100 -D bucket_angle=60 -D show_ground=false "$SCAD" >/dev/null 2>&1   # без землі: площина 9 м з --viewall лишала машині ~10 % кадру
# ground_span менший за типовий: із --viewall площина 9000 мм ужимає машину вдвічі
openscad -o "$DIR/renders/envelope.png" --imgsize=1600,1000 $CAM -D boom_angle=-38 -D stick_angle=100 -D bucket_angle=60 -D show_envelope=true -D ground_span=3000 "$SCAD" >/dev/null 2>&1
for p in boom stick bucket; do
  openscad -o "$DIR/renders/part_$p.png" --imgsize=2400,1500 --camera=800,-2500,900,0,0,0 --projection=p --colorscheme=Tomorrow --viewall --autocenter --render=cgal -D "part=\"$p\"" "$SCAD" >/dev/null 2>&1
done

# 3а. Підрізати порожні поля: --viewall вписує габаритну СФЕРУ, тож довга деталь
# займала 16 % кадру. Пози ріжуться СПІЛЬНОЮ рамкою — інакше кожна дістане свій
# масштаб і перестане бути порівнянною з рештою.
tools/.venv/bin/python tools/trim_png.py --common "$DIR/renders/folded.png" \
    "$DIR/renders/max_reach.png" "$DIR/renders/dig_deep.png" "$DIR/renders/max_height.png" | tail -1
# side_default ні з чим не порівнюється (колаж поз медіа-набору робиться зі знімків
# сторінки, не звідси), тож ріжеться по собі — це головна картинка README.
tools/.venv/bin/python tools/trim_png.py "$DIR"/renders/part_*.png \
    "$DIR/renders/side_default.png" "$DIR/renders/iso_default.png" \
    "$DIR/renders/envelope.png" | tail -1

# 4. Звіти і знімок моделі — пишуться ЛИШЕ у теку версії (у корені репозиторію згенерованих копій немає)
(cd tools && python3 kinematics.py > "../$DIR/docs/02-kinematics.md" && python3 strength.py --boom 120x80x5 --stick 100x60x5 > "../$DIR/docs/03-strength.md")
for f in "$DIR/docs/02-kinematics.md" "$DIR/docs/03-strength.md"; do   # позначка "згенеровано" з номером версії
  printf '%s\n>\n> Згенеровано автоматично (%s) скриптом `tools/build_version.sh`.\n\n' "$WARN" "$NAME" | cat - "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  printf '\n---\n<sub>%s</sub>\n' "$AUTHOR" >> "$f"
done
openscad -o "$WORK/ranges.echo" "$SCAD" >/dev/null 2>&1
# Вихідні дані пишуться вручну і можуть бути відсутні (їх немає у публічній копії) — не зупиняти через це збирання
if [ -f docs/01-design-inputs.md ]; then cp docs/01-design-inputs.md "$DIR/docs/"
else echo "  docs/01-design-inputs.md немає — пропущено (документ пишеться вручну)"; fi
(cd tools && .venv/bin/python bucket.py --png "../$DIR/renders/bucket_motion_2d.png" > "../$DIR/docs/05-bucket.md") || echo "!!! bucket.py: є зіткнення у 2D-перевірці — див. docs/05-bucket.md"
# Креслення робочої зони з розмірами (A…J) — обома мовами, як і README
tools/.venv/bin/python tools/work_range.py --out "$DIR/renders/work-range.png" | tail -1
tools/.venv/bin/python tools/work_range.py --lang en --out "$DIR/renders/work-range.en.png" >/dev/null
printf '%s\n>\n> Згенеровано автоматично (%s) скриптом `tools/build_version.sh`.\n\n' "$WARN" "$NAME" | cat - "$DIR/docs/05-bucket.md" > "$DIR/docs/05-bucket.md.tmp" && mv "$DIR/docs/05-bucket.md.tmp" "$DIR/docs/05-bucket.md"
cp "$SCAD" "$DIR/scad/"; cp -R scad/brand "$DIR/scad/"   # модель підключає include <brand/…> — без них копія не збереться
cp tools/kinematics.py tools/strength.py tools/bucket.py tools/work_range.py "$DIR/scad/"

# 5. Опис версії (функцією: пишеться двічі — для порівняння й остаточно, з правильною назвою)
write_version() {   # write_version НАЗВА [рядки «- Дата/Зміни/Оновлено» з попереднього latest/]
  {
    echo "# $1"; echo; echo "$WARN"; echo
    if [ -n "$2" ]; then printf '%s\n' "$2"; echo "- Оновлено: $(date '+%Y-%m-%d %H:%M')${DESC:+ — $DESC}"
    else echo "- Дата: $(date '+%Y-%m-%d %H:%M')"; [ -n "$DESC" ] && echo "- Зміни: $DESC"; fi
    echo "- Git (база на момент збирання): $GIT_BASE"; echo
    echo "## Діапазони (echo моделі)"; echo '```'; sed 's/^ECHO: //' "$WORK/ranges.echo"; echo '```'; echo
    echo "## STL"; echo '```'; cat "$WORK/stl_list.txt"; echo '```'
    echo "Вузли стріли — у системі стріли (A = 0, хорда вздовж +X), вузли рукояті — у системі рукояті (B = 0, вісь уздовж +X); вузли ковша — у системі ковша (E = 0, x — до вістря зуба); rocker/link/post/assembly — у позі за замовчуванням."; echo
    echo "## Інтерактивний перегляд"; echo "- viewer.html — 3D-сторінка цієї версії (обертання/масштаб, кути стріли/рукояті/ковша, цикл копання). Зміна геометрії наживо — web/viewer.sh."; echo
    echo "## BOM і креслення"; echo "- bom/bom.md, bom/bom.csv — специфікація; dxf/*.dxf — контури пластин 1:1; drawings/parts.pdf — ескізи з основними розмірами (drawings/pages.tsv — яка деталь на якій сторінці)."; echo
    echo "## Друкований набір 1:5"; echo "- print3d/ — поточна підверсія набору (VNNN.K), print3d-history/ — попередні підверсії цієї версії машини."; echo
    echo "## Перетини пластин"; echo '```'; tail -1 "$DIR/docs/overlaps.txt"; echo '```'
    echo "## Рухомі пари"; echo '```'; grep РЕЗУЛЬТАТ "$DIR/docs/motion.txt"; echo '```'
    echo; echo '---'; echo "<sub>$AUTHOR</sub>"
  } > "$DIR/VERSION.md"
}
write_version "$NAME"

# 6. Нова версія чи оновлення на місці. Незмінні STL беруться байт-у-байт із latest/ (--settle):
#    OpenSCAD міняє порядок трикутників, і без цього git бачив би «змінений» файл. bom/, drawings/,
#    dxf/ ще не зібрані (їм потрібна остаточна назва) і однаково похідні від тих самих STL.
MODE=new
if [ -d latest ]; then
  if python3 tools/compare_build.py latest "$DIR" --settle --ignore=print3d,print3d-history,bom,drawings,dxf && [ $FORCE_NEW -eq 0 ]; then
    MODE=update
    echo "  геометрія й числа ті самі — latest/ оновлюється на місці, назва лишається $OLD_NAME (--new — примусово нова версія)"
    for f in "$DIR"/docs/*.md; do sed "s/$NAME/$OLD_NAME/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done
    NAME=$OLD_NAME
    write_version "$NAME" "$(grep -E '^- (Дата|Зміни|Оновлено):' latest/VERSION.md)"
  fi
fi

# 7. BOM, DXF 1:1 і PDF-ескізи — уже з остаточною назвою (вона стоїть у шапці кожної сторінки).
#    PNG сторінок — у build/ (не комітиться): дата в шапці робила кожну сторінку новим файлом
#    при кожному збиранні, а весь вміст і так є в parts.pdf
PNG=build/drawings-png; rm -rf "$PNG"
./tools/bom_drawings.sh --out "$DIR" --version "$NAME" --png "$PNG" | tail -1

# 7а. Статична інтерактивна 3D-сторінка цієї версії (кути — у браузері; відкривається подвійним кліком, three.js тягнеться з CDN)
python3 web/viewer.py --export "$DIR/viewer.html" | tail -1

# 7б. Версія перегляду без бекенду (OpenSCAD-WASM): чи будує модель старіший браузерний рушій. Не зупиняє збирання; потрібен npm install у web/viewer-wasm
if [ -d web/viewer-wasm/node_modules ]; then
  (cd web/viewer-wasm && npm test --silent) > "$DIR/docs/viewer-wasm-test.txt" 2>&1 && echo "  viewer-wasm: тест пройдено" || echo "!!! viewer-wasm: тест НЕ пройдено — див. docs/viewer-wasm-test.txt"
fi

# 8. У latest/. Нова версія: попередній latest/ (з набором і його історією) — в архів versions/;
#    оновлення: замінюється все, крім набору (його збирає print3d-parts/make.sh).
if [ $MODE = new ] && [ -d latest ]; then
  mkdir -p versions
  if git ls-files --error-unmatch latest/VERSION.md >/dev/null 2>&1; then git mv latest "versions/$OLD_NAME"
  else mv latest "versions/$OLD_NAME"; fi
  echo "  $OLD_NAME → versions/$OLD_NAME"
  if [ $COMMIT -eq 1 ]; then git commit -q -m "Archive $OLD_NAME" && echo "== закомічено: $(git log -1 --oneline)"; fi
fi
if [ $MODE = update ]; then
  for x in latest/* latest/.[!.]*; do
    [ -e "$x" ] || continue
    case "${x#latest/}" in print3d|print3d-history) ;; *) rm -rf "$x" ;; esac
  done
  mv "$DIR"/* latest/; rmdir "$DIR"
else
  mv "$DIR" latest
fi

# 9. Картинки для README (docs/img/ — медіа README, не продукт; решта згенерованого — у latest/)
mkdir -p docs/img
cp latest/renders/side_default.png latest/renders/iso_default.png latest/renders/envelope.png latest/renders/part_boom.png latest/renders/part_stick.png latest/renders/part_bucket.png latest/renders/bucket_motion_2d.png docs/img/
cp latest/renders/work-range.png latest/renders/work-range.en.png docs/img/
cp "$PNG"/*_cheek.png docs/img/sketch_cheek.png
echo "== готово: latest/ = $NAME ($([ $MODE = new ] && echo "нова версія" || echo "оновлено на місці"))"

# 10. Нова версія машини — новий набір (VNNN.1): старий набір пішов в архів разом із машиною.
if [ $MODE = new ] && [ $KIT -eq 1 ]; then
  print3d-parts/make.sh "з нової версії машини $NAME"
fi
if [ $COMMIT -eq 1 ]; then
  git add -A && git commit -q -m "${NAME%%-*}: ${DESC:-збирання версії}" && echo "== закомічено: $(git log -1 --oneline)"
fi
