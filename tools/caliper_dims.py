#!/usr/bin/env python3
"""Розміри, які можна зняти ШТАНГЕНЦИРКУЛЕМ, — із силуету деталі (shapely Polygon, мм).

Габарит за осями сторінки (bbox) для повернутої чи клиноподібної деталі не міряється:
затиснеш під іншим кутом — інше число. Губки штангенциркуля — дві паралельні площини,
тож відтворюване показання дають лише такі випадки:

  flats   між двома паралельними плоскими кромками (ширина смуги, труби, сідла);
  flat    губка на плоскій кромці, друга — до найдальшої точки по перпендикуляру
          (вилка D: від рівного низу до горба; вежа F: від верхньої кромки до низу кола);
  edge    довжина прямої кромки (щоки, вилки — «купа рівних сторін»);
  end     ширина заокругленого кінця (дуга ≥ 175°): губки на дузі — як діаметр;
  length  найбільша протяжність деталі (від вістря зуба до задньої частини);
  humps   між двома горбами — локальний максимум ширини: показання найбільше в цьому
          положенні, людина знаходить його, погойдуючи деталь. Найменш точне.

Локальні мінімуми ширини опуклого контуру завжди досягаються губкою на кромці — тому
окремого типу для них немає, їх покриває `flat`/`flats`.

    from caliper_dims import dims_for
    dims = dims_for(poly, n_max=4)          # список PlacedDim у системі poly (мм)
    for d in dims: d.kind, d.value, d.line, d.exts, d.text_pos, d.text_dir

Кожен PlacedDim уже розставлений: розмірна лінія за межами деталі, виносні лінії від
точок дотику, положення тексту й напрямок (текст пишеться вздовж розмірної лінії).
"""
import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import orient

SCORE = {'flats': 4.0, 'flat': 3.0, 'length': 2.6, 'end': 2.5, 'edge': 2.0, 'humps': 1.5}
GAP, OFF, STEP, OVER = 0.5, 2.6, 3.6, 0.6     # мм: зазор від деталі, відступ лінії, крок стосу, вихід виносної
TXT = 1.2                                      # мм: текст над лінією
MAX_OUT, MAX_EXT = 0.12, 0.75                  # частка габариту: наскільки розмір може вийти за деталь / довжина виносних
                                               # (виступ посеред довгої основи, як вушко вилки D, тягне виносну на пів основи — це норма)


@dataclass
class Cand:
    kind: str
    value: float
    u: np.ndarray            # напрямок вимірювання (одиничний)
    A: np.ndarray            # точки дотику губок
    B: np.ndarray
    score: float
    edge: tuple = None       # для edge: (p0, p1, n_out)
    approx: bool = False     # показання з невеликим надлишком (кінець, що не дотягує до півкола)


@dataclass
class PlacedDim:
    kind: str
    value: float
    line: tuple              # ((x, y), (x, y)) розмірна лінія
    exts: list               # [((x, y), (x, y)), …] виносні лінії
    text_pos: tuple
    text_dir: tuple          # одиничний вектор уздовж тексту
    text: str = ''
    pts: list = field(default_factory=list)   # усі точки для габариту


