#!/usr/bin/env python3
"""
bom_drawings.py — специфікація (BOM), DXF 1:1 та PDF-ескізи з основними розмірами для всіх деталей стріли/рукояті.

Єдине джерело правди — scad/excavator_boom.scad:
  * списки BOM_* модель друкує через echo() (пластини, смуги, труби, втулки, пальці, параметри);
  * контур кожної пластини модель сама проєктує на площину (part="flat"), тут він лише читається з SVG:
    габарит, отвори (центр, діаметр), площа → маса.
Вихід (у теці --out): bom/bom.md, bom/bom.csv, dxf/<деталь>.dxf, drawings/parts.pdf
Запуск: tools/bom_drawings.sh [--out ТЕКА]
"""
import subprocess, json, re, os, sys, math, argparse, csv, tempfile, datetime, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAD = os.path.join(ROOT, 'scad', 'excavator_boom.scad')
RHO = 7.85e-6          # кг/мм³
PLATE_MAT = 'S235JR (Ст3сп)'
TUBE_MAT = 'Ст3сп/пс або S235JRH (ДСТУ 8940), не кп'

def openscad(out, *defs):
    cmd = ['openscad', '-o', out]
    for d in defs: cmd += ['-D', d]
    subprocess.run(cmd + [SCAD], check=True, capture_output=True)

def read_bom_echo():
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, 'bom.echo'); openscad(f)
        out = {}
        for line in open(f, encoding='utf-8'):
            m = re.match(r'ECHO: (BOM_\w+) = (.*)$', line.strip())
            if m: out[m.group(1)] = json.loads(m.group(2))
    return out

# ---------------------------------------------------------------- геометрія контурів
def parse_svg_loops(path):
    d = re.search(r'<path d="([^"]+)"', open(path).read(), re.S).group(1)
    loops, cur = [], []
    for tok in re.findall(r'([MLz])\s*([-\d.eE]+)?,?([-\d.eE]+)?', d):
        if tok[0] in 'ML':
            if tok[0] == 'M' and cur: loops.append(cur); cur = []
            cur.append((float(tok[1]), -float(tok[2])))       # SVG: вісь Y униз
        elif tok[0] == 'z' and cur: loops.append(cur); cur = []
    if cur: loops.append(cur)
    return loops

def area(pts): return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))

def as_circle(pts):
    if len(pts) < 12: return None
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    rs = [math.hypot(p[0] - cx, p[1] - cy) for p in pts]; r = sum(rs) / len(rs)
    if max(abs(x - r) for x in rs) > 0.02 * r + 0.05: return None
    # діаметр за площею багатокутника точніший для малого $fn; беремо описаний радіус (вершини лежать на колі)
    return (cx, cy, 2 * max(rs))

def analyse(loops):
    loops = sorted(loops, key=lambda l: -abs(area(l)))
    outer, inner = loops[0], loops[1:]
    xs = [p[0] for p in outer]; ys = [p[1] for p in outer]
    x0, y0 = min(xs), min(ys)
    sh = lambda l: [(p[0] - x0, p[1] - y0) for p in l]
    outer = sh(outer); inner = [sh(l) for l in inner]
    holes = []
    for l in inner:
        c = as_circle(l)
        holes.append(dict(circle=c, pts=l))
    net = abs(area(outer)) - sum(abs(area(l)) for l in inner)
    return dict(outer=outer, holes=holes, W=max(xs) - x0, H=max(ys) - y0, area=net)


fmt = lambda v: (f'{abs(v):.1f}').rstrip('0').rstrip('.')

def dim(ax, p0, p1, text, color='tab:blue'):
    """Розмірна лінія довільного напрямку з підписом уздовж неї."""
    ax.annotate('', p0, p1, arrowprops=dict(arrowstyle='<->', lw=0.8, color=color, shrinkA=0, shrinkB=0))
    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    if ang > 90: ang -= 180
    if ang <= -90: ang += 180
    ax.text((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, text, rotation=ang, rotation_mode='anchor', ha='center', va='bottom', fontsize=8.5, color=color)

def straight_edges(outer, min_len=20.0, tol_deg=0.6):
    """Прямі кромки зовнішнього контуру (дуги розпадаються на короткі відрізки й відсіюються)."""
    n = len(outer)
    seg = lambda i: (outer[i % n], outer[(i + 1) % n])
    ang = lambda i: math.atan2(seg(i)[1][1] - seg(i)[0][1], seg(i)[1][0] - seg(i)[0][0])
    dif = lambda a, b: abs((a - b + math.pi) % (2 * math.pi) - math.pi)
    start = next((i for i in range(n) if dif(ang(i - 1), ang(i)) > math.radians(tol_deg)), 0)
    edges, p0, prev = [], outer[start], ang(start)
    for k in range(1, n + 1):
        i = (start + k) % n
        if k == n or dif(ang(i), prev) > math.radians(tol_deg):
            edges.append((p0, outer[i])); p0 = outer[i]
        prev = ang(i)
    return [e for e in edges if math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]) >= min_len]

