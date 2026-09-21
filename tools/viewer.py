#!/usr/bin/env python3
"""
viewer.py — інтерактивний 3D-перегляд моделі scad/excavator_boom.scad у браузері.

Як це працює:
  * сторінка tools/viewer/index.html (three.js: обертання / панорама / масштаб) показує деталі, які OpenSCAD експортує
    у ВЛАСНИХ системах координат (стріла, рукоять, ківш, коромисло, тяга, половинки циліндрів) у форматі OFF з кольорами;
  * кути стріли / рукояті / ковша змінюються у браузері МИТТЄВО: позу складає JavaScript за тими самими формулами, що й
    функції pt_*() моделі, з точок, які модель друкує в echo(VIEW = ...);
  * будь-який інший параметр (довжини, труби, кріплення, ківш…) → сервер запускає OpenSCAD паралельно для всіх деталей
    (≈ 0.3–0.6 с) і віддає нові сітки. Параметри читаються з самого .scad (групи Customizer) — окремого списку немає.

Запуск:   tools/viewer.sh                      (або python3 tools/viewer.py --open)
Статична сторінка без сервера (лише кути, геометрія за замовчуванням):
          python3 tools/viewer.py --export versions/VNNN/viewer.html
"""
import argparse, json, os, re, subprocess, sys, tempfile, threading, time, webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAD = os.path.join(ROOT, 'scad', 'excavator_boom.scad')
PAGE = os.path.join(ROOT, 'tools', 'viewer', 'index.html')
PARTS = ['post', 'boom', 'v_stick', 'bucket', 'v_rocker', 'v_link',
         'v_cyl_boom_body', 'v_cyl_boom_rod', 'v_cyl_stick_body', 'v_cyl_stick_rod', 'v_cyl_bucket_body', 'v_cyl_bucket_rod']
# параметри, які обробляє сама сторінка (без OpenSCAD): кути, прапорці показу, рівень землі
CLIENT = {'boom_angle', 'stick_angle', 'bucket_angle', 'clamp_to_cylinders', 'ground_below_A'}
DEFAULT_COLOR = (230, 200, 60)

# ---------------------------------------------------------------- параметри з .scad
def parse_value(txt):
    txt = txt.strip()
    if txt in ('true', 'false'): return txt == 'true'
    if txt.startswith('"') and txt.endswith('"'): return txt[1:-1]
    if txt.startswith('['):
        return [parse_value(x) for x in txt[1:-1].split(',') if x.strip()]
    try:
        f = float(txt); return int(f) if re.fullmatch(r'-?\d+', txt) else f
    except ValueError:
        return None

def read_schema():
    """Групи Customizer → [{name, params: [{name, value, desc, min, max, step, options}]}] (до module __end_of_params)."""
    groups, cur, desc = [], None, []
    for line in open(SCAD, encoding='utf-8'):
        s = line.strip()
        if s.startswith('module __end_of_params'): break
        m = re.match(r'/\*\s*\[(.+?)\]\s*\*/', s)
        if m:
            cur = dict(name=m.group(1), params=[]); groups.append(cur); desc = []; continue
        if s.startswith('//'):
            desc.append(s.lstrip('/').strip()); continue
        m = re.match(r'(\$?\w+)\s*=\s*(.+?);\s*(?://\s*(.*))?$', s)
        if m and cur is not None:
            name, val, tail = m.group(1), parse_value(m.group(2)), (m.group(3) or '').strip()
            p = dict(name=name, value=val, desc=' '.join(desc)); desc = []
            r = re.fullmatch(r'\[(.*)\]', tail)
            if r:
                body = r.group(1)
                if ':' in body:
                    nums = [float(x) for x in body.split(':')]
                    p['min'], p['max'] = nums[0], nums[-1]; p['step'] = nums[1] if len(nums) == 3 else 1
                else:
                    p['options'] = [x.strip() for x in body.split(',')]
            elif tail:
                p['desc'] = (p['desc'] + ' ' + tail).strip()
            if val is not None: cur['params'].append(p)
        elif not s:
            desc = []
    for g in groups:
        for p in g['params']:
            p['client'] = p['name'] in CLIENT or p['name'].startswith('show_')
    return [g for g in groups if not g['name'].startswith('0.')]

def scad_literal(p, v):
    """Значення з браузера → безпечний літерал OpenSCAD (тип береться зі схеми; нічого, крім чисел/булів/опцій, не проходить)."""
    d = p['value']
    if isinstance(d, bool): return 'true' if bool(v) else 'false'
    if isinstance(d, (int, float)): return repr(float(v))
    if isinstance(d, list):
        if not isinstance(v, list) or len(v) != len(d): raise ValueError(p['name'])
        return '[' + ','.join(repr(float(x)) for x in v) + ']'
    if isinstance(d, str):
        if v not in p.get('options', [d]): raise ValueError(p['name'])
        return '"%s"' % v
    raise ValueError(p['name'])

