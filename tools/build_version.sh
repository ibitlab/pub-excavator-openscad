#!/usr/bin/env bash
# Збирання версії: versions/VNNN-РРРР-ММ-ДД-ГГХХ/ зі STL кожної деталі, рендерами, звітами та знімком моделі.
# Використання: tools/build_version.sh [--commit] ["короткий опис змін"]
#   --commit — після збирання закомітити все (git add -A) з повідомленням "VNNN: опис"
set -e -o pipefail
cd "$(dirname "$0")/.."
COMMIT=0; DESC=""
for a in "$@"; do case "$a" in --commit) COMMIT=1 ;; -h|--help) sed -n '2,4p' "$0"; exit 0 ;; *) DESC="$a" ;; esac; done
SCAD=scad/excavator_boom.scad
# Звіти й VERSION.md читають окремо від README — застереження має бути в кожному з них.
WARN='> **УВАГА:** згенеровано штучним інтелектом. Кваліфікований інженер не перевіряв, машину за цією моделлю не збудовано й не випробувано.
> Використання — на власний ризик і відповідальність; відомі недоробки конструкції — у `SAFETY.md`.'
# Авторство — дрібно внизу кожного згенерованого документа; джерело — AUTHORS у корені
AUTHOR="$(head -1 AUTHORS)"
GIT_BASE="$(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))"
[ -n "$(git status --porcelain)" ] && GIT_BASE="$GIT_BASE + незакомічені зміни робочого дерева"
mkdir -p versions
last=$(ls versions 2>/dev/null | sed -n 's/^V\([0-9][0-9][0-9]\)-.*/\1/p' | sort -n | tail -1)
N=$(printf "%03d" $((10#${last:-0} + 1)))
DIR="versions/V${N}-$(date +%Y-%m-%d-%H%M)"
mkdir -p "$DIR/stl" "$DIR/renders" "$DIR/docs" "$DIR/scad"   # bom/, dxf/, drawings/ створює bom_drawings.sh
echo "== $DIR"

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
done | tee "$DIR/docs/stl_list.txt"

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
openscad -o "$DIR/renders/iso_default.png" --imgsize=2400,1650 --camera=2500,-3500,1800,900,0,-100 --projection=p --viewall --autocenter --colorscheme=Tomorrow --render=cgal -D boom_angle=20 -D stick_angle=100 -D bucket_angle=60 "$SCAD" >/dev/null 2>&1
# ground_span менший за типовий: із --viewall площина 9000 мм ужимає машину вдвічі
openscad -o "$DIR/renders/envelope.png" --imgsize=1600,1000 $CAM -D boom_angle=-38 -D stick_angle=100 -D bucket_angle=60 -D show_envelope=true -D ground_span=3000 "$SCAD" >/dev/null 2>&1
for p in boom stick bucket; do
  openscad -o "$DIR/renders/part_$p.png" --imgsize=2400,1500 --camera=800,-2500,900,0,0,0 --projection=p --colorscheme=Tomorrow --viewall --autocenter --render=cgal -D "part=\"$p\"" "$SCAD" >/dev/null 2>&1
done

# Другий ракурс кожного вузла — КРІПЛЕННЯ зблизька: на загальному виді вуха ковша,
# вежа F і вилка D ховаються за корпусом. Камери тут з фіксованою відстанню (це
# наближення, а не весь вузол), тому після зміни геометрії ці три картинки треба
# переглянути очима: --viewall їх не врятує, кадр може зрізати кронштейн.
CAM_BOOM="--imgsize=2400,1700 --camera=890,0,229,42,0,205,1300"      # центр: між осями D і F
CAM_STICK="--imgsize=2400,1500 --camera=40,0,80,42,0,205,1450"        # центр: п'ята, осі B/G/H
CAM_BUCKET="--imgsize=2400,1600 --camera=0,0,0,42,0,205,0 --viewall --autocenter"
VIEW="--projection=p --colorscheme=Tomorrow --render=cgal"
openscad -o "$DIR/renders/part_boom_mount.png"   $CAM_BOOM   $VIEW -D 'part="boom"'   "$SCAD" >/dev/null 2>&1
openscad -o "$DIR/renders/part_stick_mount.png"  $CAM_STICK  $VIEW -D 'part="stick"'  "$SCAD" >/dev/null 2>&1
openscad -o "$DIR/renders/part_bucket_mount.png" $CAM_BUCKET $VIEW -D 'part="bucket"' "$SCAD" >/dev/null 2>&1

# Труба в крупному плані ЗАВЖДИ виходить за кадр — це нормально. А от кронштейн не
# повинен: перевіряємо це, рендеруючи ті самі камери з самими лише кронштейнами.
# Підрізка полів зрізаного кадру не виявить — він виглядає як нормальний.
CHK=$(mktemp -d)
for g in boom_gussets boom_bracket_D boom_bracket_F; do
  openscad -o "$CHK/$g.png" $CAM_BOOM $VIEW -D "part=\"$g\"" "$SCAD" >/dev/null 2>&1
done
for g in stick_cheeks stick_bracket_H; do
  openscad -o "$CHK/$g.png" $CAM_STICK $VIEW -D "part=\"$g\"" "$SCAD" >/dev/null 2>&1
done
openscad -o "$CHK/bucket_ears.png" $CAM_BUCKET $VIEW -D 'part="bucket_ears"' "$SCAD" >/dev/null 2>&1
tools/.venv/bin/python tools/trim_png.py --edges "$CHK"/*.png \
  || echo "!!! крупний план зрізає кронштейн — виправ камеру в tools/build_version.sh"
rm -rf "$CHK"

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
  printf '%s\n>\n> Згенеровано автоматично (%s) скриптом `tools/build_version.sh`.\n\n' "$WARN" "$(basename "$DIR")" | cat - "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  printf '\n---\n<sub>%s</sub>\n' "$AUTHOR" >> "$f"
done
openscad -o "$DIR/docs/ranges.echo" "$SCAD" >/dev/null 2>&1
# Вихідні дані пишуться вручну і можуть бути відсутні (їх немає у публічній копії) — не зупиняти через це збирання
if [ -f docs/01-design-inputs.md ]; then cp docs/01-design-inputs.md "$DIR/docs/"
else echo "  docs/01-design-inputs.md немає — пропущено (документ пишеться вручну)"; fi
(cd tools && .venv/bin/python bucket.py --png "../$DIR/renders/bucket_motion_2d.png" > "../$DIR/docs/05-bucket.md") || echo "!!! bucket.py: є зіткнення у 2D-перевірці — див. docs/05-bucket.md"
# Креслення робочої зони з розмірами (A…J) — обома мовами, як і README
tools/.venv/bin/python tools/work_range.py --out "$DIR/renders/work-range.png" | tail -1
tools/.venv/bin/python tools/work_range.py --lang en --out "$DIR/renders/work-range.en.png" >/dev/null
printf '%s\n>\n> Згенеровано автоматично (%s) скриптом `tools/build_version.sh`.\n\n' "$WARN" "$(basename "$DIR")" | cat - "$DIR/docs/05-bucket.md" > "$DIR/docs/05-bucket.md.tmp" && mv "$DIR/docs/05-bucket.md.tmp" "$DIR/docs/05-bucket.md"
cp "$SCAD" "$DIR/scad/"; cp -R scad/brand "$DIR/scad/"   # модель підключає include <brand/…> — без них копія не збереться
cp tools/kinematics.py tools/strength.py tools/bucket.py tools/work_range.py "$DIR/scad/"

# 4а. BOM, DXF 1:1 і PDF-ескізи деталей
./tools/bom_drawings.sh --out "$DIR" --version "$(basename "$DIR")" | tail -1
cp "$DIR/bom/bom.md" "$DIR/docs/04-bom.md"

# 4а'. Статична інтерактивна 3D-сторінка цієї версії (кути — у браузері; відкривається подвійним кліком, three.js тягнеться з CDN)
python3 tools/viewer.py --export "$DIR/viewer.html" | tail -1

# 4а''. Версія перегляду без бекенду (OpenSCAD-WASM): чи будує модель старіший браузерний рушій. Не зупиняє збирання; потрібен npm install у tools/viewer-wasm
if [ -d tools/viewer-wasm/node_modules ]; then
  (cd tools/viewer-wasm && npm test --silent) > "$DIR/docs/viewer-wasm-test.txt" 2>&1 && echo "  viewer-wasm: тест пройдено" || echo "!!! viewer-wasm: тест НЕ пройдено — див. docs/viewer-wasm-test.txt"
fi

# 4б. Картинки для README (єдине згенероване, що лежить поза versions/)
mkdir -p docs/img
cp "$DIR/renders/side_default.png" "$DIR/renders/envelope.png" "$DIR/renders/part_boom.png" "$DIR/renders/part_stick.png" "$DIR/renders/part_bucket.png" "$DIR/renders/bucket_motion_2d.png" docs/img/
cp "$DIR/renders/work-range.png" "$DIR/renders/work-range.en.png" docs/img/
cp "$DIR"/renders/part_*_mount.png docs/img/
cp "$DIR"/drawings/png/*_cheek.png docs/img/sketch_cheek.png

# 5. Опис версії
{
  echo "# $(basename "$DIR")"; echo; echo "$WARN"; echo
  echo "- Дата: $(date '+%Y-%m-%d %H:%M')"; echo "- Git (база на момент збирання): $GIT_BASE"
  [ -n "$DESC" ] && echo "- Зміни: $DESC"; echo
  echo "## Діапазони (echo моделі)"; echo '```'; sed 's/^ECHO: //' "$DIR/docs/ranges.echo"; echo '```'; echo
  echo "## STL"; echo '```'; cat "$DIR/docs/stl_list.txt"; echo '```'
  echo "Вузли стріли — у системі стріли (A = 0, хорда вздовж +X), вузли рукояті — у системі рукояті (B = 0, вісь уздовж +X); вузли ковша — у системі ковша (E = 0, x — до вістря зуба); rocker/link/post/assembly — у позі за замовчуванням."; echo
  echo "## Інтерактивний перегляд"; echo "- viewer.html — 3D-сторінка цієї версії (обертання/масштаб, кути стріли/рукояті/ковша, цикл копання). Зміна геометрії наживо — tools/viewer.sh."; echo
  echo "## BOM і креслення"; echo "- bom/bom.md, bom/bom.csv — специфікація; dxf/*.dxf — контури пластин 1:1; drawings/parts.pdf (+ png/) — ескізи з основними розмірами."; echo
  echo "## Перетини пластин"; echo '```'; tail -1 "$DIR/docs/overlaps.txt"; echo '```'
  echo "## Рухомі пари"; echo '```'; grep РЕЗУЛЬТАТ "$DIR/docs/motion.txt"; echo '```'
  echo; echo '---'; echo "<sub>$AUTHOR</sub>"
} > "$DIR/VERSION.md"
echo "== готово: $DIR"
if [ $COMMIT -eq 1 ]; then
  git add -A && git commit -q -m "$(basename "$DIR" | cut -d- -f1): ${DESC:-збирання версії}" && echo "== закомічено: $(git log -1 --oneline)"
fi