def _fmt(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def _ring(poly, tol=0.03):
    """Зовнішній контур проти годинникової стрілки, без колінеарних вершин."""
    r = orient(poly, 1.0).exterior.simplify(tol)
    return np.array(r.coords[:-1], float)


def _edges(pts, poly, min_len):
    hull = poly.convex_hull.exterior
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        d = p1 - p0
        L = float(np.hypot(*d))
        if L < min_len:
            continue
        t = d / L
        nrm = np.array([t[1], -t[0]])                     # зовнішня нормаль для CCW
        mid = (p0 + p1) / 2
        on_hull = all(hull.distance(Point(p)) < 0.2 for p in (p0, p1, mid))
        out.append(dict(p0=p0, p1=p1, t=t, n=nrm, L=L, hull=on_hull))
    return out


def _fit_circle(P):
    """Алгебраїчна підгонка кола (Kåsa): центр, радіус, найбільший відхил."""
    x, y = P[:, 0], P[:, 1]
    A = np.column_stack([x, y, np.ones(len(P))])
    b = -(x ** 2 + y ** 2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = -sol[0] / 2, -sol[1] / 2
    r2 = cx ** 2 + cy ** 2 - sol[2]
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    dev = np.abs(np.hypot(x - cx, y - cy) - r).max()
    return np.array([cx, cy]), r, dev


def _arcs(pts, min_len, short=3.0):
    """Дуги = серії коротких сегментів між довгими кромками. Повертає (центр, r, розмах°,
    бісектриса, кінці). Починаємо обхід із довгого сегмента, щоб дуга не рвалася на стику."""
    n = len(pts)
    L = [float(np.hypot(*(pts[(i + 1) % n] - pts[i]))) for i in range(n)]
    long_idx = [i for i in range(n) if L[i] >= short]
    if not long_idx:
        return []
    start = long_idx[0]
    order = [(start + k) % n for k in range(n)]
    runs, cur = [], []
    for i in order:
        if L[i] < short:
            cur.append(i)
        else:
            if len(cur) >= 6:
                runs.append(cur)
            cur = []
    if len(cur) >= 6:
        runs.append(cur)
    out = []
    for run in runs:
        idx = run + [(run[-1] + 1) % n]                    # вершини дуги: початки сегментів + кінець
        P = pts[idx]
        fit = _fit_circle(P)
        if fit is None:
            continue
        c, r, dev = fit
        if dev > 0.08 * max(r, 1) + 0.05 or r < 1.5:
            continue
        ang = np.unwrap(np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]))
        span = math.degrees(abs(ang[-1] - ang[0]))
        mid = (ang[0] + ang[-1]) / 2
        out.append(dict(c=c, r=r, span=span, bis=np.array([math.cos(mid), math.sin(mid)]), ends=(P[0], P[-1])))
    return out


def _widths(poly, step_deg=1.0):
    H = np.array(poly.convex_hull.exterior.coords[:-1], float)
    th = np.radians(np.arange(0, 180, step_deg))
    U = np.stack([np.cos(th), np.sin(th)], 1)
    P = H @ U.T
    return U, P.max(0) - P.min(0), H[P.argmax(0)], H[P.argmin(0)]


