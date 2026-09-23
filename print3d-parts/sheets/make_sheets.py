#!/usr/bin/env python3
"""make_sheets.py — аркуші розкладки 1:1 для сортування й склеювання набору print3d-parts.

Задача: купа надрукованих деталей, у якій втулки, пальці й шайби майже не відрізнити.
Розв'язок — папір. Для кожного вузла, що склеюється (стріла, рукоять, ківш, коромисло
і тяга, колона з циліндрами) і окремо для пальців та шайб (ними вузли з'єднуються)
друкується аркуш A4, на якому кожна деталь намальована у масштабі 1:1 контуром —
як вона лежить найбільшою плоскою гранню на столі. Деталь кладеться на свій контур:
збіглася — це вона. Однакові плоскі деталі — одним контуром, стосом; пальці — кожен
окремо, лежачи. У вільне місце аркуша стають рендери вузла з виносками до кожного
файлу, на наступних сторінках — порядок склеювання, крок за кроком, з рендером, де
попередні деталі сірі, а нова — помаранчева.

Звідки що береться (руками нічого не вписано):
  контури, габарити, отвори   — з ВИМІРЯНИХ STL набору (print3d-parts/stl/**), shapely
  склад аркушів і кроки       — print3d-parts/assembly.tsv (вузол, крок, куди, як)
  назви файлів, кількості     — print3d-parts/parts.tsv
  рендери                     — sheets.scad (кожна деталь своїм відтінком; виноски — за
                                 відтінком пікселів, ракурси — за тим, скільки деталей видно)

Виходи: SHEETS.pdf (A4, 1:1), sheets.json (усі числа: комірки, ракурси, виноски —
перевіряти можна читанням, не відкриваючи PDF), png/ — прев'ю сторінок розкладки,
відрендерені з самого PDF (poppler: pdftoppm + pdftotext; без нього — знімок HTML у Chrome).

    tools/.venv/bin/python print3d-parts/sheets/make_sheets.py            # усе
    … --only 1 --no-steps --png                                          # один аркуш, швидко
    … --fresh                                                            # перерендерити всі PNG

Масштаб 1:1 тримається на тому, що SVG сторінки має viewBox у міліметрах і ширину в
мм, а Chrome друкує CSS-міліметри без масштабування (preferCSSPageSize). На кожному
аркуші є лінійка 100 мм — перевірити принтер.
"""
import argparse
import base64
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from shapely.geometry import LineString
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
ROOT = os.path.dirname(KIT)
sys.path.insert(0, KIT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from make_assembly_pdf import to_pdf, CHROME_CANDIDATES                              # noqa: E402
from stl_mesh import read_stl, silhouette, as_circle                                 # noqa: E402
from hue_callouts import classify, anchors, finish_image, spread_rows                # noqa: E402

SCAD = os.path.join(HERE, 'sheets.scad')

# ------------------------------------------------------------------ сторінка, мм
PAGE_W, PAGE_H, MARGIN = 210, 297, 10
CW, CH = PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN      # 190 × 277
HEAD_H, FOOT_H = 9.0, 9.0
PAD = 1.6            # відступ контуру від рамки комірки
DIM_B, DIM_R = 4.6, 4.6   # місце під розмірну лінію знизу і праворуч
GAP = 1.2            # проміжок між комірками
LABEL_ROW = 4.0      # крок виносок на рендері
MAX_IMG_W = 125      # рендер на аркуші розкладки не ширший за це

# ------------------------------------------------------------------ склад аркушів
# Аркуш = вузли з assembly.tsv (усі деталі вузла — на ньому) + рендери, які його ілюструють.
SHEETS = [
    dict(slug='boom', title='Стріла', sub='вузол, що склеюється', nodes=['1. Стріла'], renders=['boom']),
    dict(slug='stick', title='Рукоять', sub='вузол, що склеюється', nodes=['2. Рукоять'], renders=['stick']),
    dict(slug='bucket', title='Ківш', sub='вузол, що склеюється', nodes=['3. Ківш'], renders=['bucket']),
    dict(slug='linkage', title='Коромисло і тяга', sub='два вузли, що склеюються', nodes=['4. Важільна система'],
         renders=['rocker', 'link']),
    dict(slug='post_cyl', title='Колона і гідроциліндри', sub='плити колони — стосом; штоки в гільзи НЕ клеїти',
         nodes=['5. Колона', '6. Гідроциліндри'], renders=['cyl', 'post']),
    dict(slug='pins', title='Пальці й шайби', sub='з’єднання вузлів — не клеїти; кожен палець лежить окремо',
         nodes=['7. Складання на пальцях'], renders=['pins']),
]
# Які деталі малює кожен рендер (для аркушів з кількома вузлами); решта — всі деталі аркуша.
RENDER_KEYS = {
    'rocker': ['rocker_plate', 'J_boss'], 'link': ['link_plate', 'link_boss'],
    'post': ['post_plate'],
    'cyl': ['cyl_boom_body', 'cyl_boom_rod', 'cyl_stick_body', 'cyl_stick_rod', 'cyl_bucket_body', 'cyl_bucket_rod'],
}
RENDER_TITLE = {'boom': 'стріла', 'stick': 'рукоять', 'bucket': 'ківш', 'rocker': 'коромисло', 'link': 'тяга',
                'post': 'колона', 'cyl': 'гідроциліндри', 'pins': 'уся машина'}
RENDER_EXTRA = {'pins': ['-D', 'show_ground=false', '-D', 'show_envelope=false']}
RENDER_NVIEWS = {'post': 1}          # плиті колони досить одного ракурсу
PIN_CLOSEUP = 700                    # відстань камери крупного плану шарніра, мм моделі (кадр ≈ 280 мм)
# Кандидати ракурсів (rotx, rotz гімбала OpenSCAD): rotx 55 — згори, 125 — знизу.
VIEWS = [(55, 25), (55, 115), (55, 205), (55, 295), (125, 25), (125, 115), (125, 205), (125, 295)]
VIEW_NAME = {55: 'згори', 125: 'знизу'}


# ------------------------------------------------------------------ дані набору
def read_tsv(path, ncol):
    rows = []
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        f = line.split('\t')
        if len(f) != ncol:
            sys.exit(f'{os.path.basename(path)}: очікував {ncol} колонок, а в рядку {len(f)}: {line[:60]}')
        rows.append(f)
    return rows


def read_parts():
    out = {}
    for pp, own, ori, pre, file, qty, group, desc in read_tsv(os.path.join(KIT, 'parts.tsv'), 8):
        out[pp] = dict(key=pp, own=own, file=file, qty=int(qty), group=group, desc=desc)
    return out


def read_assembly():
    return [dict(step=s, node=n, key=k, where=w, how=h)
            for s, n, k, w, h in read_tsv(os.path.join(KIT, 'assembly.tsv'), 5)]


def find_stl(file):
    """STL лежать у теках «одне завдання слайсера» (stl/group.sh); шукаємо рекурсивно."""
    for d, _, fs in os.walk(os.path.join(KIT, 'stl')):
        for f in fs:
            if f.startswith(file + '_x') and f.endswith('.stl'):
                return os.path.join(d, f)
    sys.exit(f'немає STL для {file} — спершу print3d-parts/make.sh')


def short_name(desc):
    """«Щока перелому стріли, лист 8 мм» → «Щока перелому стріли»."""
    s = re.split(r' — |, | \(', desc)[0].strip()
    return s if len(s) <= 34 else s[:33] + '…'


# ------------------------------------------------------------------ STL → силует (tools/stl_mesh.py)
def lay_down(tri, key):
    """Як деталь лежить на папері. Друкована орієнтація вже кладе найбільшу грань на стіл —
    крім пальців: друкуються стоячи, на папері лежать. Обичайка ковша лишається так, як
    друкується, — боком, на профілі: дном вона давала б на папері лише прямокутник, а
    профіль (полиця, дуги, дно) — це і є її форма."""
    if key.startswith('pin_'):
        R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0.0]])       # +Z → −Y: палець лягає вздовж Y
        tri = tri @ R.T
    tri = tri - tri.reshape(-1, 3).min(0)
    return tri


