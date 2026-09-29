**English** · [Українська](QUICKSTART.uk.md)

# Quick start

> ⚠️ **Ihor Ivaniuk (@IBITLAB) is the originator and product owner: organises the AI's work, sets the tasks, makes the decisions. The execution — geometry, calculations, drawings, code and texts — is done by AI (Claude Code by Anthropic).** No qualified engineer has checked the model, the calculations or the drawings, and no machine has ever been built or tested from them. A mini excavator maims and kills. No warranty of any kind; the author accepts no liability for harm to life, health or property. Everything is at your own risk and on your own responsibility. The full disclaimer is in [README.md, section Disclaimer](../README.md#disclaimer).

A parametric model of the working equipment of a towable mini excavator — boom, stick, linkage and a **300 mm bucket** — built around already-purchased hydraulic cylinders. One OpenSCAD model produces STL files, drawings (DXF, PDF), a bill of materials, the calculations and an interactive 3D page. The overview and the live 3D model are in [README.md](../README.md), the details in [TECHNICAL.md](TECHNICAL.md).

## What you need

| For what | Dependency |
|---|---|
| The model, building versions, the 3D page with a server | **OpenSCAD** — a nightly build with the Manifold engine (verified on 2025.07 and 2026.09; the stable 2021.01 will not do), `openscad` on the PATH; **Python 3** |
| PDF sketches, the bucket report, the twin check | nothing to install: `tools/.venv` (`tools/requirements.txt`: numpy, shapely, matplotlib, Pillow) is created on the first build; the linters for `tools/lint.sh` — `tools/.venv/bin/python -m pip install -r tools/requirements-dev.txt` |
| The 3D page without a backend (WASM) | **Node.js ≥ 20.19** |
| The printed kit and its 1:1 sorting sheets (`print3d-parts/make.sh`) | **Chrome** (HTML → PDF) and **poppler** (`brew install poppler`: `pdftoppm`, `pdfinfo`, `pdftotext` — previews and page checks from the PDF itself; without it the previews are screenshots of the HTML) |
| README media: the page tour GIF and the PDF previews (`tools/media/readme_media.sh`) | **ffmpeg**, **poppler**, Chrome and `puppeteer-core` for Node (once: `npm i --no-save --prefix tools/media puppeteer-core`; it also puts page numbers on the PDFs) |
| A SpaceMouse 3D mouse (optional) | Chrome / Edge; on macOS the 3Dconnexion driver is switched off for the session — the `:sm` commands do that for you |

## Core commands

```bash
# open the model: boom / stick / bucket angles are the first parameters in the Customizer
openscad scad/excavator_boom.scad

# build a version → latest/ (STL, renders, reports, BOM, DXF, PDF, viewer.html, the 1:5 kit); the previous one → versions/
tools/build_version.sh --commit "what changed"

# checks only: plates abut without overlapping / moving pairs never collide over the full cylinder stroke /
# the Python twins match the model / linters
tools/check_overlaps.sh
tools/check_motion.sh
tools/.venv/bin/python tools/check_twins.py
tools/lint.sh

# the 1:5 printed kit: STL of every component, checks, BOM, 1:1 sorting sheets (SHEETS.pdf)
print3d-parts/make.sh

# the 3D page in a browser: angles are instant, other parameters rebuild through OpenSCAD in ≈ 0.4 s
web/viewer.sh

# the same without a backend: OpenSCAD-WASM in the browser (the first run does npm install itself)
web/viewer-wasm.sh              # dev server;  build → a static site in dist/;  preview;  test

# with a SpaceMouse on macOS: the driver is released while the server runs and restored on exit
tools/dev/with-spacemouse.sh web/viewer.sh
cd web/viewer-wasm && npm run preview:sm
```

Once after cloning: `git config core.hooksPath tools/git-hooks` — before every commit that touches the model or its Python twins this checks that the twins still match the model and that the plates do not overlap.

The results of the last build are in `latest/`: `drawings/parts.pdf`, `dxf/`, `bom/bom.md`, `docs/`, `viewer.html`, and the printed kit in `print3d/`. Earlier versions are in `versions/`.
