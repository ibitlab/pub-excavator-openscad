[English](ARCHITECTURE.md) · **Українська**

# Програмна архітектура

Коротка карта: з чого складається код, хто кого викликає і в якому форматі йдуть дані. Інженерні подробиці — у [TECHNICAL.uk.md](TECHNICAL.uk.md); геометрія в сторінках, друк проти металу і формат OFF — у [GEOMETRY.uk.md](GEOMETRY.uk.md).

## 1. Принцип

- **Одне джерело правди** — `scad/excavator_boom.scad`. Усе інше — його споживачі.
- **Інтерфейс моделі — командний рядок OpenSCAD**: вхід — `-D назва=значення`, вихід — файл геометрії та рядки `ECHO:` у stderr. Жоден інструмент не має власного списку розмірів: числа читаються з echo, контури — з експорту.
- **Двійники** (`tools/kinematics.py`, `tools/bucket.py`, блок `//<pose>` у сторінках) повторюють формули моделі незалежним кодом; розбіжність ловлять перевірки (розділ 6): `check_twins.py` для Python, `npm test` для сторінок.
- **Згенероване** живе в `latest/` (поточна версія, набір 1:5 — у ній) і `versions/VNNN-…/` (архів); у корені — лише джерела й `docs/img/`. Проміжне — у `build/`, його немає в git.

## 2. Стек

| Шар | Технології |
|---|---|
| Модель | OpenSCAD (настільний 2026.x, рушій Manifold; CGAL — лише для рендерів) |
| Розрахунки, креслення, PDF | Python 3: стандартна бібліотека (системний `python3`); numpy, shapely, matplotlib, Pillow (`tools/.venv`) |
| Оркестрація | bash-скрипти (`build_version.sh`, `make.sh`, `check_*.sh`) |
| 3D-сторінка з сервером | `http.server` (Python) + three.js 0.160 з CDN, один HTML без збирання |
| 3D-сторінка без бекенду | Vite, three.js, `openscad-wasm-prebuilt` (рушій 2025.01) у веб-воркері, WebXR (AR на Android); тест — node |
| PDF / знімки / відео | Chrome headless (HTML → PDF, знімки), puppeteer-core, ffmpeg, poppler |
| CI / хостинг | GitHub Actions → GitHub Pages (лише WASM-сторінка) |
| Процес | git-хук `tools/git-hooks/pre-commit`, лінтери `tools/lint.sh` (ruff, shellcheck), skills і workflow Claude Code у `.claude/` |

## 3. Схема зв'язків

```mermaid
flowchart LR
  SCAD["scad/excavator_boom.scad<br/>+ scad/brand/*.scad"]
  subgraph Перевірки
    OV[check_overlaps.sh]
    MO[check_motion.sh]
    TW[check_twins.py]
  end
  subgraph "Версія → latest/ (build_version.sh)"
    STL[stl/*.stl]
    PNG[renders/*.png]
    REP["docs/*.md<br/>kinematics · strength · bucket"]
    BOM["bom_drawings.py<br/>bom · dxf · parts.pdf"]
    VH[viewer.html]
  end
  subgraph "Друкований набір → latest/print3d/ (print3d-parts/make.sh)"
    PS[parts.scad] --> PSTL[stl/**]
    PSTL --> SH["sheets/make_sheets.py<br/>SHEETS.pdf · sheets.json"]
    PSTL --> DR["model_drive.py<br/>DRIVE.md"]
  end
  subgraph Сторінки
    SRV[viewer.py + viewer/index.html]
    WASM[viewer-wasm/ → dist/]
  end
  SCAD -->|"-D part=overlap/collide → STL"| OV & MO
  SCAD -->|"-D part=… → STL/PNG"| STL & PNG
  SCAD -->|"ECHO BOM_* + SVG part=flat"| BOM
  SCAD -->|"include, part=none"| PS
  SCAD -->|"12 × OFF + ECHO VIEW"| SRV
  SCAD -->|"?raw у збірку, view_all → OFF"| WASM
  PY["kinematics.py · bucket.py<br/>strength.py · work_range.py"] --> REP
  SCAD -->|"-D TWIN__=echo(…)"| TW
  PY --> TW
  VJ[views.json] --> SRV & WASM
  VJ --> VP[views.py → PNG]
  SRV --> VH
  WASM -->|"GitHub Actions"| PAGES[GitHub Pages]
  PNG & PSTL & WASM --> MEDIA["tools/media → docs/img/"]
```

## 4. Інтерфейс моделі

**Вхід** — лише `-D`:

