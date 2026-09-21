#!/usr/bin/env python3
"""Кольори числом: чи розрізняються, чи читається текст, що насправді на пікселях.

Правило проєкту — не відповідати оком на те, на що відповідає число. Для кольорів
таких питань три, і всі три тут:

  tools/media/color.py de "#e0a021" "#2f8f6b" …        # ΔE між УСІМА парами (CIE76 в Lab)
  tools/media/color.py de --cvd "#e0a021" "#2f8f6b"    # те саме + очима дальтоніка (дейтеранопія)
  tools/media/color.py contrast "#ffffff" "#a85d12"    # WCAG: чи читається текст на тлі
  tools/media/color.py px знімок.png 40,700,60,40      # середній колір прямокутника (x,y,ш,в)

ΔE < 25 — око вже плутає (цей поріг тут і підсвічується). Саме ним підбиралися
палітра моделі, легенда й кінематичні кольори: міряються НЕ всі пари підряд, а ті,
що справді дотикаються у вузлі, — сусідство на екрані важить, далекі деталі ні.

WCAG: 4.5 — мінімум для звичайного тексту, 3.0 — для великого й для меж елементів.
Саме тут видно, що біле на `--acc` дає 3.53 (мало), а на `--acc-on` — 4.95.

`px` потребує PIL: tools/.venv/bin/python tools/media/color.py px …
`de` і `contrast` — чиста арифметика, їм годиться будь-який python3.
"""
import sys

# ---------------------------------------------------------------- перетворення
def rgb(h):
    h = h.strip().lstrip('#')
    if len(h) == 3: h = ''.join(c * 2 for c in h)
    if len(h) != 6: sys.exit(f'не колір: {h}')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def lin(c):                                  # sRGB 0..255 → лінійний 0..1
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def lab(c):
    r, g, b = (lin(v) for v in c)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

def de(a, b):                                # CIE76: евклідова відстань у Lab
    la, lb = lab(a), lab(b)
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5

def deuter(c):
    """Як колір бачить дейтеранопік (немає M-колбочок) — ~5 % чоловіків.

    Наближення Віно–Бреттеля–Моллона на гамма-кодованих sRGB, як у поширених
    симуляторах: воно грубе, але відповідає на єдине потрібне питання — чи не
    зіллються ці два кольори в один.
    """
    r, g, b = c
    L = 17.8824 * r + 43.5161 * g + 4.11935 * b
    M = 3.45565 * r + 27.1554 * g + 3.86714 * b
    S = 0.0299566 * r + 0.184309 * g + 1.46709 * b
    M = 0.494207 * L + 1.24827 * S                      # M відновлюється з L і S
    out = (0.0809444479 * L - 0.130504409 * M + 0.116721066 * S,
           -0.0102485335 * L + 0.0540193266 * M - 0.113614708 * S,
           -0.000365296938 * L - 0.00412161469 * M + 0.693511405 * S)
    return tuple(max(0, min(255, round(v))) for v in out)

def lum(c):
    r, g, b = (lin(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

# ------------------------------------------------------------------- підкоманди
def cmd_de(args):
    cvd = '--cvd' in args
    cols = [a for a in args if a != '--cvd']
    if len(cols) < 2: sys.exit('потрібно щонайменше два кольори')
    worst = None
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = rgb(cols[i]), rgb(cols[j])
            d = de(a, b)
            line = f'{cols[i]:>9} ↔ {cols[j]:<9} ΔE {d:6.1f}'
            if cvd:
                dc = de(deuter(a), deuter(b))
                line += f'   дейтеранопія {dc:6.1f}'
                d = min(d, dc)
            print(line + ('   ← плутається (<25)' if d < 25 else ''))
            worst = d if worst is None else min(worst, d)
    print(f'\nнайгірша пара: ΔE {worst:.1f}' + ('  — ПЕРЕРОБИТИ' if worst < 25 else '  — розрізняються'))

def cmd_contrast(args):
    if len(args) != 2: sys.exit('потрібно два кольори: текст і тло')
    a, b = rgb(args[0]), rgb(args[1])
    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    k = (l1 + 0.05) / (l2 + 0.05)
    note = 'звичайний текст ✔' if k >= 4.5 else ('лише великий текст і межі' if k >= 3 else 'НЕ ЧИТАЄТЬСЯ')
    print(f'{args[0]} на {args[1]}: контраст {k:.2f}  — {note}  (норма 4.5 / 3.0)')

def cmd_px(args):
    if not args: sys.exit('потрібен файл знімка')
    try:
        from PIL import Image
    except ImportError:
        sys.exit('потрібен PIL: tools/.venv/bin/python tools/media/color.py px …')
    im = Image.open(args[0]).convert('RGB')
    boxes = args[1:] or [f'0,0,{im.width},{im.height}']
    for spec in boxes:
        # Координати — В ПІКСЕЛЯХ ФАЙЛУ. Знімок із --dsf 2 удвічі більший за CSS-координати,
        # якими цілився probe.mjs, тож прямокутник туди треба подвоїти.
        x, y, w, h = (int(v) for v in spec.split(','))
        b = im.crop((x, y, x + w, y + h)).tobytes()
        px = [b[i:i + 3] for i in range(0, len(b), 3)]
        n = len(px) or 1
        m = tuple(round(sum(p[i] for p in px) / n) for i in range(3))
        grey = round(sum(0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in px) / n)
        print(f'{spec:>22}  середній #{m[0]:02x}{m[1]:02x}{m[2]:02x}  rgb{m}  яскравість {grey}/255  пікселів {n}')

if __name__ == '__main__':
    cmd, *rest = sys.argv[1:] or ['']
    {'de': cmd_de, 'contrast': cmd_contrast, 'px': cmd_px}.get(cmd, lambda a: sys.exit(__doc__))(rest)
