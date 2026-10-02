# V006.2-2026-10-02-2125

> Друкований набір 1:5 машини `V006-2026-09-29-1841`. Згенеровано `print3d-parts/make.sh` — руками не правити.
> Масштабна модель, не іграшка і не проєктна документація; див. `SAFETY.md`.

- Дата: 2026-10-02 21:28
- Git (база на момент збирання): 609e6bf (Print kit: per-part visibility checkboxes in the M5 cylinder model) + незакомічені зміни робочого дерева
- Зміни: M5-циліндри: датчики (SS41F, SS49E) винесено в sensors.py, перероблено m5_cyl.scad, оновлено CALC і README

- `stl/<тека>/` — одна тека = одне завдання слайсера (колір · висота шару · підпори), пояснення — у `print3d-parts/README.md`
- `BOM.md` — специфікація з виміряних STL; `DRIVE.md` — привід циліндрів гвинтом M5
- `m5_cylinders/` — циліндри на шпильці M5 з моторедуктором N20: `stl/`, `img/`, `CALC.md`, `WIRING.svg`, `SENSORS.svg` (як влаштовано — `print3d-parts/m5_cylinders/README.md`)
- `sheets/SHEETS.pdf` — аркуші розкладки 1:1 для сортування й склеювання; `sheets/sheets.json` — усі числа (прев'ю сторінок — у `build/sheets-png/`, не в git)

---
<sub>Ihor Ivaniuk · @IBITLAB</sub>