def width_at(poly, x):
    """Ширина силуету на вертикалі x (для діаметра стрижня пальця)."""
    b = poly.bounds
    cut = poly.intersection(LineString([(x, b[1] - 1), (x, b[3] + 1)]))
    return cut.length


def measure(key, path):
    tri = lay_down(read_stl(path), key)
    poly = silhouette(tri)
    poly = affinity.scale(poly, 1, -1, origin=(0, 0))      # погляд згори: у SVG вісь Y униз
    b = poly.bounds
    poly = affinity.translate(poly, -b[0], -b[1])
    b = poly.bounds
    m = dict(w=b[2], h=b[3], z=float(tri[:, :, 2].max()), poly=poly, holes=[], ring=None, pin=None)
    for ring in poly.interiors:
        c = as_circle(list(ring.coords))
        rb = ring.bounds
        m['holes'].append(dict(circle=c, w=rb[2] - rb[0], h=rb[3] - rb[1], cx=(rb[0] + rb[2]) / 2, cy=(rb[1] + rb[3]) / 2))
    oc = as_circle(list(poly.exterior.coords))
    if oc and len(m['holes']) == 1 and m['holes'][0]['circle']:
        m['ring'] = dict(od=oc[2], id=m['holes'][0]['circle'][2])
    if key.startswith('pin_'):
        L, W = max(b[2], b[3]), min(b[2], b[3])
        along_x = b[2] >= b[3]
        # голівка — на одному з кінців; стрижень міряємо на 1/4 довжини від протилежного
        w0 = width_at(poly, 0.05 * L) if along_x else width_at(affinity.rotate(poly, 90, origin=(0, 0)), -0.05 * L)
        p2 = poly if along_x else affinity.rotate(poly, 90, origin=(0, 0))
        b2 = p2.bounds
        xs = [b2[0] + 0.25 * L, b2[0] + 0.75 * L]
        shaft = min(width_at(p2, x) for x in xs)
        m['pin'] = dict(L=L, d=shaft, head=W)
    return m


# ------------------------------------------------------------------ комірки
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def text_w(s, size):
    """Ширина рядка, мм — оцінка для верстки (Helvetica ≈ 0.55 em на знак, цифри вужчі)."""
    return sum(0.32 if ch in ' .,:·' else 0.62 if ch.isupper() else 0.55 for ch in s) * size + 0.5


