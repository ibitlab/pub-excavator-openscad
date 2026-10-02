#!/usr/bin/env python3
"""Як ставити датчики Холла в циліндр M5 → SENSORS.svg (однаково для стріли, рукояті й ковша).

Корпус SS41F / SS49E, куди дивиться сторона з маркуванням, куди йдуть ніжки й де який вивід,
якщо дивитися з того боку, з якого датчик вставляється в гніздо. Розташування — з m5_cyl.scad:
латчі енкодера під PHI+90° і PHI+180°, кінцевики під PHI+180° (PHI — напрямок на мотор).
Чистий Python без залежностей (make.sh кличе його системним python3).

usage: sensors.py [--out SENSORS.svg]
"""
import argparse
import math
import os
import re
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools'))
from author import line as author_line  # noqa: E402

W, H = 1200, 1010
FONT = 'DejaVu Sans, Arial, sans-serif'
INK, GREY, BOX = '#212121', '#616161', '#fafafa'
C_BODY, C_MARK, C_MAG_N, C_MAG_S = '#263238', '#ffca28', '#c62828', '#1565c0'
C_PLA, C_HEAD, C_LEAD = '#cfd8dc', '#90caf9', '#9e9e9e'
PIN_FRONT = ('VS', 'GND', 'OUT')   # сторона з маркуванням до себе, ніжки донизу: зліва направо
PIN_C = {'VS': '#c62828', 'GND': '#37474f', 'OUT': '#2e7d32'}

out = []


def scad_consts():
    src = open(os.path.join(HERE, 'm5_cyl.scad'), encoding='utf-8').read()

    def num(name):
        m = re.search(rf'^{name}\s*=\s*([\d.]+)\s*;', src, re.M)
        if not m:
            sys.exit(f'sensors.py: у m5_cyl.scad немає сталої {name}')
        return float(m.group(1))
    return {'R_MAG': num('R_MAG'), 
        'ENC': re.search(r'^ENC_ANG\s*=\s*\[PHI \+ (\d+), PHI \+ (\d+)\]', src, re.M).groups(),
        'SENS': re.search(r'^PHI_SENS\s*=\s*PHI \+ (\d+)', src, re.M).group(1)}


def ln(x1, y1, x2, y2, c=INK, w=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}"{d}/>')


def tx(x, y, s, size=12, anchor='start', weight='normal', c=INK):
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
               f'fill="{c}">{escape(s)}</text>')


def rect(x, y, w, h, fill=BOX, c=INK, rx=0, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
               f'stroke="{c}" stroke-width="{sw}"{d}/>')


def circ(x, y, r, fill=BOX, c=INK, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{c}" stroke-width="{sw}"{d}/>')


def arrow(x1, y1, x2, y2, c=INK, w=2):
    ln(x1, y1, x2, y2, c, w)
    a = math.atan2(y2 - y1, x2 - x1)
    pts = [(x2, y2), (x2 - 10 * math.cos(a - 0.4), y2 - 10 * math.sin(a - 0.4)),
           (x2 - 10 * math.cos(a + 0.4), y2 - 10 * math.sin(a + 0.4))]
    out.append(f'<polygon points="{" ".join(f"{p:.1f},{q:.1f}" for p, q in pts)}" fill="{c}"/>')


def sensor(cx, cy, leads, face, label='', k=10.0):
    """Датчик у пласкому TO-92 (4.1×3.0 мм), вид на одну зі сторін.

    leads: куди йдуть ніжки — 'down' | 'left' | 'up' | 'right'; face: 'front' (маркування до нас) |
    'back' (маркування від нас, як видно з боку вставляння). k — пікселів на мм."""
    rot = {'down': 0, 'left': 90, 'up': 180, 'right': 270}[leads]
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def p(x, y):   # локально: ніжки вздовж +y (донизу в SVG), поворот за годинниковою стрілкою
        return cx + (x * ca - y * sa) * k, cy + (x * sa + y * ca) * k
    body = [p(-2.05, -1.5), p(2.05, -1.5), p(2.05, 1.5), p(-2.05, 1.5)]
    fill = C_BODY if face == 'front' else '#546e7a'
    out.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in body)}" fill="{fill}" '
               f'stroke="{INK}" stroke-width="1.5"/>')
    names = PIN_FRONT if face == 'front' else PIN_FRONT[::-1]
    for i, name in enumerate(names):
        x = (i - 1) * 1.27
        c = PIN_C[name]
        (x1, y1), (x2, y2) = p(x, 1.5), p(x, 4.2)
        ln(x1, y1, x2, y2, c, 2.5)
        lx, ly = p(x, 5.2 + (1.1 if i == 1 and leads in ('up', 'down') else 0) * 10 / k)   # середній — нижче
        tx(lx, ly + 4, name, 10, 'middle', 'bold', c)
    mx, my = p(0, 0)
    if face == 'front':
        tx(mx, my + 4, label, 10, 'middle', 'bold', C_MARK)
    else:
        tx(mx, my + 4, 'зворот', 9, 'middle', c='#eceff1')


