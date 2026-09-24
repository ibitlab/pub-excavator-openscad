#!/usr/bin/env python3
"""Перевірка друкованості бінарного STL, надрукованого вздовж +Z.

Скіловий check_overhang.py розрахований на осесиметричні деталі (ріже площиною
y=0), а тут деталі плоскі й несиметричні. Тому перевіряється інше:

  габарит      — чи влазить у стіл (за замовчуванням 250×250×250)
  оболонки     — скільки замкнених тіл; вузли цієї моделі складені з пластин, які
                 ПРИЛЯГАЮТЬ, не перетинаючись, тож кілька тіл — норма, їх зливає
                 слайсер. Нуль тіл = порожній STL, який пройшов би будь-яку іншу перевірку.
  краї         — ребро, використане не двома трикутниками: дірка або защемлений злам
  нависання    — площа граней, що дивляться вниз під кутом, який FDM не тримає
  дно          — площа контакту зі столом: мало контакту = деталь відірве

usage: check_print.py файл.stl [--bed 250] [--angle 45] [--json]
"""
import json
import math
import struct
import sys
from collections import defaultdict

TOL = 1e-4          # сітка зварювання вершин, мм — як у слайсері
BED = 250.0
MAX_OVERHANG = 45.0  # ° від вертикалі; більше — потрібні підпори
BOTTOM = 0.25        # мм від найнижчої точки — шар, що лічиться як контакт зі столом


def load(path):
    data = open(path, "rb").read()
    if len(data) < 84:
        return []
    n = struct.unpack("<I", data[80:84])[0]
    if len(data) < 84 + n * 50:
        raise SystemExit(f"{path}: файл обрізаний ({len(data)} байт на {n} трикутників)")
    out = []
    for i in range(n):
        v = struct.unpack("<12f", data[84 + i * 50: 84 + i * 50 + 48])
        out.append((v[0:3], v[3:6], v[6:9], v[9:12]))
    return out


