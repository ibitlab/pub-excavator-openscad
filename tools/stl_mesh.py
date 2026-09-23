#!/usr/bin/env python3
"""Бінарний STL → numpy; найбільша плоска грань; силует деталі на столі (shapely).

Спільна бібліотека для генераторів, що працюють з ВИМІРЯНИМИ STL (аркуші розкладки,
підписані рендери, будь-що нове). Потрібен `tools/.venv` (numpy, shapely).
Чисті від numpy читачі — `print3d-parts/check_print.py` і `tools/stl_volume.py` — лишаються
окремо навмисно: їх запускає системний python з `make.sh` і `check_overlaps.sh`.

    from stl_mesh import read_stl, largest_face, rot_to_down, silhouette, as_circle
    tri = read_stl('деталь.stl')            # (n, 3, 3), мм
    n = largest_face(tri)                    # нормаль грані з найбільшою сумарною площею
    tri = tri @ rot_to_down(n).T             # покласти її на стіл
    poly = silhouette(tri)                   # shapely Polygon: контур + отвори (interiors)
"""
import struct

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

_REC = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])


def read_stl(path):
    """Трикутники бінарного STL як масив (n, 3, 3). OpenSCAD без `--export-format binstl`
    пише текстовий STL — на ньому кажемо зрозуміло, а не читаємо сміття."""
    d = open(path, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    if len(d) != 84 + n * 50:
        if d[:5] == b'solid':
            raise ValueError(f'{path}: текстовий STL — експортуй з --export-format binstl')
        raise ValueError(f'{path}: обрізаний або не STL ({len(d)} байт, заявлено {n} трикутників)')
    return np.frombuffer(d[84:84 + n * 50], dtype=_REC)['v'].astype(float)


def largest_face(tri):
    """Одинична нормаль плоскої грані з найбільшою сумарною площею трикутників
    (нормалі квантуються до 1/50, щоб грань із багатьох трикутників рахувалась одною)."""
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    n = np.cross(e1, e2)
    a = np.linalg.norm(n, axis=1) / 2
    ok = a > 1e-9
    n = n[ok] / (2 * a[ok])[:, None]
    q = np.round(n * 50).astype(int)
    acc = {}
    for k, ar in zip(map(tuple, q), a[ok]):
        acc[k] = acc.get(k, 0) + ar
    v = np.array(max(acc, key=acc.get), float)
    return v / np.linalg.norm(v)


def rot_to_down(n):
    """Матриця повороту, що переводить одиничний вектор n у (0, 0, −1) (Родрігес)."""
    t = np.array([0, 0, -1.0])
    v = np.cross(n, t); s = np.linalg.norm(v); c = float(np.dot(n, t))
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1, -1, -1.0])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)


def silhouette(tri, weld=0.02):
    """Тінь деталі на площині XY: об'єднання проєкцій усіх граней з помітною складовою
    нормалі по Z (вертикальні грані проєктуються у відрізки і нічого не додають).
    Мілісекунди на деталь; отвори — `poly.interiors`. З кількох тіл лишається найбільше."""
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    nz = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    u = unary_union([Polygon(t[:, :2]) for t in tri[np.abs(nz) > 1e-6]])
    u = u.buffer(weld).buffer(-weld)
    if u.geom_type == 'MultiPolygon':
        u = max(u.geoms, key=lambda g: g.area)
    return u


def as_circle(coords, tol=0.02):
    """(cx, cy, діаметр), якщо замкнений контур — коло (радіуси вершин рівні в межах tol·r + 0.05),
    інакше None. Діаметр — за середнім радіусом: вершини OpenSCAD лежать НА колі."""
    pts = np.array(coords[:-1])
    if len(pts) < 12:
        return None
    c = pts.mean(0); r = np.linalg.norm(pts - c, axis=1)
    if r.max() - r.min() > tol * r.mean() + 0.05:
        return None
    return (float(c[0]), float(c[1]), float(2 * r.mean()))
