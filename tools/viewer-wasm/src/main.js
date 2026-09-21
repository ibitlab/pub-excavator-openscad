import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import scadDefault from '../../../scad/excavator_boom.scad?raw';
import repoViewsFile from '../../../views.json';                 // ракурси з репозиторію; Vite вшиває JSON у dist/      // модель вшивається у сторінку; у dev правка .scad перезавантажує сторінку
import { readSchema, scadLiteral } from './schema.js';
import { LANGS, initLang, setLang, getLang, t, tp, tg } from './i18n.js';

// Друга версія перегляду: БЕЗ бекенду. OpenSCAD працює у веб-воркері (WASM), сторінка — звичайна статика.
// Усе інше (сцена, поза, керування) — те саме, що в tools/viewer/index.html; блок складання пози (позначений тегами pose нижче) має лишатися однаковим в обох — це перевіряє npm test.

//<pose> ------------------------------------------------------------------------------------------
// Складання пози — ті самі формули, що й функції pt_*() у scad/excavator_boom.scad. Площина XZ, точка = [x, z].
const RAD = Math.PI / 180;
const rot2 = (v, a) => [v[0] * Math.cos(a * RAD) - v[1] * Math.sin(a * RAD), v[0] * Math.sin(a * RAD) + v[1] * Math.cos(a * RAD)];
const add = (a, b) => [a[0] + b[0], a[1] + b[1]], sub = (a, b) => [a[0] - b[0], a[1] - b[1]], mul = (a, k) => [a[0] * k, a[1] * k];
const norm = a => Math.hypot(a[0], a[1]), ang = v => Math.atan2(v[1], v[0]) / RAD;
function circX(p0, r0, p1, r1, side) {              // перетин кіл; side=+1 — точка ліворуч від напрямку p0→p1
  const d = norm(sub(p1, p0)); if (d < 1e-9 || d > r0 + r1 || d < Math.abs(r0 - r1)) return null;
  const a = (r0 * r0 - r1 * r1 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, r0 * r0 - a * a)), u = mul(sub(p1, p0), 1 / d);
  return [p0[0] + u[0] * a - u[1] * side * h, p0[1] + u[1] * a + u[0] * side * h];
}
function pose(V, th, psi, om) {
  const B = rot2(V.B_l, th), D = rot2(V.D_l, th), F = rot2(V.F_l, th), C = V.C_w;
  const sdir = ang(mul(B, -1)) + psi, sp = p => add(B, rot2(p, sdir));
  const E = sp(V.E_s), G = sp(V.G_s), H = sp(V.H_s), R = sp(V.R_s);
  const bdir = sdir - om, Q = add(E, rot2(V.ear, bdir)), T = add(E, rot2([V.tip, 0], bdir));
  const J = circX(R, V.rocker_L, Q, V.link_L, +1);
  return { A: [0, 0], B, C, D, F, E, G, H, R, Q, J, T, th, sdir, bdir,
           L: { boom: norm(sub(D, C)), stick: norm(sub(G, F)), bucket: J ? norm(sub(J, H)) : null } };
}
//</pose> -----------------------------------------------------------------------------------------

const $ = id => document.getElementById(id);
// Усе, що приходить із .scad (назви груп, описи, варіанти, текст echo) і з імені
// відкритого файлу, — ЧУЖИЙ текст: «Відкрити .scad…» бере довільний файл із диска.
// Тому такі рядки складаються через DOM і textContent, а не вставляються в розмітку.
const el = (tag, props) => Object.assign(document.createElement(tag), props);
const scadSource = scadDefault;          // модель вшита збіркою; сторінка чужих файлів не приймає
let schema = [], byName = {}, values = {}, V = null, lastLog = [];
const ang3 = { boom: 15, stick: 100, bucket: 60 };
const ANG = [['boom', 'boom_angle'], ['stick', 'stick_angle'], ['bucket', 'bucket_angle']];   // підписи — t('ang.<key>')

// ---------------------------------------------------------------- сцена
THREE.Object3D.DEFAULT_UP.set(0, 0, 1);                       // як в OpenSCAD: X — вперед, Y — вбік, Z — вгору
const canvas = $('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new THREE.Scene(); scene.background = new THREE.Color(0xf3f1ec);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8478, 1.15));
const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(-1500, -3000, 4000); scene.add(sun);
const fill = new THREE.DirectionalLight(0xffffff, 0.5); fill.position.set(2500, 3000, 800); scene.add(fill);
let camera, controls, ortho = false;
function makeCamera(isOrtho, pos, target) {
  const w = canvas.clientWidth || 800, h = canvas.clientHeight || 600;
  if (isOrtho) { const d = pos.distanceTo(target) * 0.42; camera = new THREE.OrthographicCamera(-d * w / h, d * w / h, d, -d, -20000, 40000); }
  else camera = new THREE.PerspectiveCamera(32, w / h, 20, 60000);
  camera.position.copy(pos); camera.up.set(0, 0, 1);
  if (controls) controls.dispose();
  controls = new OrbitControls(camera, canvas); controls.target.copy(target);
  controls.enableDamping = true; controls.dampingFactor = 0.12; controls.screenSpacePanning = true; controls.zoomToCursor = true;
  controls.update(); ortho = isOrtho;
}
makeCamera(false, new THREE.Vector3(1300, -5200, 900), new THREE.Vector3(1300, 0, -100));
const bodies = {}, world = new THREE.Group(); scene.add(world);
const pinsGroup = new THREE.Group(); world.add(pinsGroup);
const ground = new THREE.Group(); world.add(ground);
const envelope = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ color: 0xd0402f, size: 5, sizeAttenuation: false })); world.add(envelope);
const show = { cylinders: true, linkage: true, bucket: true, post: true, ground: true, pins: true, edges: true, envelope: false };

