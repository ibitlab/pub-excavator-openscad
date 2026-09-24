#!/usr/bin/env python3
"""Зливає полігони логотипа (scad/brand/*.scad) в ОДИН polygon() на модуль.

Генератор знака віддає сотні окремих polygon(): справжні контури і 600–800 скалок
нульової площі (трикутники по 0.001 мм). OpenSCAD щоразу об'єднує їх заново — у
3D-сторінці (OpenSCAD-WASM) це втричі подовжувало кожну перебудову моделі.

Об'єднання рахує САМ OpenSCAD (експорт модуля у SVG): його правило заповнення в
перекритих контурах не even-odd, і вгадане правило дало б знак із меншою площею. Тут
лише переписується результат: один polygon(points, paths) — контури, що не
перетинаються.

Кожен контур ще й спрощується з допуском SIMPLIFY (друковані мм): генератор ставить
вершину кожні ~0.05 мм, і навіть злитий знак (≈ 3000 вершин) коштував сторінці +3.5 с на
кожну перебудову. 0.01 мм — у 40 разів менше за сопло, на друці різниці немає (виїмки
збігаються з попередніми на IoU ≥ 0.99), а вершин утричі менше.

    tools/.venv/bin/python tools/brand_merge.py scad/brand/*.scad      # переписує файли на місці

Запускати після кожного нового експорту полігонів із генератора. Повторний запуск нічого
не змінює. Рядки поза polygon() (коментар, *_bounds, module …) лишаються як були.
"""
import os
import re
import subprocess
import sys
import tempfile

from shapely.geometry import Polygon

POLY = re.compile(r'^\s*polygon\(points=.*\);\s*$')
SIMPLIFY = 0.01


def openscad_rings(path, module):
    """Контури модуля так, як їх об'єднав OpenSCAD: список кілець [(x, y), …]."""
    with tempfile.TemporaryDirectory() as d:
        src, svg = os.path.join(d, 'm.scad'), os.path.join(d, 'm.svg')
        with open(src, 'w', encoding='utf-8') as f:
            f.write(f'include <{os.path.abspath(path)}>\n{module}();\n')
        subprocess.run(['openscad', '-o', svg, src], check=True, capture_output=True)
        d_attr = re.search(r'd="([^"]*)"', open(svg, encoding='utf-8').read()).group(1)
    rings = []
    for chunk in re.findall(r'M([^z]*)z', d_attr):
        pts = [tuple(map(float, p.split(','))) for p in re.findall(r'-?[\d.]+,-?[\d.]+', chunk)]
        ring = Polygon([(x, -y) for x, y in pts])         # у SVG вісь y донизу
        simple = list(ring.exterior.simplify(SIMPLIFY, preserve_topology=True).coords)[:-1]
        rings.append(simple if len(simple) >= 3 else list(ring.exterior.coords)[:-1])
    return rings


def emit(rings):
    pts, paths = [], []
    for r in rings:
        paths.append(list(range(len(pts), len(pts) + len(r))))
        pts.extend(r)
    p = ','.join(f'[{x:.3f},{y:.3f}]' for x, y in pts)
    q = ','.join('[' + ','.join(map(str, r)) + ']' for r in paths)
    return f'  polygon(points=[{p}], paths=[{q}]);\n'


def even_odd_area(rings):
    g = Polygon()
    for r in rings:
        g = g.symmetric_difference(Polygon(r).buffer(0))
    return g.area


for path in sys.argv[1:]:
    lines = open(path, encoding='utf-8').readlines()
    polys = [i for i, l in enumerate(lines) if POLY.match(l)]
    if len(polys) <= 1:
        print(f'  {path}: уже один polygon()')
        continue
    module = re.search(r'^module (\w+)\(\)', ''.join(lines), re.M).group(1)
    rings = openscad_rings(path, module)
    head, tail = lines[:polys[0]], lines[polys[-1] + 1:]
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(head)
        f.write(emit(rings))
        f.writelines(tail)
    print(f'  {path}: {len(polys)} polygon() → 1 ({len(rings)} контурів, {sum(map(len, rings))} вершин), '
          f'площа {even_odd_area(rings):.3f} мм²')
