[English](QUICKSTART.md) · **Українська**

# Швидкий старт

> ⚠️ **Модель, розрахунки й креслення згенеровані штучним інтелектом, їх не перевіряв кваліфікований інженер, машину ніхто не будував і не випробовував.** Міні-екскаватор калічить і вбиває. Жодних гарантій; автор не несе відповідальності за шкоду життю, здоров'ю чи майну. Усе — на ваш власний ризик і відповідальність. Повне застереження — у [README.uk.md, розділ «Застереження»](README.uk.md#застереження).

Параметрична модель робочого обладнання причіпного міні-екскаватора — стріла, рукоять, важелі, ківш 300 мм — під уже закуплені гідроциліндри. Одна модель OpenSCAD дає STL, креслення (DXF, PDF), специфікацію, розрахунки та інтерактивну 3D-сторінку. Огляд і жива 3D-модель — у [README.uk.md](README.uk.md), подробиці — у [TECHNICAL.uk.md](TECHNICAL.uk.md).

## Що потрібно

| Для чого | Залежність |
|---|---|
| Модель, збирання версій, 3D-сторінка з сервером | **OpenSCAD** — нічна збірка з рушієм Manifold (перевірено на 2025.07 і 2026.09; стабільна 2021.01 не підійде), `openscad` у PATH; **Python 3** |
| PDF-ескізи, звіт ковша | нічого ставити не треба: `tools/.venv` (matplotlib, shapely) створюється сам при першому збиранні |
| 3D-сторінка без бекенду (WASM) | **Node.js ≥ 20.19** |
| Друкований набір і його аркуші розкладки 1:1 (`print3d-parts/make.sh`) | **Chrome** (HTML → PDF) і **poppler** (`brew install poppler`: `pdftoppm`, `pdfinfo`, `pdftotext` — прев'ю та перевірка сторінок із самого PDF; без нього прев'ю робляться знімком HTML) |
| Медіа README: GIF-тур сторінкою і прев'ю PDF (`tools/media/readme_media.sh`) | **ffmpeg**, **poppler**, Chrome і `puppeteer-core` для Node (один раз: `npm i --no-save --prefix tools/media puppeteer-core`; він же ставить номери сторінок у PDF) |
| 3D-миша SpaceMouse (необов'язково) | Chrome / Edge; на macOS драйвер 3Dconnexion на час роботи вимикається — це роблять команди з `:sm` |

## Основні команди

```bash
# відкрити модель: кути стріли / рукояті / ковша — перші параметри в Customizer
openscad scad/excavator_boom.scad

# зібрати версію → versions/VNNN-дата-час/ (STL, рендери, звіти, BOM, DXF, PDF, viewer.html); --commit одразу комітить
tools/build_version.sh --commit "що змінено"

# лише перевірки: пластини не перекриваються / рухомі пари не зіткаються на всьому ході циліндрів
tools/check_overlaps.sh
tools/check_motion.sh

# друкований набір 1:5: STL кожного компонента, перевірки, BOM, аркуші розкладки 1:1 (SHEETS.pdf)
print3d-parts/make.sh

# 3D-сторінка в браузері: кути — миттєво, інші параметри — через OpenSCAD за ≈ 0.4 с
tools/viewer.sh

# те саме без бекенду: OpenSCAD-WASM у браузері (перший раз сам зробить npm install)
tools/viewer-wasm.sh              # dev-сервер;  build → статичний сайт у dist/;  preview;  test

# зі SpaceMouse на macOS: драйвер вимикається на час роботи сервера і повертається після виходу
tools/with-spacemouse.sh tools/viewer.sh
cd tools/viewer-wasm && npm run preview:sm
```

Один раз після клонування: `git config core.hooksPath tools/git-hooks` — перевірка перекриттів перед комітом змін моделі.

Результати останнього збирання — у теці `versions/` з найбільшим номером: `drawings/parts.pdf`, `dxf/`, `bom/bom.md`, `docs/`, `viewer.html`.