def concentric_R(c, outer):
    ds = [math.hypot(p[0] - c[0], p[1] - c[1]) for p in outer]; best = None
    for r in sorted(set(round(x, 1) for x in ds)):
        cnt = sum(1 for x in ds if abs(x - r) < 0.3)
        if cnt >= 8 and (best is None or cnt > best[1]): best = (r, cnt)
    return best[0] if best else None

def hole_refs(g):
    """Прив'язки отворів: базовий отвір (найбільший) → до баз A (найдовша пряма кромка) і B (найближча ⟂ кромка)
    або вздовж A від її кінця; інші отвори → до базового вздовж/поперек A; + концентричність заокругленням контуру."""
    circ = sorted([h['circle'] for h in g['holes'] if h['circle']], key=lambda c: -c[2])
    g['circ'] = circ; R = dict(dims=[], table=[])
    if not circ: R['table'] = ['Отворів немає.']; return R
    L = lambda e: math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1])
    def foot(e, c):
        u = ((e[1][0] - e[0][0]) / L(e), (e[1][1] - e[0][1]) / L(e)); t = (c[0] - e[0][0]) * u[0] + (c[1] - e[0][1]) * u[1]
        fp = (e[0][0] + u[0] * t, e[0][1] + u[1] * t); return fp, t, math.hypot(c[0] - fp[0], c[1] - fp[1]), u
    edges = straight_edges(g['outer']); c0 = circ[0]
    conc = [concentric_R(c, g['outer']) for c in circ]
    R['table'].append('Прив\'язки отворів (A, B — кромки-бази на ескізі):')
    A = max(edges, key=lambda e: L(e) * (1.0 if foot(e, c0)[2] >= 0.75 * c0[2] else 0.1), default=None)
    line = f'  1: Ø{fmt(c0[2])} (базовий)'
    if A:
        R['A'] = A; fp, t, dA, u = foot(A, c0)
        ext = None if -1e-6 <= t <= L(A) + 1e-6 else ((A[0] if t < 0 else A[1]), fp)
        R['dims'].append((fp, (c0[0], c0[1]), fmt(dA), 'tab:green', ext)); line += f' — від A: {fmt(dA)}'
        perp = [e for e in edges if e is not A and abs(abs(e_dot(e, A)) ) < math.sin(math.radians(15))]
        if perp:
            B = min(perp, key=lambda e: foot(e, c0)[2]); R['B'] = B; fb, tb, dB, _ = foot(B, c0)
            extb = None if -1e-6 <= tb <= L(B) + 1e-6 else ((B[0] if tb < 0 else B[1]), fb)
            R['dims'].append((fb, (c0[0], c0[1]), fmt(dB), 'tab:olive', extb)); line += f'; від B: {fmt(dB)}'
        else:
            end = A[0] if t <= L(A) / 2 else A[1]; along = min(abs(t), abs(L(A) - t))
            n = (-u[1], u[0]); sgn = -1 if ((c0[0] - fp[0]) * n[0] + (c0[1] - fp[1]) * n[1]) > 0 else 1   # винести назовні від деталі
            off = (n[0] * sgn * 14, n[1] * sgn * 14)
            R['dims'].append(((end[0] + off[0], end[1] + off[1]), (fp[0] + off[0], fp[1] + off[1]), fmt(along), 'tab:green', None))
            line += f'; уздовж A від її кінця: {fmt(along)}'
    if conc[0]: line += f'; концентр. R{fmt(conc[0])}'
    R['table'].append(line)
    u = foot(A, c0)[3] if A else (1.0, 0.0); n = (-u[1], u[0])
    for i, c in enumerate(circ[1:], start=2):
        dx = (c[0] - c0[0]) * u[0] + (c[1] - c0[1]) * u[1]; dy = (c[0] - c0[0]) * n[0] + (c[1] - c0[1]) * n[1]
        m = (c0[0] + u[0] * dx, c0[1] + u[1] * dx)
        if abs(dx) > 0.05: R['dims'].append(((c0[0], c0[1]), m, fmt(dx), 'tab:purple', None))
        if abs(dy) > 0.05: R['dims'].append((m, (c[0], c[1]), fmt(dy), 'tab:purple', None))
        line = f'  {i}: Ø{fmt(c[2])} — від отвору 1: уздовж A {fmt(dx)}, поперек {fmt(dy)}; міжосьова {fmt(math.hypot(dx, dy))}'
        if conc[i - 1]: line += f'; концентр. R{fmt(conc[i - 1])}'
        R['table'].append(line)
    if not A: R['table'].append('  (прямих кромок немає — отвір концентричний зовнішньому контуру)')
    return R

