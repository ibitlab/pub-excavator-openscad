#!/usr/bin/env python3
"""Складає BOM.md з опису набору (parts.tsv) і РЕАЛЬНИХ вимірів надрукованих STL.

Нічого не вписується руками: габарити, об'єм, площа контакту зі столом і полиці в
повітрі беруться з check_print.py, тож BOM не може розійтися з файлами.

Спільний для print3d/ і print3d-parts/: беруться ЧОТИРИ ОСТАННІ колонки TSV
(файл, к-сть, група, опис), тож зайві колонки спереду (як `own` у print3d-parts)
не заважають.

usage: make_bom.py parts.tsv check.json report.echo ["Заголовок"] [тека_версії] [ескізи]

`ескізи` = "так" лише для набору ОКРЕМИХ компонентів. У наборі зварних вузлів
(print3d/) їх вимкнено навмисно: там ключ `stick` означає весь зварний вузол, а
аркуш `05_stick.png` — саму лише трубу, і посилання вводило б в оману.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from author import md_footer                  # noqa: E402  авторство внизу BOM.md (AUTHORS у корені)

PLA = 1.24          # г/см³
VOL = "об'єм, см³"  # ключ із апострофом — окремою змінною, щоб не лізти в f-рядок


def sheets(ver_dir, base):
    """ключ деталі → відносне посилання на аркуш ескізу з розмірами в металі.

    Аркуші робить bom_drawings.sh і називає `NN_<ключ>.png`, тож зіставлення
    виходить за самою назвою — окремого списку тримати не треба. Спільне з
    make_assembly.py, тому лежить тут (цей файл і так спільний на два набори).
    """
    out = {}
    d = os.path.join(ver_dir, "drawings", "png") if ver_dir else ""
    if not d or not os.path.isdir(d):
        return out
    rel = os.path.relpath(d, base)
    for f in sorted(os.listdir(d)):
        m = re.match(r"\d+_(.+)\.png$", f)
        if m:
            out[m.group(1)] = f"{rel}/{f}"
    return out


def sheet(smap, key):
    """`tube_stick` у наборі — це аркуш `stick`: труби названі без префікса.
    `bk_side_L` / `bk_side_R` — аркуш `bk_side`: у металі це одна деталь ×2, розділені
    вони лише в наборі (логотип на зовнішній грані кожної)."""
    return (smap.get(key) or smap.get(key.replace("tube_", ""))
            or smap.get(re.sub(r"_[LR]$", "", key)) or "")


def main():
    tsv, js, echo = sys.argv[1], sys.argv[2], sys.argv[3]
    ver_dir = sys.argv[5] if len(sys.argv) > 5 else ""
    want_sheets = len(sys.argv) > 6 and sys.argv[6] == "так"
    checks = {c["файл"]: c for c in json.load(open(js, encoding="utf-8"))}
    smap = sheets(ver_dir, os.path.dirname(os.path.abspath(tsv))) if want_sheets else {}

    rows = []
    for line in open(tsv, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        key = line.split("\t")[0]
        file, qty, group, desc = line.split("\t")[-4:]
        name = f"{file}_x{qty}.stl"
        rows.append((group, name, int(qty), desc, checks.get(name, {}), sheet(smap, key)))

    scale = "?"
    for l in open(echo, encoding="utf-8"):
        m = re.search(r"=== друк[^\"]*?1:(\d+), сопло ([\d.]+)", l)
        if m:
            scale, nozzle = m.group(1), m.group(2)

    total_v = sum(r[4].get(VOL, 0) * r[2] for r in rows)
    total_n = sum(r[2] for r in rows)

    title = sys.argv[4] if len(sys.argv) > 4 else "Специфікація друкованого набору"
    print(f"# {title} 1:{scale}")
    print()
    print("> Згенеровано `make.sh` з **виміряних** STL — руками тут нічого не вписано.")
    # Набори підключають ЖИВУ модель (`include <../scad/excavator_boom.scad>`), а не
    # знімок із versions/. Номер версії тут — лише підпис «на яку геометрію це схоже»,
    # і його передає make.sh (тека з найбільшим номером), щоб він не застигав.
    ver = os.path.basename(ver_dir) if ver_dir else "не вказано"
    print(f"> Модель-джерело: `scad/excavator_boom.scad`, версія геометрії `{ver}`.")
    print(">")
    # найменша деталь набору — за найбільшим габаритом, а не за товщиною
    small = min((max(r[4]["габарит"]) for r in rows if r[4].get("габарит")), default=0)
    print("> **УВАГА:** це масштабна модель, згенерована штучним інтелектом. Вона не є ні")
    print("> проєктною документацією, ні іграшкою, ні тренажером: метал не різаний, машину")
    print(f"> не збудовано й не випробувано. У наборі є деталі від {small:.0f} мм — не для дітей.")
    print("> Див. `SAFETY.md`.")
    print()
    print(f"**Усього:** {total_n} друкованих деталей, {len(rows)} різних файлів, "
          f"{total_v:.1f} см³ суцільного об'єму (≈ {total_v * PLA:.0f} г PLA при 100 % заповненні; "
          f"при звичайних 20 % і 2 периметрах — приблизно вдвічі менше).")
    print()

    last = None
    for group, name, qty, desc, c, sh_link in rows:
        if group != last:
            print(f"\n## {group}\n")
            col = " Ескіз |" if smap else ""
            sep = "---|" if smap else ""
            print(f"| Файл | К-сть | Габарит XYZ, мм | Об'єм, см³ | Низ, мм² | Полиці |{col} Опис |")
            print(f"|---|---:|---|---:|---:|---|{sep}---|")
            last = group
        d = c.get("габарит", [0, 0, 0])
        shelf = c.get("полиці, %", 0)
        lv = c.get("рівні полиць", [])
        levels = ", ".join(f"{z:g} мм" for z, _ in lv[:2])
        sh = "—" if shelf == 0 else f"{shelf}% ({levels})"
        vol = c.get(VOL, 0)
        bed = c.get("контакт зі столом, мм²", 0)
        link = (f" [аркуш]({sh_link}) |" if sh_link else " — |") if smap else ""
        print(f"| `{name}` | {qty} | {d[0]:.1f} × {d[1]:.1f} × {d[2]:.1f} | {vol:.2f} "
              f"| {bed:.0f} | {sh} |{link} {desc} |")

    print()
    print("## Позначення")
    print()
    if smap:
        print("- **Ескіз** — аркуш із контуром і розмірами деталі В МЕТАЛІ (з теки версії).")
        print("  Є тільки для пластин, труб і обичайки: смуги, круглі деталі й пальці окремих")
        print("  аркушів не мають — їхні розміри повністю описані рядком специфікації.")
    print("- **Низ** — площа, якою деталь лежить на столі. Менше ~20 мм² — обов'язковий brim.")
    print("- **Полиці** — частка площі, що друкується в повітрі майже горизонтально, і висота")
    print("  найбільших над столом. Дужки з висотою 0.5–1.5 мм означають підсічки під")
    print("  пластинами: підпора зі столу їх бере. Полиці всередині труб — це містки, не звиси")
    print("  (див. README), підпору туди пускати НЕ можна.")
    print("- Габарити — уже в друкованих міліметрах, деталі повернуті в позу друку.")


if __name__ == "__main__":
    main()
    print(md_footer())