def svg(path):
    C = scad_consts()
    out.clear()
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
               f'font-family="{FONT}">')
    out.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    tx(40, 40, 'Циліндр M5 · датчики Холла: де стоять і як повернуті', 18, weight='bold')
    tx(40, 62, 'однаково для стріли, рукояті й ковша; усі гнізда відкриті назовні — датчики вставляються після друку', 12,
       c=GREY)

    # ---------------- 1. корпус
    rect(30, 84, 360, 330, rx=6)
    tx(46, 108, '1. Корпус SS41F і SS49E (пласкі TO-92)', 13, weight='bold')
    sensor(120, 170, 'down', 'front', '41F', 16)
    tx(120, 310, 'сторона з маркуванням', 11, 'middle'); tx(120, 325, 'до себе, ніжки донизу', 11, 'middle')
    sensor(290, 170, 'down', 'back', k=16)
    tx(290, 310, 'та сама, зі звороту', 11, 'middle'); tx(290, 325, '(як видно при вставлянні)', 11, 'middle')
    notes = ['Чутливий елемент — ближче до сторони з маркуванням;',
             'поле має входити в неї поперек корпусу.',
             'Тому маркування — завжди до магніту.',
             'Виводи в обох датчиків однакові: VS · GND · OUT.']
    for i, s in enumerate(notes):
        tx(46, 350 + 16 * i, s, 11, c='#424242')

    # ---------------- 2. енкодер: вид з боку носа
    ox, oy, R = 640, 296, 108            # центр голови на схемі, зовнішній радіус
    rect(410, 84, 760, 330, rx=6)
    tx(426, 108, '2. Енкодер: 2 × SS41F у передній стінці голови — вид з боку носа (спереду)', 13, weight='bold')
    enc_a, enc_b = (int(a) for a in C['ENC'])
    out.append(f'<path d="M {ox + 40} {oy - 100} L {ox + 195} {oy - 88} A 92 92 0 0 1 {ox + 195} {oy + 88} '
               f'L {ox + 40} {oy + 100} Z" fill="{C_HEAD}" stroke="{INK}" stroke-width="1.5"/>')
    circ(ox, oy, R, C_HEAD)
    circ(ox + 180, oy, 16, '#fff8e1'); tx(ox + 180, oy + 42, 'вал мотора', 10, 'middle', c=GREY)
    tx(ox + 180, oy - 60, 'МОТОР (PHI)', 11, 'middle', 'bold')
    circ(ox, oy, 26, '#eceff1'); circ(ox, oy, 12, 'white'); tx(ox, oy + 44, 'ніс, шпилька', 10, 'middle', c=GREY)
    rm = 62                                # R_MAG на схемі
    for name, a in (('A', enc_a), ('B', enc_b)):
        # вид спереду: +Y світу — праворуч, +Z — угору; кут a від напрямку на мотор (праворуч) проти год. стрілки
        ux, uy = round(math.cos(math.radians(a)), 6), round(-math.sin(math.radians(a)), 6)
        cx, cy = ox + rm * ux, oy + rm * uy
        ln(cx + 20 * ux, cy + 20 * uy, ox + (R + 12) * ux, oy + (R + 12) * uy, '#e0e0e0', 22)   # канавка під ніжки
        leads = {(0, -1): 'up', (-1, 0): 'left', (0, 1): 'down', (1, 0): 'right'}[(round(ux), round(uy))]
        sensor(cx, cy, leads, 'back', k=13)
        lx, ly = (cx + 40, cy - 40) if ux == 0 else (ox + (R + 30) * ux, oy + (R + 30) * uy - 30)
        tx(lx, ly, f'латч {name}', 12, 'end' if ux < 0 else 'start', 'bold')
        tx(lx, ly + 15, f'PHI + {a}°', 10, 'end' if ux < 0 else 'start', c=GREY)
    tx(1150, 140, 'Маркування — ДО ШЕСТЕРНІ (вглиб', 11, 'end', 'bold')
    tx(1150, 156, 'гнізда); видно зворот. Ніжки — у', 11, 'end')
    tx(1150, 172, f'канавку назовні (гніздо на R {C["R_MAG"]:g} мм,', 11, 'end')
    tx(1150, 188, 'навпроти магнітів шестерні).', 11, 'end')
    tx(1150, 212, 'Переплутав A і B — лише знак', 11, 'end', c=GREY)
    tx(1150, 228, 'напрямку в прошивці.', 11, 'end', c=GREY)
    # переріз: шестерня з магнітами → зазор → стінка з латчем
    sx, sy = 960, 262
    tx(sx, sy, 'переріз по латчу:', 11, weight='bold')
    rect(sx, sy + 12, 60, 110, '#ffcc80'); tx(sx + 30, sy + 138, 'шестерня', 10, 'middle', c=GREY)
    rect(sx + 60 - 12, sy + 38, 12, 20, C_MAG_N); tx(sx + 42, sy + 52, 'N', 10, 'end', 'bold', C_MAG_N)
    rect(sx + 60 - 12, sy + 78, 12, 20, C_MAG_S); tx(sx + 42, sy + 92, 'S', 10, 'end', 'bold', C_MAG_S)
    rect(sx + 70, sy + 12, 34, 110, C_HEAD); tx(sx + 87, sy + 138, 'стінка', 10, 'middle', c=GREY)
    rect(sx + 86, sy + 36, 16, 30, C_BODY)
    ln(sx + 88, sy + 36, sx + 88, sy + 66, C_MARK, 3)
    arrow(sx + 150, sy + 51, sx + 108, sy + 51, INK, 1.5)
    tx(sx + 154, sy + 47, 'маркування', 10); tx(sx + 154, sy + 60, 'до шестерні', 10)

    # ---------------- 3. кінцевики: вид збоку з боку датчиків
    rect(30, 432, 1140, 460, rx=6)
    tx(46, 456, f'3. Кінцевики: 2 × SS49E на боці PHI + {C["SENS"]}° (навпроти мотора) — вид ззовні на прилив, голова праворуч',
       13, weight='bold')
    y0, y1 = 560, 640                     # гільза
    rect(150, y0, 780, y1 - y0, '#455a64')
    rect(150, y0 + 14, 780, y1 - y0 - 28, '#78909c', sw=0)
    rect(70, y0 - 16, 110, y1 - y0 + 32, '#546e7a'); tx(125, y1 + 38, 'задня кришка', 11, 'middle', c=GREY)
    circ(40 + 30, (y0 + y1) / 2, 0.1, INK)
    rect(930, y0 - 70, 120, y1 - y0 + 140, C_HEAD); tx(990, y1 + 92, 'голова', 11, 'middle', c=GREY)
    rect(930, y0 - 70, 16, 34, 'white', c=INK); tx(952, y0 - 44, 'виріз під дроти', 10, c=GREY)
    ln(150, (y0 + y1) / 2 + 30, 930, (y0 + y1) / 2 + 30, '#bdbdbd', 1, '5 4')
    tx(540, (y0 + y1) / 2 + 26, 'канавка під дроти «зведеного» — уздовж гільзи, на 60° від осі датчиків, збоку від приливу', 10,
       'middle', c='#eceff1')
    for x_s, name, pos, boss_x0, boss_x1 in ((135, 'зведений', 'у приливі кришки', 90, 180),
                                            (880, 'розкритий', 'у приливі гільзи («горбик» біля голови)', 820, 930)):
        rect(boss_x0, y0 - 44, boss_x1 - boss_x0, 44, '#b0bec5')
        ret = name == 'зведений'          # «зведений» — ніжками до голови, «розкритий» — до кришки
        ln(x_s + (22 if ret else -22), (y0 + y1) / 2 - 8, boss_x1 + 20 if ret else boss_x0 - 10, (y0 + y1) / 2 - 8,
           '#e0e0e0', 16)                 # проріз під ніжки
        sensor(x_s, (y0 + y1) / 2 - 8, 'right' if ret else 'left', 'back', k=10)
        anc = 'middle' if name == 'зведений' else 'end'
        xl = x_s if name == 'зведений' else boss_x1 - 4
        tx(xl, y0 - 56, f'«{name}»', 12, anc, 'bold'); tx(xl, y0 - 72, pos, 10, anc, c=GREY)
    tx(470, y0 - 30, 'Маркування — ДО ГІЛЬЗИ, видно зворот. «Зведений» — ніжками до голови,', 11, 'middle', 'bold')
    tx(470, y0 - 14, '«розкритий» — до кришки (біля голови не загнути); його дроти — поверх приливу до голови.', 11, 'middle')
    # переріз поперек гільзи по датчику
    px, py = 380, 790
    tx(px - 150, py - 86, 'переріз поперек гільзи по датчику, поршень (сталева гайка) на упорі:', 11, weight='bold')
    def hexagon(flat, fill, clip=None):   # грань — ліворуч, до датчиків; clip — радіус зрізаних вершин
        pts = []
        for i in range(6):
            a0 = math.radians(150 + 60 * i)
            r = flat / math.cos(math.radians(30))
            if clip and clip < r:        # вершина зрізана колом гайки: дві точки по обидва боки
                d = math.radians(30) - math.acos(flat / clip)
                pts += [(px + clip * math.cos(a0 + e), py - clip * math.sin(a0 + e)) for e in (-d, d)]
            else:
                pts.append((px + r * math.cos(a0), py - r * math.sin(a0)))
        out.append(f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="{fill}" '
                   f'stroke="{INK}" stroke-width="1.2"/>')
    k = 10                                  # пікселів на мм; гільза рукояті Ø12
    circ(px, py, 6 * k, '#455a64')
    hexagon(4.2 * k, 'white')                                        # канал під ключ 8.4
    rect(px - 5.25 * k, py - 1.2 * k, 1.6 * k, 2.4 * k, 'white', sw=0)   # паз під магніт уздовж грані
    hexagon(3.95 * k, '#9e9e9e', 4.485 * k)                          # гайка-поршень 7.9 / 8.97
    circ(px, py, 2.42 * k, '#cfd8dc'); tx(px, py + 4, 'M5', 9, 'middle', 'bold', INK)
    tx(px, py + 76, 'поршень — сталева гайка M5 у шестигранному каналі', 10, 'middle', c=GREY)
    rect(px - 60 - 44, py - 22, 34, 44, '#b0bec5')
    rect(px - 60 - 16, py - 20, 16, 40, C_BODY)
    ln(px - 60 - 2, py - 20, px - 60 - 2, py + 20, C_MARK, 3)
    rect(px - 4.95 * k, py - 1.0 * k, 1.0 * k, 2.0 * k, C_MAG_N)       # магніт на грані гайки
    arrow(px - 200, py + 50, px - 64, py + 12, INK, 1.5)
    tx(px - 206, py + 56, 'маркування — до гільзи', 10, 'end')
    arrow(px + 20, py - 70, px - 46, py - 8, INK, 1.5)
    tx(px + 24, py - 72, 'магніт Ø2×1 на грані гайки, полюс будь-який', 10)
    arrow(px - 200, py - 50, px - 92, py - 20, INK, 1.5)
    tx(px - 206, py - 46, 'прилив, гніздо відкрите назовні', 10, 'end')
    tips = ['SS49E лінійний: полюс магніту не важить, поріг і нуль — у прошивці після калібрування.',
            'Датчик сідає на клей врівень із дном гнізда; щілина між ним і гільзою — ворог сигналу.',
            'Ніжки згинати не ближче 1 мм від корпусу. Перед вклеюванням перевір маркування:',
            'SS41F і SS49E в одному корпусі — сплутати легко (41F — енкодер, 49E — кінцевики).']
    for i, s in enumerate(tips):
        tx(640, py - 50 + 18 * i, '• ' + s, 11, c='#424242')

    tx(40, 924, '• Магніти енкодера — у передньому торці шестерні, під 180° один від одного, назовні різними полюсами (N і S):',
       11, c='#424242')
    tx(52, 940, 'один притягується до пробного магніту, другий відштовхується. Тоді кожен латч дає меандр 50/50, пара — квадратуру.',
       11, c='#424242')
    tx(40, 960, '• Кути — від напрямку на мотор (PHI у m5_cyl.scad); на схемі мотор праворуч. Масштаб не дотримано.', 11,
       c='#424242')
    tx(W - 12, H - 10, author_line(), 9, 'end', c='#9e9e9e')
    out.append('</svg>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(HERE, '..', '..', 'build', 'm5_cylinders', 'SENSORS.svg'))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    svg(a.out)
    print(f'  {os.path.relpath(a.out)} — як ставити датчики')
