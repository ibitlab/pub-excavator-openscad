#!/usr/bin/env python3
"""Два збирання (машини чи набору) — що змінилось ПО СУТІ, а що лише в підписах.

    python3 tools/compare_build.py СТАРЕ НОВЕ [--settle] [--ignore=тека,тека]

Суть:
  * STL — за НАБОРОМ трикутників (вершини до 1e-4 мм): OpenSCAD між запусками міняє порядок
    трикутників, і файл «змінюється», хоча деталь та сама;
  * текст (.md .txt .csv .tsv .json) — порядково, без номерів версій, дат, застережень і підписів;
    у `VERSION.md` звіряється лише блок «Діапазони» (решта — дата, git, розміри файлів).
Картинки, PDF, DXF, viewer.html — оформлення або похідне від тих самих STL: не звіряються.

--settle: STL з тими самими трикутниками копіюється зі старого збирання в нове — git не
побачить «зміненого» файлу там, де змінився лише порядок трикутників.

--ignore: верхні теки, яких не звіряти (машина в `latest/` несе в собі набір — `print3d*`).

Код виходу: 0 — по суті те саме; 1 — є зміни (перелік у виводі); 2 — старого збирання немає.
Лише системний python (як check_print.py): його кличуть build_version.sh і make.sh набору.
"""
import os
import re
import shutil
import struct
import sys

TEXT = ('.md', '.txt', '.csv', '.tsv', '.json')
# «V006», «V006.2», «V006-2026-10-02-1430», дати й час — це підписи, не суть
NOISE = [(re.compile(r'V\d{3}(?:\.\d+)?(?:-\d{4}-\d{2}-\d{2}-\d{4})?'), 'V'),
         (re.compile(r'\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?'), 'D')]
# лічильник кешу рендерів аркушів; застереження («> …»), підпис автора, роздільники й порожні рядки
SKIP_LINE = re.compile(r'renders_made|^\s*(?:>|<sub>|---\s*$|$)')
SKIP_FILE = {'docs/viewer-wasm-test.txt'}        # журнал тесту сторінки, не машина


def tris(path):
    """Набір трикутників двійкового STL і його об'єм, см³."""
    b = open(path, 'rb').read()
    n = struct.unpack_from('<I', b, 80)[0] if len(b) >= 84 else 0
    out, vol = set(), 0.0
    for i in range(n):
        v = struct.unpack_from('<9f', b, 84 + 50 * i + 12)
        out.add(tuple(round(x, 4) for x in v))
        ax, ay, az, bx, by, bz, cx, cy, cz = v
        vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6
    return out, abs(vol) / 1000


def norm(path):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    if os.path.basename(path) == 'VERSION.md':                       # лише діапазони кутів моделі
        txt = '\n'.join(lines)
        m = re.search(r'^## Діапазони.*?(?=^## )', txt, re.S | re.M)
        lines = m.group(0).split('\n') if m else []
    out = []
    for l in lines:
        if SKIP_LINE.search(l):
            continue
        for rx, rep in NOISE:
            l = rx.sub(rep, l)
        out.append(l.rstrip())
    return out


def files(root, ignore=()):
    out = {}
    for d, dirs, fs in os.walk(root):
        if d == root:
            dirs[:] = [x for x in dirs if x not in ignore]
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = p
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    settle = '--settle' in sys.argv
    ignore = [x for a in sys.argv if a.startswith('--ignore=') for x in a.split('=', 1)[1].split(',') if x]
    if len(args) != 2:
        sys.exit(__doc__)
    old_root, new_root = args
    if not os.path.isdir(old_root):
        print(f'  порівнювати нема з чим: {old_root} немає')
        sys.exit(2)
    old, new = files(old_root, ignore), files(new_root, ignore)
    changes, settled = [], 0
    for rel in sorted(set(old) | set(new)):
        ext = os.path.splitext(rel)[1].lower()
        if (ext != '.stl' and ext not in TEXT) or rel in SKIP_FILE:
            continue
        if rel not in new:
            changes.append(f'прибрано: {rel}'); continue
        if rel not in old:
            changes.append(f'додано: {rel}'); continue
        if ext == '.stl':
            (a, va), (b, vb) = tris(old[rel]), tris(new[rel])
            if a == b:
                if settle and open(old[rel], 'rb').read() != open(new[rel], 'rb').read():
                    shutil.copyfile(old[rel], new[rel]); settled += 1
            else:
                changes.append(f'геометрія: {rel}  об\'єм {va:.3f} → {vb:.3f} см³')
        else:
            a, b = norm(old[rel]), norm(new[rel])
            if a != b:
                diff = [(x, y) for x, y in zip(a, b) if x != y][:2]
                if len(a) != len(b):
                    diff.append((f'{len(a)} рядків', f'{len(b)} рядків'))
                changes.append(f'текст: {rel}' + ''.join(f'\n      - {x.strip()[:110]}\n      + {y.strip()[:110]}' for x, y in diff))
    if settled:
        print(f'  STL, де змінився лише порядок трикутників, повернуто як були: {settled}')
    if not changes:
        print(f'  по суті без змін відносно {old_root}')
        sys.exit(0)
    print(f'  змінено відносно {old_root}: {len(changes)}')
    for c in changes:
        print('    ' + c)
    sys.exit(1)


if __name__ == '__main__':
    main()