# ---------------------------------------------------------------- OpenSCAD → сітки
def parse_off(path):
    """OFF з кольорами граней → {pos: [x,y,z,...], groups: [{color:[r,g,b], idx:[...]}]} (трикутники)."""
    tok = open(path, encoding='utf-8').read().split('\n')
    lines = [l for l in (t.strip() for t in tok) if l and not l.startswith('#')]
    i = 0
    head = lines[i]; i += 1
    counts = head[3:].split() if len(head) > 3 else []
    if len(counts) < 2: counts = lines[i].split(); i += 1
    nv, nf = int(counts[0]), int(counts[1])
    pos = []
    for k in range(nv):
        x, y, z = lines[i + k].split()[:3]; pos += [round(float(x), 2), round(float(y), 2), round(float(z), 2)]
    i += nv
    groups = {}
    for k in range(nf):
        a = lines[i + k].split(); n = int(a[0]); idx = [int(x) for x in a[1:1 + n]]; rest = a[1 + n:]
        if len(rest) >= 3:
            col = tuple(float(x) for x in rest[:3])
            col = tuple(int(round(c * 255)) if max(col) <= 1.0 and any('.' in x for x in rest[:3]) else int(c) for c in col)
        else:
            col = DEFAULT_COLOR
        g = groups.setdefault(col, [])
        for t in range(1, n - 1): g += [idx[0], idx[t], idx[t + 1]]
    return dict(pos=pos, groups=[dict(color=list(c), idx=ix) for c, ix in groups.items()])

def run_part(part, defs, tmp):
    out = os.path.join(tmp, part + '.off')
    r = subprocess.run(['openscad', '-o', out, '-D', f'part="{part}"'] + defs + [SCAD], capture_output=True, text=True, timeout=180)
    mesh = parse_off(out) if os.path.exists(out) and os.path.getsize(out) > 0 else None
    return part, mesh, r.stderr

_lock = threading.Lock(); _cache = {}
def build(params, schema):
    """params — лише змінені параметри {назва: значення}. Повертає dict для сторінки."""
    byname = {p['name']: p for g in schema for p in g['params']}
    defs = []
    for k in sorted(params):
        if k not in byname or byname[k]['client']: continue
        defs += ['-D', f'{k}={scad_literal(byname[k], params[k])}']
    key = json.dumps(defs)
    with _lock:
        if key in _cache: return dict(_cache[key], cached=True)
        t0 = time.time()
        with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=min(len(PARTS), os.cpu_count() or 4)) as ex:
            res = list(ex.map(lambda p: run_part(p, defs, tmp), PARTS))
        view, log = None, []
        for line in res[0][2].split('\n'):
            line = line.strip()
            m = re.match(r'ECHO: VIEW = (.*)$', line)
            if m:
                view = dict(json.loads(re.sub(r'\b(undef|nan|inf|-inf)\b', 'null', m.group(1))))
            elif line.startswith('ECHO: "') and ('!!!' in line or '===' in line):
                log.append(line[7:-1])
            elif line.startswith(('WARNING', 'ERROR')):
                log.append(line)
        parts = {p: m for p, m, _ in res if m}
        missing = [p for p, m, _ in res if not m]
        if missing: log.append('!!! OpenSCAD не зміг побудувати: ' + ', '.join(missing))
        out = dict(view=view, parts=parts, log=log, ms=int((time.time() - t0) * 1000), cached=False)
        if len(_cache) > 12: _cache.pop(next(iter(_cache)))
        _cache[key] = out
        return out

# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    schema = None
    def log_message(self, *a): pass
    def _send(self, code, body, ctype):
        if isinstance(body, str): body = body.encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        path = self.path.split('?')[0]                           # ?параметр=значення розбирає сама сторінка
        if path in ('/', '/index.html'):
            self._send(200, open(PAGE, encoding='utf-8').read(), 'text/html; charset=utf-8')
        elif path == '/api/views':                               # ракурси з views.json у корені
            f = os.path.join(ROOT, 'views.json')
            self._send(200, open(f, encoding='utf-8').read() if os.path.isfile(f) else '{"views":[]}',
                       'application/json')
        elif path == '/api/schema':
            Handler.schema = read_schema()                       # перечитується: модель могли відредагувати
            self._send(200, json.dumps(Handler.schema, ensure_ascii=False), 'application/json')
        else:
            self._send(404, 'not found', 'text/plain')
    def do_POST(self):
        if self.path != '/api/build': return self._send(404, 'not found', 'text/plain')
        try:
            req = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if Handler.schema is None: Handler.schema = read_schema()
            if req.get('fresh'): _cache.clear()
            self._send(200, json.dumps(build(req.get('params', {}), Handler.schema), ensure_ascii=False, separators=(',', ':')), 'application/json')
        except Exception as e:                                   # помилку показуємо на сторінці, сервер живе далі
            self._send(200, json.dumps(dict(error=f'{type(e).__name__}: {e}'), ensure_ascii=False), 'application/json')

def export_static(path):
    schema = read_schema(); data = build({}, schema)
    html = open(PAGE, encoding='utf-8').read()
    vf = os.path.join(ROOT, 'views.json')                    # ракурси теж вшиваємо: статична сторінка нікуди не ходить
    views = json.load(open(vf, encoding='utf-8')).get('views', []) if os.path.isfile(vf) else []
    blob = json.dumps(dict(schema=schema, build=data, views=views, made=time.strftime('%Y-%m-%d %H:%M')), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = html.replace('window.__STATIC__ = null;', 'window.__STATIC__ = ' + blob + ';', 1)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(html)
    print(f'== статична сторінка: {path} ({os.path.getsize(path) / 1e6:.1f} МБ; кути — у браузері, геометрія — за замовчуванням)')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8765); ap.add_argument('--open', action='store_true', help='відкрити браузер')
    ap.add_argument('--export', metavar='ФАЙЛ.html', help='зберегти статичну сторінку і вийти')
    a = ap.parse_args()
    if a.export:
        export_static(a.export); sys.exit(0)
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    url = f'http://127.0.0.1:{a.port}/'
    print(f'== перегляд моделі: {url}   (Ctrl+C — зупинити)')
    if a.open: threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print('\n== зупинено')