def candidates(poly):
    pts = _ring(poly)
    b = poly.bounds
    extent = max(b[2] - b[0], b[3] - b[1])
    min_len = max(5.0, 0.06 * extent)                 # торець труби 20 мм при довжині 210 — теж опора
    edges = _edges(pts, poly, min_len)
    longest = max((e['L'] for e in edges if e['hull']), default=0)
    cands = []
    # --- кромки: довжина (edge) і перпендикуляр до найдальшої точки (flat / flats)
    for e in edges:
        pen = 0 if e['hull'] else -1.2
        rel = min(1.0, e['L'] / extent)                    # довгі кромки — перше, що міряють
        first = 0.6 if e['hull'] and e['L'] >= longest - 1e-6 else 0   # найдовша плоска сторона — завжди
        cands.append(Cand('edge', e['L'], e['t'].copy(), e['p0'], e['p1'], SCORE['edge'] + 1.5 * rel + first + pen, (e['p0'], e['p1'], e['n'])))
        u = -e['n']
        # --- паралельна кромка навпроти, з перекриттям уздовж t: ширина між двома площинами.
        # Дотик — на самих кромках, тому виступ поруч (голівка пальця, друга половина
        # щоки) не заважає: губки стають там, де кромки перекриваються.
        par = None
        tx = (pts - e['p0']) @ e['t']
        for e2 in edges:
            if e2 is e or np.dot(e2['n'], e['n']) > -0.999:
                continue
            s0, s1 = sorted([float((e2['p0'] - e['p0']) @ e['t']), float((e2['p1'] - e['p0']) @ e['t'])])
            o0, o1 = max(0.0, s0), min(e['L'], s1)
            if o1 - o0 < 3:
                continue
            dist = float((e2['p0'] - e['p0']) @ u)
            if dist > 0.5 and (par is None or dist < par[0]):
                # дотик — на тому кінці перекриття, що ближчий до краю деталі (коротші виносні)
                tm = o0 if (o0 - tx.min()) < (tx.max() - o1) else o1
                par = (dist, tm)
        if par is not None:
            dist, tm = par
            A = e['p0'] + e['t'] * tm
            cands.append(Cand('flats', dist, u, A, A + u * dist, SCORE['flats'] + 0.8 * rel + pen))
        # --- найдальша точка по перпендикуляру: губка на кромці, друга — до неї
        proj = (pts - e['p0']) @ u
        j = int(proj.argmax())
        val = float(proj[j])
        if val < 1.0 or (par is not None and val > par[0] + 0.2):
            continue                                        # далі за паралельну площину лише виступ
        far = pts[j]
        tA = float(tx[j])
        A = e['p0'] if abs(tA) < abs(tA - e['L']) else e['p1']
        # найдальша точка далеко збоку від кромки (не «над» нею) — губка на кромці, а друга
        # десь у стороні: знімається, але незручно і ні про що не каже
        aside = -0.8 if (tA < -0.25 * e['L'] or tA > 1.25 * e['L']) else 0
        reach = -0.6 if val > 4 * e['L'] else 0             # коротка опора, далекий дотик — хитко
        cands.append(Cand('flat', val, u, A, far, SCORE['flat'] + 0.8 * rel + aside + reach + pen))
    # --- заокруглені кінці. Розмах дуги міряється між крайніми вершинами після спрощення
    # контуру, тож справжні 180° виглядають як ≈172°; кінець, що не дотягує до півкола,
    # губки вимірюють з невеликим надлишком (дотик ковзає на дотичні кромки) — це «≈».
    for a in _arcs(pts, min_len):
        if a['span'] < 165:
            continue
        u = np.array([-a['bis'][1], a['bis'][0]])
        c = Cand('end', 2 * a['r'], u, a['c'] - a['r'] * u, a['c'] + a['r'] * u, SCORE['end'])
        c.approx = a['span'] < 178
        cands.append(c)
    # --- ширина опуклої оболонки за напрямком: найбільша і локальні максимуми
    U, w, Pmax, Pmin = _widths(poly)
    k = len(w)
    imax = int(w.argmax())
    extent = float(w[imax])                                # справжня довжина, а не габарит за осями
    cands.append(Cand('length', extent, U[imax], Pmin[imax], Pmax[imax], SCORE['length']))
    for i in range(k):
        if i == imax:
            continue
        if not (w[i] > w[i - 1] and w[i] >= w[(i + 1) % k]):
            continue
        lo = min(w[(i + d) % k] for d in range(-30, 31))
        if w[i] - lo < 0.5 or w[i] < 0.25 * w[imax]:
            continue
        cands.append(Cand('humps', float(w[i]), U[i], Pmin[i], Pmax[i], SCORE['humps']))
    return cands, extent


def _same_dir(u1, u2, tol_deg=15):
    return abs(np.dot(u1, u2)) > math.cos(math.radians(tol_deg))