function buildGround(z) {
  ground.clear();
  const pl = new THREE.Mesh(new THREE.PlaneGeometry(9000, 6000), new THREE.MeshBasicMaterial({ color: 0x8a6a45, transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false }));
  pl.position.set(1500, 0, -z); ground.add(pl);
  const grid = new THREE.GridHelper(9000, 18, 0x9a8a70, 0xc9bfae); grid.rotation.x = Math.PI / 2; grid.position.set(1500, 0, -z + 1); ground.add(grid);
}
function setMeshes(parts) {
  for (const k in bodies) { world.remove(bodies[k]); bodies[k].traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); delete bodies[k]; }
  for (const [name, m] of Object.entries(parts)) {
    const g = new THREE.Group(); g.name = name;
    const pos = new THREE.Float32BufferAttribute(m.pos, 3);
    for (const grp of m.groups) {
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', pos); geo.setIndex(Array.isArray(grp.idx) ? grp.idx : new THREE.BufferAttribute(grp.idx, 1));
      const flat = geo.toNonIndexed(); flat.computeVertexNormals(); geo.dispose();
      const c = new THREE.Color(grp.color[0] / 255, grp.color[1] / 255, grp.color[2] / 255);
      const mesh = new THREE.Mesh(flat, new THREE.MeshStandardMaterial({ color: c, roughness: 0.62, metalness: 0.12, side: THREE.DoubleSide }));
      mesh.userData.base = c.clone(); g.add(mesh);
      const ed = new THREE.LineSegments(new THREE.EdgesGeometry(flat, 28), new THREE.LineBasicMaterial({ color: 0x2b2b2b, transparent: true, opacity: 0.35 }));
      ed.userData.edge = true; g.add(ed);
    }
    bodies[name] = g; world.add(g);
  }
  applyShow();
}
function setPins() {
  pinsGroup.clear(); if (!V) return;
  const mat = new THREE.MeshStandardMaterial({ color: 0xc8ccd0, roughness: 0.35, metalness: 0.6 });
  for (const [k, d, len] of V.pins) { const m = new THREE.Mesh(new THREE.CylinderGeometry(d / 2, d / 2, len, 24), mat); m.name = k; pinsGroup.add(m); }   // вісь циліндра three.js — уздовж Y, як і пальці
}
const place = (o, p, a) => { if (!o) return; o.position.set(p[0], 0, p[1]); o.rotation.set(0, -a * RAD, 0); };

// ---------------------------------------------------------------- поза
function limits(key) { const l = V && V['lim_' + key]; return l && l[0] != null && l[1] != null ? l : null; }
function effAngles() {
  const out = {};
  for (const [key, pname] of ANG) {
    const l = limits(key); let v = ang3[key];
    if ($('clamp').checked && l) v = Math.min(l[1], Math.max(l[0], v));
    out[key] = v;
  }
  return out;
}
function updatePose() {
  if (!V) return;
  const a = effAngles(), P = pose(V, a.boom, a.stick, a.bucket);
  place(bodies.post, [0, 0], 0); place(bodies.boom, [0, 0], P.th);
  place(bodies.v_stick, P.B, P.sdir); place(bodies.bucket, P.E, P.bdir);
  const cyl = (key, p1, p2) => { const ok = !!p2; for (const s of ['body', 'rod']) { const o = bodies[`v_cyl_${key}_${s}`]; if (o) o.visible = ok && show.cylinders; }
    if (ok) { const an = ang(sub(p2, p1)); place(bodies[`v_cyl_${key}_body`], p1, an); place(bodies[`v_cyl_${key}_rod`], p2, an); } };
  cyl('boom', P.C, P.D); cyl('stick', P.F, P.G); cyl('bucket', P.H, P.J);
  if (bodies.v_rocker) bodies.v_rocker.visible = !!P.J && show.linkage;
  if (bodies.v_link) bodies.v_link.visible = !!P.J && show.linkage;
  if (P.J) { place(bodies.v_rocker, P.R, ang(sub(P.J, P.R))); place(bodies.v_link, P.J, ang(sub(P.Q, P.J))); }
  for (const m of pinsGroup.children) { const p = P[m.name]; m.visible = !!p && show.pins; if (p) m.position.set(p[0], 0, p[1]); }
  // циліндр поза ходом → червоний корпус
  const warn = [];
  for (const [key] of ANG) {
    const title = t('ang.' + key);
    const [closed, stroke] = V['cyl_' + key], L = P.L[key], bad = L == null || L < closed - 0.5 || L > closed + stroke + 0.5;
    const body = bodies[`v_cyl_${key}_body`]; if (body) body.traverse(o => { if (o.isMesh) o.material.color.copy(bad ? new THREE.Color(0xd23c2c) : o.userData.base); });
    const el = $('cyl_' + key); if (el) { const f = L == null ? 0 : (L - closed) / stroke;
      el.querySelector('.bar').classList.toggle('bad', bad); el.querySelector('i').style.width = Math.max(0, Math.min(1, f)) * 100 + '%';
      el.querySelector('span').textContent = L == null ? t('cyl.nolink') : t('cyl.state', { L: L.toFixed(0), used: (L - closed).toFixed(0), stroke }); }
    if (bad) warn.push(L == null ? t('cyl.out', { part: title })
      : t('cyl.out.range', { part: title, L: L.toFixed(0), lo: closed, hi: closed + stroke }));
    const inp = $('num_' + key), sl = $('sl_' + key); if (document.activeElement !== inp) inp.value = (+a[key].toFixed(1)); sl.value = a[key];
  }
  const gz = -groundZ(), T = P.T, mm = t('hud.mm');
  const where = z => t(z >= 0 ? 'hud.above' : 'hud.below');
  const tbl = el('table');
  const line = (label, ...kids) => { const tr = el('tr'); tr.append(el('td', { textContent: label }), el('td')); tr.lastChild.append(...kids); tbl.appendChild(tr); };
  line(t('hud.reach'), el('b', { textContent: T[0].toFixed(0) }), ' ' + mm);
  line(t('hud.tooth', { where: where(T[1] - gz) }), el('b', { textContent: Math.abs(T[1] - gz).toFixed(0) }), ' ' + mm);
  line(t('hud.axisE', { where: where(P.E[1] - gz) }), Math.abs(P.E[1] - gz).toFixed(0) + ' ' + mm);
  line(t('hud.tilt'), tiltText(P.bdir));
  $('hud').replaceChildren(tbl);
  // Ті самі числа — у ручці шухляди: у згорнутому стані це все, що видно з панелі.
  $('grab_info').textContent = `${t('m.reach')} ${T[0].toFixed(0)} ${mm} · ${t('m.tooth')} `
    + `${Math.abs(T[1] - gz).toFixed(0)} ${mm} ${where(T[1] - gz)}`;
  // Попередження приходять з echo() моделі — у відкритому з диска .scad там може бути будь-що.
  for (const w of [...warn, ...lastLog.filter(l => l.includes('!!!')).map(l => l.replace(/!!!\s*/, ''))])
    $('hud').appendChild(el('div', { className: 'w', textContent: '⚠ ' + w }));
}
function tiltText(bdir) {                                    // отвір дивиться у бік −ŷ ковша; горизонтальний, коли вісь ковша дивиться на 180°
  let tilt = ((bdir - 180) % 360 + 540) % 360 - 180;         // −: нахил назад (тримає), +: вперед (висипає)
  const a = Math.abs(tilt).toFixed(0);
  return Math.abs(tilt) < 3 ? t('tilt.level') : tilt < 0 ? (tilt > -90 ? t('tilt.up', { a }) : t('tilt.over', { a }))
    : (tilt < 60 ? t('tilt.dig', { a }) : t('tilt.dump', { a }));
}
const groundZ = () => values.ground_below_A ?? (V ? V.ground : 650);
function updateEnvelope() {
  const pts = []; const lb = limits('boom'), ls = limits('stick'), lk = limits('bucket');
  if (V && lb && ls && lk && show.envelope) for (let i = 0; i <= 24; i++) for (let j = 0; j <= 24; j++) for (const o of [lk[0], lk[1]]) {
    const P = pose(V, lb[0] + (lb[1] - lb[0]) * i / 24, ls[0] + (ls[1] - ls[0]) * j / 24, o); pts.push(P.T[0], 0, P.T[1]); }
  envelope.geometry.dispose(); envelope.geometry = new THREE.BufferGeometry(); envelope.geometry.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
}
function applyShow() {
  if (bodies.post) bodies.post.visible = show.post; if (bodies.bucket) bodies.bucket.visible = show.bucket;
  ground.visible = show.ground; envelope.visible = show.envelope;
  for (const k in bodies) bodies[k].traverse(o => { if (o.userData.edge) o.visible = show.edges; });
  updateEnvelope(); updatePose();
}

