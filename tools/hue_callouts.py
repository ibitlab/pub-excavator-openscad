#!/usr/bin/env python3
"""Виноски на рендері без жодних координат з моделі.

Ідея: i-ту деталь сцени фарбують у відтінок hue = i·360/n (в OpenSCAD — обгорткою,
зовнішній `color()` у прев'ю перекриває внутрішні), а на знімку деталь знаходять за
відтінком пікселів. Якір виноски — піксель маски, найближчий до її центроїда: сам
центроїд у дзеркальної пари падає в порожнечу між половинками.

    from hue_callouts import classify, anchors, finish_image, spread_rows, draw_callouts_png
    a, lab = classify('render.png', n)             # lab: −1 тло, −2 сіре/без відтінку, i — деталь i
    anc = anchors(lab, n)                          # [(пікселів, (x, y) або None), …]
    crop = finish_image(a, lab, 'clean.png')       # біле тло, темні межі між деталями, обрізка
    draw_callouts_png('clean.png', [('04_gusset', (x - crop[0], y - crop[1]))], 'out.png')

Потрібні numpy і Pillow (`tools/.venv`). SVG-варіант з мм-розкладкою підписів —
`print3d-parts/sheets/make_sheets.py`, клас `View` (той самий `spread_rows`).

Пастка: індекс i — це позиція у списку ключів, яким РЕНДЕРИЛИ. Передаси в `classify`
той самий список в іншому порядку — підписи мовчки поміняються місцями (так і сталося
на тесті: кеш рендера був у порядку assembly.tsv, список — у порядку parts.tsv). Тому
кеш рендерів має містити хеш списку ключів у назві файлу.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def hue_colors(n, s=0.85, v=0.95):
    """n рівновіддалених відтінків як RGB у 0…1 — для сцен, які фарбує сам Python
    (для OpenSCAD те саме робить `hsv()` в обгортці sheets.scad)."""
    out = []
    for i in range(n):
        h = (i * 360 / max(n, 1)) / 60
        k = int(h) % 6; f = h - int(h)
        p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
        out.append([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][k])
    return out


def classify(path, n, hi_mode=False, sat_min=0.35, val_min=0.15, bg_tol=10):
    """Мітка кожного пікселя: −1 тло (колір кутового пікселя ± bg_tol), −2 об'єкт без
    відтінку (сірий), i — деталь i за відтінком у ±180/n°. hi_mode: усе насичене = 0
    (одна підсвічена деталь на сірому тлі)."""
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(np.uint8)
    hsv = np.asarray(im.convert('HSV')).astype(float)
    H, S, V = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    bg = np.abs(a.astype(int) - a[0, 0].astype(int)).sum(-1) < bg_tol
    lab = np.full(H.shape, -2, int)
    lab[bg] = -1
    sat = (S > sat_min) & (V > val_min) & ~bg
    if hi_mode:
        lab[sat] = 0
    else:
        for i in range(n):
            d = np.abs((H - i * 360 / n + 180) % 360 - 180)
            lab[sat & (d < 180 / n)] = i
    return a, lab


def anchors(lab, n):
    """Для кожної деталі: кількість пікселів і точка НА деталі, найближча до центроїда."""
    out = []
    for i in range(n):
        ys, xs = np.nonzero(lab == i)
        if len(xs) == 0:
            out.append((0, None)); continue
        cx, cy = xs.mean(), ys.mean()
        j = np.argmin((xs - cx) ** 2 + (ys - cy) ** 2)
        out.append((int(len(xs)), (int(xs[j]), int(ys[j]))))
    return out


def finish_image(a, lab, out_path, edge_mm=0.14, pad_frac=0.05, edge_rgb=(45, 45, 45)):
    """Тло → біле, межі між деталями (де мітка сусіда інша) → темна лінія, кадр обрізаний
    до вмісту з полем pad_frac. Повертає (x0, y0, w, h) вирізки у пікселях оригіналу.
    Товщина лінії — від ширини вмісту (≈ edge_mm при кадрі 110 мм завширшки): без ліній
    на чорно-білому папері форма зникає — headless `--view=edges` нічого не малює."""
    ys, xs = np.nonzero(lab != -1)
    if len(xs) == 0:
        raise ValueError('порожній рендер: ' + out_path)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    edge = np.zeros(lab.shape, bool)
    edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edge[1:, :] |= lab[1:, :] != lab[:-1, :]
    k = max(1, round(edge_mm * (x1 - x0) / 110))
    for _ in range(k - 1):
        e2 = edge.copy()
        e2[:, 1:] |= edge[:, :-1]; e2[1:, :] |= edge[:-1, :]
        edge = e2
    out = a.copy()
    out[lab == -1] = 255
    out[edge] = edge_rgb
    px, py = int((x1 - x0) * pad_frac) + k + 2, int((y1 - y0) * pad_frac) + k + 2
    X0, X1 = max(0, x0 - px), min(out.shape[1], x1 + px + 1)
    Y0, Y1 = max(0, y0 - py), min(out.shape[0], y1 + py + 1)
    Image.fromarray(out[Y0:Y1, X0:X1]).save(out_path, optimize=True)
    return (X0, Y0, X1 - X0, Y1 - Y0)


def spread_rows(ys, step, y_max):
    """Розсунути координати підписів (відсортованих за якорем), щоб не наїжджали:
    крок ≥ step, останній не нижче y_max, після зсуву вгору — знову без наїздів."""
    ys = list(ys)
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + step)
    over = ys[-1] - y_max if ys else 0
    if over > 0:
        ys = [v - over for v in ys]
    for i in range(len(ys) - 2, -1, -1):
        ys[i] = min(ys[i], ys[i + 1] - step)
    return ys


def _font(size):
    for f in ('/System/Library/Fonts/Helvetica.ttc', '/System/Library/Fonts/Supplemental/Arial.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_callouts_png(png_path, labels, out_path, font_px=None, margin_px=None, color=(20, 20, 20)):
    """Дописати виноски на готову картинку (для постів і README, де SVG не потрібен):
    підписи ліворуч/праворуч за положенням якоря, лінія до якоря, крапка на ньому.
    labels = [(текст, (x, y) у пікселях png_path), …]. Полотно розширюється на поля."""
    im = Image.open(png_path).convert('RGB')
    W, H = im.size
    fp = font_px or max(14, W // 60)
    font = _font(fp)
    step = int(fp * 1.6)
    d0 = ImageDraw.Draw(im)
    widths = {t: d0.textlength(t, font=font) for t, _ in labels}
    left = sorted([l for l in labels if l[1][0] < W / 2], key=lambda l: l[1][1])
    right = sorted([l for l in labels if l[1][0] >= W / 2], key=lambda l: l[1][1])
    ml = int(max([widths[t] for t, _ in left], default=0) + fp) if left else 0
    mr = int(max([widths[t] for t, _ in right], default=0) + fp) if right else 0
    if margin_px is not None:
        ml, mr = (margin_px if left else 0), (margin_px if right else 0)
    canvas = Image.new('RGB', (W + ml + mr, H), 'white')
    canvas.paste(im, (ml, 0))
    d = ImageDraw.Draw(canvas)
    for side, items in (('l', left), ('r', right)):
        if not items:
            continue
        ys = spread_rows([p[1] for _, p in items], step, H - step)
        for (t, p), y in zip(items, ys):
            ax, ay = ml + p[0], p[1]
            if side == 'l':
                tx = ml - fp * 0.6 - widths[t]; lx = ml - fp * 0.4
            else:
                tx = ml + W + fp * 0.6; lx = ml + W + fp * 0.4
            d.line([(lx, y), (ax, ay)], fill=color, width=max(1, fp // 9))
            d.ellipse([ax - fp * 0.18, ay - fp * 0.18, ax + fp * 0.18, ay + fp * 0.18], fill=color)
            d.text((tx, y - fp * 0.55), t, fill=color, font=font)
    canvas.save(out_path, optimize=True)
    return canvas.size