def e_dot(e1, e2):
    l1 = math.hypot(e1[1][0] - e1[0][0], e1[1][1] - e1[0][1]); l2 = math.hypot(e2[1][0] - e2[0][0], e2[1][1] - e2[0][1])
    return ((e1[1][0] - e1[0][0]) * (e2[1][0] - e2[0][0]) + (e1[1][1] - e1[0][1]) * (e2[1][1] - e2[0][1])) / (l1 * l2)

# ---------------------------------------------------------------- PDF
def make_pdf(path, bom, flats, tubes, version):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Polygon, Circle
    P = dict(bom['BOM_PARAMS'])
    A4 = (11.69, 8.27)
    # Аркуші й DXF фізично йдуть у цех різання окремо від репозиторію — застереження має бути на них самих.
    WARN = 'УВАГА: згенеровано ШІ, інженером не перевірено, машину не випробувано — використання на власний ризик; див. SAFETY.md'
    png_dir = os.path.join(os.path.dirname(path), 'png'); os.makedirs(png_dir, exist_ok=True); cnt = [0]
    def save(pdf, fig, name):
        cnt[0] += 1; pdf.savefig(fig); fig.savefig(os.path.join(png_dir, f'{cnt[0]:02d}_{name}.png'), dpi=90); plt.close(fig)
    def page(title, sub=''):
        fig = plt.figure(figsize=A4); ax = fig.add_axes([0.06, 0.10, 0.88, 0.66]); ax.set_aspect('equal'); ax.axis('off')
        fig.text(0.06, 0.93, title, fontsize=15, weight='bold'); fig.text(0.06, 0.895, sub, fontsize=10)
        fig.text(0.06, 0.04, f'Стріла міні-екскаватора · {version} · ескіз не в масштабі, розміри в мм; для різання пластин — DXF 1:1\n{WARN}', fontsize=8, color='0.35')
        return fig, ax
    def dim_h(ax, x0, x1, y, text, off=0):
        ax.annotate('', (x0, y), (x1, y), arrowprops=dict(arrowstyle='<->', lw=0.8, color='tab:blue'))
        ax.text((x0 + x1) / 2, y + off, text, ha='center', va='bottom', fontsize=9, color='tab:blue')
    def dim_v(ax, x, y0, y1, text):
        ax.annotate('', (x, y0), (x, y1), arrowprops=dict(arrowstyle='<->', lw=0.8, color='tab:blue'))
        ax.text(x, (y0 + y1) / 2, text + ' ', ha='right', va='center', fontsize=9, color='tab:blue', rotation=90)
    # Специфікація росте з моделлю, тому аркуш не фіксований: довгі рядки переносяться, список ділиться на сторінки.
    # Ширину підібрано за відбитком: у рядках є «→», «—», «×», яких немає у моноширинному шрифті, і підставлені
    # з пропорційного вони ширші за знакомісце, тому 140+ знаків вилазять за аркуш. 120 тримається із запасом.
    def text_page(pdf, title, lines, per_page=44, width=120):
        wrapped = []
        for ln in lines:
            if len(ln) <= width: wrapped.append(ln); continue
            pad = ' ' * (len(ln) - len(ln.lstrip()) + 2)          # продовження — з відступом під колонку опису
            wrapped += textwrap.wrap(ln, width, subsequent_indent=pad) or ['']
        pages = [wrapped[i:i + per_page] for i in range(0, len(wrapped), per_page)] or [[]]
        for n, chunk in enumerate(pages, 1):
            fig = plt.figure(figsize=A4)
            fig.text(0.06, 0.93, title if len(pages) == 1 else f'{title} ({n}/{len(pages)})', fontsize=15, weight='bold')
            fig.text(0.06, 0.88, '\n'.join(chunk), fontsize=8.5, family='DejaVu Sans Mono', va='top')
            fig.text(0.06, 0.04, f'Стріла міні-екскаватора · {version}\n{WARN}', fontsize=8, color='0.35')
            save(pdf, fig, 'bom' if len(pages) == 1 else f'bom{n}')

    with PdfPages(path) as pdf:
        # --- 1. зведена специфікація
        L = ['ТРУБИ (' + TUBE_MAT + ')']
        for k, h, w, t, ln, note in bom['BOM_TUBES']: L += [f'  {k:<10} {h}×{w}×{t}  L={ln:>5} мм   {note}']
        L += ['', f'ПЛАСТИНИ КОНТУРНІ ({PLATE_MAT}) — окремі аркуші далі + DXF']
        for f in flats: L += [f"  {f['key']:<13} {f['qty']} шт  t={f['t']:>2}  габарит {f['W']:.0f}×{f['H']:.0f}  маса {f['mass']:.2f} кг/шт   {f['name']}"]
        L += ['', f'СМУГИ / ПРЯМОКУТНІ ПЛАСТИНИ ({PLATE_MAT})']
        for k, q, ln, w, t, name in bom['BOM_STRIPS']: L += [f'  {k:<13} {q} шт  {ln:.0f}×{w:.0f}×{t:.0f}   {name}']
        L += ['', 'ЗНОСОСТІЙКІ ДЕТАЛІ КОВША (Hardox 400/450, 65Г, 30ХГСА — не Ст3)']
        for k, q, ln, w, t, name in bom.get('BOM_WEAR', []): L += [f'  {k:<13} {q} шт  {ln:.0f}×{w:.0f}×{t:.0f}   {name}']
        L += ['', 'ВТУЛКИ, БОБИШКИ, ШАЙБИ (труба/круг; OD×ID×L)']
        for k, q, od, idd, ln, name in bom['BOM_ROUND']: L += [f'  {k:<13} {q} шт  Ø{od:g}×Ø{idd:g}×{ln:g}   {name}']
        L += ['', 'ПАЛЬЦІ (шкворні 45Х ТВЧ або 40Х покращена; посадка H8/f7)']
        for k, q, d, ln, name in bom['BOM_PINS']: L += [f'  {k:<13} {q} шт  Ø{d:g}×{ln:g}   {name}']
        text_page(pdf, 'Специфікація деталей', L)

        # --- 2. труби: розгортка з 4 боків (контури стінок проєктує сама модель: косі різи, скіс торця, отвори)
        FACES = [('top', 'Верхня полиця', 'w'), ('left', 'Ліва стінка (вид збоку; верх труби вгорі)', 'h'), ('bottom', 'Нижня полиця', 'w'), ('right', 'Права стінка', 'h')]
        for tb in tubes:
            nom = dict(h=tb['h'], w=tb['w'])
            fig = plt.figure(figsize=A4)
            fig.text(0.06, 0.93, f"{tb['key']} — труба {tb['h']:g}×{tb['w']:g}×{tb['t']:g}, заготовка {tb['L']:g} мм: розгортка з 4 боків", fontsize=15, weight='bold')
            fig.text(0.06, 0.895, tb['note'], fontsize=9.5)
            fig.text(0.06, 0.872, f'{TUBE_MAT}. База розмірів по довжині — крайній задній торець труби (x = 0), однакова для всіх чотирьох стінок.\nСірі числа — відступ початку/кінця стінки від бази та від протилежного торця; отвори — ланцюжком від бази і від нижньої кромки своєї стінки.', fontsize=8.5, color='0.25', va='top')
            fig.text(0.06, 0.04, f'Стріла міні-екскаватора · {version} · ескіз не в масштабі між аркушами, розміри в мм\n{WARN}', fontsize=8, color='0.35')
            # один спільний масштаб на аркуш: k мм/дюйм — за довжиною АБО за сумарною висотою стінок + місце під підписи
            X1 = tb['X1']; W_in, H_in, S_in, L_in = 0.86 * A4[0], 0.70 * A4[1], 0.66, 0.55
            k = max(X1 / (W_in - L_in - 0.35), sum(nom[hk] for _, _, hk in FACES) / (H_in - S_in * len(FACES)))
            ax = fig.add_axes([0.08, 0.09, 0.86, 0.70]); ax.axis('off'); ax.set_xlim(-L_in * k, (W_in - L_in) * k); ax.set_ylim(0, H_in * k)
            ycur = H_in * k
            for (face, title, hk) in FACES:
                Hn = nom[hk]; F = tb['faces'][face]; xs, xe = F['x0'], F['x1']
                ytitle = ycur - 0.10 * k; oy = ycur - 0.27 * k - Hn; ydim = oy - 0.20 * k; ycur = oy - 0.39 * k
                ax.add_patch(Polygon([(x, y + oy) for x, y in F['outer']], fill=True, fc='0.93', ec='k', lw=1.3))
                ax.text(-L_in * k, ytitle, title, fontsize=9, weight='bold', va='top')
                # відступи < 2 мм — артефакт заокруглених кутів труби у вирізаному шарі стінки, не показуємо
                if xs > 2: dim(ax, (0, ydim), (xs, ydim), fmt(round(xs)), 'tab:gray')
                dim(ax, (xs, ydim), (xe, ydim), fmt(round(xe - xs)))
                if X1 - xe > 2: dim(ax, (xe, ydim), (X1, ydim), fmt(round(X1 - xe)), 'tab:gray')
                dim(ax, (-0.22 * k, oy), (-0.22 * k, oy + Hn), fmt(Hn))
                prev = 0.0
                for (cx, cy, d) in sorted(F['circ']):
                    ax.add_patch(Circle((cx, cy + oy), d / 2, fc='w', ec='k', lw=1.2))
                    ax.plot([cx - d * .7, cx + d * .7], [cy + oy, cy + oy], 'k-.', lw=.4); ax.plot([cx, cx], [cy + oy - d * .7, cy + oy + d * .7], 'k-.', lw=.4)
                    dim(ax, (prev, cy + oy), (cx, cy + oy), fmt(cx - prev), 'tab:green'); dim(ax, (cx, oy), (cx, cy + oy), fmt(cy), 'tab:green')
                    ax.text(cx + d / 2 + 0.06 * k, cy + oy + d * 0.28, f'Ø{fmt(d)} наскрізь', fontsize=8.5, color='tab:red', va='bottom'); prev = cx
            save(pdf, fig, tb['key'])

        # --- 2б. розгортка обичайки ковша: лінії початку/кінця гнуття від бази (кромка губи)
        if 'BOM_SHELL' in bom:
            w_in, t_sh, segs = bom['BOM_SHELL']; total = sum(v for _, v in segs)
            fig, ax = page(f'bk_shell — обичайка ковша: розгортка {total:.0f} × {w_in:g} мм, t = {t_sh:g}',
                           f'{PLATE_MAT}. База — кромка губи (x = 0). Довжини — по нейтральній лінії (середина товщини).')
            fig.text(0.06, 0.865, 'Гнути/вальцювати всередину (до порожнини ковша) за шаблоном-боковиною; зони гнуття зафарбовано. Потім обварити з боковинами суцільним швом.', fontsize=8.5, color='0.25')
            ax.add_patch(Polygon([(0, 0), (total, 0), (total, w_in), (0, w_in)], fill=True, fc='0.93', ec='k', lw=1.4))
            x = 0.0
            for i, (nm, ln) in enumerate(segs):
                bend = nm.startswith('гнуття')
                if bend: ax.add_patch(Polygon([(x, 0), (x + ln, 0), (x + ln, w_in), (x, w_in)], fill=True, fc='#f4d9a0', ec='tab:red', lw=0.8, ls='--'))
                ax.text(x + ln / 2, w_in * (0.62 if i % 2 else 0.38), f'{nm}\n{ln:.0f}', ha='center', va='center', fontsize=8.5, rotation=90 if ln < 120 else 0, color='tab:red' if bend else 'k')
                dim(ax, (x, -w_in * 0.10), (x + ln, -w_in * 0.10), fmt(round(ln)))
                if i: dim(ax, (0, -w_in * (0.22 + 0.09 * i)), (x, -w_in * (0.22 + 0.09 * i)), fmt(round(x)), 'tab:green')
                x += ln
            dim(ax, (0, -w_in * 0.70), (total, -w_in * 0.70), fmt(round(total))); dim(ax, (-total * 0.05, 0), (-total * 0.05, w_in), fmt(w_in))
            ax.set_xlim(-total * 0.12, total * 1.04); ax.set_ylim(-w_in * 0.85, w_in * 1.1); save(pdf, fig, 'bk_shell')

        # --- 3. контурні пластини: отвори прив'язані до логічних кромок (бази A, B) або до базового отвору
        for f in flats:
            fig, ax = page(f"{f['key']} — {f['name']}", f"{f['qty']} шт · t = {f['t']} мм · {PLATE_MAT} · габарит {f['W']:.1f} × {f['H']:.1f} мм · маса {f['mass']:.2f} кг/шт · DXF: dxf/{f['key']}.dxf")
            ax.add_patch(Polygon(f['outer'], fill=True, fc='0.93', ec='k', lw=1.4))
            W, H = f['W'], f['H']; pad = max(W, H) * 0.06
            for hle in f['holes']:
                if not hle['circle']: ax.add_patch(Polygon(hle['pts'], fc='w', ec='k', lw=1.0))
            for c in f['circ']:
                cx, cy, d = c
                ax.add_patch(Circle((cx, cy), d / 2, fc='w', ec='k', lw=1.2)); ax.plot([cx - d * .7, cx + d * .7], [cy, cy], 'k-.', lw=.4); ax.plot([cx, cx], [cy - d * .7, cy + d * .7], 'k-.', lw=.4)
            dim(ax, (0, -pad * 1.6), (W, -pad * 1.6), fmt(W)); dim(ax, (-pad * 1.4, 0), (-pad * 1.4, H), fmt(H))
            R = f['refs']
            for key, col in (('A', 'tab:green'), ('B', 'tab:olive')):
                e = R.get(key)
                if e:
                    ax.plot([e[0][0], e[1][0]], [e[0][1], e[1][1]], color=col, lw=3, solid_capstyle='butt', zorder=5)
                    mx, my = (e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2
                    ax.text(mx, my, f' {key} ', fontsize=9, weight='bold', color='w', ha='center', va='center', zorder=6, bbox=dict(boxstyle='round,pad=0.15', fc=col, ec='none'))
            for (p0, p1, txt, col, ext) in R['dims']:
                if ext: ax.plot([ext[0][0], ext[1][0]], [ext[0][1], ext[1][1]], color='0.5', lw=0.6, ls='--')
                dim(ax, p0, p1, txt, col)
            for i, c in enumerate(f['circ']):
                ax.text(c[0], c[1] + c[2] / 2 + pad * .25, f'{i + 1}: Ø{fmt(c[2])}', ha='center', fontsize=8.5, color='tab:red')
            if f['key'] == 'bk_side' and 'BOM_SHELL' in bom:    # контур без отворів: даємо побудову профілю (для перевірки DXF і шаблону гнуття)
                R['table'] = ['Контур = зовнішня поверхня обичайки (боковина — шаблон для гнуття). Від губи за годинниковою стрілкою:',
                              '  ' + ' → '.join(f'{nm} {ln:.0f}' for nm, ln in bom['BOM_SHELL'][2]) + ' → уступ під ніж → передня кромка до губи.',
                              '  Довжини ділянок — по нейтральній лінії обичайки; радіуси — внутрішні (зовнішній = + товщина обичайки).']
            fig.text(0.06, 0.865, '\n'.join(R['table']), fontsize=8.2, va='top', family='DejaVu Sans Mono')
            ax.set_xlim(-pad * 3.2, W + pad); ax.set_ylim(-pad * 3.4, H + pad * 1.5); save(pdf, fig, f['key'])

# ---------------------------------------------------------------- BOM
def tube_kg_m(h, w, t):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import strength
    return strength.rhs_props(h, w, t)['mass']

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=os.path.join(ROOT, 'build')); ap.add_argument('--version', default='')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    for d in ('bom', 'dxf', 'drawings'): os.makedirs(os.path.join(out, d), exist_ok=True)
    version = a.version or datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    bom = read_bom_echo()
    problems = []      # перевірка здорового глузду контурів: дефект проєкції дає «ключові» контури, скалки й діагоналі в ескізі (так було з лівою стінкою рукояті)
    flats = []
    with tempfile.TemporaryDirectory() as t:
        for key, qty, th, name in bom['BOM_FLAT']:
            svg = os.path.join(t, key + '.svg')
            openscad(svg, 'part="flat"', f'flat_name="{key}"')
            openscad(os.path.join(out, 'dxf', key + '.dxf'), 'part="flat"', f'flat_name="{key}"')
            lp = parse_svg_loops(svg)
            if any(abs(area(l)) < 20 for l in lp): problems.append(f'пластина {key}: скалка в контурі (петля площею < 20 мм²)')
            g = analyse(lp)
            g.update(key=key, qty=qty, t=th, name=name, mass=g['area'] * th * RHO); g['refs'] = hole_refs(g)
            flats.append(g); print(f"  {key:<13} {g['W']:.0f}×{g['H']:.0f}  отворів {len(g['holes'])}  {g['mass']:.2f} кг")
    tubes = []
    with tempfile.TemporaryDirectory() as t:
        for key, h, w, th, ln, note in bom['BOM_TUBES']:
            faces = {}
            for face in ('top', 'bottom', 'left', 'right'):
                svg = os.path.join(t, f'{key}_{face}.svg')
                openscad(svg, 'part="tubeface"', f'tube_name="{key}"', f'tube_face="{face}"')
                loops = sorted(parse_svg_loops(svg), key=lambda l: -abs(area(l)))
                faces[face] = dict(outer=loops[0], circ=[c for c in (as_circle(l) for l in loops[1:]) if c])
                if len(loops[0]) > 12: problems.append(f'труба {key}, стінка {face}: зовнішній контур із {len(loops[0])} точок — отвір злився з контуром?')
                if any(not as_circle(l) for l in loops[1:]): problems.append(f'труба {key}, стінка {face}: некруглий внутрішній контур (скалка або виріз, якого скрипт не вміє показати)')
            xmin = min(p[0] for f in faces.values() for p in f['outer'])
            for f in faces.values():                       # спільна база x = 0 (крайній задній торець); низ кожної стінки y = 0 (за номіналом)
                ymid = (min(p[1] for p in f['outer']) + max(p[1] for p in f['outer'])) / 2
                Hn = h if f is faces['left'] or f is faces['right'] else w
                sh = lambda p: (p[0] - xmin, p[1] - ymid + Hn / 2)
                f['outer'] = [sh(p) for p in f['outer']]; f['circ'] = [(c[0] - xmin, c[1] - ymid + Hn / 2, c[2]) for c in f['circ']]
                f['x0'] = min(p[0] for p in f['outer']); f['x1'] = max(p[0] for p in f['outer'])
            tubes.append(dict(key=key, h=h, w=w, t=th, L=ln, note=note, faces=faces, X1=max(f['x1'] for f in faces.values())))
            print(f"  труба {key:<10} стінки: " + ', '.join(f"{k} {v['x0']:.0f}…{v['x1']:.0f}" for k, v in faces.items()))
    # --- Markdown + CSV
    rows = []; md = [f'# Специфікація (BOM) — {version}', '', '> **УВАГА:** цю специфікацію, як і всю модель, згенеровано штучним інтелектом. Кваліфікований інженер її не перевіряв, '
     'машину за цією моделлю не збудовано й не випробувано. Використання — на власний ризик і відповідальність; '
     'відомі недоробки конструкції — у `SAFETY.md`.', '',
     'Згенеровано `tools/bom_drawings.sh` з моделі `scad/excavator_boom.scad`. Розміри в мм, маса — за ρ = 7.85 г/см³.', '']
    md += ['## 1. Профільна труба (' + TUBE_MAT + ')', '', '| Деталь | Профіль | Довжина заготовки | кг/м | Маса, кг | Обробка |', '|---|---|---|---|---|---|']
    tot_tube = 0; need = {}
    for k, h, w, t, ln, note in bom['BOM_TUBES']:
        kgm = tube_kg_m(h, w, t); m = kgm * ln / 1000; tot_tube += m; need[(h, w, t)] = need.get((h, w, t), 0) + ln
        md.append(f'| {k} | {h}×{w}×{t} | {ln} | {kgm:.2f} | {m:.1f} | {note} |'); rows.append(['труба', k, 1, f'{h}x{w}x{t}', ln, '', '', round(m, 2), note])
    md += ['', 'Потреба: ' + '; '.join(f'{h}×{w}×{t} — {l/1000:.2f} м (+ різи/запас ≈ 0.1 м)' for (h, w, t), l in need.items()), '']
    md += [f'## 2. Контурні пластини ({PLATE_MAT}) — різання за DXF (`dxf/`), ескізи в `drawings/parts.pdf`', '', '| Деталь | Назва | К-сть | t | Габарит | Отвори | Маса 1 шт, кг | Разом, кг |', '|---|---|---|---|---|---|---|---|']
    by_t = {}
    for f in flats:
        holes = ', '.join(f"Ø{h['circle'][2]:.1f}" if h['circle'] else 'фігурний' for h in f['holes']) or '—'
        md.append(f"| {f['key']} | {f['name']} | {f['qty']} | {f['t']} | {f['W']:.0f}×{f['H']:.0f} | {holes} | {f['mass']:.2f} | {f['mass'] * f['qty']:.2f} |")
        e = by_t.setdefault(f['t'], [0, 0]); e[0] += f['W'] * f['H'] * f['qty']; e[1] += f['mass'] * f['qty']
        rows.append(['пластина', f['key'], f['qty'], f"t{f['t']}", round(f['W']), round(f['H']), holes, round(f['mass'] * f['qty'], 2), f['name']])
    md += ['', f'## 3. Смуги та прямокутні пластини ({PLATE_MAT})', '', '| Деталь | Назва | К-сть | Довжина × ширина × t | Маса разом, кг |', '|---|---|---|---|---|']
    for k, q, ln, w, t, name in bom['BOM_STRIPS']:
        m = ln * w * t * RHO * q; e = by_t.setdefault(t, [0, 0]); e[0] += ln * w * q; e[1] += m
        md.append(f'| {k} | {name} | {q} | {ln:.0f} × {w:.0f} × {t:.0f} | {m:.2f} |'); rows.append(['смуга', k, q, f't{t:g}', round(ln), round(w), '', round(m, 2), name])
    md += ['', '### Потреба в листі за товщинами (площа габаритних прямокутників, без розкрою)', '', '| t, мм | Площа заготовок, м² | Маса деталей, кг | Що брати на металобазі |', '|---|---|---|---|']
    hint = {5: 'лист 5 г/к S235JR зі складу (обичайка ковша — вальцювати або гнути сегментами)', 6: 'лист 6 г/к S235JR зі складу (боковини ковша)', 8: 'лист 8 (на замовлення) або смуга 100×8 / 80×8 зі складу для вузьких деталей', 10: 'смуга 100×10 / 80×10 зі складу; лист 10 мм 2000×6000 S235JR', 12: 'лист 12 (на замовлення); допустима заміна на 10 мм для вилок'}
    tot_plate = 0
    for t in sorted(by_t): md.append(f'| {t:g} | {by_t[t][0] / 1e6:.3f} | {by_t[t][1]:.1f} | {hint.get(int(t), "")} |'); tot_plate += by_t[t][1]
    md += ['', '## 3б. Зносостійкі деталі ковша (Hardox 400/450, 65Г, 30ХГСА або ніж грейдера — НЕ Ст3; зуби можна купити приварні під ніж 12 мм)', '', '| Деталь | Назва | К-сть | Довжина × ширина × t | Маса разом, кг |', '|---|---|---|---|---|']
    tot_wear = 0
    for k, q, ln, w, t, name in bom.get('BOM_WEAR', []):
        m = ln * w * t * RHO * q * (0.6 if k == 'bk_tooth' else 1.0); tot_wear += m      # зуб — клин, ≈ 60 % від бруска
        md.append(f'| {k} | {name} | {q} | {ln:.0f} × {w:.0f} × {t:.0f} | {m:.2f} |'); rows.append(['зносостійке', k, q, f't{t:g}', round(ln), round(w), '', round(m, 2), name])
    md += ['', '## 4. Втулки, бобишки, шайби', '', '| Деталь | Назва | К-сть | OD × ID × L | Маса разом, кг |', '|---|---|---|---|---|']
    tot_round = 0
    for k, q, od, idd, ln, name in bom['BOM_ROUND']:
        m = math.pi / 4 * (od ** 2 - idd ** 2) * ln * RHO * q; tot_round += m
        md.append(f'| {k} | {name} | {q} | Ø{od:g} × Ø{idd:g} × {ln:g} | {m:.2f} |'); rows.append(['втулка', k, q, f'OD{od:g}', f'ID{idd:g}', ln, '', round(m, 2), name])
    md += ['', '## 5. Пальці (шкворні 45Х ТВЧ куплені: Ø25 — 2 шт, Ø30 — 1 к-т; решту точити з 40Х покращеної, H8/f7)', '', '| Деталь | Назва | К-сть | Ø × L | Маса разом, кг |', '|---|---|---|---|---|']
    tot_pin = 0
    for k, q, d, ln, name in bom['BOM_PINS']:
        m = math.pi / 4 * d * d * ln * RHO * q; tot_pin += m
        md.append(f'| {k} | {name} | {q} | Ø{d:g} × {ln:g} | {m:.2f} |'); rows.append(['палець', k, q, f'D{d:g}', ln, '', '', round(m, 2), name])
    md += ['', '## 6. Покупні', '', '- Гідроциліндри: ГЦ 63.40.500.700 (стріла), ГЦ ЦС50.25.400.600 (рукоять), ГЦ ЦС50.25.300.510 (ківш) — уже закуплені.',
           '- Зуби ковша приварні під ніж 12 мм — 3 шт (якщо не робити самому); ніж — смуга зносостійкої сталі 300×100×12.',
           '- Маслянки М6/М8 — 8 шт (осі A, B, E, R, J, Q, G + запас); стопорні пластини/шплінти пальців — 12 к-тів.', '',
           '## 7. Підсумок маси', '', f'| Труби | Пластини (зі Ст3-деталями ковша) | Зносостійкі деталі ковша | Втулки | Пальці | **Разом (стріла + рукоять + важелі + ківш; без циліндрів і колони)** |', '|---|---|---|---|---|---|',
           f'| {tot_tube:.1f} кг | {tot_plate:.1f} кг | {tot_wear:.1f} кг | {tot_round:.1f} кг | {tot_pin:.1f} кг | **{tot_tube + tot_plate + tot_wear + tot_round + tot_pin:.1f} кг** |', '']
    open(os.path.join(out, 'bom', 'bom.md'), 'w', encoding='utf-8').write('\n'.join(md))
    with open(os.path.join(out, 'bom', 'bom.csv'), 'w', newline='', encoding='utf-8') as fcsv:
        w = csv.writer(fcsv)
        w.writerow([f'# {version}: згенеровано ШІ, інженером не перевірено, машину не випробувано — на власний ризик; див. SAFETY.md'])
        w.writerow(['тип', 'деталь', 'к-сть', 'розмір1', 'розмір2', 'розмір3', 'отвори', 'маса_кг', 'примітка']); w.writerows(rows)
    make_pdf(os.path.join(out, 'drawings', 'parts.pdf'), bom, flats, tubes, version)
    if problems:
        print('!!! ЕСКІЗИ: підозрілі контури — перевір проєкцію в моделі (tube_face_2d / flat):\n  ' + '\n  '.join(problems)); sys.exit(1)
    print(f"== BOM: {out}/bom/bom.md, bom.csv; DXF: {len(flats)} шт; PDF: {out}/drawings/parts.pdf; маса разом {tot_tube + tot_plate + tot_wear + tot_round + tot_pin:.1f} кг")

if __name__ == '__main__':
    main()