// ---------------------------------------------------------------- керування: кути, пози, вигляд
function buildAngleUI() {
  $('angles').innerHTML = '';
  for (const [key] of ANG) {
    const title = t('ang.' + key), hint = t('ang.' + key + '.hint');
    const d = document.createElement('div'); d.className = 'ang';
    d.innerHTML = `<div class="top"><label for="sl_${key}" title="${hint}">${title} <span style="color:var(--mute);font-weight:400">· ${hint}</span></label><span><input type="number" id="num_${key}" step="1"> °</span></div>
      <input type="range" id="sl_${key}" step="0.1"><div class="cyl" id="cyl_${key}"><div class="bar"><i></i></div><span></span></div>`;
    $('angles').appendChild(d);
    const set = v => { if (!isFinite(v)) return; ang3[key] = v; stopPlay(); updatePose(); };
    d.querySelector('input[type=range]').addEventListener('input', e => set(+e.target.value));
    d.querySelector('input[type=number]').addEventListener('input', e => set(+e.target.value));
  }
}
function updateAngleRanges() {
  for (const [key, pname] of ANG) {                          // pname — ім'я параметра в моделі (межі повзунка, коли обмеження вимкнене)
    const p = byName[pname] || {}, l = limits(key), clamp = $('clamp').checked && l;
    const lo = clamp ? l[0] : (p.min ?? -90), hi = clamp ? l[1] : (p.max ?? 180), sl = $('sl_' + key);
    sl.min = lo; sl.max = hi; $('num_' + key).min = Math.floor(lo); $('num_' + key).max = Math.ceil(hi);
    sl.title = `${lo.toFixed(1)}° … ${hi.toFixed(1)}°`;
  }
}
// Ключі поз і виглядів — стабільні id (не підписи): на них зав'язані ?view= в адресі та цикл кнопки SpaceMouse.
const POSES = { work: [15, 100, 60], transport: [58, 51, 139], reach: [-5, 156, -17], deep: [-38, 90, 60], high: [58, 156, 0], dump: [45, 140, -17] };
function buildPoseUI() {
  $('poses').innerHTML = '';
  for (const [id, a] of Object.entries(POSES)) { const b = document.createElement('button'); b.textContent = t('pose.' + id); b.onclick = () => { stopPlay(); glide(a); }; $('poses').appendChild(b); }
}
let anim = null;
function glide(to, ms = 600, then) {
  const from = [ang3.boom, ang3.stick, ang3.bucket], t0 = performance.now(); anim = { cancel: false };
  const me = anim, step = t => { if (me.cancel) return; const k = Math.min(1, (t - t0) / ms), e = k * k * (3 - 2 * k);
    ang3.boom = from[0] + (to[0] - from[0]) * e; ang3.stick = from[1] + (to[1] - from[1]) * e; ang3.bucket = from[2] + (to[2] - from[2]) * e; updatePose();
    if (k < 1) requestAnimationFrame(step); else if (then) then(); }; requestAnimationFrame(step);
}
const CYCLE = [[12, 145, 0, 900], [-22, 142, 5, 1100], [-26, 95, 45, 1500], [-22, 78, 125, 1000], [38, 80, 135, 1400], [42, 140, 120, 1100], [42, 142, -17, 900], [12, 145, 0, 1000]];
let playing = false;
function playFrom(i) { if (!playing) return; const k = CYCLE[i % CYCLE.length]; glide(k.slice(0, 3), k[3], () => playFrom(i + 1)); }
function stopPlay() { playing = false; if (anim) anim.cancel = true; $('play').classList.remove('on'); $('play').textContent = t('play'); }
$('play').onclick = () => { if (playing) return stopPlay(); playing = true; $('play').classList.add('on'); $('play').textContent = t('stop'); playFrom(0); };
$('clamp').onchange = () => { updateAngleRanges(); updatePose(); };