def fmt(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


class Cell:
    """Одна деталь (файл) на аркуші: контур + підписи. Дві орієнтації (0/90°), підписи
    завжди горизонтальні — обертається лише контур."""

    def __init__(self, part, step, m, note=''):
        self.part, self.step, self.m = part, step, m
        key = part['key']
        title = f"{step['step']}  {part['file']}"
        if part['qty'] > 1:
            title += f"  ×{part['qty']}" + ('' if key.startswith('pin_') else ' стосом')
        lines = [(title, 2.5, 'b'), (short_name(part['desc']), 2.0, 'i')]
        if m['ring']:
            dims = f"Ø{fmt(m['ring']['od'])} / отвір Ø{fmt(m['ring']['id'])} · h {fmt(m['z'])}"
        elif m['pin']:
            dims = f"Ø{fmt(m['pin']['d'])} × {fmt(m['pin']['L'])} · голівка Ø{fmt(m['pin']['head'])}"
        else:
            dims = f"{fmt(m['w'])} × {fmt(m['h'])} · h {fmt(m['z'])}"
            small = [h for h in m['holes'] if h['circle'] and h['circle'][2] < 8]
            if small:
                ds = sorted({round(h['circle'][2], 1) for h in small})
                dims += ' · отв. ' + ', '.join(f'Ø{fmt(d)}' for d in ds)
                if len(small) > 1:
                    dims += f' ×{len(small)}'
            odd = [h for h in m['holes'] if not h['circle']]
            if odd:
                dims += ' · виріз ' + ', '.join(f"{fmt(h['w'])}×{fmt(h['h'])}" for h in odd)
        lines.append((dims, 1.9, ''))
        if note:
            lines.append((note, 1.9, 'n'))
        self.lines = lines
        self.band = sum(s * 1.28 for _, s, _ in lines) + 1.0
        self.text_w = max(text_w(t, s) for t, s, _ in lines)
        self.has_dims = not (m['ring'] or m['pin']) and min(m['w'], m['h']) >= 4
        self.pin_dim = bool(m['pin'])

    def size(self, rot):
        ow, oh = (self.m['h'], self.m['w']) if rot else (self.m['w'], self.m['h'])
        dr = DIM_R if self.has_dims else 0
        db = DIM_B if (self.has_dims or self.pin_dim) else 0
        w = max(ow + 2 * PAD + dr, self.text_w + 2 * PAD)
        h = self.band + oh + 2 * PAD + db
        return w, h

    def svg(self, x, y, rot):
        m = self.m
        w, h = self.size(rot)
        poly = m['poly']
        if rot:
            poly = affinity.rotate(poly, -90, origin=(0, 0))
            b = poly.bounds
            poly = affinity.translate(poly, -b[0], -b[1])
        ow, oh = (m['h'], m['w']) if rot else (m['w'], m['h'])
        ox, oy = x + PAD, y + self.band + PAD
        out = [f'<rect class="cell" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="1.2"/>']
        ty = y + 1.0
        for t, s, st in self.lines:
            ty += s * 1.28
            cls = {'b': 'tt', 'i': 'tn', 'w': 'tw', 'n': 'tx'}.get(st, 'td')
            out.append(f'<text class="{cls}" x="{x + PAD:.2f}" y="{ty - s * 0.28:.2f}" font-size="{s}">{html.escape(t)}</text>')
        out.append(f'<path class="part" d="{svg_path(poly, ox, oy)}"/>')
        # діаметри великих отворів — усередині
        for hole in m['holes']:
            c = hole['circle']
            if c and c[2] >= 8:
                cx, cy = (c[0], c[1])
                if rot:                                   # той самий поворот на −90°, що й у контуру
                    cx, cy = c[1] - b[0], -c[0] - b[1]
                out.append(f'<text class="th" x="{ox + cx:.2f}" y="{oy + cy + 0.75:.2f}" font-size="2.1" text-anchor="middle">Ø{fmt(c[2])}</text>')
        if self.has_dims:
            out.append(dim_line(ox, oy + oh + 2.2, ox + ow, oy + oh + 2.2, fmt(ow), vertical=False))
            out.append(dim_line(ox + ow + 2.2, oy, ox + ow + 2.2, oy + oh, fmt(oh), vertical=True))
        elif self.pin_dim:
            L = m['pin']['L']
            if ow >= oh:
                out.append(dim_line(ox, oy + oh + 2.2, ox + ow, oy + oh + 2.2, fmt(ow), vertical=False))
            else:
                out.append(dim_line(ox + ow + 2.2, oy, ox + ow + 2.2, oy + oh, fmt(oh), vertical=True))
        return '\n'.join(out)


def svg_path(poly, dx, dy):
    def ring(coords):
        return 'M' + ' L'.join(f'{px + dx:.2f},{py + dy:.2f}' for px, py in coords) + ' Z'
    parts = [ring(poly.exterior.coords)] + [ring(r.coords) for r in poly.interiors]
    return ' '.join(parts)


def dim_line(x0, y0, x1, y1, txt, vertical):
    t = 0.9
    if vertical:
        s = (f'<line class="dim" x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}"/>'
             f'<line class="dim" x1="{x0 - t:.2f}" y1="{y0:.2f}" x2="{x0 + t:.2f}" y2="{y0:.2f}"/>'
             f'<line class="dim" x1="{x0 - t:.2f}" y1="{y1:.2f}" x2="{x0 + t:.2f}" y2="{y1:.2f}"/>'
             f'<text class="tm" font-size="2.0" text-anchor="middle" transform="translate({x0 + 2.4:.2f},{(y0 + y1) / 2:.2f}) rotate(-90)">{txt}</text>')
    else:
        s = (f'<line class="dim" x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}"/>'
             f'<line class="dim" x1="{x0:.2f}" y1="{y0 - t:.2f}" x2="{x0:.2f}" y2="{y0 + t:.2f}"/>'
             f'<line class="dim" x1="{x1:.2f}" y1="{y0 - t:.2f}" x2="{x1:.2f}" y2="{y0 + t:.2f}"/>'
             f'<text class="tm" font-size="2.0" text-anchor="middle" x="{(x0 + x1) / 2:.2f}" y="{y0 + 2.6:.2f}">{txt}</text>')
    return s


# ------------------------------------------------------------------ пакування (MaxRects, зверху-ліворуч)
class MaxRects:
    """Пакування прямокутників у сторінку. Евристика вибору місця — параметр: 'tl' зверху-
    ліворуч, 'bssf' найменший залишок по короткій стороні, 'baf' найменший залишок площі.
    Аркуш пакується всіма трьома, береться найкращий результат (див. pack_best)."""

    def __init__(self, w, h, heur='bssf'):
        self.free = [(0.0, 0.0, float(w), float(h))]
        self.placed = []
        self.heur = heur

    def insert(self, sizes, tag=None):
        """sizes: [(w, h, rot), …] — варіанти орієнтації."""
        best = None
        for fx, fy, fw, fh in self.free:
            for w, h, rot in sizes:
                if w <= fw + 1e-6 and h <= fh + 1e-6:
                    if self.heur == 'tl':
                        key = (round(fy, 3), round(fx, 3), rot)
                    elif self.heur == 'baf':
                        key = (round(fw * fh - w * h, 3), round(min(fw - w, fh - h), 3), round(fy, 3), round(fx, 3))
                    else:
                        key = (round(min(fw - w, fh - h), 3), round(max(fw - w, fh - h), 3), round(fy, 3), round(fx, 3))
                    if best is None or key < best[0]:
                        best = (key, fx, fy, w, h, rot)
        if best is None:
            return None
        _, x, y, w, h, rot = best
        self.place(x, y, w, h, tag)
        return x, y, w, h, rot

    def largest_free(self):
        return max((f[2] * f[3] for f in self.free), default=0)

    def place(self, x, y, w, h, tag=None):
        X, Y, W, H = x, y, w + GAP, h + GAP        # проміжок — праворуч і знизу
        new = []
        for f in self.free:
            fx, fy, fw, fh = f
            if X >= fx + fw or X + W <= fx or Y >= fy + fh or Y + H <= fy:
                new.append(f); continue
            if X > fx:            new.append((fx, fy, X - fx, fh))
            if X + W < fx + fw:   new.append((X + W, fy, fx + fw - X - W, fh))
            if Y > fy:            new.append((fx, fy, fw, Y - fy))
            if Y + H < fy + fh:   new.append((fx, Y + H, fw, fy + fh - Y - H))
        new = [f for f in new if f[2] > 1 and f[3] > 1]
        self.free = [f for i, f in enumerate(new)
                     if not any(j != i and g[0] <= f[0] and g[1] <= f[1] and g[0] + g[2] >= f[0] + f[2]
                                and g[1] + g[3] >= f[1] + f[3] for j, g in enumerate(new))]
        self.placed.append((x, y, w, h, tag))


def pack_best(cells, w, h):
    """Пакує комірки кожною евристикою і кількома порядками; повертає розкладку, де все
    вмістилось і лишився найбільший суцільний вільний прямокутник (туди стануть рендери)."""
    orders = {
        'long': sorted(cells, key=lambda c: -max(c.m['w'], c.m['h'])),
        'area': sorted(cells, key=lambda c: -c.size(False)[0] * c.size(False)[1]),
        'tall': sorted(cells, key=lambda c: -min(c.size(True)[1], c.size(False)[1])),
    }
    best = None
    for heur in ('bssf', 'baf', 'tl'):
        for oname, order in orders.items():
            P = MaxRects(w, h, heur)
            placed, ok = [], True
            for c in order:
                w0, h0 = c.size(False); w1, h1 = c.size(True)
                r = P.insert([(w0, h0, False), (w1, h1, True)], tag=c.part['file'])
                if r is None:
                    ok = False; break
                placed.append((c, r))
            if not ok:
                continue
            key = (P.largest_free(), sum(f[2] * f[3] for f in P.free))
            if best is None or key > best[0]:
                best = (key, P, placed, heur, oname)
    if best is None:
        return None, None
    print(f'  пакування: {best[3]}/{best[4]}, найбільший вільний прямокутник {best[0][0]:.0f} мм²')
    return best[1], best[2]


# ------------------------------------------------------------------ рендери
class Renders:
    """Кеш рендерів OpenSCAD у робочій теці: назва файлу = усі параметри."""

    def __init__(self, tmp, fresh=False):
        self.tmp, self.fresh, self.n = tmp, fresh, 0
        os.makedirs(tmp, exist_ok=True)

    @staticmethod
    def defs(node, keys, hi='', upto=-1, fat=False):
        klist = '[' + ','.join(f'"{k}"' for k in keys) + ']'
        return ['-D', 'part="none"', '-D', f'node="{node}"', '-D', f'keys={klist}', '-D', f'hi="{hi}"',
                '-D', f'upto={upto}', '-D', f'fat={"true" if fat else "false"}'] + RENDER_EXTRA.get(node, [])

    def png(self, node, keys, view, size, hi='', upto=-1, fat=False, camera=None):
        """camera = (центр xyz, відстань) — крупний план без --viewall; інакше вся сцена в кадрі."""
        cam = '' if camera is None else '_' + '_'.join(f'{v:.0f}' for v in camera[0]) + f'_{camera[1]:.0f}'
        # Хеш списку ключів у назві: відтінок деталі = її позиція у списку, і кеш без хешу
        # після перестановки рядків у assembly.tsv мовчки поміняв би виноски місцями.
        kh = hashlib.md5(','.join(keys).encode()).hexdigest()[:6]
        name = f"{node}_{kh}_{view[0]}_{view[1]}_{size[0]}_{hi or 'all'}_{upto}{'_fat' if fat else ''}{cam}.png"
        out = os.path.join(self.tmp, name)
        if self.fresh or not os.path.exists(out):
            if camera is None:
                view_args = ['--viewall', '--autocenter', f'--camera=0,0,0,{view[0]},0,{view[1]},500']
            else:
                c, dist = camera
                view_args = [f'--camera={c[0]:.1f},{c[1]:.1f},{c[2]:.1f},{view[0]},0,{view[1]},{dist:.0f}']
            cmd = ['openscad', '--preview', '-o', out, f'--imgsize={size[0]},{size[1]}', '--colorscheme=Tomorrow',
                   '--projection=o'] + view_args + self.defs(node, keys, hi, upto, fat) + [SCAD]
            # Headless OpenSCAD зрідка падає мовчки (порожній stderr, файлу нема) — повторюємо.
            for attempt in range(3):
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0 and os.path.exists(out):
                    break
            else:
                sys.exit(f'openscad не зробив {name} (3 спроби):\n{r.stderr[-1200:]}')
            # «невідома деталь: none» модель каже завжди, коли part="none" — це не помилка
            bad = [ln for ln in r.stderr.splitlines() if re.search(r'ERROR|WARNING:|!!!', ln) and 'деталь: none' not in ln]
            if bad:
                print('  УВАГА у рендері', name + ':', '; '.join(bad)[:300])
            self.n += 1
        return out

    def pin_positions(self, keys):
        """Світові координати шарнірів з echo(PINPOS) обгортки — центри крупних планів."""
        out = os.path.join(self.tmp, 'pins.echo')
        r = subprocess.run(['openscad', '-o', out] + self.defs('pins', keys) + [SCAD], capture_output=True, text=True)
        m = re.search(r'ECHO: PINPOS = (\[.*?\])\n', r.stderr + open(out, encoding='utf-8').read() if os.path.exists(out) else r.stderr, re.S)
        if not m:
            sys.exit('sheets.scad не віддав PINPOS:\n' + r.stderr[-800:])
        return {k: v for k, v in json.loads(m.group(1))}


# classify / anchors / finish_image — tools/hue_callouts.py (спільні з media-kit)
def data_uri(path):
    return 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()


class View:
    """Готовий рендер із виносками: обрізана картинка + якорі деталей у її пікселях."""

    def __init__(self, node, view, png, crop, labels):
        self.node, self.view, self.png, self.crop = node, view, png, crop
        self.labels = labels            # [(текст, (px, py)), …] у координатах обрізаної картинки
        self.pw, self.ph = crop[2], crop[3]
        self.left = [l for l in labels if l[1][0] < self.pw / 2]
        self.right = [l for l in labels if l[1][0] >= self.pw / 2]
        self.lw_l = max([text_w(t, 2.3) + 2.5 for t, _ in self.left], default=0)
        self.lw_r = max([text_w(t, 2.3) + 2.5 for t, _ in self.right], default=0)
        self.title = f"{RENDER_TITLE.get(node, node)}, {VIEW_NAME.get(view[0], '')} ({view[0]}°/{view[1]}°)"

    def box(self, s):
        """Розмір блоку при масштабі s мм/px."""
        return self.lw_l + self.pw * s + self.lw_r, max(self.ph * s, len(self.left) * LABEL_ROW, len(self.right) * LABEL_ROW) + 3.5

    def svg(self, x, y, s, with_title=True):
        iw, ih = self.pw * s, self.ph * s
        bw, bh = self.box(s)
        ix, iy = x + self.lw_l, y + (bh - 3.5 - ih) / 2
        out = [f'<image x="{ix:.2f}" y="{iy:.2f}" width="{iw:.2f}" height="{ih:.2f}" href="{data_uri(self.png)}" preserveAspectRatio="none"/>']
        for side, items in (('l', self.left), ('r', self.right)):
            if not items:
                continue
            items = sorted(items, key=lambda l: l[1][1])
            # розсунути підписи, щоб не наїжджали, і не вилазити за блок
            ys_ = spread_rows([iy + p[1] * s for _, p in items], LABEL_ROW, y + bh - 4.5)
            for (t, p), ly in zip(items, ys_):
                ax, ay = ix + p[0] * s, iy + p[1] * s
                if side == 'l':
                    tx, lx = x + self.lw_l - 2.0, x + self.lw_l - 1.2
                    anchor = 'end'
                else:
                    tx, lx = x + self.lw_l + iw + 2.0, x + self.lw_l + iw + 1.2
                    anchor = 'start'
                out.append(f'<line class="lead" x1="{lx:.2f}" y1="{ly - 0.7:.2f}" x2="{ax:.2f}" y2="{ay:.2f}"/>'
                           f'<circle class="dot" cx="{ax:.2f}" cy="{ay:.2f}" r="0.55"/>'
                           f'<text class="tl" font-size="2.3" x="{tx:.2f}" y="{ly:.2f}" text-anchor="{anchor}">{html.escape(t)}</text>')
        if with_title:
            out.append(f'<text class="tv" font-size="2.0" x="{x + bw / 2:.2f}" y="{y + bh - 0.6:.2f}" text-anchor="middle">{html.escape(self.title)}</text>')
        return '\n'.join(out)


def choose_views(R, node, keys, size=(900, 675), fat=False):
    """Два ракурси, за яких видно якнайбільше деталей: перший — згори, другий — той,
    що додає найбільше до першого. Видимість деталі рахується в пікселях її відтінку."""
    n = len(keys)
    counts = {}
    for v in VIEWS:
        _, lab = classify(R.png(node, keys, v, size, fat=fat), n)
        counts[v] = [c for c, _ in anchors(lab, n)]
    ref = [max(counts[v][i] for v in VIEWS) for i in range(n)]
    vis = lambda c, i: min(1.0, c / max(1, ref[i]))
    score = lambda v: sum(vis(counts[v][i], i) for i in range(n))
    first = max([v for v in VIEWS if v[0] < 90], key=score)
    second = max([v for v in VIEWS if v != first],
                 key=lambda v: sum(max(vis(counts[first][i], i), vis(counts[v][i], i)) for i in range(n)))
    return [first, second], ref, counts


def make_view(R, node, keys, view, labels_by_key, ref, size=(1400, 1050), out_dir=None, fat=False):
    """Повний рендер ракурсу з виносками до кожної видимої деталі."""
    n = len(keys)
    src = R.png(node, keys, view, size, fat=fat)
    a, lab = classify(src, n)
    anc = anchors(lab, n)
    scale2 = (size[0] / 900) ** 2
    out = os.path.join(out_dir or R.tmp, f'view_{node}_{view[0]}_{view[1]}.png')
    crop = finish_image(a, lab, out)
    labels = []
    for i, k in enumerate(keys):
        c, p = anc[i]
        if p is None or c < 25 * scale2 or c < 0.12 * ref[i] * scale2:
            continue
        labels.append((labels_by_key[k], (p[0] - crop[0], p[1] - crop[1])))
    return View(node, view, out, crop, labels), [keys[i] for i in range(n) if anc[i][1] is not None and anc[i][0] >= 25 * scale2]


def make_step_view(R, node, keys, idx, views, label, size=(1000, 750), camera=None):
    """Крок складання: деталі 0..idx, остання помаранчева. Ракурс — основний, а якщо на
    ньому нову деталь майже не видно, той із кандидатів, де її видно найбільше.
    camera — крупний план (центр, відстань) для пальців: на плані всієї машини їх не видно."""
    hi = keys[idx]
    best = None
    for v in list(views) + [v for v in VIEWS if v not in views]:
        src = R.png(node, keys, v, size, hi=hi, upto=idx, camera=camera)
        a, lab = classify(src, 1, hi_mode=True)
        c, p = anchors(lab, 1)[0]
        if best is None or c > best[0]:
            best = (c, v, src, a, lab, p)
        if v in views and c >= 400:        # основний ракурс годиться — далі не шукаємо
            break
    c, v, src, a, lab, p = best
    out = os.path.join(R.tmp, f'step_{node}_{idx:02d}.png')
    crop = finish_image(a, lab, out)
    labels = [(label, (p[0] - crop[0], p[1] - crop[1]))] if p is not None else []
    return View(node, v, out, crop, labels), c


# ------------------------------------------------------------------ аркуш
CSS = f"""
@page {{ size: A4 portrait; margin: {MARGIN}mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: {FONT}; color: #000; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: {CW}mm; height: {CH}mm; break-after: page; overflow: hidden; position: relative; }}
.page svg {{ display: block; width: {CW}mm; height: {CH}mm; }}
svg text {{ font-family: {FONT}; }}
.cell {{ fill: none; stroke: #9a9a9a; stroke-width: 0.25; }}
.part {{ fill: #e9eef5; stroke: #1a1a1a; stroke-width: 0.35; fill-rule: evenodd; stroke-linejoin: round; }}
.tt {{ font-weight: 700; }}
.tn {{ font-style: italic; fill: #333; }}
.td {{ fill: #000; }}
.tw {{ fill: #1f4e9c; }}
.tx {{ fill: #8a2b2b; }}
.th {{ fill: #1f4e9c; }}
.tm {{ fill: #1f4e9c; }}
.dim {{ stroke: #1f4e9c; stroke-width: 0.18; }}
.lead {{ stroke: #222; stroke-width: 0.22; }}
.dot {{ fill: #222; }}
.tl {{ fill: #000; font-weight: 600; }}
.tv {{ fill: #555; font-style: italic; }}
.head {{ font-weight: 700; }}
.hsub {{ fill: #333; }}
.hr {{ stroke: #000; stroke-width: 0.5; }}
.ruler {{ stroke: #000; stroke-width: 0.3; }}
.tf {{ fill: #333; }}
.rbox {{ fill: none; stroke: #bbb; stroke-width: 0.2; stroke-dasharray: 1 0.8; }}

.steps {{ break-before: page; }}
.steps h2 {{ font-size: 14pt; margin: 0 0 2mm; padding-bottom: 1.2mm; border-bottom: 1pt solid #000; }}
.steps .lead-p {{ font-size: 9pt; color: #333; margin: 0 0 3mm; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm 5mm; }}
.card {{ break-inside: avoid; border: 0.3pt solid #aaa; border-radius: 1.2mm; padding: 2mm; }}
/* SVG зберігає свій розмір у мм (width/height атрибутами): width:100% розтягував би
   вузький портретний рендер на всю колонку — картка сідла D виходила 83 мм замість 62 */
.card svg {{ display: block; width: auto; max-width: 100%; height: auto; margin: 0 auto; }}
.card .txt {{ font-size: 8.6pt; line-height: 1.3; margin-top: 1.5mm; }}
.card .txt b {{ font-size: 10pt; }}
.card code {{ font: 8.6pt/1.3 "SF Mono", Menlo, Consolas, monospace; background: #eee; padding: 0 0.6mm; border-radius: 0.5mm; white-space: nowrap; }}
.card .where {{ color: #1f4e9c; font-weight: 600; }}
.card .how {{ color: #222; }}
.ov {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3mm 5mm; margin-bottom: 4mm; }}
.ov svg {{ display: block; width: auto; max-width: 100%; height: auto; margin: 0 auto; border: 0.2pt dashed #bbb; }}
.note {{ font-size: 8.6pt; color: #333; border: 0.6pt solid #000; padding: 2mm 2.5mm; margin: 0 0 3mm; break-inside: avoid; }}
"""


def head_svg(no, total, sheet, nparts, nfiles, ver, date):
    t = f'Аркуш {no} з {total} · {sheet["title"].upper()}'
    return (f'<text class="head" font-size="5.0" x="0" y="4.6">{html.escape(t)}</text>'
            f'<text class="hsub" font-size="2.5" x="{CW}" y="4.6" text-anchor="end">print3d-parts · {html.escape(ver)} · {date}</text>'
            f'<text class="hsub" font-size="2.5" x="0" y="7.9">{html.escape(sheet["sub"])} · деталей {nparts} у {nfiles} файлах · '
            f'масштаб 1:1 — кладіть деталь на її контур</text>'
            f'<line class="hr" x1="0" y1="{HEAD_H - 0.5:.1f}" x2="{CW}" y2="{HEAD_H - 0.5:.1f}"/>')


def foot_svg(note):
    y = CH - FOOT_H + 2.0
    out = [f'<line class="hr" x1="0" y1="{y - 1.6:.1f}" x2="{CW}" y2="{y - 1.6:.1f}"/>',
           f'<line class="ruler" x1="0" y1="{y + 2.5}" x2="100" y2="{y + 2.5}"/>']
    for i in range(0, 101, 10):
        h = 2.2 if i % 50 == 0 else 1.4
        out.append(f'<line class="ruler" x1="{i}" y1="{y + 2.5}" x2="{i}" y2="{y + 2.5 - h}"/>')
    for i, anc in ((0, 'start'), (50, 'middle'), (100, 'end')):
        out.append(f'<text class="tf" font-size="2.0" x="{i}" y="{y + 5.3}" text-anchor="{anc}">{i}</text>')
    out.append(f'<text class="tf" font-size="2.1" x="104" y="{y + 1.0}">лінійка 100 мм — перевірте принтер: друк 100 %, без «за розміром сторінки»</text>')
    for i, ln in enumerate(note):
        out.append(f'<text class="tf" font-size="2.1" x="104" y="{y + 3.7 + 2.7 * i:.1f}">{html.escape(ln)}</text>')
    return '\n'.join(out)


def same_size_notes(cells):
    """Деталі, що збігаються всіма трьома габаритами (у межах 0.3 мм): напис «= файл».
    Пари, що різняться менше ніж на 1 мм, — «схожа: файл (чим різниться)»."""
    dims = {c.part['file']: (round(c.m['w'], 1), round(c.m['h'], 1), round(c.m['z'], 1)) for c in cells}
    notes = {}
    files = list(dims)
    for i, f in enumerate(files):
        a = dims[f]
        for g in files:
            if g == f:
                continue
            b = dims[g]
            d = [abs(x - y) for x, y in zip(a, b)]
            if max(d) <= 0.3:
                notes.setdefault(f, []).append(f'= {g} (однакові)')
            elif max(d) < 1.0:
                j = max(range(3), key=lambda k: d[k])
                what = ['довжина', 'ширина', 'висота'][j]
                notes.setdefault(f, []).append(f'≈ {g}: {what} {fmt(b[j])} проти {fmt(a[j])}')
    return {f: '; '.join(v) for f, v in notes.items()}


def build_sheet(no, sheet, parts, steps, R, ver, date, want_steps, report):
    keys = [s['key'] for s in steps if s['node'] in sheet['nodes']]
    step_of = {s['key']: s for s in steps}
    print(f'== аркуш {no}: {sheet["title"]} — {len(keys)} файлів')
    cells = []
    for k in keys:
        p = parts.get(k) or sys.exit(f'assembly.tsv: ключа {k} немає в parts.tsv')
        cells.append(Cell(p, step_of[k], measure(k, find_stl(p['file']))))
    notes = same_size_notes(cells)
    for c in cells:
        if c.part['file'] in notes:
            c.__init__(c.part, c.step, c.m, notes[c.part['file']])
    # --- пакування комірок
    area_y0 = HEAD_H + 1.0
    packer, placed = pack_best(cells, CW, CH - area_y0 - FOOT_H - 1.0)
    if packer is None:
        sys.exit(f'аркуш {no}: комірки не вміщаються на A4 — треба ділити аркуш')
    # --- рендери вузлів: спершу по першому ракурсу кожного вузла, потім другі
    views, leftover, covered = [], [], {}
    labels_by_key = {k: parts[k]['file'] + (f" ×{parts[k]['qty']}" if parts[k]['qty'] > 1 else '') for k in keys}
    node_views, by_rank = {}, {0: [], 1: []}
    for node in sheet['renders']:
        nkeys = [k for k in keys if k in RENDER_KEYS.get(node, keys)]
        fat = node == 'pins'
        chosen, ref, counts = choose_views(R, node, nkeys, fat=fat)
        chosen = chosen[:RENDER_NVIEWS.get(node, 2)]
        node_views[node] = (nkeys, chosen, ref)
        for rank, v in enumerate(chosen):
            vw, seen = make_view(R, node, nkeys, v, labels_by_key, ref, fat=fat)
            by_rank[rank].append(vw)
            for k in seen:
                covered[k] = covered.get(k, 0) + 1
    views = by_rank[0] + by_rank[1]
    pinpos = R.pin_positions(keys) if 'pins' in sheet['renders'] else {}
    missing = [k for k in keys if k not in covered]
    if missing:
        print('  УВАГА: без виноски на жодному ракурсі:', ', '.join(missing))
    # --- рендери у вільне місце
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{CW}mm" height="{CH}mm" viewBox="0 0 {CW} {CH}">']
    svg.append(head_svg(no, len(SHEETS), sheet, sum(c.part['qty'] for c in cells), len(cells), ver, date))
    svg.append(f'<g transform="translate(0,{area_y0})">')
    for c, (x, y, w, h, rot) in placed:
        svg.append(c.svg(x, y, rot))
    render_boxes = []
    for vw in views:
        best = None
        for f in sorted(packer.free, key=lambda f: -f[2] * f[3]):
            fx, fy, fw, fh = f
            avail_w = fw - GAP - vw.lw_l - vw.lw_r
            if avail_w < 40:
                continue
            s = min(avail_w / vw.pw, (fh - GAP - 3.5) / vw.ph, MAX_IMG_W / vw.pw)
            bw, bh = vw.box(s)
            if vw.pw * s < 40 or vw.ph * s < 28 or bh > fh - GAP:
                continue
            if best is None or vw.pw * s > best[0]:
                best = (vw.pw * s, fx, fy, s, bw, bh)
        if best is None:
            leftover.append(vw); continue
        _, fx, fy, s, bw, bh = best
        packer.place(fx, fy, bw, bh, tag='render:' + vw.title)
        svg.append(f'<rect class="rbox" x="{fx:.2f}" y="{fy:.2f}" width="{bw:.2f}" height="{bh:.2f}"/>')
        svg.append(vw.svg(fx, fy, s))
        render_boxes.append(dict(view=vw.title, x=fx, y=fy + area_y0, w=bw, h=bh, img_w=vw.pw * s, labels=len(vw.labels)))
    svg.append('</g>')
    note = (['Пальці й шайби НЕ клеїти. Куди який — у виносках', 'на рендері й у кроках на наступній сторінці.']
            if sheet['renders'] == ['pins'] else
            ['Розкладіть надруковане по контурах, потім клейте', 'у порядку кроків на наступній сторінці.'])
    svg.append(foot_svg(note))
    svg.append('</svg>')
    page_html = f'<div class="page">{"".join(svg)}</div>'
    # --- сторінки кроків
    steps_html = ''
    step_report = []
    if want_steps:
        parts_html = [f'<section class="steps"><h2>Аркуш {no} · {html.escape(sheet["title"])} — порядок склеювання</h2>']
        parts_html.append('<p class="lead-p">Сірі деталі вже на місці, помаранчева — ця. Порядок той самий, що й у зварюванні в металі. '
                          'Номер кроку стоїть і на контурі деталі на аркуші розкладки.</p>')
        if leftover:
            parts_html.append('<div class="ov">' + ''.join(overview_html(vw) for vw in leftover) + '</div>')
        parts_html.append('<div class="grid">')
        for node in sheet['renders']:
            nkeys, chosen, ref = node_views[node]
            for i, k in enumerate(nkeys):
                st = step_of[k]
                cam = (pinpos[k], PIN_CLOSEUP) if node == 'pins' else None
                vw, cnt = make_step_view(R, node, nkeys, i, chosen, labels_by_key[k], camera=cam)
                step_report.append(dict(step=st['step'], key=k, view=vw.view, px=int(cnt)))
                if cnt < 60:
                    print(f'  УВАГА: крок {st["step"]} ({k}) — деталь майже не видно ({cnt} px)')
                parts_html.append(card_html(st, parts[k], vw))
        parts_html.append('</div></section>')
        steps_html = ''.join(parts_html)
    elif leftover:
        steps_html = ('<section class="steps"><h2>Аркуш %d · %s — ракурси</h2><div class="ov">%s</div></section>'
                      % (no, html.escape(sheet['title']), ''.join(overview_html(vw) for vw in leftover)))
    report['sheets'].append(dict(
        no=no, slug=sheet['slug'], title=sheet['title'], files=len(cells), parts=sum(c.part['qty'] for c in cells),
        cells=[dict(file=c.part['file'], step=c.step['step'], x=round(x, 2), y=round(y + area_y0, 2), w=round(w, 2), h=round(h, 2),
                    rot=rot, outline=[round(c.m['w'], 2), round(c.m['h'], 2), round(c.m['z'], 2)],
                    holes=[round(h_['circle'][2], 2) if h_['circle'] else [round(h_['w'], 2), round(h_['h'], 2)] for h_ in c.m['holes']],
                    ring=c.m['ring'], pin=c.m['pin'], note=notes.get(c.part['file'], ''))
               for c, (x, y, w, h, rot) in placed],
        renders_on_sheet=render_boxes,
        renders_overflow=[vw.title for vw in leftover],
        views={node: dict(keys=nk, chosen=ch, ref_px=rf) for node, (nk, ch, rf) in node_views.items()},
        uncovered=missing, steps=step_report,
        free_area=round(sum(f[2] * f[3] for f in packer.free), 0)))
    return page_html, steps_html


def overview_html(vw):
    s = (92 - vw.lw_l - vw.lw_r) / vw.pw
    bw, bh = vw.box(s)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {bw:.2f} {bh:.2f}" width="{bw:.2f}mm" height="{bh:.2f}mm">'
            + vw.svg(0, 0, s) + '</svg>')