def select(cands, extent, n_max=None):
    """Найкращі за оцінкою, без дублів (той самий розмір у тому ж напрямку), і так, щоб
    були обидва напрямки — «довжина» і «ширина», якщо такі кандидати є."""
    if n_max is None:
        n_max = 5 if extent >= 60 else 4 if extent >= 30 else 3
    # «Найбільша протяжність» і «між горбами» потрібні лише там, де в цьому напрямку
    # немає вимірювання від плоскої кромки: діагональ прямокутника — теж найбільше
    # показання, але її ніхто не міряє, коли є дві плоскі сторони.
    firm = [c for c in cands if c.kind in ('flat', 'flats')]

    def is_diagonal(c):
        """Протяжність, що дорівнює гіпотенузі двох плоских розмірів, — діагональ."""
        for i, f1 in enumerate(firm):
            for f2 in firm[i + 1:]:
                if not _same_dir(f1.u, f2.u, 60) and abs(math.hypot(f1.value, f2.value) - c.value) < 0.02 * c.value + 0.3:
                    return True
        return False

    cands = [c for c in cands if c.kind not in ('length', 'humps')
             or not (any(_same_dir(c.u, f.u, 25) for f in firm) or is_diagonal(c))]
    cands = sorted(cands, key=lambda c: -c.score)
    # Те саме число вдруге нічого не додає: дзеркальні сторони вилки, обидві половини
    # щоки шириною 28 — досить одного напису. Довжина кромки і ширина від кромки — різні
    # речі, окрім випадку, коли вони збігаються і напрямком (прямокутник).
    kept = []
    for c in cands:
        cls = 'edge' if c.kind == 'edge' else 'width'
        dup = False
        for k in kept:
            if abs(c.value - k.value) >= max(0.3, 0.015 * c.value):  # 67 і 67.6 — одне й те саме
                continue
            kcls = 'edge' if k.kind == 'edge' else 'width'
            if cls == kcls or _same_dir(c.u, k.u):
                dup = True; break
        if not dup:
            kept.append(c)
    # Повертається ВЕСЬ упорядкований список: розставляння може відкинути кандидата (лінія
    # вилазить за габарит), і тоді наступний за оцінкою займе його місце. Поперечний до
    # довжини розмір («ширина») просувається у перші n_max, якщо його там немає.
    longest = next((c for c in kept if c.kind == 'length'), None)
    if longest is not None and len(kept) > n_max:
        fam = np.array([-longest.u[1], longest.u[0]])
        if not any(_same_dir(c.u, fam, 30) for c in kept[:n_max]):
            alt = next((c for c in kept[n_max:] if _same_dir(c.u, fam, 30)), None)
            if alt is not None:
                kept.remove(alt); kept.insert(n_max - 1, alt)
    return kept, n_max