function sceneBox() { const b = new THREE.Box3(); for (const k in bodies) if (bodies[k].visible) b.expandByObject(bodies[k]); return b.isEmpty() ? new THREE.Box3(new THREE.Vector3(-300, -300, -900), new THREE.Vector3(3000, 300, 1500)) : b; }
function setView(dir, isOrtho = ortho) {
  const b = sceneBox(), c = b.getCenter(new THREE.Vector3()), r = b.getSize(new THREE.Vector3()).length() * 0.5;
  const d = dir ? new THREE.Vector3(...dir).normalize() : camera.position.clone().sub(controls.target).normalize();
  // У вертикальному кадрі машину обмежує ШИРИНА: горизонтальний кут огляду вужчий
  // за вертикальний рівно в aspect разів. Без цього в портреті вона тулиться до краю.
  const a = (canvas.clientWidth || 1) / (canvas.clientHeight || 1);
  makeCamera(isOrtho, c.clone().addScaledVector(d, r * 3.4 / Math.min(1, a)), c); resize();
}
const VIEWS = { side: [0, -1, 0], iso: [0.55, -1, 0.45], back: [-0.8, -1, 0.35], top: [0, -0.001, 1], front: [1, 0, 0.05], fit: null };
function buildViewUI() {
  $('views').innerHTML = '';
  for (const [id, d] of Object.entries(VIEWS)) { const b = document.createElement('button'); b.textContent = t('view.' + id); b.onclick = () => setView(d); $('views').appendChild(b); }
  const b = document.createElement('button'); b.textContent = t('view.ortho'); b.classList.toggle('on', ortho);
  b.onclick = () => { setView(null, !ortho); b.classList.toggle('on', ortho); }; $('views').appendChild(b);
}
const TOG = ['cylinders', 'linkage', 'bucket', 'post', 'pins', 'ground', 'edges', 'envelope'];
function buildToggleUI() {
  $('toggles').innerHTML = '';
  for (const k of TOG) { const l = document.createElement('label'); l.className = 'chk'; l.innerHTML = `<input type="checkbox" ${show[k] ? 'checked' : ''}> ${t('tog.' + k)}`;
    l.querySelector('input').onchange = e => { show[k] = e.target.checked; applyShow(); }; $('toggles').appendChild(l); }
}
canvas.addEventListener('dblclick', e => {                   // подвійний клік — новий центр обертання на поверхні моделі
  const r = canvas.getBoundingClientRect(), ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const hit = ray.intersectObjects(Object.values(bodies), true).find(h => h.object.isMesh && h.object.visible); if (hit) { controls.target.copy(hit.point); controls.update(); }
});

// ---------------------------------------------------------------- параметри моделі (OpenSCAD)
const changed = () => { const o = {}; for (const g of schema) for (const p of g.params) if (!p.client && JSON.stringify(values[p.name]) !== JSON.stringify(p.value)) o[p.name] = values[p.name]; return o; };
function buildParamUI() {
  const root = $('groups');
  const open = new Set([...root.children].filter(d => d.open).map(d => d.dataset.g));   // розгорнуті групи переживають зміну мови
  root.innerHTML = '';
  for (const g of schema) {
    const ps = g.params.filter(p => !p.client); if (!ps.length) continue;
    const det = document.createElement('details'); det.dataset.g = g.name; det.open = open.has(g.name);
    const sum = el('summary', { textContent: tg(g.name) });      // назва групи — з .scad
    sum.appendChild(el('span', { className: 'n' })); det.appendChild(sum); root.appendChild(det);
    for (const p of ps) {
      const row = el('div', { className: 'p', id: 'p_' + p.name });
      const vec = Array.isArray(p.value), vals = vec ? p.value : [p.value], cur = values[p.name], curs = vec ? cur : [cur];
      const ds = tp(p);                                         // опис — теж із .scad
      const box = el('span', { className: 'in' });
      if (typeof p.value === 'boolean') box.appendChild(el('input', { type: 'checkbox', checked: !!cur }));
      else if (p.options) { const sel = el('select');           // варіанти — теж; new Option ставить ТЕКСТ
        for (const o of p.options) sel.add(new Option(o, o, false, o === cur)); box.appendChild(sel); }
      else vals.forEach((v, i) => {
        const inp = el('input', { type: 'number', value: curs[i] });
        inp.step = p.step ?? (Math.abs(v) < 20 && !Number.isInteger(v) ? 0.5 : (Math.abs(v) >= 200 ? 5 : 1));
        if (p.min != null) { inp.min = p.min; inp.max = p.max; }
        box.appendChild(inp);
      });
      box.appendChild(el('button', { className: 'rs', textContent: '↺', title: t('p.restore', { v: JSON.stringify(p.value) }) }));
      row.append(el('span', { className: 'nm', textContent: p.name, title: ds }), box);
      if (ds) row.appendChild(el('span', { className: 'ds', textContent: ds }));
      det.appendChild(row);
      const els = [...row.querySelectorAll('input,select')];
      const read = () => { let v; if (typeof p.value === 'boolean') v = els[0].checked; else if (p.options) v = els[0].value; else { const n = els.map(e => +e.value); if (n.some(x => !isFinite(x) || e_empty(els))) return; v = vec ? n : n[0]; }
        values[p.name] = v; mark(); schedule(); };
      els.forEach(e => e.addEventListener('input', read));
      row.querySelector('.rs').onclick = () => { values[p.name] = p.value; if (typeof p.value === 'boolean') els[0].checked = p.value; else if (p.options) els[0].value = p.value; else els.forEach((e, i) => e.value = vals[i]); mark(); schedule(); };
    }
  }
  mark();
}
const e_empty = els => els.some(e => e.value === '');
function mark() {
  const ch = changed();
  for (const det of $('groups').children) { let n = 0; for (const row of det.querySelectorAll('.p')) { const on = row.id.slice(2) in ch; row.classList.toggle('ch', on); n += on; } det.querySelector('.n').textContent = n ? t('p.changed', { n }) : ''; }
}
let timer = null, inflight = false, again = false, worker = null, jobId = 0, engineReady = false;
function schedule() { clearTimeout(timer); timer = setTimeout(rebuild, 300); }
function runOpenSCAD(defs) {                                  // один запуск у воркері: part="view_all" → усі деталі одразу
  if (!worker) worker = new Worker(new URL('./scad-worker.js', import.meta.url), { type: 'module' });
  const id = ++jobId;
  return new Promise((resolve, reject) => {
    const done = e => { if (e.data.id !== id) return; worker.removeEventListener('message', done); resolve(e.data); };
    worker.addEventListener('message', done);
    worker.onerror = e => { worker.terminate(); worker = null; reject(new Error(e.message || t('st.worker'))); };
    worker.postMessage({ id, source: scadSource, defs });
  });
}
async function rebuild() {
  if (inflight) { again = true; return; } inflight = true;
  status(engineReady ? 'st.build' : 'st.engine', {}, 'busy');
  try {
    const ch = changed(), defs = Object.keys(ch).sort().map(k => `${k}=${scadLiteral(byName[k], ch[k])}`);
    const t0 = performance.now(), d = await runOpenSCAD(defs);
    if (d.error) { status('st.err', { msg: d.error }, 'err'); lastLog = d.log || []; }
    else { engineReady = true; applyBuild(d); status('st.done', { ms: (d.ms / 1000).toFixed(2), total: ((performance.now() - t0) / 1000).toFixed(2), n: Object.keys(ch).length }); }
  } catch (e) { status('st.err', { msg: e.message }, 'err'); }
  inflight = false; if (again) { again = false; rebuild(); }
}
let lastStatus = null;                                        // останній рядок стану — щоб перемалювати його новою мовою
function status(key, vars = {}, cls = '') { lastStatus = { key, vars, cls }; const s = $('status'); s.textContent = t(key, vars); s.className = 'adv ' + cls; }   // adv — мітка «розширене», її не можна стирати
function applyBuild(d) {
  lastLog = (d.log || []).filter(l => !/ПОТОЧНЕ|ЗУБ КОВША|поза межами циліндра|Циліндр між/.test(l));
  if (d.view) V = d.view; setMeshes(d.parts || {}); setPins(); buildGround(groundZ()); updateAngleRanges(); updateEnvelope(); updatePose();
}
$('reset').onclick = () => { for (const g of schema) for (const p of g.params) values[p.name] = p.value; buildParamUI(); buildGround(groundZ()); schedule(); updatePose(); };
$('copy').onclick = async () => { const ch = changed(), txt = Object.keys(ch).length ? Object.entries(ch).map(([k, v]) => `${k} = ${JSON.stringify(v)};`).join('\n') : t('st.nochange');
  try { await navigator.clipboard.writeText(txt); status('st.copied'); $('status').textContent += ' ' + txt.replace(/\n/g, '  '); } catch { prompt(t('st.prompt'), txt); } };

