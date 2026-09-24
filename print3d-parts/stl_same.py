#!/usr/bin/env python3
"""Повертає до закоміченого стану STL, у яких геометрія та сама, а змінився лише порядок
трикутників. OpenSCAD від запуску до запуску може віддати ті самі трикутники в іншому
порядку: файл «змінений», хоча деталь та сама, і такий шум лізе в кожен коміт. Звіряється
НАБІР трикутників (вершини, округлені до 1e-4 мм) з версією в індексі git.

    python3 print3d-parts/stl_same.py            # останній крок make.sh

Лише системний python (як check_print.py і make_bom.py). Поза git-репозиторієм нічого не робить.
"""
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tris(b):
    """Набір трикутників двійкового STL: вершини кожного, округлені до 1e-4."""
    n = struct.unpack_from('<I', b, 80)[0]
    out = set()
    for i in range(n):
        v = struct.unpack_from('<9f', b, 84 + 50 * i + 12)
        out.add(tuple(round(x, 4) for x in v))
    return out, n


def git(*a):
    return subprocess.run(['git', *a], cwd=ROOT, capture_output=True)


if git('rev-parse', '--git-dir').returncode:
    sys.exit(0)
changed = [f for f in git('diff', '--name-only', '-z', '--diff-filter=M', '--', 'print3d-parts/stl').stdout.decode().split('\0')
           if f.endswith('.stl')]
same, real = [], []
for f in changed:
    old = git('show', ':' + f).stdout
    new = open(os.path.join(ROOT, f), 'rb').read()
    (a, na), (b, nb) = tris(old), tris(new)
    (same if na == nb and a == b else real).append(f)
if same:
    git('checkout', '--', *same)
print(f'  STL: змінено геометрію {len(real)}, повернуто без змін (лише порядок трикутників) {len(same)}')
for f in real:
    print('    змінено:', os.path.basename(f))