def card_html(st, part, vw):
    s = (90 - vw.lw_l - vw.lw_r) / vw.pw
    s = min(s, 62 / vw.ph)
    bw, bh = vw.box(s)
    img = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {bw:.2f} {bh:.2f}" width="{bw:.2f}mm" height="{bh:.2f}mm">'
           + vw.svg(0, 0, s, with_title=False) + '</svg>')
    qty = f" ×{part['qty']}" if part['qty'] > 1 else ''
    where = '' if st['where'] in ('—', '-', '') else f'<span class="where">{html.escape(st["where"])}</span>'
    how = '' if st['how'] in ('—', '-', '') else f'<div class="how">{html.escape(st["how"])}</div>'
    return (f'<div class="card">{img}<div class="txt"><b>{html.escape(st["step"])}</b> &nbsp;<code>{html.escape(part["file"])}</code>{qty} '
            f'— {html.escape(short_name(part["desc"]))}<br>{where}{how}</div></div>')


# ------------------------------------------------------------------ головне
def main():
    ap = argparse.ArgumentParser(description='аркуші розкладки 1:1 для набору print3d-parts')
    ap.add_argument('--out', default=os.path.join(HERE, 'SHEETS.pdf'))
    ap.add_argument('--only', type=int, help='лише один аркуш (номер)')
    ap.add_argument('--no-steps', action='store_true', help='без сторінок кроків (швидко)')
    ap.add_argument('--no-pdf', action='store_true')
    ap.add_argument('--png', action='store_true', help='прев’ю сторінок розкладки у png/')
    ap.add_argument('--fresh', action='store_true', help='перерендерити всі PNG')
    ap.add_argument('--tmp', default=os.path.join(tempfile.gettempdir(), 'p3d_sheets'))
    ap.add_argument('--keep-html')
    a = ap.parse_args()

    parts, steps = read_parts(), read_assembly()
    vers = sorted(d for d in os.listdir(os.path.join(ROOT, 'versions')) if d.startswith('V')) if os.path.isdir(os.path.join(ROOT, 'versions')) else []
    ver = vers[-1] if vers else 'без версії'
    date = datetime.date.today().isoformat()
    R = Renders(a.tmp, a.fresh)
    report = dict(version=ver, date=date, sheets=[])
    pages, tails = [], []
    for no, sheet in enumerate(SHEETS, 1):
        if a.only and no != a.only:
            continue
        p, t = build_sheet(no, sheet, parts, steps, R, ver, date, not a.no_steps, report)
        pages.append(p); tails.append(t)
    # усі деталі набору мають бути на якомусь аркуші
    on_sheets = {c['file'] for s in report['sheets'] for c in s['cells']}
    if not a.only:
        lost = [p['file'] for p in parts.values() if p['file'] not in on_sheets]
        if lost:
            sys.exit('деталі без аркуша: ' + ', '.join(lost))
    doc = ('<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>Аркуші розкладки 1:1</title>'
           f'<style>{CSS}</style></head><body>')
    for p, t in zip(pages, tails):
        doc += p + t
    doc += '</body></html>'
    html_path = a.keep_html or os.path.join(a.tmp, 'sheets.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    report['renders_made'] = R.n
    print(f'  рендерів зроблено: {R.n}')

    chrome = os.environ.get('CHROME') or next((c for c in CHROME_CANDIDATES if os.path.exists(c)), None)
    png_dir = os.path.join(HERE, 'png')
    if a.no_pdf:
        if a.png and chrome:
            previews_from_html(pages, report, a.tmp, chrome, png_dir)
        print('  HTML:', html_path)
    else:
        if not chrome:
            sys.exit('не знайшов Chrome; вкажіть CHROME=/шлях/до/chrome')
        how = to_pdf(html_path, os.path.abspath(a.out), chrome, 'Аркуші розкладки 1:1 · print3d-parts', date)
        report['pdf_pages'] = pdf_pages(a.out)
        print(f'  {os.path.relpath(a.out, ROOT)}: {report["pdf_pages"]} стор., {os.path.getsize(a.out) // 1024} КБ ({how})')
        if a.png:
            if shutil.which('pdftoppm') and shutil.which('pdftotext'):
                previews_from_pdf(a.out, report, png_dir)
            elif chrome:
                print('  poppler не знайдено (brew install poppler) — прев’ю зі знімка HTML, не з PDF')
                previews_from_html(pages, report, a.tmp, chrome, png_dir)
    with open(os.path.join(HERE, 'sheets.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print('  sheets.json записано')


def pdf_pages(path):
    """Кількість сторінок: pdfinfo, якщо є; інакше регулярка по байтах (працює лише на
    нестиснутих об'єктах, як пише Chrome)."""
    if shutil.which('pdfinfo'):
        m = re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', path], capture_output=True, text=True).stdout)
        if m:
            return int(m.group(1))
    return len(re.findall(rb'/Type\s*/Page[^s]', open(path, 'rb').read()))


def previews_from_pdf(pdf, report, png_dir, dpi=192):
    """Прев'ю аркушів розкладки з САМОГО PDF (poppler): сторінка кожного аркуша
    знаходиться за текстом його шапки у виводі pdftotext (сторінки розділені \\f).
    Це перевіряє те, що піде на принтер, а не HTML-проксі."""
    os.makedirs(png_dir, exist_ok=True)
    txt = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    pages_txt = txt.split('\f')
    for s in report['sheets']:
        marker = f'Аркуш {s["no"]} з '
        idx = next((i for i, t in enumerate(pages_txt) if marker in t and 'масштаб 1:1' in t), None)
        if idx is None:
            print(f'  УВАГА: у PDF не знайшов сторінку аркуша {s["no"]}'); continue
        out = os.path.join(png_dir, f'{s["no"]}_{s["slug"]}')          # латинські назви: на них посилаються README
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-f', str(idx + 1), '-l', str(idx + 1), '-singlefile', pdf, out], check=True)
        s['pdf_page'] = idx + 1
        print(f'  прев’ю: {os.path.relpath(out + ".png", ROOT)} (стор. {idx + 1} PDF)')


def previews_from_html(pages, report, tmp, chrome, png_dir):
    """Запасний шлях без poppler: знімок HTML однієї сторінки в Chrome (A4 при 96 dpi × 2).
    Показує розкладку, але не сам PDF."""
    os.makedirs(png_dir, exist_ok=True)
    for p, s in zip(pages, report['sheets']):
        one = os.path.join(tmp, f'page_{s["no"]}.html')
        with open(one, 'w', encoding='utf-8') as f:
            f.write(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS} body{{padding:{MARGIN}mm;}}</style></head><body>{p}</body></html>')
        out = os.path.join(png_dir, f'{s["no"]}_{s["slug"]}.png')
        subprocess.run([chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                        '--window-size=794,1123', f'--screenshot={out}', 'file://' + one], capture_output=True)
        print('  прев’ю (знімок HTML):', os.path.relpath(out, ROOT))


if __name__ == '__main__':
    main()