async function loadSchema() {
  schema = readSchema(scadSource);
  byName = {}; const old = values; values = {};
  for (const g of schema) for (const p of g.params) { byName[p.name] = p; values[p.name] = (p.name in old && JSON.stringify(old[p.name]).length && typeof old[p.name] === typeof p.value) ? old[p.name] : p.value; }
  // З АДРЕСИ НІЧОГО, КРІМ МОВИ. Раніше тут читалися початкові значення параметрів
  // (?boom_L1=1000) — прибрано навмисно: це був єдиний шлях, яким чуже значення з
  // посилання потрапляло у ТЕКСТ моделі OpenSCAD. Жоден скрипт цим не користувався.
  buildParamUI(); $('gz').value = values.ground_below_A;
}
$('gz').addEventListener('input', e => { if (e.target.value !== '' && isFinite(+e.target.value)) { values.ground_below_A = +e.target.value; buildGround(groundZ()); updatePose(); } });
function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight; renderer.setSize(w, h, false);
  if (camera.isPerspectiveCamera) camera.aspect = w / h; else { const d = camera.top; camera.left = -d * w / h; camera.right = d * w / h; }
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
//<spacemouse> ------------------------------------------------------------------------------------
// 3Dconnexion SpaceMouse (6 ступенів вільності). Два шляхи, обидва без драйверних плагінів:
//  * WebHID — Chrome / Edge / Opera: кнопка «SpaceMouse» → дозвіл на пристрій (сторінка має бути на https або localhost);
//  * Gamepad API — Firefox (і Chrome як запасний шлях): миша видна як 6-осьовий «геймпад»; з'являється після першого руху ковпачка.
// Система миші права: X — праворуч, Y — до себе, Z — вниз; сирі значення ≈ ±350. Режим «об'єкт у руці»: модель рухається за ковпачком.
const SM = { t: [0, 0, 0], r: [0, 0, 0], src: null, hids: [], btn: 0, last: 0, view: 0, cfg: { speed: 1, invPan: false, invZoom: false, invRot: false } };
try { Object.assign(SM.cfg, JSON.parse(localStorage.getItem('spacemouse') || '{}')); } catch (e) { /* сховище недоступне — лишаються типові */ }
const smSave = () => { try { localStorage.setItem('spacemouse', JSON.stringify(SM.cfg)); } catch (e) { /* не критично */ } };
function smUI() {                                            // підписи через t() — сторінка може бути будь-якою мовою
  $('sm').innerHTML = `<div class="row" style="align-items:center;margin-top:6px"><button id="sm_btn" title="${t('sm.btn.title')}">SpaceMouse</button><span id="sm_st" style="color:var(--mute);font-size:11.5px;flex:1;min-width:150px"></span></div>
  <div class="row" style="align-items:center"><label>${t('sm.speed')} <input type="range" id="sm_speed" min="0.2" max="3" step="0.1" style="width:80px;vertical-align:middle;accent-color:var(--acc)"></label>
  <label class="chk"><input type="checkbox" id="sm_ip"> ${t('sm.invPan')}</label><label class="chk"><input type="checkbox" id="sm_iz"> ${t('sm.invZoom')}</label><label class="chk"><input type="checkbox" id="sm_ir"> ${t('sm.invRot')}</label></div>
  <div id="sm_dbg" style="font:11px ui-monospace,Menlo,monospace;color:var(--mute);min-height:14px"></div>`;
  $('sm_speed').value = SM.cfg.speed; $('sm_ip').checked = SM.cfg.invPan; $('sm_iz').checked = SM.cfg.invZoom; $('sm_ir').checked = SM.cfg.invRot;
  $('sm_speed').oninput = e => { SM.cfg.speed = +e.target.value; smSave(); };
  for (const [id, key] of [['sm_ip', 'invPan'], ['sm_iz', 'invZoom'], ['sm_ir', 'invRot']]) $(id).onchange = e => { SM.cfg[key] = e.target.checked; smSave(); };
  $('sm_btn').onclick = smAsk; smStatus();
}
function smStatus(msg) {
  $('sm_st').textContent = msg || (SM.src === 'hid' ? t('sm.hid', { name: SM.hids[0]?.productName || 'SpaceMouse' }) : SM.src === 'pad' ? t('sm.pad', { name: SM.padId })
    : 'hid' in navigator ? t('sm.press') : t('sm.nohid'));
  $('sm_btn').classList.toggle('on', !!SM.src);
}
function smButtons(bits) {                                   // кнопка 1 — вписати модель, кнопка 2 — наступний стандартний вигляд
  const down = bits & ~SM.btn; SM.btn = bits;
  if (down & 1) setView(null);
  if (down & 2) { const ids = ['side', 'iso', 'top', 'front']; SM.view = (SM.view + 1) % ids.length; setView(VIEWS[ids[SM.view]]); }
}
function smReport(e) {                                       // звіт 1 — зсув (у нових моделях одразу і оберт, 12 байт), 2 — оберт, 3 — кнопки
  const d = e.data, n = d.byteLength, v = k => d.getInt16(k, true) / 350;
  if (e.reportId === 1 && n >= 6) { SM.t = [v(0), v(2), v(4)]; if (n >= 12) SM.r = [v(6), v(8), v(10)]; }
  else if (e.reportId === 2 && n >= 6) SM.r = [v(0), v(2), v(4)];
  else if (e.reportId === 3 && n >= 1) smButtons(d.getUint8(0) | (n > 1 ? d.getUint8(1) << 8 : 0));
  SM.last = performance.now(); SM.dbg = t('sm.report', { id: e.reportId, n }); SM.cnt = (SM.cnt || 0) + 1;
}
async function smOpen(dev) {
  if (!dev.opened) await dev.open();
  dev.addEventListener('inputreport', smReport); if (!SM.hids.includes(dev)) SM.hids.push(dev); SM.src = 'hid'; smStatus();
}
const SM_FILTERS = [{ vendorId: 0x256f }, { vendorId: 0x046d, usagePage: 0x01, usage: 0x08 }];   // 3Dconnexion; старі Logitech/3Dconnexion: «multi-axis controller»
async function smAsk() {
  if (!('hid' in navigator)) return smStatus();
  try { const devs = await navigator.hid.requestDevice({ filters: SM_FILTERS }); if (!devs.length) return smStatus(t('sm.nodev')); for (const d of devs) await smOpen(d); }
  catch (e) { smStatus(t('sm.failed', { msg: e.message })); }
}
if ('hid' in navigator) {
  navigator.hid.getDevices().then(ds => ds.filter(d => d.vendorId === 0x256f || d.vendorId === 0x046d).forEach(d => smOpen(d).catch(() => {})));   // уже дозволені пристрої — без запиту
  navigator.hid.addEventListener('connect', e => { if (e.device.vendorId === 0x256f || e.device.vendorId === 0x046d) smOpen(e.device).catch(() => {}); });   // мишу з чинним дозволом знову ввімкнули в USB
  navigator.hid.addEventListener('disconnect', e => { SM.hids = SM.hids.filter(d => d !== e.device); if (!SM.hids.length && SM.src === 'hid') { SM.src = null; SM.t = [0, 0, 0]; SM.r = [0, 0, 0]; smStatus(); } });
}
function smGamepad() {
  if (SM.src === 'hid' || !navigator.getGamepads) return;
  const g = [...navigator.getGamepads()].find(p => p && p.axes.length >= 6 && /3dconnexion|space ?(mouse|navigator|pilot|explorer|ball)|256f/i.test(p.id));
  if (!g) { if (SM.src === 'pad') { SM.src = null; SM.t = [0, 0, 0]; SM.r = [0, 0, 0]; smStatus(); } return; }
  SM.t = [g.axes[0], g.axes[1], g.axes[2]]; SM.r = [g.axes[3], g.axes[4], g.axes[5]]; SM.last = performance.now();
  smButtons(g.buttons.reduce((b, x, i) => b | (x.pressed ? 1 << i : 0), 0));
  if (SM.src !== 'pad') { SM.src = 'pad'; SM.padId = g.id.slice(0, 40); smStatus(); }
}
function smTick(dt) {                                         // викликається кожен кадр перед controls.update()
  smGamepad();
  if (!SM.src || performance.now() - SM.last > 400) return;
  const dz = x => Math.abs(x) < 0.04 ? 0 : Math.max(-1, Math.min(1, x)), [tx, ty, tz] = SM.t.map(dz), [rx, , rz] = SM.r.map(dz);
  if (!(tx || ty || tz || rx || rz)) return;
  const c = SM.cfg, k = c.speed * dt, sp = c.invPan ? -1 : 1, sz = c.invZoom ? -1 : 1, sr = c.invRot ? -1 : 1;
  const off = camera.position.clone().sub(controls.target); let r = off.length();
  let th = Math.atan2(off.y, off.x), ph = Math.acos(Math.max(-1, Math.min(1, off.z / r)));
  th += sr * rz * 1.8 * k;                                   // скрут ковпачка за годинниковою → модель крутиться за годинниковою (камера — проти)
  ph = Math.max(0.02, Math.min(Math.PI - 0.02, ph - sr * rx * 1.4 * k));   // нахил до себе → бачимо модель більше згори
  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  const span = camera.isPerspectiveCamera ? r * 0.9 : (camera.top - camera.bottom) / camera.zoom;
  controls.target.addScaledVector(right, -sp * tx * span * k).addScaledVector(up, sp * tz * span * k);   // ковпачок праворуч/вниз → модель праворуч/вниз
  if (camera.isPerspectiveCamera) r = Math.max(50, Math.min(40000, r * Math.exp(-sz * ty * 1.6 * k)));  // до себе → ближче
  else { camera.zoom = Math.max(0.05, Math.min(50, camera.zoom * Math.exp(sz * ty * 1.6 * k))); camera.updateProjectionMatrix(); }
  camera.position.copy(controls.target).add(new THREE.Vector3(r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th), r * Math.cos(ph)));
  camera.lookAt(controls.target);
}
setInterval(() => {                                           // діагностика: чи взагалі приходять дані з миші та які
  const f = a => a.map(x => (x >= 0 ? '+' : '') + x.toFixed(2)).join(' ');
  $('sm_dbg').textContent = !SM.src ? '' : performance.now() - SM.last > 1500 ? (SM.src === 'hid' ? t('sm.nodata', { n: SM.cnt || 0 }) : '')
    : t('sm.dbg', { src: SM.src === 'hid' ? SM.dbg : 'gamepad', t: f(SM.t), r: f(SM.r) });
}, 200);
smUI(); window.__SM__ = SM; window.__CAM__ = () => ({ p: camera.position.toArray(), t: controls.target.toArray(), zoom: camera.zoom });   // для тестів
//</spacemouse> -----------------------------------------------------------------------------------
//<viewjson> ---------------------------------------------------------------------------------------
// Ракурс у JSON: щоб вид, знайдений тут очима, можна було відрендерити OpenSCAD'ом (tools/views.py).
// Камера сторінки вже в системі координат моделі (camera.up = 0,0,1), тому око й ціль пишуться як є.
// А кут огляду різний: тут 32° по вертикалі, в OpenSCAD 22.5° — перерахунок робить views.py,
// сторінка лише чесно каже свій кут (і півкадр, якщо проєкція паралельна).
// show.pins і show.edges — суто сторінкові: у моделі таких параметрів немає, CLI їх не відтворить.
const VIEW_FOV = 32;                                          // = fov у makeCamera(); тримати однаковим
const VJ_KEY = 'views';                                       // сховище браузера: ракурси переживають перезавантаження
const r1 = v => Math.round(v * 10) / 10;
// Без назви ракурс нічим не адресувати у views.py, а поле легко лишити порожнім —
// тож порожнє замінюємо міткою часу: 2026-09-21-13-47.
const stamp = () => new Date().toLocaleString('sv').replace(/[: ]/g, '-').slice(0, 16);