def tri_area(a, b, c):
    ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cx, cy, cz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def analyse(path, bed=BED, max_ang=MAX_OVERHANG):
    tris = load(path)
    r = {"файл": path.split("/")[-1], "трикутників": len(tris)}
    if not tris:
        r["помилки"] = ["STL порожній — деталь не відрендерилась"]
        return r

    lo = [min(t[k][i] for t in tris for k in (1, 2, 3)) for i in range(3)]
    hi = [max(t[k][i] for t in tris for k in (1, 2, 3)) for i in range(3)]
    dim = [round(hi[i] - lo[i], 2) for i in range(3)]
    r["габарит"] = dim
    errs, warns = [], []
    if max(dim[0], dim[1]) > bed or dim[2] > bed:
        errs.append(f"не влазить у стіл {bed:.0f}: {dim}")

    # оболонки й краї
    key = lambda p: (round(p[0] / TOL), round(p[1] / TOL), round(p[2] / TOL))
    edges = defaultdict(int)
    adj = defaultdict(set)
    for _, a, b, c in tris:
        ka, kb, kc = key(a), key(b), key(c)
        for u, v in ((ka, kb), (kb, kc), (kc, ka)):
            edges[tuple(sorted((u, v)))] += 1
            adj[u].add(v)
            adj[v].add(u)
    open_e = sum(1 for v in edges.values() if v == 1)
    over_e = sum(1 for v in edges.values() if v > 2)
    seen, shells = set(), 0
    for v in adj:
        if v in seen:
            continue
        shells += 1
        stack = [v]
        seen.add(v)
        while stack:
            for w in adj[stack.pop()]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
    r["тіл"] = shells
    r["відкритих ребер"] = open_e
    r["ребер >2 гранях"] = over_e
    if open_e:
        errs.append(f"{open_e} відкритих ребер — поверхня не замкнена")
    if over_e:
        warns.append(f"{over_e} ребер у понад двох гранях — защемлені злами на дотичних площинах")

    # Нависання і контакт зі столом.
    #
    # Самої лише нормалі не досить: у горизонтального циліндра ВЕСЬ низ дивиться вниз,
    # але друкується без підпор — кожен шар ширший за попередній, звис нікуди не падає.
    # Тому граней, що дивляться вниз, тут дві категорії:
    #   полиця  — площина ближча до горизонталі, ніж SHELF°: під нею порожнеча, шар лягає в повітря;
    #   схил    — від SHELF° до max_ang: опуклі дуги й скоси, друкуються з провисанням, без підпор.
    # Підпори вимагають полиці; схили лише псують поверхню знизу.
    SHELF = 20.0
    cos_lim = math.cos(math.radians(max_ang))
    cos_shelf = math.cos(math.radians(SHELF))
    a_shelf = a_slope = a_bottom = a_total = 0.0
    shelf_z = defaultdict(float)
    for nrm, a, b, c in tris:
        ar = tri_area(a, b, c)
        if ar <= 0:
            continue
        a_total += ar
        ln = math.sqrt(nrm[0] ** 2 + nrm[1] ** 2 + nrm[2] ** 2)
        nz = nrm[2] / ln if ln else 0.0
        if nz >= -1e-6:
            continue                                        # не дивиться вниз
        zmax = max(a[2], b[2], c[2])
        if zmax - lo[2] <= BOTTOM:                          # лежить на столі
            a_bottom += ar
            continue
        if -nz > cos_shelf:
            a_shelf += ar
            shelf_z[round((min(a[2], b[2], c[2]) - lo[2]) * 2) / 2] += ar   # рівні з кроком 0.5 мм
        elif -nz > cos_lim:
            a_slope += ar
    # Об'єм суцільного тіла (сума знакових тетраедрів). Це ВЕРХНЯ межа витрати пластику:
    # реальна залежить від заповнення. За модулем — бо оболонки, що прилягають, можуть
    # мати різний напрям обходу, а сумарний знак тут значення не має.
    vol = 0.0
    for _, a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    r["об'єм, см³"] = round(abs(vol) / 1000.0, 2)
    r["площа, мм²"] = round(a_total, 1)
    r["контакт зі столом, мм²"] = round(a_bottom, 1)
    r["полиці в повітрі, мм²"] = round(a_shelf, 1)
    r["схили, мм²"] = round(a_slope, 1)
    r["полиці, %"] = round(100 * a_shelf / a_total, 1) if a_total else 0.0
    if a_bottom < 15:
        warns.append(f"контакт зі столом {a_bottom:.1f} мм² — тримати не буде, потрібен brim")
    # На якій висоті над столом висять полиці: 1–2 мм прибираються підпорою легко,
    # високі означають, що орієнтацію варто міняти або різати деталь площиною симетрії.
    # рівні з площею < 1 мм² — вироджені трикутники на стиках граней (наприклад, по краю
    # виїмки бренду), не полиці: у перелік не потрапляють
    top = sorted(((z, ar) for z, ar in shelf_z.items() if ar >= 1), key=lambda kv: -kv[1])[:3]
    r["рівні полиць"] = [[z, round(ar, 1)] for z, ar in top]
    if a_shelf > 0.02 * a_total:
        lv = ", ".join(f"{z:.1f} мм: {ar:.0f} мм²" for z, ar in top)
        warns.append(f"полиць у повітрі {a_shelf:.0f} мм² ({r['полиці, %']}%) — підпори; найбільші на висоті {lv}")
    elif a_shelf > 0:
        warns.append(f"полиць у повітрі {a_shelf:.0f} мм² ({r['полиці, %']}%) — дрібні, підпори за бажанням")

    r["помилки"] = errs
    r["зауваження"] = warns
    return r


def main():
    args = [a for a in sys.argv[1:]]
    bed = BED
    ang = MAX_OVERHANG
    as_json = "--json" in args
    for i, a in enumerate(args):
        if a == "--bed":
            bed = float(args[i + 1])
        if a == "--angle":
            ang = float(args[i + 1])
    files = [a for a in args if a.endswith(".stl")]
    res = [analyse(f, bed, ang) for f in files]
    if as_json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        for r in res:
            d = r.get("габарит", [0, 0, 0])
            print(f"{r['файл']:34s} {d[0]:7.1f}×{d[1]:6.1f}×{d[2]:6.1f}  тіл {r.get('тіл', 0):3d}  "
                  f"низ {r.get('контакт зі столом, мм²', 0):7.1f}  полиці {r.get('полиці, %', 0):5.1f}%  "
                  f"схили {r.get('схили, мм²', 0):7.1f}")
            for e in r.get("помилки", []):
                print(f"    ПОМИЛКА: {e}")
            for w in r.get("зауваження", []):
                print(f"    увага:   {w}")
    bad = sum(len(r.get("помилки", [])) for r in res)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