| Параметр | Значення |
|---|---|
| `part` | `assembly` (типово), вузол (`boom`, `stick`, `bucket`, `post`, …), група пластин (`boom_gussets`, …), `flat` / `tubeface` / `flatbrand` / `tubebrand` (2D-проєкції), `overlap` / `collide` (перетин `ov_a`×`ov_b`), `view_all` (усі тіла сторінки в одному файлі), `none` (модель як бібліотека) |
| `boom_angle`, `stick_angle`, `bucket_angle` | поза, градуси; поза ходом циліндра модель сама обмежує |
| `show_*`, `ground_span` | видимість вузлів і допоміжного (земля, зона досяжності, логотип) |
| решта | будь-який параметр Customizer (групи `/* [Назва] */` на початку файлу) |

**Вихід:**

| Канал | Формат | Хто читає |
|---|---|---|
| `ECHO: "=== …"` | текст: діапазони кутів, поточна поза, ківш | `VERSION.md`, лог сторінок |
| `ECHO: "!!! …"` | текст: попередження (циліндр не дістає, мертва точка) | сторінки, `npm test` (валиться на них) |
| `ECHO: VIEW = [[ключ, значення], …]` | список пар ≈ JSON (`undef/nan/inf` → `null`) | обидві сторінки: точки шарнірів, список тіл, пальці |
| `ECHO: BOM_PARAMS / BOM_FLAT / BOM_STRIPS / BOM_WEAR / BOM_SHELL / BOM_TUBES / BOM_ROUND / BOM_PINS` | вкладені списки | `bom_drawings.py` |
| STL (binary) | геометрія вузлів | версія, перевірки (`stl_volume.py` → см³), набір |
| OFF з кольорами граней | сітка + RGB грані | сторінки (колір = матеріал / роль) |
| SVG | 2D-контур пластини (`part="flat"`) | `bom_drawings.py` → DXF, розміри, маса |
| PNG | рендер (`--render=cgal`, ортогональна/перспектива) | версія, аркуші, `views.py` |

## 5. Потоки даних

| Звідки → куди | Формат | Хто / як |
|---|---|---|
| модель → перевірки | STL перетину → об'єм, см³ (допуск 0.05) | `check_overlaps.sh` (пари пластин вузла), `check_motion.sh` (рухомі пари на всьому ході) |
| модель ↔ Python-двійники | параметри й результати двійників як вирази OpenSCAD в одному `-D TWIN__=echo(…)` → список ≈ JSON; допуск 0.05 мм / 0.01° | `check_twins.py` (у `build_version.sh` і git-хуку) |
| модель → версія | STL, PNG, echo → `VERSION.md`, усе в `build/version/` | `build_version.sh` |
| нове збирання ↔ `latest/` | STL — набором трикутників, звіти й діапазони кутів — текстом без номерів і дат → код виходу 0 (те саме) / 1 (змінилось) | `compare_build.py`: змінилось — старий `latest/` у `versions/` (git mv), нова версія; те саме — `latest/` оновлюється на місці |
| двійники → звіти | Markdown у stdout, PNG (matplotlib) | `kinematics.py`, `strength.py`, `bucket.py`, `work_range.py` |
| модель → BOM і креслення | echo `BOM_*` + SVG → `bom.md`, `bom.csv`, DXF 1:1, `parts.pdf` | `bom_drawings.py` |
| версія → README | копії PNG у `docs/img/`; `README*.md` посилаються на `latest/…` (шляхи сталі). Сторінка креслення копіюється, лише якщо змінилась поза шапкою й підвалом із датою | `build_version.sh`, `copy_if_changed.py` |
| сторінка (сервер) ↔ `viewer.py` | `GET /api/schema` → JSON параметрів; `GET /api/views` → `views.json`; `POST /api/build {params, fresh}` → `{view, parts{тіло: {pos, groups[{color, idx}]}}, log, ms}` | 12 процесів OpenSCAD паралельно, по OFF на тіло; кеш останніх наборів параметрів |
| WASM-сторінка ↔ воркер | `postMessage {id, source, files, defs}` → `{id, view, parts, log, ms}` (буфери — transfer) | один запуск `part="view_all"`: тіла зсунуті на `i·spacing` по Y, `offmesh.js` розрізає назад |
| модель → WASM-сторінка | текст `.scad` вшивається збіркою (`?raw`), `views.json` — як JSON | Vite; інших входів немає (з адреси — лише `?lang`) |
| поза в браузері | кути → точки `pose()` → матриці тіл | JS, без OpenSCAD; ті самі формули, що `pt_*()` моделі |
| сторінка → ракурси | JSON (камера, кути, змінені параметри, видимість): буфер обміну / файл `views.json` / `localStorage` | `views.py render` → PNG OpenSCAD |
| модель → набір 1:5 | `parts.scad` + `parts.tsv` (TSV, «-» = порожньо) → STL по одному компоненту, у `build/print3d/` → `latest/print3d/` підверсією VNNN.K (попередня → `print3d-history/`) | `print3d-parts/make.sh` (лише якщо модель збігається з `latest/scad/`); `check_print.py` → JSON; `make_bom.py` → `BOM.md`; `model_drive.py` → `DRIVE.md` |
| набір → аркуші | STL (силуети shapely) + `assembly.tsv` + `sheets.scad` (PNG) → HTML → PDF | `make_sheets.py` → `SHEETS.pdf`, `sheets.json` (усі числа); прев'ю `png/` (з PDF через poppler) лишаються в `build/`, аркуш ковша йде в `docs/img/` через `copy_if_changed.py` |
| сторінка/PDF → медіа README | знімки puppeteer → GIF (ffmpeg); прев'ю PDF | `tools/media/readme_media.sh` → `docs/img/` |
| `main` → Pages | `npm ci` → `npm test` → `vite build` → `dist/` + LICENSE, THIRD-PARTY | `.github/workflows/pages.yml` |