// Мої ракурси — у сховищі браузера; ті, що лежать у репозиторії (views.json), кожна
// сторінка передає сюди сама: сервер маршрутом, WASM — вшитим import'ом. Сховище може
// бути недоступне (приватне вікно), тому кожне звертання загорнуте.
let myViews = [];
let repoViews = [];
try { myViews = JSON.parse(localStorage.getItem(VJ_KEY) || '[]'); } catch (e) { myViews = []; }
const vjStore = () => { try { localStorage.setItem(VJ_KEY, JSON.stringify(myViews)); } catch (e) { /* немає сховища */ } };
function vjRepo(list) { repoViews = Array.isArray(list) ? list : []; vjFill(); }

function viewJSON(name) {
  const e = camera.position, c = controls.target, par = changed();
  for (const k of ['boom_angle', 'stick_angle', 'bucket_angle']) delete par[k];   // вони окремо, в angles
  const cam = { eye: [r1(e.x), r1(e.y), r1(e.z)], target: [r1(c.x), r1(c.y), r1(c.z)],
                projection: camera.isPerspectiveCamera ? 'p' : 'o',
                aspect: Math.round(canvas.clientWidth / canvas.clientHeight * 100) / 100 };
  if (camera.isPerspectiveCamera) cam.fov_v = VIEW_FOV; else cam.half_height = r1(camera.top / camera.zoom);
  // ground_below_A — «клієнтський» параметр: changed() його НЕ віддає, бо сторінка
  // рухає землю сама, не перебудовуючи модель. Кути — з ang3 з тієї ж причини:
  // повзунки пишуть лише туди, а values.*_angle лишається типовим.
  return { name: name || stamp(), note: '', camera: cam,
           angles: { boom: r1(ang3.boom), stick: r1(ang3.stick), bucket: r1(ang3.bucket) },
           ground_below_A: values.ground_below_A,
           params: par, show: { ...show } };
}