def place(chosen, poly, n_max=None):
    """Розставити розмірні лінії за межами деталі без наїздів одна на одну — за порядком
    списку, поки не набереться n_max. Найбільша протяжність (`length`), якщо пережила
    фільтри (не діагональ, не дубль плоского розміру), ставиться понад ліміт: від вістря
    зуба до задньої частини — перше, що міряють."""
    pts_all = np.array(poly.exterior.coords)
    bx0, by0, bx1, by1 = poly.bounds
    extent = max(bx1 - bx0, by1 - by0)
    max_out, max_ext = max(9.0, MAX_OUT * extent), max(20.0, MAX_EXT * extent)
    placed = []

    def inside(pts):
        """Похила розмірна лінія на довгій деталі вилазить за габарит на десятки мм (у труби
        розмір від косого торця тягнувся на 58 мм убік) — такий розмір не ставимо."""
        return all(bx0 - max_out <= p[0] <= bx1 + max_out and by0 - max_out <= p[1] <= by1 + max_out for p in pts)

    def clear_of(line_pts, dirn):
        """Чи не лягає нова лінія на вже поставлену (майже) паралельну: відстань між
        відрізками — не в одній точці, а найменша по всій довжині (похилі лінії сходяться),
        і підписи не ближче 4 мм."""
        seg = LineString([tuple(line_pts[0]), tuple(line_pts[1])])
        tmid = (np.array(line_pts[0]) + np.array(line_pts[1])) / 2
        for p in placed:
            q0, q1 = np.array(p.line[0]), np.array(p.line[1])
            d = q1 - q0
            if np.hypot(*d) < 1e-6 or not _same_dir(d / np.hypot(*d), dirn, 25):
                continue
            if seg.distance(LineString([p.line[0], p.line[1]])) < 3.2:
                return False
            if np.hypot(*(tmid - np.array(p.text_pos))) < 4.0:
                return False
        return True

    for c in chosen:
        if n_max is not None and len(placed) >= n_max and c.kind != 'length':
            continue
        text = ('≈' if c.approx else '') + _fmt(c.value)
        if c.kind == 'edge':
            p0, p1, n = c.edge
            t = c.u
            # Назовні, а якщо зовні заважає сама деталь (кромка у вирізі — нижні кромки щоки
            # перелому сходяться кутом) — усередину, по деталі: для пластини це звично.
            for off in [OFF + i * STEP for i in range(4)] + [-(OFF + i * STEP) for i in range(2)]:
                l0, l1 = p0 + n * off, p1 + n * off
                seg = LineString([l0, l1])
                ok = poly.contains(seg) if off < 0 else (not seg.crosses(poly) and not poly.contains(seg))
                if ok and clear_of((l0, l1), t):
                    break
            else:
                continue
            sgn = 1 if off > 0 else -1
            a = abs(off)
            exts = [(tuple(p0 + n * sgn * GAP), tuple(p0 + n * sgn * (a + OVER))), (tuple(p1 + n * sgn * GAP), tuple(p1 + n * sgn * (a + OVER)))]
            tp = (p0 + p1) / 2 + n * sgn * (a + TXT)
            pts = [l0, l1, tp + t * (len(text) * 0.6), tp - t * (len(text) * 0.6), tp + n * sgn * 1.1]
            if not inside(pts):
                continue
            placed.append(PlacedDim(c.kind, c.value, (tuple(l0), tuple(l1)), exts, tuple(tp), tuple(t), text, pts))
            continue
        u = c.u
        v = np.array([-u[1], u[0]])
        pv = pts_all @ v
        vmin, vmax = float(pv.min()), float(pv.max())
        vA, vB = float(c.A @ v), float(c.B @ v)
        # бік, де виносні лінії коротші
        side = 1 if (vmax - max(vA, vB)) <= (min(vA, vB) - vmin) else -1
        off = OFF
        for _ in range(4):
            vd = (vmax + off) if side > 0 else (vmin - off)
            PA = c.A + (vd - vA) * v
            PB = c.B + (vd - vB) * v
            if clear_of((PA, PB), u):
                break
            off += STEP
        if max(abs(vd - vA), abs(vd - vB)) > max_ext:      # довгі виносні = розмір «десь збоку»
            continue
        exts = []
        for P, Q in ((c.A, PA), (c.B, PB)):
            sgn = 1 if (Q - P) @ v > 0 else -1
            if abs((Q - P) @ v) > GAP + 0.1:
                exts.append((tuple(P + v * sgn * GAP), tuple(Q + v * sgn * OVER)))
        tp = (PA + PB) / 2 + v * side * TXT
        pts = [PA, PB, tp + u * (len(text) * 0.6), tp - u * (len(text) * 0.6), tp + v * side * 1.1]
        if not inside(pts):
            continue
        placed.append(PlacedDim(c.kind, c.value, (tuple(PA), tuple(PB)), exts, tuple(tp), tuple(u), text, pts))
    return placed


def dims_for(poly, n_max=None):
    cands, extent = candidates(poly)
    kept, n_max = select(cands, extent, n_max)
    return place(kept, poly, n_max)


def bounds_with(poly, dims):
    """Габарит деталі разом з розмірами (для комірки)."""
    xs = [poly.bounds[0], poly.bounds[2]]
    ys = [poly.bounds[1], poly.bounds[3]]
    for d in dims:
        for p in d.pts:
            xs.append(float(p[0])); ys.append(float(p[1]))
    return min(xs), min(ys), max(xs), max(ys)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, __import__('os').path.dirname(__file__))
    from stl_mesh import read_stl, silhouette
    for path in sys.argv[1:]:
        poly = silhouette(read_stl(path))
        print(path, '(у друкованій орієнтації, без укладання пальців)')
        for d in dims_for(poly):
            print(f'   {d.kind:7s} {d.value:7.2f}  напрямок {math.degrees(math.atan2(d.text_dir[1], d.text_dir[0])):6.1f}°')