## 6. Що має збігатися і хто це перевіряє

| Інваріант | Перевірка |
|---|---|
| пластини прилягають, не перекриваються | `check_overlaps.sh`; git-хук перед комітом змін у `scad/` |
| у коді Python і shell немає справжніх помилок | `tools/lint.sh` (ruff: pyflakes і bugbear; shellcheck) — запускається вручну |
| рухомі пари не зіткаються | `check_motion.sh` (у складі збирання версії) |
| Python-двійники = модель (`kinematics.py`, `bucket.py`) | `check_twins.py`: кожен параметр, точки шарнірів і довжини циліндрів у 27 позах, діапазони кутів, профіль ковша — одним запуском OpenSCAD (≈ 0.3 с); зупиняє збирання версії, працює в git-хуку при коміті `scad/` чи двійника |
| модель будується старішим рушієм WASM без попереджень | `npm test` (також у CI перед публікацією) |
| блоки `//<pose>`, `//<spacemouse>`, `//<viewjson>` однакові в обох сторінках | `npm test` |
| поза JS = echo моделі (зуб ковша) | `npm test` |
| переклад повний, кольори легенди є в `color(...)` моделі | `npm test` |
| перерахунок камери сторінка → OpenSCAD | `views.py check` + `media/view_roundtrip.mjs` |
| кожна деталь набору — рівно в одному кроці | `make.sh` (звірка `parts.tsv` ↔ `assembly.tsv`) |
| набір зібраний з моделі `latest/` | `make.sh` відмовляє, якщо `scad/` відрізняється від `latest/scad/` |
| новий номер версії — лише коли змінилось по суті | `compare_build.py` у `build_version.sh` (`--new` — примусово) |
| документи: посилання, якорі, кістяк двомовних пар | `check_docs.py` |
| у коміті немає особистих даних (текст і метадані PDF, PNG, zip) | `check_personal.py` |

## 7. Де що лежить

| Тека | Вміст |
|---|---|
| `scad/` | модель і полігони логотипа |
| `tools/` | двійники, генератори, перевірки, `media/`, `git-hooks/`, `dev/` (помічник SpaceMouse, аналітика агентів) |
| `web/` | сторінки: `viewer/` із сервером `viewer.py`, `viewer-wasm/` (публікується на Pages); як ними користуватися — [web/README.uk.md](../web/README.uk.md) |
| `latest/` | поточна версія: `stl/`, `renders/`, `docs/`, `bom/`, `dxf/`, `drawings/`, `scad/` (знімок моделі й скриптів), `viewer.html`, `VERSION.md`; `print3d/` — поточний набір 1:5 (VNNN.K), `print3d-history/` — його попередні підверсії |
| `versions/VNNN-…/` | архів: сюди переїжджає колишній `latest/` (git mv), коли змінились геометрія чи числа звітів |
| `build/` | проміжне й журнали перевірок, PNG-прев'ю ескізів і аркушів; не в git |
| `print3d-parts/` | джерела набору 1:5: `parts.scad`, `parts.tsv`, `assembly.tsv`, `make.sh`, `group.sh`, `sheets/` (генератор), `stand/` (окрема стійка зі своїм `make.sh` і STL); результат — у `latest/print3d/`; опис — [print3d-parts/README.md](../print3d-parts/README.md) |
| `docs/` | документи: TECHNICAL, QUICKSTART, ARCHITECTURE, GEOMETRY, STORY (`.md` / `.uk.md`); README і SAFETY — у корені |
| `docs/img/` | картинки README (оновлюють `build_version.sh` і `readme_media.sh`) |
| `views.json` | збережені ракурси (спільні для сторінок і `views.py`) |
| `.claude/` | skills і workflow агентів |
| `temp/` | чернетки й медіа для публікацій, не в git |
| `_deprecated/` | архів, не використовується |