function vjFill() {
  // Через DOM, а не innerHTML: назва ракурсу — чужий текст (її вводить користувач
  // і вона приходить із views.json), а екранування «<» вручну рано чи пізно забудеться.
  // new Option(текст) і g.label ставлять ТЕКСТ, розмітка в них не оживає.
  const sel = $('vj_pick');
  sel.replaceChildren(new Option(t('vw.pick'), ''));
  const grp = (label, list) => {
    if (!list.length) return;
    const g = document.createElement('optgroup'); g.label = label;
    for (const v of list) g.appendChild(new Option(v.name || '—'));
    sel.appendChild(g);
  };
  grp(t('vw.mine'), myViews); grp(t('vw.repo'), repoViews);
  $('vj_row').hidden = !(myViews.length || repoViews.length);
}

function vjUI() {                                             // підписи через t() — сторінка може бути будь-якою мовою
  $('vjson').innerHTML = `<div class="row" style="align-items:center;margin-top:6px" id="vj_row" hidden>
      <select id="vj_pick" style="flex:1;min-width:110px"></select>
      <button id="vj_del" title="${t('vw.del.title')}">✕</button></div>
    <div id="vj_edit" class="adv">
      <div class="row" style="align-items:center;margin-top:6px">
        <input id="vj_name" placeholder="${t('vw.name')}" style="flex:1;min-width:80px">
        <button id="vj_copy" title="${t('vw.copy.title')}">${t('vw.copy')}</button>
        <button id="vj_add" title="${t('vw.add.title')}">${t('vw.add')}</button>
        <button id="vj_save" title="${t('vw.save.title')}">${t('vw.save')}</button></div>
      <div id="vj_st" style="color:var(--mute);font-size:11.5px;margin-top:2px"></div></div>`;
  const st = extra => { const v = viewJSON();
    $('vj_st').textContent = (extra ? extra + ' · ' : '') +
      t('vw.state', { p: v.camera.projection === 'p' ? t('vw.persp') : t('vw.ortho'),
                      e: v.camera.eye.join(', '), c: v.camera.target.join(', '), n: myViews.length }); };
  const picked = () => { const n = $('vj_pick').value;
    return myViews.find(v => (v.name || '—') === n) || repoViews.find(v => (v.name || '—') === n); };
  $('vj_copy').onclick = async () => { await navigator.clipboard.writeText(JSON.stringify(viewJSON($('vj_name').value), null, 2)); st(t('vw.copied')); };
  $('vj_add').onclick = () => { myViews.push(viewJSON($('vj_name').value)); vjStore(); $('vj_name').value = ''; vjFill(); st(t('vw.added')); };
  $('vj_del').onclick = () => { const v = picked(); if (!v) return;
    myViews = myViews.filter(x => x !== v); vjStore(); vjFill(); st(t('vw.removed')); };
  $('vj_pick').onchange = () => { const v = picked(); if (v) { window.__SETVIEW__(v); st(t('vw.applied')); } };
  $('vj_save').onclick = () => {
    const blob = new Blob([JSON.stringify({ views: myViews }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'views.json'; a.click(); URL.revokeObjectURL(a.href);
  };
  controls.addEventListener('change', () => st());
  vjFill();
  st();
}
vjUI(); window.__VIEW__ = viewJSON; window.__VJREPO__ = vjRepo;   // для тестів і для списку з репозиторію
// Поставити сторінку в збережений ракурс — так знімок сторінки можна порівняти
// з рендером тієї самої камери, а не з чимось схожим.
window.__SETVIEW__ = v => {
  camera.position.set(...v.camera.eye); controls.target.set(...v.camera.target);
  if (v.angles) for (const [k, n] of ANG) if (k in v.angles) { values[n] = v.angles[k]; ang3[k] = v.angles[k]; }
  if (v.ground_below_A != null) { values.ground_below_A = v.ground_below_A; buildGround(groundZ()); }
  controls.update(); updatePose();
};
//</viewjson> --------------------------------------------------------------------------------------
vjRepo(repoViewsFile.views);                                  // вшито збіркою

// --------------------------------------------- шухляда знизу на дотикових пристроях
// Три стани: згорнута (сама ручка з числами), робоча і повна. Тягнеться за ручку,
// дотик по ручці згортає/розгортає, дотик по моделі прибирає повну назад у робочу.
// Канва міняє висоту разом зі шухлядою, тож resize() потрібен після переходу.
let sheet = 1;
function setSheet(n) {
  sheet = Math.max(0, Math.min(2, n));
  document.body.classList.toggle('sheet0', sheet === 0);
  document.body.classList.toggle('sheet2', sheet === 2);
  $('grab').setAttribute('aria-expanded', String(sheet > 0));
  try { localStorage.setItem('sheet', String(sheet)); } catch (e) { /* немає сховища */ }
}
{
  const g = $('grab');
  let y0 = null, h0 = 0, raf = 0;
  // Шапка з назвою — 38 px, яких у робочому стані бракує саме на перший ряд поз.
  // На телефоні вона ховається, а перемикач мови переїжджає в ручку шухляди.
  const mob = matchMedia('(max-width: 900px), (pointer: coarse)');
  const placeLang = () => (mob.matches ? g : document.querySelector('.hdr')).appendChild($('lang'));
  placeLang(); mob.addEventListener('change', placeLang);
  // Рух і відпускання слухаємо на ВІКНІ, а не на ручці: палець одразу йде за її межі,
  // а setPointerCapture при емуляції дотику спрацьовує не завжди — перевірено, драг
  // мовчки не доходив до кінця на двох розмірах із трьох.
  g.addEventListener('pointerdown', e => {
    if (e.target.closest('.lang')) return;            // кнопки мови всередині ручки — не драг
    y0 = e.clientY; h0 = $('side').getBoundingClientRect().height;
    document.body.classList.add('dragging');
    e.preventDefault();
  });
  addEventListener('pointermove', e => {
    if (y0 === null) return;
    const h = Math.min(innerHeight * 0.9, Math.max(50, h0 + (y0 - e.clientY)));
    document.body.style.setProperty('--sheet', h + 'px');
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; resize(); });   // без throttle WebGL перемальовується на кожен рух
  });
  const release = e => {
    if (y0 === null) return;
    const h = $('side').getBoundingClientRect().height, moved = Math.abs(e.clientY - y0);
    y0 = null;
    document.body.classList.remove('dragging');
    document.body.style.removeProperty('--sheet');
    setSheet(moved < 6 ? (sheet === 0 ? 1 : 0)
                       : h < innerHeight * 0.2 ? 0 : h > innerHeight * 0.62 ? 2 : 1);
  };
  addEventListener('pointerup', release);
  addEventListener('pointercancel', release);
  g.addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault(); setSheet(sheet === 0 ? 1 : 0);
  });
  $('main').addEventListener('pointerdown', () => { if (sheet === 2) setSheet(1); });
  // Канва міняє не лише висоту, а й ПРОПОРЦІЮ: у згорнутому стані вона вища й вужча,
  // і при сталому вертикальному куті огляду широка машина обрізалася б з боків.
  // Тому після переходу вписуємо її заново — напрямок погляду при цьому зберігається.
  // Змінювати camera.fov не можна: його як сталу віддає viewJSON у спільному блоці.
  $('main').addEventListener('transitionend', e => {
    if (e.propertyName !== 'height') return;
    if (mob.matches) setView(null); else resize();
  });

  let start = 1;
  try { const v = localStorage.getItem('sheet'); if (v !== null) start = +v; } catch (e) { /* немає сховища */ }
  setSheet(Number.isFinite(start) ? start : 1);
  // На великому екрані попередження про ШІ розгорнуте: місця вдосталь, і воно важливе.
  if (!matchMedia('(max-width: 900px), (pointer: coarse)').matches) $('warn').open = true;
}

