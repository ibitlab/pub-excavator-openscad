**English** · [Українська](#сторонні-складники)

# Third-party components

This file lists everything in this repository that was **not** written here, together with the licence that applies to it.

**The project has not chosen its own licence yet.** Until it does, what was authored here is simply "all rights reserved" — no permission to use, modify or redistribute it is granted. That is deliberate: a licence can be added at any time, but one that has been granted cannot be taken back. It does not affect the disclaimers in [README.md](README.md) and [SAFETY.md](SAFETY.md), which stand regardless.

## Redistributed as a binary — GPL obligations apply

| Component | Version | Licence | Where it ends up |
|---|---|---|---|
| **OpenSCAD**, compiled to WebAssembly, via the npm package `openscad-wasm-prebuilt` | engine reports **OpenSCAD version 2025.01.19**; npm package `openscad-wasm-prebuilt@1.2.0` | **GPL-2.0-or-later** — the package ships the licence text itself, copied to [tools/viewer-wasm/LICENSE](tools/viewer-wasm/LICENSE) | embedded into `tools/viewer-wasm/dist/` at build time (≈11 MB of the ≈12 MB bundle) |

**Corresponding source:** `https://github.com/lorenzowritescode/openscad-wasm`, declared as the `repository` of the npm package. That project builds the engine from OpenSCAD itself (`https://github.com/openscad/openscad`, GPL-2.0-or-later).

Building `tools/viewer-wasm` produces a `dist/` folder that **contains OpenSCAD itself**. Publishing that folder (for example to GitHub Pages) is distribution of a GPL-2.0 binary, and GPL-2.0 §1 and §3 then apply: the copyright and licence notices must be kept intact, and the recipient must be able to obtain the corresponding source code. To satisfy this, publish `tools/viewer-wasm/LICENSE` and this file alongside the site.

### Why not the official `openscad/openscad-wasm` artefact

That is where the engine ideally comes from, but the project **publishes no current prebuilt release**: the newest one is `2022.03.20`, which predates the Manifold backend this project depends on. Current builds are only obtainable by building from source (Docker + `gmake` + Deno). That remains the option for perfect provenance.

### Why this package was chosen over `openscad-wasm@0.0.4`

The project previously used `openscad-wasm@0.0.4`, which **shipped no licence file at all**, declared no `repository` and no `homepage`, and was published by an unrelated third party. Its binary's provenance could not be established, so the GPL obligation to supply the corresponding source could not have been met. Measured against it, the current engine builds the model identically (same part count, same tooth position, no warnings) but about **60 % slower** — ≈2.2 s instead of ≈1.4 s per rebuild. The bundle also shrank from ≈15 MB to ≈12 MB.

## Loaded at runtime, not redistributed

| Component | Version | Licence | Notes |
|---|---|---|---|
| **three.js** | 0.160.1 (npm) / 0.160.0 (CDN) | MIT | bundled into `tools/viewer-wasm/dist/`; the server page `tools/viewer/index.html` and the exported `viewer.html` load it from `cdn.jsdelivr.net` instead |

## Build-time only — never shipped

| Component | Version | Licence |
|---|---|---|
| **Vite** | 8.3.0 | MIT |
| **puppeteer-core** | installed with `--no-save` for tests only | Apache-2.0 |
| **matplotlib**, **shapely** | in `tools/.venv`, for PDF sketches and the bucket report | PSF-like / BSD-3-Clause |

## What is *not* affected by the GPL

The OpenSCAD model, and everything OpenSCAD produces from it — STL, DXF, PDF sketches, the BOM, the renders and the reports in `versions/` — are the work of this project. The output of a GPL program is not a derivative work of that program, and this model includes no external SCAD library (no `include`/`use`, no MCAD), so no third-party code is embedded in it.

## Referenced but not included

Standards cited by number only (ДСТУ 8940, ГОСТ 8645, РД 22-158-86, ISO 7451) are **not** reproduced here; their texts are copyrighted and must be obtained from the publisher. Product names such as Bobcat are trademarks of their owners and are used only descriptively, for class comparison.

---

# Сторонні складники

Тут перелічено все, що **не** написано в цьому репозиторії, разом із ліцензіями.

**Власну ліцензію проєкт поки не обрав.** Доки її немає, створене тут лишається «всі права збережено»: дозволу використовувати, змінювати чи поширювати не надано. Це свідомо — ліцензію можна додати будь-коли, а от видану вже не відкликати. На застереження в [README.uk.md](README.uk.md) і [SAFETY.uk.md](SAFETY.uk.md) це не впливає: вони діють незалежно.

## Роздається як бінарник — діють вимоги GPL

| Складник | Версія | Ліцензія | Куди потрапляє |
|---|---|---|---|
| **OpenSCAD**, скомпільований у WebAssembly, через пакет `openscad-wasm-prebuilt` | рушій повідомляє **OpenSCAD version 2025.01.19**; пакет `openscad-wasm-prebuilt@1.2.0` | **GPL-2.0-or-later** — пакет сам містить текст ліцензії, скопійований у [tools/viewer-wasm/LICENSE](tools/viewer-wasm/LICENSE) | вшивається у `tools/viewer-wasm/dist/` під час збирання (≈11 МБ із ≈12 МБ) |

**Відповідні вихідні коди:** `https://github.com/lorenzowritescode/openscad-wasm` — вказано як `repository` пакета npm. Той проєкт збирає рушій із самого OpenSCAD (`https://github.com/openscad/openscad`, GPL-2.0-or-later).

Збирання `tools/viewer-wasm` дає теку `dist/`, яка **містить сам OpenSCAD**. Публікація цієї теки (наприклад, на GitHub Pages) — це поширення GPL-бінарника, і діють §1 та §3 GPL-2.0: зберегти повідомлення про авторство й ліцензію та дати одержувачу можливість отримати відповідні вихідні коди. Щоб це виконати, публікуй поруч із сайтом `tools/viewer-wasm/LICENSE` і цей файл.

### Чому не офіційний артефакт `openscad/openscad-wasm`

Саме звідти рушій мав би братися, але проєкт **не публікує актуальних готових збірок**: найновіша — `2022.03.20`, ще до появи Manifold, на який спирається цей проєкт. Свіжу збірку можна отримати лише зібравши з вихідників (Docker + `gmake` + Deno). Це лишається варіантом для ідеального походження.

### Чому цей пакет, а не `openscad-wasm@0.0.4`

Раніше використовувався `openscad-wasm@0.0.4`: він **не містив жодного файлу ліцензії**, не вказував ні `repository`, ні `homepage`, і був опублікований сторонньою особою. Походження його бінарника встановити було неможливо, отже обов'язок надати відповідні вихідні коди виконати не вдалося б. Порівняно з ним нинішній рушій будує модель ідентично (та сама кількість деталей, те саме положення зуба, без попереджень), але приблизно на **60 % повільніше** — ≈2.2 с замість ≈1.4 с на перебудову. Збірка до того ж схудла з ≈15 МБ до ≈12 МБ.

## Завантажується під час роботи, не роздається нами

| Складник | Версія | Ліцензія | Примітка |
|---|---|---|---|
| **three.js** | 0.160.1 (npm) / 0.160.0 (CDN) | MIT | вшивається у `tools/viewer-wasm/dist/`; серверна сторінка `tools/viewer/index.html` і експортована `viewer.html` тягнуть її з `cdn.jsdelivr.net` |

## Лише для збирання — нікуди не потрапляє

| Складник | Версія | Ліцензія |
|---|---|---|
| **Vite** | 8.3.0 | MIT |
| **puppeteer-core** | ставиться з `--no-save` лише для тестів | Apache-2.0 |
| **matplotlib**, **shapely** | у `tools/.venv`, для PDF-ескізів і звіту ковша | PSF-подібна / BSD-3-Clause |

## Чого GPL не стосується

Модель OpenSCAD і все, що вона видає — STL, DXF, PDF-ескізи, специфікація, рендери та звіти у `versions/` — робота цього проєкту. Вихід GPL-програми не є похідним твором від неї, а модель не підключає жодної зовнішньої SCAD-бібліотеки (немає `include`/`use`, немає MCAD), тож чужого коду всередині неї немає.

## Згадується, але не включене

Стандарти, названі лише за номером (ДСТУ 8940, ГОСТ 8645, РД 22-158-86, ISO 7451), тут **не** відтворені: їхні тексти захищені й купуються у видавця. Назви на кшталт Bobcat — торгові марки власників, ужиті лише описово, для порівняння класу.