Ключові файли за роллю (сторінки й друкований набір описані у своїх README):

| Файл | Що робить |
|---|---|
| `scad/excavator_boom.scad` | **Модель.** Усі параметри — на початку файлу (групи Customizer); кути — первинні параметри, їхні діапазони обчислюються з довжин циліндрів і виводяться через `echo()` |
| `tools/kinematics.py` | Двійник кінематики: діапазони кутів, плечі моментів, зусилля на зубі, робоча зона; `--search` — підбір положень кріплень |
| `tools/bucket.py` | Двійник ковша: місткість (врівень / з «шапкою»), маса, кути утримання й висипання, 2D-зазори рухомих пар на всьому ході, міцність вух, пальців E/Q і швів. Запуск — `tools/.venv/bin/python` |
| `tools/strength.py` | Статика ланок + опір матеріалів: епюри N/V/M, труби й накладки, пальці, втулки, шви; порівняння профілів (`--boom 120x80x5 --stick 100x60x5`) |
| `tools/work_range.py` | Креслення робочої зони з розмірами A…J перебором усього ходу трьох циліндрів; `--lang uk\|en` |
| `tools/check_twins.py` | Звірка Python-двійників з моделлю (розділ 6) |
| `tools/check_overlaps.sh`, `tools/check_motion.sh` | Пластини прилягають, але не перекриваються; рухомі пари не зіткаються на всьому ході циліндрів |
| `tools/build_version.sh`, `tools/compare_build.py` | Збирання версії (перевірки → STL → рендери → звіти → BOM і креслення → `latest/`) і рішення «нова версія чи оновлення на місці» |
| `tools/bom_drawings.sh` → `bom_drawings.py` | BOM, DXF 1:1 кожної пластини, PDF-ескізи — з echo моделі та проєкцій пластин, без окремого списку розмірів |
| `views.json` → `tools/views.py` | Ракурси, збережені в 3D-сторінці, стають відтворюваними рендерами: `list` / `flags` / `render НАЗВА` / `check` |
| `scad/brand/` → `tools/brand_merge.py` | Логотип: один polygon() на розмір (~800 скалок нульової площі з генератора втричі сповільнювали кожну перебудову у WASM); де він стоїть — таблиця `brand_marks` у моделі |
| `tools/page_style.py`, `tools/author.py` | Один вигляд усіх PDF (шапка, підвал); авторство з `AUTHORS` |
| `tools/copy_if_changed.py` | Копіює PNG сторінки PDF у `docs/img/`, лише якщо сторінка змінилась поза шапкою й підвалом із датою — інакше кожне збирання комітило б новий двійковий файл |
| `tools/media/` | Медіа README (`readme_media.sh`: GIF-тур сторінкою, прев'ю PDF) і медіа для публікацій (`make_media.sh` → `temp/media/`) |
| `tools/check_personal.py` | Перед кожним комітом: особисті дані в staged-тексті й метаданих двійкових файлів (PDF, PNG, zip-формати на кшталт `.3mf`); особисте цієї машини скрипт бере під час запуску, у ньому самому цього немає |
| `tools/check_docs.py` | Після правок документації: посилання, якорі, кістяк двомовних пар |
| `tools/lint.sh` | ruff (`ruff.toml`) і shellcheck (`.shellcheckrc`); залежності Python — `tools/requirements.txt`, лінтери — `tools/requirements-dev.txt` |
| `tools/git-hooks/pre-commit` | Перед комітом `scad/` чи двійника: `check_twins.py` і перевірка перекриттів. Увімкнути один раз: `git config core.hooksPath tools/git-hooks` |
| `CLAUDE.md`, `.claude/skills/`, `.claude/workflows/` | Правила для Claude Code; skills проєкту; багатоагентні workflow (`design-review`, `research-sweep`), агенти яких одразу пишуть результат у файли |