// ------------------------------------------ розширене: параметри моделі та пристрої, сховані
(function () {                                  // більшості достатньо кутів і вигляду
  const sw = $('adv_on');
  try { sw.checked = localStorage.getItem('adv') === '1'; } catch (e) { /* немає сховища */ }
  const apply = () => {
    document.body.classList.toggle('advon', sw.checked);       // решту робить CSS: body:not(.advon) .adv
    try { localStorage.setItem('adv', sw.checked ? '1' : '0'); } catch (e) { /* не критично */ }
  };
  sw.onchange = apply;
  apply();
})();
let tPrev = performance.now();
(function loop() { const now = performance.now(); smTick(Math.min(0.05, (now - tPrev) / 1000)); tPrev = now; controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); })();

// ---------------------------------------------------------------- мова сторінки
function applyStatic() {                                      // статичні підписи index.html: data-i18n / data-i18n-title
  document.documentElement.lang = getLang();
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll('[data-i18n-title]')) el.title = t(el.dataset.i18nTitle);
  for (const el of document.querySelectorAll('[data-i18n-aria]')) el.setAttribute('aria-label', t(el.dataset.i18nAria));   // елементи без тексту
  for (const el of document.querySelectorAll('[data-i18n-html]')) el.innerHTML = t(el.dataset.i18nHtml);   // рядки з посиланнями
  if (playing) $('play').textContent = t('stop');
}
function buildLangUI() {
  $('lang').innerHTML = '';
  for (const l of LANGS) {
    const b = document.createElement('button'); b.textContent = l.toUpperCase(); b.classList.toggle('on', l === getLang());
    b.onclick = () => { if (l !== getLang()) { setLang(l); renderAll(); } };
    $('lang').appendChild(b);
  }
}
// Зміна мови лише перемальовує підписи: OpenSCAD не перезапускається, кути, галочки й змінені параметри лишаються.
function renderAll() {
  buildLangUI(); applyStatic(); buildAngleUI(); buildPoseUI(); buildViewUI(); buildToggleUI(); smUI();
  if (schema.length) buildParamUI();
  if (lastStatus) status(lastStatus.key, lastStatus.vars, lastStatus.cls);
  updateAngleRanges(); updatePose();
  const u = new URL(location.href);                           // якщо мова прийшла з адреси — тримаємо її актуальною для «поділитися»
  if (u.searchParams.has('lang')) { u.searchParams.set('lang', getLang()); history.replaceState(null, '', u); }
}

(async function init() {
  initLang(location.search);
  renderAll(); resize();
  try {
    await loadSchema();
    ang3.boom = values.boom_angle; ang3.stick = values.stick_angle; ang3.bucket = values.bucket_angle;
    await rebuild();
    setView(VIEWS.side);                       // ракурс з адреси більше не беремо
    window.__READY__ = true;
  } catch (e) { status('st.load', { msg: e.message }, 'err'); }
})();
