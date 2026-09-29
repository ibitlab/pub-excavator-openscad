#!/usr/bin/env python3
"""Схема підключення одного циліндра M5 → WIRING.svg (однакова для стріли, рукояті й ковша).

Датчики, контролер ESP32-C3 SuperMini, драйвер, живлення. Виводи — ті самі, що в таблиці
розділу «Підключення й керування» README.md поруч: змінив тут — зміни й там.
Чистий Python без залежностей (make.sh кличе його системним python3).

usage: wiring.py [--out WIRING.svg]
"""
import argparse
import os
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools'))
from author import line as author_line  # noqa: E402

W, H = 1200, 860
FONT = 'DejaVu Sans, Arial, sans-serif'
NET = {'+12V': '#c62828', '+5V': '#e65100', '+3V3': '#8d6e00', 'GND': '#37474f'}
C_ENC, C_LIM, C_IN, C_MOT = '#1565c0', '#2e7d32', '#6a1b9a', '#795548'
INK, BOX = '#212121', '#fafafa'

out = []


def ln(x1, y1, x2, y2, c=INK, w=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{w}"{d}/>')


def tx(x, y, s, size=12, anchor='start', weight='normal', c=INK):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
               f'fill="{c}">{escape(s)}</text>')


def box(x, y, w, h, fill=BOX, dash=None, c=INK):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{c}" stroke-width="1.5"{d}/>')


def dot(x, y, c=INK):
    out.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{c}"/>')


def flag(x, y, net, side='right'):
    """Мітка кола живлення на кінці виводу: side — у який бік від x вона тягнеться."""
    c = NET[net]; w = 12 + 7.5 * len(net); x0 = x if side == 'right' else x - w
    out.append(f'<rect x="{x0}" y="{y - 9}" width="{w}" height="18" rx="9" fill="white" stroke="{c}" stroke-width="1.5"/>')
    tx(x0 + w / 2, y + 4, net, 11, 'middle', 'bold', c)


def resistor_v(x, y1, y2, c=INK):
    """Резистор вертикально між y1 і y2 (зигзаг посередині)."""
    top, bot = min(y1, y2), max(y1, y2); m1, m2 = top + (bot - top) * 0.25, top + (bot - top) * 0.75
    zz = [(x, m1)] + [(x + (6 if i % 2 else -6), m1 + (m2 - m1) * (i + 0.5) / 6) for i in range(6)] + [(x, m2)]
    ln(x, top, x, m1, c); ln(x, m2, x, bot, c)
    pts = ' '.join(f'{a:.1f},{b:.1f}' for a, b in zz)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"/>')


def sensor(y0, part, role, vs):
    """Датчик у пласкому TO-92: виводи VS, GND, OUT; повертає y виводу OUT."""
    box(40, y0, 200, 84)
    tx(52, y0 + 26, part, 14, weight='bold'); tx(52, y0 + 46, role, 11)
    for i, (pin, net) in enumerate([('VS', vs), ('GND', 'GND'), ('OUT', None)]):
        y = y0 + 20 + 22 * i
        tx(232, y + 4, pin, 10, 'end', c='#616161'); ln(240, y, 270, y)
        if net:
            flag(274, y, net)
    return y0 + 64


