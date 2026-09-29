**English** · [Українська](GEOMETRY.uk.md)

# Geometry: page, steel, print

Where the 3D pages get their geometry, how the STL for printing differs from the model for steel, and how the OFF format that carries meshes to the browser is laid out. The overall map of the code is [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Who builds from what

| Consumer | Source | Output |
|---|---|---|
| WASM page (`web/viewer-wasm/`) | `scad/excavator_boom.scad` — steel at 1:1, welded bodies | OFF in browser memory |
| Page with a server (`web/viewer.py`) | the same model | one OFF per body → JSON |
| `tools/build_version.sh` | the same model | STL 1:1 in `latest/stl/` |
| `print3d-parts/make.sh` | `print3d-parts/parts.scad` (the model as a library) | STL 1:5, one component per file |

The pages do not use the printed kit and do not produce STL.

## 2. The WASM page

- **The model is bundled.** Vite puts the text of `scad/excavator_boom.scad` (and `scad/brand/*.scad`) into the build via `?raw`. The page has no other source of `.scad`.
- **Angles need no OpenSCAD.** JavaScript (the `//<pose>` block) poses the boom, stick and bucket from the joint points the model printed in `echo(VIEW = …)`.
- **Other parameters mean a rebuild.** A changed parameter goes to the web worker as `-D name=value`. The worker runs OpenSCAD-WASM with `part="view_all"`, gets one OFF file, cuts it into bodies ([section 5](#5-how-12-bodies-fit-in-one-file)) and returns the meshes to the page.
- **Changes live only in the browser.** Nothing is written to disk. To get a parameter into the STL for steel or for print, write it into the `.scad` (the "Copy" button gives ready lines) and rebuild the version or the kit.

## 3. Print versus steel

The kit is a wrapper, `print3d-parts/parts.scad`: it `include`s the model with `part="none"`, and not a single line of the model is changed. The shape of every part is the same; the wrapper adds the differences:

| What | Steel (model) | Print (wrapper) |
|---|---|---|
| Scale | 1:1 | 1:5 (the longest tube, 1050 mm → 210 mm, fits a 250 mm bed) |
| Split | welded sub-assemblies | every component on its own: tube, plate, bushing, pin |
| Placement | in the sub-assembly's frame | laid with its smallest dimension up: axis and angle from `parts.tsv` |
| Pins | nominal diameter | 0.40 mm thinner (clearance), with a head; holes in the sub-assemblies stay unchanged |
| Hydraulic cylinder | solid body | blind bore for the rod, 0.35 mm clearance |
| Logo | a decal, absent from the STL | recessed into faces; positions from the model (`brand_marks`), depth from the wrapper |
| Kit only | — | pins with heads, rings, post plates, split cylinder — from the same expressions as the model; numbers match `echo(BOM_*)` |

## 4. The OFF format

OFF (Object File Format) is a text mesh. It is an old open format from the Geomview program (early 1990s); MeshLab and CGAL read it, and the ModelNet and Princeton Shape Benchmark model collections are stored in it. OpenSCAD exports to it out of the box (`-o file.off`) and in recent versions writes the colour of every face; STL has no colour. The only thing invented in this project is packing 12 bodies into one file and cutting them apart again ([section 5](#5-how-12-bodies-fit-in-one-file)); both parsers read only what OpenSCAD writes: faces with a colour, no vertex colours or normals. An example — the output of `openscad -o t.off` for two cubes of different colours (shortened):

```
OFF                     ← format signature
16 24 0                 ← vertices, faces, edges (edges are not written, always 0)
0 0 0                   ← vertex 0: x y z, mm
0 10 0                  ← vertex 1
…                       ← 16 vertex lines in total
3 0 3 1 229 153 25      ← face: 3 vertices, indices 0 3 1, colour R G B
3 9 0 1 229 153 25
…
3 4 7 5 48 96 160       ← a face of the second cube, another colour
```

| Part | Contents |
|---|---|
| Header | `OFF` and three counts: the desktop engine writes them on the next line, WASM on the same one (`OFF 8 6 0`); both parsers accept either |
| Vertices | each written once, mm, the model's coordinate system |
| Faces | `n`, then `n` vertex indices, then (optionally) a colour. The desktop engine writes triangles, WASM polygons too (a cube face is one quad `4 …`); the parser fans each into `0, t, t+1` |
| Colour | integer RGB 0–255 from the model's `color(...)`: `[0.9,0.6,0.1]` → `229 153 25`. Transparency is not written. No colour — default `230,200,60`. The server parser also accepts floats 0–1 |

**Why OFF and not STL.** STL has no colour, and the page colours parts by material and role. STL also repeats every vertex in every triangle, so it is three times larger. 3MF has colours, but it is zip with XML — needless work for the worker.

**Why not glTF.** OpenSCAD does not write it. What both engines can do (checked by exporting a coloured cube):

| Format | Desktop 2026.09 | WASM 2025.01 (page) |
|---|---|---|
| OFF | yes, with face colours | yes, with face colours |
| OBJ | yes (colour in a separate `.mtl`) | yes |
| 3MF | yes | no (no file is produced) |
| glTF / GLB | no | no (`Invalid suffix glb`) |

Converting OFF to glTF for the pages makes no sense: the mesh never crosses a network (worker → page within one tab, the server is localhost), JavaScript does the posing, and three.js would turn glTF into the same `BufferGeometry` with groups anyway. glTF would only be needed for export elsewhere (Blender, `<model-viewer>`, AR).

## 5. How 12 bodies fit in one file

`part="view_all"` places the i-th body from the `view_parts` list in its own coordinate system, shifted by `i · view_spacing` (5000 mm) along Y. The model prints the list and the step in `echo(VIEW = …)` (keys `parts`, `spacing`). `web/viewer-wasm/src/offmesh.js` cuts the file apart:

1. A vertex's body number is `round(y / spacing)`; the shift is subtracted and the vertex returns to the body's own coordinates.
2. A face goes to the body of its first vertex, and there into the group of its colour; indices are renumbered within the body.
3. The result per body: `{ pos: Float32Array [x,y,z,…], groups: [{ color: [r,g,b], idx: Uint32Array }] }`. The buffers leave the worker without copying (transfer). In three.js a body is one `BufferGeometry` with an index group and a material per colour.

**Condition:** every body must be shorter than half the step (2500 mm) along Y, otherwise its vertices land in the neighbour. The machine's bodies are a few hundred millimetres wide.

The page with a server works differently: 12 OpenSCAD processes write one OFF per body, with no shift. `viewer.py` parses them the same way and returns JSON with the same `{pos, groups}` structure, only as plain arrays.
