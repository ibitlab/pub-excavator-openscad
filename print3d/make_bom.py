#!/usr/bin/env python3
"""Складає print3d/BOM.md з опису набору (parts.tsv) і РЕАЛЬНИХ вимірів надрукованих STL.

Нічого не вписується руками: габарити, об'єм, площа контакту зі столом і полиці в
повітрі беруться з check_print.py, тож BOM не може розійтися з файлами.

usage: make_bom.py parts.tsv check.json report.echo
"""
import json
import re
import sys

PLA = 1.24          # г/см³
VOL = "об'єм, см³"  # ключ із апострофом — окремою змінною, щоб не лізти в f-рядок


def main():
    tsv, js, echo = sys.argv[1], sys.argv[2], sys.argv[3]
    checks = {c["файл"]: c for c in json.load(open(js, encoding="utf-8"))}

    rows = []
    for line in open(tsv, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        pp, file, qty, group, desc = line.split("\t")
        name = f"{file}_x{qty}.stl"
        rows.append((group, name, int(qty), desc, checks.get(name, {})))

    scale = "?"
    for l in open(echo, encoding="utf-8"):
        m = re.search(r"=== друк 1:(\d+), сопло ([\d.]+)", l)
        if m:
            scale, nozzle = m.group(1), m.group(2)

    total_v = sum(r[4].get(VOL, 0) * r[2] for r in rows)
    total_n = sum(r[2] for r in rows)

    print(f"# Специфікація друкованого набору 1:{scale}")
    print()
    print("> Згенеровано `print3d/make.sh` з **виміряних** STL — руками тут нічого не вписано.")
    print("> Модель-джерело: `scad/excavator_boom.scad`, версія геометрії `V001-2026-09-20-0505`.")
    print(">")
    print("> **УВАГА:** це масштабна модель для показу й перевірки кінематики, згенерована штучним")
    print("> інтелектом. Вона не є ні проєктною документацією, ні іграшкою, ні тренажером.")
    print("> Дрібні деталі (пальці Ø3–4 мм) — не для дітей. Див. `SAFETY.md`.")
    print()
    print(f"**Усього:** {total_n} друкованих деталей, {len(rows)} різних файлів, "
          f"{total_v:.1f} см³ суцільного об'єму (≈ {total_v * PLA:.0f} г PLA при 100 % заповненні; "
          f"при звичайних 20 % і 2 периметрах — приблизно вдвічі менше).")
    print()

    last = None
    for group, name, qty, desc, c in rows:
        if group != last:
            print(f"\n## {group}\n")
            print("| Файл | К-сть | Габарит XYZ, мм | Об'єм, см³ | Низ, мм² | Полиці | Опис |")
            print("|---|---:|---|---:|---:|---|---|")
            last = group
        d = c.get("габарит", [0, 0, 0])
        shelf = c.get("полиці, %", 0)
        lv = c.get("рівні полиць", [])
        levels = ", ".join(f"{z:g} мм" for z, _ in lv[:2])
        sh = "—" if shelf == 0 else f"{shelf}% ({levels})"
        vol = c.get(VOL, 0)
        bed = c.get("контакт зі столом, мм²", 0)
        print(f"| `{name}` | {qty} | {d[0]:.1f} × {d[1]:.1f} × {d[2]:.1f} | {vol:.2f} "
              f"| {bed:.0f} | {sh} | {desc} |")

    print()
    print("## Позначення")
    print()
    print("- **Низ** — площа, якою деталь лежить на столі. Менше ~20 мм² — обов'язковий brim.")
    print("- **Полиці** — частка площі, що друкується в повітрі майже горизонтально, і висота")
    print("  найбільших над столом. Дужки з висотою 0.5–1.5 мм означають підсічки під")
    print("  пластинами: підпора зі столу їх бере. Полиці всередині труб — це містки, не звиси")
    print("  (див. README), підпору туди пускати НЕ можна.")
    print("- Габарити — уже в друкованих міліметрах, деталі повернуті в позу друку.")


if __name__ == "__main__":
    main()