def svg(path):
    out.clear()
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
               f'font-family="{FONT}">')
    out.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    tx(40, 40, 'Циліндр M5 · схема підключення', 18, weight='bold')
    tx(40, 62, 'однакова для стріли, рукояті й ковша: у кожного циліндра свій контролер і свій драйвер', 12, c='#616161')

    # межа циліндра: зліва — те, що сидить у циліндрі, справа — біля контролера
    ln(360, 96, 360, 700, '#9e9e9e', 1.5, '6 5')
    tx(352, 90, 'у циліндрі', 11, 'end', c='#757575'); tx(368, 90, 'джгут, 9 дротів →', 11, c='#757575')
    box(640, 90, 190, 590)   # контролер — першим: підписи його виводів лягають поверх

    # --- датчики й сигнали до контролера (рядки OUT = рядки виводів контролера, дроти прямі)
    sig = [(sensor(120, 'SS41F', 'енкодер, латч A', '+5V'), 'ENC_A', 'GPIO5', C_ENC, True),
           (sensor(220, 'SS41F', 'енкодер, латч B', '+5V'), 'ENC_B', 'GPIO6', C_ENC, True),
           (sensor(340, 'SS49E', 'кінцевик «розкритий»', '+3V3'), 'LIM_EXT', 'GPIO3 · ADC', C_LIM, False),
           (sensor(440, 'SS49E', 'кінцевик «зведений»', '+3V3'), 'LIM_RET', 'GPIO4 · ADC', C_LIM, False)]
    for y, net, pin, c, pull in sig:
        ln(270, y, 640, y, c, 2.5)
        tx(376, y - 6, net, 11, weight='bold', c=c)
        tx(648, y + 4, pin, 12)
        if pull:   # відкритий колектор SS41F — підтягування до 3.3 В
            dot(500, y, c); resistor_v(500, y - 40, y); flag(500 - 23, y - 49, '+3V3')
            tx(512, y - 16, '10 кОм', 10, c='#616161')

    # --- мотор і драйвер
    out.append(f'<circle cx="140" cy="625" r="30" fill="{BOX}" stroke="{INK}" stroke-width="1.5"/>')
    tx(140, 632, 'M', 20, 'middle', 'bold')
    tx(140, 676, 'N20 12GAN20-298, 12 В', 11, 'middle')
    for y, net in [(610, 'M+'), (640, 'M−')]:
        ln(140 + (30 ** 2 - (y - 625) ** 2) ** 0.5, y, 400, y, C_MOT, 2.5)
        tx(376, y - 6, net, 11, weight='bold', c=C_MOT)
    box(400, 580, 160, 110)
    tx(480, 628, 'DRV8871', 13, 'middle', 'bold'); tx(480, 646, 'драйвер мотора', 10, 'middle', c='#616161')
    for y, a, b in [(610, 'OUT1', 'IN1'), (640, 'OUT2', 'IN2')]:
        tx(406, y + 4, a, 10, c='#616161'); tx(554, y + 4, b, 10, 'end', c='#616161')
    for y, net, pin in [(610, 'IN1', 'GPIO7 · PWM'), (640, 'IN2', 'GPIO10 · PWM')]:
        ln(560, y, 640, y, C_IN, 2.5); tx(648, y + 4, pin, 12)
        tx(566, y - 6, net, 10, weight='bold', c=C_IN)
    tx(450, 596, 'VM', 10, 'middle', c='#616161'); ln(450, 580, 450, 562); flag(450 - 23, 553, '+12V')
    tx(440, 684, 'GND', 10, 'middle', c='#616161'); ln(440, 690, 440, 712); flag(440 - 19, 721, 'GND')
    tx(520, 684, 'ILIM', 10, 'middle', c='#616161'); resistor_v(520, 690, 740); flag(520 - 19, 749, 'GND')
    tx(532, 722, 'R_ILIM на ≈0.2 А', 10, c='#616161'); tx(532, 736, '(номінал — з даташиту)', 10, c='#616161')

    # --- контролер
    for y, pin, net in [(110, '5V', '+5V'), (132, '3V3', '+3V3'), (154, 'GND', 'GND')]:
        ln(606, y, 640, y); flag(606, y, net, 'left'); tx(648, y + 4, pin, 12)
    tx(770, 116, '3V3 — вихід', 10, 'middle', c='#616161'); tx(770, 130, 'стабілізатора плати', 10, 'middle', c='#616161')
    tx(770, 330, 'ESP32-C3', 15, 'middle', 'bold'); tx(770, 350, 'SuperMini', 15, 'middle', 'bold')
    tx(770, 372, 'свій на кожен циліндр', 10, 'middle', c='#616161')
    tx(770, 552, 'не займати:', 10, 'middle', c='#616161')
    tx(770, 568, 'GPIO2 · GPIO8 · GPIO9', 10, 'middle', c='#616161')
    tx(735, 668, 'USB-C — прошивка', 10, 'middle', c='#616161')
    for y, pin in [(200, 'GPIO20 RX'), (222, 'GPIO21 TX')]:
        tx(822, y + 4, pin, 12, 'end'); ln(830, y, 870, y, '#757575', 2, '5 4')
    tx(876, 206, 'до інших циліндрів: UART', 11, c='#757575')
    tx(876, 222, 'або ESP-NOW — не вирішено', 11, c='#757575')

    # --- живлення
    box(880, 430, 150, 70)
    tx(892, 460, 'Блок живлення', 12, weight='bold'); tx(892, 478, '12 В', 12)
    for y, pin, net in [(448, '+', '+12V'), (482, '−', 'GND')]:
        tx(1024, y + 4, pin, 12, 'end', 'bold'); ln(1030, y, 1060, y); flag(1064, y, net)
    box(880, 540, 150, 110)
    tx(892, 566, 'Понижувач', 12, weight='bold'); tx(892, 584, '12 → 5 В', 12)
    for i, (pin, net) in enumerate([('IN+', '+12V'), ('IN−', 'GND'), ('OUT+', '+5V'), ('OUT−', 'GND')]):
        y = 560 + 24 * i
        tx(1024, y + 4, pin, 10, 'end', c='#616161'); ln(1030, y, 1060, y); flag(1064, y, net)

    # --- примітки
    notes = ['Усі GND — спільні. Однакові мітки (+5V, +3V3, +12V, GND) — одне коло.',
             'SS41F і SS49E: виводи VS · GND · OUT зліва направо, якщо дивитися на бік із маркуванням.',
             'SS49E живиться від +3V3: вихід 1.5–2.2 В, АЦП ESP32-C3 з ослабленням 12 дБ міряє до ~2.5 В.',
             'Пороги кінцевиків — у прошивці, після калібрування (README, «Підключення й керування»).',
             'USB і зовнішні 5 В одночасно — лише якщо на платі між ними є діод.']
    for i, s in enumerate(notes):
        tx(40, 782 + 16 * i, '• ' + s, 11, c='#424242')
    tx(W - 12, H - 10, author_line(), 9, 'end', c='#9e9e9e')
    out.append('</svg>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(HERE, '..', '..', 'build', 'm5_cylinders', 'WIRING.svg'))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    svg(a.out)
    print(f'  {os.path.relpath(a.out)} — схема підключення')
