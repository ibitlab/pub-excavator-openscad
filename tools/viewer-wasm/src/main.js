import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import scadDefault from '../../../scad/excavator_boom.scad?raw';
// Полігони логотипа: модель підключає їх `include <brand/…>`, тож воркер кладе їх поруч із
// /model.scad. Вшиваються збіркою так само, як модель, — інших джерел файлів сторінка не має.
const scadBrand = Object.fromEntries(Object.entries(
  import.meta.glob('../../../scad/brand/*.scad', { query: '?raw', import: 'default', eager: true }))
  .map(([p, text]) => ['brand/' + p.split('/').pop(), text]));
import repoViewsFile from '../../../views.json';                 // ракурси з репозиторію; Vite вшиває JSON у dist/      // модель вшивається у сторінку; у dev правка .scad перезавантажує сторінку
import { readSchema, scadLiteral } from './schema.js';
import workerUrl from './scad-worker.js?worker&url';
import { LEGEND } from './legend.js';
import { KIN, PIN_HEX, kinLegend } from './kin.js';
import { armFromTip } from './ik.js';   // саме так, інакше Vite не підставить збудований шлях
import { Room, KIND, planeTris, meshTris } from './room.js';
import { Keep } from './keep.js';
import { Scan } from './scan.js';
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
const MOB = matchMedia('(max-width: 900px), (pointer: coarse)');   // розкладка з шухлядою
let lastInfo = ['', ''];                       // два рядки підпису під збереженою картинкою
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
const hemi = new THREE.HemisphereLight(0xffffff, 0x8a8478, 1.15); scene.add(hemi);
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
const show = { cylinders: true, linkage: true, bucket: true, post: true, ground: true, pins: true, edges: true, envelope: false, kin: false };

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
  const base = new THREE.Color(0xc8ccd0);
  for (const [k, d, len] of V.pins) {                         // свій матеріал у кожного: інакше перефарбування чіпає всі разом
    const m = new THREE.Mesh(new THREE.CylinderGeometry(d / 2, d / 2, len, 24),
                             new THREE.MeshStandardMaterial({ color: base.clone(), roughness: 0.35, metalness: 0.6 }));
    m.name = k; m.userData.base = base.clone(); pinsGroup.add(m);   // вісь циліндра three.js — уздовж Y, як і пальці
  }
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
    const nm = `v_cyl_${key}_body`, body = bodies[nm];
    if (body) body.traverse(o => { if (o.isMesh) o.material.color.copy(bad ? new THREE.Color(0xd23c2c) : toneFor(nm, o)); });
    const el = $('cyl_' + key); if (el) { const f = L == null ? 0 : (L - closed) / stroke;
      el.querySelector('.bar').classList.toggle('bad', bad); el.querySelector('i').style.width = Math.max(0, Math.min(1, f)) * 100 + '%';
      el.querySelector('span').textContent = L == null ? t('cyl.nolink') : t('cyl.state', { L: L.toFixed(0), used: (L - closed).toFixed(0), stroke }); }
    if (bad) warn.push(L == null ? t('cyl.out', { part: title })
      : t('cyl.out.range', { part: title, L: L.toFixed(0), lo: closed, hi: closed + stroke }));
    const inp = $('num_' + key), sl = $('sl_' + key); if (document.activeElement !== inp) inp.value = (+a[key].toFixed(1)); sl.value = a[key];
    const arSl = $('ar_' + key); if (arSl) arSl.value = a[key];   // повзунки накладки AR (є після першого входу)
  }
  const gz = -groundZ(), T = P.T, mm = t('hud.mm');
  const where = z => t(z >= 0 ? 'hud.above' : 'hud.below');
  const tbl = el('table');
  const line = (label, ...kids) => { const tr = el('tr'); tr.append(el('td', { textContent: label }), el('td')); tr.lastChild.append(...kids); tbl.appendChild(tr); };
  const dz = T[1] - gz, під = dz < 0;                         // головне число сторінки: куди дістає зуб
  line(t('hud.reach'), el('b', { textContent: T[0].toFixed(0) }), ' ' + mm);
  line(t('hud.tooth', { where: where(dz) }),
       el('b', { textContent: Math.abs(dz).toFixed(0), className: під ? 'neg' : '' }),
       el('span', { textContent: ' ' + mm, className: під ? 'neg' : '' }));
  line(t('hud.axisE', { where: where(P.E[1] - gz) }), Math.abs(P.E[1] - gz).toFixed(0) + ' ' + mm);
  line(t('hud.tilt'), tiltText(P.bdir));
  $('hud').replaceChildren(tbl);
  // Ті самі числа — у ручці шухляди: у згорнутому стані це все, що видно з панелі.
  // «мм» один раз: у ручці лічені пікселі. Через DOM, бо «нижче землі» фарбуємо.
  // Без «мм»: у ручці лічені пікселі, а одиниці тут і так очевидні — повні числа
  // з одиницями лишаються в HUD і в підписі під збереженою картинкою.
  $('grab_info').replaceChildren(`${t('m.reach')} ${T[0].toFixed(0)} · ${t('m.tooth')} `,
    el('b', { textContent: `${Math.abs(dz).toFixed(0)} ${where(dz)}`,
              style: під ? 'color:var(--bad)' : 'font-weight:400' }));
  $('gz_info').textContent = `${t('gz.info')}: ${values.ground_below_A} ${mm}`;
  // те саме текстом — для підпису під збереженою картинкою
  lastInfo = [`${t('hud.reach')}: ${T[0].toFixed(0)} ${mm} · ${t('hud.tooth', { where: where(dz) })}: `
              + `${Math.abs(dz).toFixed(0)} ${mm} · ${t('hud.axisE', { where: where(P.E[1] - gz) })}: `
              + `${Math.abs(P.E[1] - gz).toFixed(0)} ${mm}`,
              ANG.map(([k]) => `${t('ang.' + k)} ${effAngles()[k].toFixed(0)}°`).join(' · ')
              + ` · ${t('hud.tilt')}: ${tiltText(P.bdir)}`
              + ` · ${t('gz.info')}: ${values.ground_below_A} ${mm}`];
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
// Перефарбування за жорсткими тілами і підсвітка вибраного. Базовий колір кожної
// сітки лежить у userData.base — тим самим шляхом гільза червоніє поза ходом.
let picked = null;                                            // тіло, підсвічене дотиком
const FADE = new THREE.Color(0xe6e3dc);                       // у що гасимо решту
const HILITE = new THREE.Color(0xc9731a);                     // вибране тіло — одним кольором
// Один обчислювач тону на всіх: ним же користується updatePose, коли фарбує гільзу
// червоним поза ходом. Інакше вона щокадру поверталася б до базового кольору й
// збивала і кінематичне фарбування, і підсвітку.
function toneFor(name, mesh) {
  const kin = show.kin && KIN[name] ? new THREE.Color(KIN[name].hex) : null;
  const on = picked === name;
  // Вибране тіло фарбуємо ОДНИМ кольором, а не лишаємо власні: половина деталей
  // і так сіра, і на тлі вицвілого сірого підсвітки просто не видно.
  const c = on ? (kin || HILITE) : (kin || mesh.userData.base);
  return (picked && !on) ? c.clone().lerp(FADE, 0.75) : c;
}
function paint() {
  for (const [name, g] of Object.entries(bodies))
    g.traverse(o => { if (o.isMesh) o.material.color.copy(toneFor(name, o)); });
  for (const m of pinsGroup.children) {
    const c = show.kin ? new THREE.Color(PIN_HEX) : m.userData.base;
    m.material.color.copy(picked ? c.clone().lerp(FADE, 0.75) : c);
  }
}
function pick(name) {                                         // null — зняти підсвітку
  picked = picked === name ? null : name;
  paint();
}
window.__PICK__ = () => picked;                               // для тестів
function applyShow() {
  if (bodies.post) bodies.post.visible = show.post; if (bodies.bucket) bodies.bucket.visible = show.bucket;
  ground.visible = show.ground; envelope.visible = show.envelope;
  for (const k in bodies) bodies[k].traverse(o => { if (o.userData.edge) o.visible = show.edges; });
  paint(); buildLegend();                                     // легенда залежить від режиму
  updateEnvelope(); updatePose();
}

// ---------------------------------------------------------------- керування: кути, пози, вигляд
function buildAngleUI() {
  $('angles').innerHTML = '';
  for (const [key] of ANG) {
    const title = t('ang.' + key), hint = t('ang.' + key + '.hint');
    const d = document.createElement('div'); d.className = 'ang';
    d.innerHTML = `<div class="top"><label for="sl_${key}" title="${t('ang.' + key + '.ref')}">${title} <span style="color:var(--mute);font-weight:400">· ${hint}</span></label><span><input type="number" id="num_${key}" step="1"> °</span></div>
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
// Кадри анімації пози — з власного циклу рендера, а не з requestAnimationFrame вікна:
// у сеансі AR браузер його не викликає, і цикл копання там стояв би.
const frameQ = [], nextFrame = f => frameQ.push(f);
function glide(to, ms = 600, then) {
  const from = [ang3.boom, ang3.stick, ang3.bucket], t0 = performance.now(); anim = { cancel: false };
  const me = anim, step = t => { if (me.cancel) return; const k = Math.min(1, (t - t0) / ms), e = k * k * (3 - 2 * k);
    ang3.boom = from[0] + (to[0] - from[0]) * e; ang3.stick = from[1] + (to[1] - from[1]) * e; ang3.bucket = from[2] + (to[2] - from[2]) * e; updatePose();
    if (k < 1) nextFrame(step); else if (then) then(); }; nextFrame(step);
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
// Іконки видів — як у CAD: куб в ізометрії з підсвіченою гранню, на яку дивишся.
// Розмітка тут НАША власна й стала (жодних чужих даних), тому insertAdjacentHTML
// доречний; підпис поруч лишається текстом.
const CUBE = { top: 'M12 3l8 4.5-8 4.5-8-4.5z', left: 'M4 7.5l8 4.5v9l-8-4.5z', right: 'M20 7.5l-8 4.5v9l8-4.5z' };
// Заливка навмисно бліда: при щільній три залиті грані зливаються в темний кубик
// і жодної інформації не лишається — перевірено на знімку.
const cube = (...faces) =>
  '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false">'
  + faces.map(f => `<path d="${CUBE[f]}" fill="currentColor" opacity=".38"/>`).join('')
  + '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round">'
  + `<path d="${CUBE.top}"/><path d="${CUBE.left}"/><path d="${CUBE.right}"/></g></svg>`;
const ICON = {
  side:  cube('right'),                 // дивимось збоку — світиться бічна грань
  iso:   cube(),                        // три чверті — жодної грані, просто куб
  back:  cube('top', 'right'),          // ззаду-згори — дві грані
  top:   cube('top'),
  front: cube('left'),
  fit:   '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false">'
       + '<rect x="9" y="9" width="6" height="6" fill="currentColor" opacity=".55"/>'
       + '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" stroke="currentColor"'
       + ' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  // Проєкція — не вид, а СТАН, тож іконка показує поточний: у перспективі
  // сторони кадру сходяться, в ортогональній — паралельні.
  ortho: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false">'
       + '<rect x="5" y="7" width="14" height="10" rx="1" fill="currentColor" fill-opacity=".2"'
       + ' stroke="currentColor" stroke-width="1.4"/></svg>',
  lockOn:  '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false">'
         + '<rect x="5" y="10.5" width="14" height="9.5" rx="2" fill="currentColor" fill-opacity=".25"'
         + ' stroke="currentColor" stroke-width="1.4"/>'
         + '<path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
  lockOff: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false">'
         + '<rect x="5" y="10.5" width="14" height="9.5" rx="2" fill="none"'
         + ' stroke="currentColor" stroke-width="1.4"/>'
         + '<path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
  persp: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" focusable="false">'
       + '<path d="M8 7h8l3 10H5z" fill="currentColor" fill-opacity=".2" stroke="currentColor"'
       + ' stroke-width="1.4" stroke-linejoin="round"/></svg>',
};
function viewButton(id, onclick) {
  const b = el('button', { onclick });
  b.insertAdjacentHTML('afterbegin', ICON[id]);
  b.appendChild(el('span', { className: 'lbl', textContent: t('view.' + id) }));
  b.title = t('view.' + id);
  b.setAttribute('aria-label', t('view.' + id));
  return b;
}
// Перемикач проєкції серед кнопок видів читався як сьомий вид. Тепер він і
// виглядає перемикачем: окрема група за роздільником, кругла форма замість
// прямокутної, іконка показує ПОТОЧНИЙ стан, і є aria-pressed.
function syncOrtho(b) {
  b.classList.toggle('on', ortho);
  b.setAttribute('aria-pressed', String(ortho));
  b.firstChild.remove();
  b.insertAdjacentHTML('afterbegin', ICON[ortho ? 'ortho' : 'persp']);
  const txt = t(ortho ? 'view.ortho' : 'view.persp');
  b.querySelector('.lbl').textContent = txt;
  b.title = t('view.proj', { p: txt });
  b.setAttribute('aria-label', b.title);
}
function buildViewUI() {
  const box = $('views');
  box.replaceChildren();
  const sep = () => box.appendChild(el('span', { className: 'sep' }));
  for (const [id, d] of Object.entries(VIEWS)) {
    if (id === 'fit') sep();                                  // далі вже не види, а дія
    box.appendChild(viewButton(id, () => setView(d)));
  }
  sep();
  const b = viewButton('ortho', () => { setView(null, !ortho); syncOrtho(b); });
  b.classList.add('tgl');
  box.appendChild(b);
  syncOrtho(b);
  placeLock();                                                // ряд щойно перебудовано — замок повертаємо на місце
}
// На телефоні замок живе в РУЧЦІ шухляди, поруч зі значком ⚠: ручка прилипла до
// верху панелі й видна завжди, а ряд видів у заголовку «Кути» прокручується.
// На комп'ютері замок плаває над канвою. Тримаємо ВУЗОЛ, а не шукаємо щоразу:
// при перебудові ряду видів від'єднаний вузол уже не знайшовся б.
const lockBtn = $('lock');
function placeLock() { (MOB.matches ? $('grab') : $('main')).appendChild(lockBtn); }
function buildLegend() {                                      // кольори — з color(...) моделі, див. legend.js
  const box = $('legend'); box.replaceChildren();
  for (const l of (show.kin ? kinLegend() : LEGEND)) {
    const sp = el('span'); sp.append(el('i', { style: `background:${l.hex}` }), t(l.key));
    box.appendChild(sp);
  }
}
const TOG = ['cylinders', 'linkage', 'bucket', 'post', 'pins', 'ground', 'edges', 'envelope', 'kin'];
function buildToggleUI() {
  $('toggles').innerHTML = '';
  // id="tog_НАЗВА" — щоб проба (tools/media/probe.mjs) цілилася в прапорець за ім'ям,
  // а не за порядковим номером чи підписом: підпис змінюється з мовою.
  for (const k of TOG) { const l = document.createElement('label'); l.className = 'chk'; l.innerHTML = `<input type="checkbox" id="tog_${k}" ${show[k] ? 'checked' : ''}> ${t('tog.' + k)}`;
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
// Рушій — 11 МБ одним файлом (wasm зашито в base64 усередині воркера), і браузер
// тягне його мовчки. Тому завантажуємо самі, потоково, з показом відсотків, і
// віддаємо воркеру вже готовий Blob — так файл їде рівно один раз.
// У dev так не можна: там воркер ще не зібраний і має справжні import-и.
function loadNote(key, vars, pct, sub) {
  const box = $('load');
  box.hidden = false;
  box.querySelector('.ttl').textContent = t(key, vars);
  box.classList.toggle('busy', pct == null);                  // без відсотків — біжуча смужка
  box.querySelector('.track i').style.width = pct == null ? '' : pct + '%';
  box.querySelector('.sub').textContent = sub || '';
}
const ENGINE_MB = 11;                                         // приблизний розмір воркера з убудованим wasm
let noBlob = false;                                           // якщо Blob-воркер не заведеться — більше не пробуємо
async function makeWorker() {
  const plain = () => new Worker(workerUrl, { type: 'module' });
  if (!import.meta.env.PROD || noBlob) return plain();
  try {
    const r = await fetch(workerUrl);
    if (!r.ok || !r.body) return plain();
    // Content-Length при стисненні — це розмір СТИСНУТОГО, а читач дає розпакований.
    // Тому точну частку беремо лише без стиснення, інакше рахуємо від відомих ~11 МБ.
    const total = (!r.headers.get('content-encoding') && +r.headers.get('content-length')) || ENGINE_MB * 1e6;
    const reader = r.body.getReader(), chunks = [];
    let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value); got += value.length;
      loadNote('load.engine', {}, Math.min(99, Math.round(got / total * 100)),
               `${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(0)} ${t('hud.mb')}`);
    }
    // файл уже тут, але далі ще кілька секунд — компіляція wasm і перша побудова моделі;
    // без цього смужка так і стояла б на 99 % «завантаження», ніби сторінка зависла
    loadNote('load.build', {}, null);
    return new Worker(URL.createObjectURL(new Blob(chunks, { type: 'text/javascript' })), { type: 'module' });
  } catch (e) {
    return plain();                                           // не вийшло — хай тягне браузер, як раніше
  }
}
async function runOpenSCAD(defs) {                            // один запуск у воркері: part="view_all" → усі деталі одразу
  if (!worker) worker = await makeWorker();
  const id = ++jobId;
  return new Promise((resolve, reject) => {
    const done = e => { if (e.data.id !== id) return; worker.removeEventListener('message', done); resolve(e.data); };
    worker.addEventListener('message', done);
    worker.onerror = e => {
      worker.terminate(); worker = null;
      if (!noBlob) { noBlob = true; resolve(runOpenSCAD(defs)); return; }   // Blob не завівся — пробуємо звичайним шляхом
      reject(new Error(e.message || t('st.worker')));
    };
    worker.postMessage({ id, source: scadSource, files: scadBrand, defs });
  });
}
async function rebuild() {
  if (inflight) { again = true; return; } inflight = true;
  status(engineReady ? 'st.build' : 'st.engine', {}, 'busy');
  if (!engineReady) loadNote('load.engine', {}, null); else if (!$('load').hidden) loadNote('load.build', {}, null);
  // Поки смужка біжуча (без відсотків), під нею йдуть секунди — видно, що робота триває
  const tStart = performance.now(), tick = setInterval(() => {
    const box = $('load');
    if (!box.hidden && box.classList.contains('busy'))
      box.querySelector('.sub').textContent = t('load.elapsed', { s: Math.round((performance.now() - tStart) / 1000) });
  }, 500);
  try {
    const ch = changed(), defs = Object.keys(ch).sort().map(k => `${k}=${scadLiteral(byName[k], ch[k])}`);
    const t0 = performance.now(), d = await runOpenSCAD(defs);
    if (d.error) { status('st.err', { msg: d.error }, 'err'); lastLog = d.log || []; }
    else { engineReady = true; $('load').hidden = true; showTip(); applyBuild(d); status('st.done', { ms: (d.ms / 1000).toFixed(2), total: ((performance.now() - t0) / 1000).toFixed(2), n: Object.keys(ch).length }); }
  } catch (e) { status('st.err', { msg: e.message }, 'err'); }
  clearInterval(tick);
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

// ------------------------------------------ перетягування машини за ківш
// Хапаєш корпус ковша — за пальцем іде вся стріла (зворотна задача, ik.js).
// Хапаєш зуби — ківш підвертається навколо осі E, стріла стоїть.
// Замок вимикає обертання камери зовсім: тоді тягнути можна з будь-якого місця.
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
const GROUND_PLANE = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
let drag = null, locked = false;

function aim(e) {                                             // промінь із пальця/курсора
  const r = canvas.getBoundingClientRect();
  ndc.set((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height * 2 - 1));
  ray.setFromCamera(ndc, camera);
}
function planePoint(e) {                                      // машина пласка, тож ціль — площина y=0
  aim(e);
  const p = new THREE.Vector3();
  return ray.ray.intersectPlane(GROUND_PLANE, p) ? [p.x, p.z] : null;
}
function onBucket(e) {
  if (!bodies.bucket || !bodies.bucket.visible) return false;
  aim(e);
  return ray.intersectObject(bodies.bucket, true).length > 0;
}
const clampAng = (key, v) => {
  const l = limits(key);
  return ($('clamp').checked && l) ? Math.min(l[1], Math.max(l[0], v)) : v;
};

// Підказка про перетягування має ДВА місця. Постійне — у картці під значком ⚠
// (там же, де попередження про ШІ): її видно завжди й на телефоні, і на комп'ютері.
// Плашка над моделлю — лише для того, хто тут уперше, і тримається, доки він не
// зробить ДВІ операції: після однієї ще не видно, що жест повторюваний, а таймер
// сховав би її від того, хто читає повільно.
const TIP_NEED = 2;
let tipDone = 0;
function hideTip(learned) {
  const box = $('tip');
  if (box.hidden || box.classList.contains('away')) return;
  box.classList.add('away');
  setTimeout(() => { box.hidden = true; }, 400);
  if (learned) { try { localStorage.setItem('tip', 'off'); } catch (e) { /* немає сховища */ } }
}
function tipOperation() {                                     // одне завершене перетягування
  if ($('tip').hidden) return;
  if (++tipDone >= TIP_NEED) hideTip(true);
}
function showTip() {
  let seen = null;
  try { seen = localStorage.getItem('tip'); } catch (e) { /* приватне вікно — покажемо */ }
  if (seen === 'off') return;                                 // вже навчився; текст лишається за значком ⚠
  $('tip').hidden = false;
}
$('tip_x').onclick = () => hideTip(true);

canvas.addEventListener('pointerdown', e => {
  if (!V || e.button === 2) return;
  if (!locked && !onBucket(e)) return;                        // без замка порожнє місце крутить камеру
  const p = planePoint(e); if (!p) return;
  const a = effAngles(), P = pose(V, a.boom, a.stick, a.bucket);
  const близькоЗуба = Math.hypot(p[0] - P.T[0], p[1] - P.T[1]) < V.tip * 0.4;
  drag = близькоЗуба
    ? { curl: true, off: ang(sub(p, P.E)) - P.bdir }          // тримаємо взяту точку під пальцем
    : { curl: false, off: sub(P.T, p) };
  controls.enabled = false;
  canvas.setPointerCapture(e.pointerId);
  canvas.style.cursor = 'grabbing';
  stopPlay();
});
canvas.addEventListener('pointermove', e => {
  if (!drag) {
    if (!matchMedia('(pointer: coarse)').matches)
      canvas.style.cursor = locked ? 'grab' : (V && onBucket(e) ? 'grab' : '');
    return;
  }
  const p = planePoint(e); if (!p) return;
  drag.moved = true;
  const a = effAngles();
  if (drag.curl) {
    const P = pose(V, a.boom, a.stick, a.bucket);
    ang3.bucket = clampAng('bucket', P.sdir - (ang(sub(p, P.E)) - drag.off));
  } else {
    const r = armFromTip(V, add(p, drag.off), a.bucket, ang3);
    if (r) { ang3.boom = clampAng('boom', r.boom); ang3.stick = clampAng('stick', r.stick); }
  }
  updatePose();
});
// Дотик без руху — не перетягування, а питання «що рухається разом із цим?».
// Слухаємо на перехопленні, щоб спрацювало й тоді, коли перетягування не почалося
// (порожнє місце крутить камеру, і звичайний pointerdown туди не дійде).
let tapAt = null;
canvas.addEventListener('pointerdown', e => { tapAt = [e.clientX, e.clientY]; }, true);
canvas.addEventListener('pointerup', e => {
  if (!tapAt) return;
  const moved = Math.hypot(e.clientX - tapAt[0], e.clientY - tapAt[1]);
  tapAt = null;
  if (moved > 6 || !V) return;
  aim(e);
  const hit = ray.intersectObjects(Object.values(bodies), true).find(i => i.object.isMesh);
  let o = hit && hit.object;
  while (o && !bodies[o.name]) o = o.parent;
  pick(o ? o.name : null);
});

const dropDrag = e => {
  if (!drag) return;
  if (drag.moved) tipOperation();                             // рахуємо саме ЗАВЕРШЕНІ перетягування, а не дотики
  drag = null; controls.enabled = !locked;
  canvas.style.cursor = locked ? 'grab' : '';
  if (e && canvas.hasPointerCapture?.(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
};
canvas.addEventListener('pointerup', dropDrag);
canvas.addEventListener('pointercancel', dropDrag);

function syncLock() {
  const b = lockBtn;
  b.classList.toggle('on', locked);
  b.setAttribute('aria-pressed', String(locked));
  if (b.firstChild && b.firstChild.tagName === 'svg') b.firstChild.remove();
  b.insertAdjacentHTML('afterbegin', ICON[locked ? 'lockOn' : 'lockOff']);
  b.querySelector('.lbl').textContent = t('lock');
  b.title = t('lock.title');
  b.setAttribute('aria-label', t('lock'));
}
lockBtn.onclick = () => {
  locked = !locked;
  controls.enabled = !locked;
  canvas.style.cursor = locked ? 'grab' : '';
  syncLock();
};

// ------------------------------------------------------- знімок кадру у PNG
// Канва рендериться з preserveDrawingBuffer, тож її можна просто перемалювати в
// інший canvas. Під кадром — смуга з тими самими числами, що в HUD: знімок без
// них нічого не доводить, а екранний знімок тягне за собою всю панель.
function pngBlob() {
  renderer.render(scene, camera);                             // свіжий кадр у буфері
  const w = canvas.width, h = canvas.height, k = w / (canvas.clientWidth || w);
  const pad = Math.round(13 * k), lh = Math.round(17 * k), strip = pad * 2 + lh * 2;
  const out = document.createElement('canvas');
  out.width = w; out.height = h + strip;
  const g = out.getContext('2d');
  g.drawImage(canvas, 0, 0);
  g.fillStyle = '#fbfaf7'; g.fillRect(0, h, w, strip);
  g.fillStyle = '#ddd8cd'; g.fillRect(0, h, w, Math.max(1, Math.round(k)));
  g.textBaseline = 'top';
  g.fillStyle = '#23262b'; g.font = `${Math.round(12.5 * k)}px -apple-system, "Segoe UI", Roboto, Arial, sans-serif`;
  g.fillText(lastInfo[0], pad, h + pad);
  g.fillStyle = '#6d7278'; g.font = `${Math.round(11.5 * k)}px -apple-system, "Segoe UI", Roboto, Arial, sans-serif`;
  g.fillText(lastInfo[1], pad, h + pad + lh);
  return new Promise(res => out.toBlob(res, 'image/png'));
}
window.__PNG__ = pngBlob;                                     // для тестів і для набору матеріалів
// Екранні координати зуба й осі ковша — потрібні тестам, щоб «схопити» ківш там,
// де він насправді намальований, а не вгадувати точку.
window.__ONSCREEN__ = () => {
  if (!V) return null;
  const a = effAngles(), P = pose(V, a.boom, a.stick, a.bucket), r = canvas.getBoundingClientRect();
  const to2d = q => { const v = new THREE.Vector3(q[0], 0, q[1]).project(camera);
    return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height]; };
  const box = new THREE.Box3().setFromObject(bodies.bucket), c = box.getCenter(new THREE.Vector3());
  return { tooth: to2d(P.T), axisE: to2d(P.E), body: to2d([c.x, c.z]) };   // body — центр габариту, там метал
};
$('png').onclick = async () => {
  const blob = await pngBlob();
  const name = `excavator-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}.png`;
  const file = new File([blob], name, { type: 'image/png' });
  // На телефоні «завантажити» веде в теку, якої користувач може й не знайти;
  // системний «Поділитися» дає і збереження у фото, і надсилання.
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file] }); return; } catch (e) { if (e.name === 'AbortError') return; }
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
};

// ------------------------------------------------------------------- клавіші
// Лише для клавіатури: на дотикових це мертвий код, тож і не вішаємо.
if (!matchMedia('(pointer: coarse)').matches) {
  const KEYS = Object.keys(VIEWS);                            // 1..6 — ті самі види, що кнопками
  addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const el = document.activeElement;
    if (el && /^(input|select|textarea|summary)$/.test(el.tagName.toLowerCase())) return;
    const i = '123456'.indexOf(e.key);
    if (i >= 0 && i < KEYS.length) { setView(VIEWS[KEYS[i]]); e.preventDefault(); return; }
    if (e.key === ' ') { $('play').click(); e.preventDefault(); }
  });
}

// --------------------------------------------- шухляда знизу на дотикових пристроях
// Три стани: згорнута (сама ручка з числами), робоча і повна. Тягнеться за ручку,
// дотик по ручці згортає/розгортає, дотик по моделі прибирає повну назад у робочу.
// Канва міняє висоту разом зі шухлядою, тож resize() потрібен після переходу.
let sheet = 1, prevSheet = 1, savedScroll = 0, restoreScroll = false;
function setSheet(n) {
  const from = sheet;
  sheet = Math.max(0, Math.min(2, n));
  // Згортаємо — запамʼятовуємо, де людина була: і стан, і місце прокрутки. Інакше
  // після згортання панель повертається на початок, а вона могла гортати її донизу.
  if (from > 0 && sheet === 0) { prevSheet = from; savedScroll = $('side').scrollTop; }
  if (from === 0 && sheet > 0) restoreScroll = true;
  document.body.classList.toggle('sheet0', sheet === 0);
  document.body.classList.toggle('sheet2', sheet === 2);
  $('grab').setAttribute('aria-expanded', String(sheet > 0));
  $('fold_btn').textContent = sheet > 0 ? '▾' : '▴';
  try { localStorage.setItem('sheet', String(sheet)); } catch (e) { /* немає сховища */ }
}
const foldToggle = () => setSheet(sheet > 0 ? 0 : prevSheet);
{
  const g = $('grab');
  let y0 = null, h0 = 0, raf = 0;
  // Шапка з назвою — 38 px, яких у робочому стані бракує саме на перший ряд поз.
  // На телефоні вона ховається, а перемикач мови переїжджає в ручку шухляди.
  const mob = matchMedia('(max-width: 900px), (pointer: coarse)');
  const placeLang = () => (mob.matches ? g : document.querySelector('.hdr')).appendChild($('lang'));
  // Види на телефоні переїжджають у рядок заголовка «Кути»: так вони на першому
  // екрані, без прокрутки, а сам заголовок коротшає, щоб звільнити місце.
  const h2ang = $('h2ang'), h2txt = h2ang.firstElementChild;
  const placeViews = () => {
    // на великому екрані види повертаються у свій блок «Вигляд», а не під «Кути»
    if (mob.matches) h2ang.appendChild($('views'));
    else document.querySelector('h2[data-i18n="h2.view"]').after($('views'));
    h2txt.textContent = t(mob.matches ? 'h2.angles.short' : 'h2.angles');
  };
  placeLang(); placeViews(); placeLock(); syncLock();
  mob.addEventListener('change', () => { placeLang(); placeViews(); placeLock(); });
  // Рух і відпускання слухаємо на ВІКНІ, а не на ручці: палець одразу йде за її межі,
  // а setPointerCapture при емуляції дотику спрацьовує не завжди — перевірено, драг
  // мовчки не доходив до кінця на двох розмірах із трьох.
  $('fold_btn').onclick = foldToggle;
  $('warn_btn').onclick = () => { $('warn').open = !$('warn').open; };
  $('warn').addEventListener('click', () => { if (mob.matches) $('warn').open = false; });
  g.addEventListener('pointerdown', e => {
    if (e.target.closest('.lang') || e.target.closest('button')) return;   // кнопки в ручці — не драг
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
    if (moved < 6) foldToggle();                       // дотик по ручці — те саме, що кнопка
    else setSheet(h < innerHeight * 0.2 ? 0 : h > innerHeight * 0.62 ? 2 : 1);
  };
  addEventListener('pointerup', release);
  addEventListener('pointercancel', release);
  g.addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault(); foldToggle();
  });
  $('main').addEventListener('pointerdown', () => { if (sheet === 2) setSheet(1); });
  // Канва міняє не лише висоту, а й ПРОПОРЦІЮ: у згорнутому стані вона вища й вужча,
  // і при сталому вертикальному куті огляду широка машина обрізалася б з боків.
  // Тому після переходу вписуємо її заново — напрямок погляду при цьому зберігається.
  // Змінювати camera.fov не можна: його як сталу віддає viewJSON у спільному блоці.
  $('main').addEventListener('transitionend', e => {
    if (e.propertyName !== 'height') return;
    if (mob.matches) setView(null); else resize();
    if (restoreScroll) { $('side').scrollTop = savedScroll; restoreScroll = false; }
  });

  let start = 1;
  try { const v = localStorage.getItem('sheet'); if (v !== null) start = +v; } catch (e) { /* немає сховища */ }
  setSheet(Number.isFinite(start) ? start : 1);
  // Попередження згорнуте ВСЮДИ: видно рядок-підсумок, решту користувач розкриває
  // сам. Розгорнутий абзац на кожному екрані лише відволікає від моделі.
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
// ------------------------------------------ AR: машина в кімнаті через камеру телефона
// WebXR immersive-ar — Chrome на Android з ARCore. Сцену й далі малює ця сторінка, тож
// поза працює так само, як на екрані: повзунки → ang3 → updatePose(). Safari на iPhone
// WebXR для AR не має — там кнопка просто не з'являється.
// Модель — у мм і з Z догори, WebXR — у метрах і з Y догори. Тому world повертається
// на −90° навколо X (x, y, z → x, z, −y) і масштабується, а arRoot стоїть у точці на підлозі.
// Камера своя: у камери сторінки near = 20 (мм), а WebXR прочитав би це як 20 м.
const arRoot = new THREE.Group();
const arCam = new THREE.PerspectiveCamera(50, 1, 0.02, 100);
const reticle = new THREE.Mesh(new THREE.RingGeometry(0.11, 0.14, 40).rotateX(-Math.PI / 2),
                               new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false }));
reticle.matrixAutoUpdate = false; reticle.renderOrder = 10;
const AR_SCALES = [1, 5];                                     // 1:1 — надворі, 1:5 — на столі
const AR = { session: null, hitSrc: null, placing: true, scale: 1, saved: null,
             feat: null, depthFmt: '', occl: true, room: true, coll: true, hits: [], tHit: 0, tBuild: 0, dirty: false,
             scan: false, dz: null, tScan: 0, tMesh: 0, tKeep: 0 };

// --- AR: кімната. Три необов'язкові можливості WebXR, кожна вмикається лише там, де браузер її дав:
// depth-sensing — карта глибин кадру (Chrome на Android з ARCore Depth): справжні предмети затуляють машину;
// plane-detection — площини підлоги, стін, столів (Chrome — за прапорцем WebXR Incubations; Quest);
// mesh-detection — сітка приміщення (Quest 3; Chrome на Android її не дає).
// Площини й сітки малюються напівпрозоро і йдуть у перевірку зіткнень (room.js).
//
// Затуляння: перед машиною малюємо на весь кадр «невидимий» прямокутник, що пише в буфер глибини
// відстань до справжньої поверхні. Тоді все, що в моделі далі за неї, не проходить тест глибини —
// і так для будь-якого матеріалу, без правки шейдерів деталей. Глибину відсуваємо на 2 % + 3 см,
// інакше площини кімнати, які лежать рівно на поверхнях, мерехтіли б від шуму вимірювання.
const occlU = { depth: { value: null }, uvm: { value: new THREE.Matrix4() }, p10: { value: 0 }, p14: { value: 0 } };
const occl = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
  uniforms: occlU, colorWrite: false, depthWrite: true, depthTest: true, depthFunc: THREE.AlwaysDepth,
  vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 1.0, 1.0); }',
  fragmentShader: `uniform sampler2D depth; uniform mat4 uvm; uniform float p10, p14; varying vec2 vUv;
    void main() {
      vec2 duv = (uvm * vec4(vUv.x, 1.0 - vUv.y, 0.0, 1.0)).xy;   // нормалізовані координати виду: початок угорі ліворуч
      float d = texture2D(depth, duv).r;
      if (d <= 0.0) gl_FragDepth = 1.0;                           // глибини немає — нічого не затуляє
      else { d = d * 1.02 + 0.03; gl_FragDepth = clamp(((p14 - p10 * d) / d) * 0.5 + 0.5, 0.0, 1.0); }
      gl_FragColor = vec4(0.0);
    }` }));
occl.frustumCulled = false; occl.renderOrder = -1e6; occl.visible = false;
occl.onBeforeRender = (r, s, cam) => { const e = cam.projectionMatrix.elements; occlU.p10.value = e[10]; occlU.p14.value = e[14]; };

const roomGroup = new THREE.Group(), roomSrc = new Map(), room = new Room();   // roomSrc: XRPlane / XRMesh → що з нього зроблено
const ROOM_HEX = [0x3aa0ff, 0x3ccf7a, 0xffb020];               // за KIND: стіна · поверхня · предмет
const roomFill = ROOM_HEX.map(c => new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false }));
const roomLine = ROOM_HEX.map(c => new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0.8 }));
const roomWire = ROOM_HEX.map(c => new THREE.MeshBasicMaterial({ color: c, wireframe: true, transparent: true, opacity: 0.35, depthWrite: false }));
// Зліпок (keep.js): площини, які ARCore перестав віддавати, лишаються тінями — штриховий контур;
// поки тінь чекає рішення, заливка ледь видна, а залишена назавжди — як у живої площини.
const keep = new Keep(), ghostObj = new Map();
const ghostFill = ROOM_HEX.map(c => new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.06, side: THREE.DoubleSide, depthWrite: false }));
const ghostLine = ROOM_HEX.map(c => new THREE.LineDashedMaterial({ color: c, dashSize: 0.06, gapSize: 0.04, transparent: true, opacity: 0.8 }));
// Скан кімнати з карт глибин (кнопка ▤, scan.js): поки кнопка ввімкнена, кадри глибини зливаються в 3D-модель
// простору сеансу. Малюється заливкою й сіткою, кольорами кімнати за нахилом поверхні; прозорість — повзунок у панелі:
// від ледь видимої до суцільної (тоді видно лише модель, а реальність — там, де скану ще немає).
// Об'єм: світло сцени на гладких нормалях скану (градієнт TSDF), затінення кутів (AO зі scan.js — у кольорі вершин),
// і в шейдері ще два множники, що не чіпають машину: поверхня боком до погляду темніша (як ліхтар на камері —
// найсильніша підказка форми), далека — трохи тьмяніша.
// Модель ділиться на шматки 1.6 м (scan.takeChunks): раз на секунду перебудовуються лише змінені.
const scan = new Scan(), SCAN_L = 96, ROOM_RGB = ROOM_HEX.map(c => new THREE.Color(c).toArray());   // SCAN_L — променів уздовж довшого боку кадру
const scanFillM = new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, depthWrite: false });
scanFillM.onBeforeCompile = sh => {
  sh.fragmentShader = sh.fragmentShader.replace('#include <opaque_fragment>',
    `outgoingLight *= mix(0.45, 1.0, abs(normal.z)) * mix(1.0, 0.7, smoothstep(1.5, 6.0, length(vViewPosition)));
    #include <opaque_fragment>`);                              // normal — у просторі камери: z = 1 — дивиться просто на нас
};
const scanWireM = new THREE.MeshBasicMaterial({ vertexColors: true, wireframe: true, transparent: true, opacity: 0.45, depthWrite: false });
const scanGroup = new THREE.Group(), scanParts = new Map();  // ключ шматка → Mesh заливки (сітка — його дочірній Mesh на тій самій геометрії)
scanGroup.visible = false;
function scanOpacity(v) {                                     // 0.1…1; суцільна пише глибину, як звичайне тіло
  const solid = v >= 0.99;
  scanFillM.opacity = v; scanWireM.opacity = solid ? 0.3 : 0.45;
  if (scanFillM.transparent === solid) { scanFillM.transparent = !solid; scanFillM.depthWrite = solid; scanFillM.needsUpdate = true; }
}
scanOpacity(0.3);
const HIT_MAX = 48;                                           // червоні кульки в точках зіткнення — видно й без накладки (Quest)
const hitMarks = new THREE.InstancedMesh(new THREE.SphereGeometry(0.025, 10, 8),
  new THREE.MeshBasicMaterial({ color: 0xff2a2a, depthTest: false }), HIT_MAX);
hitMarks.count = 0; hitMarks.renderOrder = 11; hitMarks.frustumCulled = false;
const HIT_TINT = new THREE.Color(0x901010), NO_TINT = new THREE.Color(0);

function planeObj(poly, fill, line) {                         // опуклий многокутник площини: заливка віялом + контур
  const pts = poly.map(p => new THREE.Vector3(p.x, p.y || 0, p.z)), g = new THREE.BufferGeometry().setFromPoints(pts);
  g.setIndex(pts.slice(2).flatMap((_, i) => [0, i + 1, i + 2]));
  const loop = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), line);
  if (line.isLineDashedMaterial) loop.computeLineDistances();
  return [new THREE.Mesh(g, fill), loop];
}
function roomMake(s) {
  const obj = new THREE.Group(); obj.matrixAutoUpdate = false; obj.visible = AR.room;
  let kind, src;
  if (s.planeSpace) {
    kind = s.orientation === 'vertical' ? 0 : 1;
    src = s.polygon.map(p => ({ x: p.x, y: p.y, z: p.z }));
    obj.add(...planeObj(src, roomFill[kind], roomLine[kind]));
  } else {
    // semanticLabel — рядок від браузера: лише порівнюємо, у сторінку він не потрапляє
    kind = s.semanticLabel === 'wall' ? 0 : ['ceiling', 'table', 'floor'].includes(s.semanticLabel) ? 1 : 2;
    src = { v: Float32Array.from(s.vertices), i: Uint32Array.from(s.indices) };
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(src.v, 3)); g.setIndex(new THREE.BufferAttribute(src.i, 1));
    obj.add(new THREE.Mesh(g, roomWire[kind]));
  }
  roomGroup.add(obj);
  return { obj, kind, src, plane: !!s.planeSpace, t: s.lastChangedTime, m: null, tris: null };
}
function roomDrop(r) { roomGroup.remove(r.obj); r.obj.traverse(o => { if (o.geometry) o.geometry.dispose(); }); }
function roomSync(frame, ref) {                               // щокадру: нові, змінені й зниклі площини та сітки
  const seen = new Set();
  for (const set of [AR.feat.planes && frame.detectedPlanes, AR.feat.meshes && frame.detectedMeshes]) if (set) for (const s of set) {
    seen.add(s);
    const pose = frame.getPose(s.planeSpace || s.meshSpace, ref); if (!pose) continue;
    let r = roomSrc.get(s);
    if (!r || r.t !== s.lastChangedTime) { if (r) roomDrop(r); r = roomMake(s); roomSrc.set(s, r); }
    const m = pose.transform.matrix;
    if (!r.m || r.m.some((v, i) => Math.abs(v - m[i]) > 0.005)) {   // трекінг уточнює позу — перераховуємо лише помітне
      r.m = Float32Array.from(m); r.obj.matrix.fromArray(m); r.obj.matrixWorldNeedsUpdate = true;
      r.tris = r.plane ? planeTris(r.src, r.m) : meshTris(r.src.v, r.src.i, r.m); AR.dirty = true;
    }
  }
  for (const [s, r] of roomSrc) if (!seen.has(s)) { roomDrop(r); roomSrc.delete(s); AR.dirty = true; }
}
function arDepth(frame, ref) {                                // карта глибин → текстура для затуляння
  const view = frame.getViewerPose(ref)?.views[0]; if (!view) return;
  let d;
  try { d = frame.getDepthInformation(view); } catch (e) { AR.feat.depth = false; occl.visible = false; arFeatUI(); return; }
  if (!d) { occl.visible = false; AR.dz = null; return; }    // ще не готова
  const n = d.width * d.height;
  let tex = occlU.depth.value;
  if (!tex || tex.image.width !== d.width || tex.image.height !== d.height) {
    if (tex) tex.dispose();
    tex = new THREE.DataTexture(new Float32Array(n), d.width, d.height, THREE.RedFormat, THREE.FloatType);
    tex.minFilter = tex.magFilter = THREE.NearestFilter; occlU.depth.value = tex;
  }
  const raw = AR.depthFmt === 'float32' ? new Float32Array(d.data) : new Uint16Array(d.data), k = d.rawValueToMeters, out = tex.image.data;
  for (let i = 0; i < n; i++) out[i] = raw[i] * k;
  tex.needsUpdate = true;
  occlU.uvm.value.fromArray(d.normDepthBufferFromNormView.matrix);
  occl.visible = AR.occl;
  // той самий кадр — для зліпка й площин з глибини: карта, її перетворення, проєкція й поза камери
  AR.dz = { data: out, w: d.width, h: d.height, uvm: Float32Array.from(d.normDepthBufferFromNormView.matrix),
            P: Float32Array.from(view.projectionMatrix), V: Float32Array.from(view.transform.matrix), Vi: Float32Array.from(view.transform.inverse.matrix) };
}
function dzAt(z, u, v) {                                      // нормалізовані координати виду (0..1, угорі ліворуч) → метри, 0 — невідомо
  const m = z.uvm, du = m[0] * u + m[4] * v + m[12], dv = m[1] * u + m[5] * v + m[13];   // як у шейдері затуляння
  const x = Math.floor(du * z.w), y = Math.floor(dv * z.h);
  return x >= 0 && y >= 0 && x < z.w && y < z.h ? z.data[y * z.w + x] : 0;
}
function dzSeen(z, p) {                                       // → [виміряна глибина, глибина точки p] або null: поза кадром чи без глибини
  const V = z.Vi, P = z.P;
  const x = V[0] * p[0] + V[4] * p[1] + V[8] * p[2] + V[12], y = V[1] * p[0] + V[5] * p[1] + V[9] * p[2] + V[13];
  const zz = V[2] * p[0] + V[6] * p[1] + V[10] * p[2] + V[14], w = -zz;
  if (w < 0.3) return null;
  const nx = (P[0] * x + P[8] * zz + P[12]) / w, ny = (P[5] * y + P[9] * zz + P[13]) / w;
  if (Math.abs(nx) > 1 || Math.abs(ny) > 1) return null;
  const m = dzAt(z, (nx + 1) / 2, (1 - ny) / 2);
  return m > 0 ? [m, w] : null;
}
// Зліпок: живі площини → keep; тіні перевіряються картою глибин — крізь хибну площину видно далі (≥ 25 см),
// справжню камера бачить саму (±10 см). Точки поза кадром не голосують.
function keepSync(now) {
  const live = [];
  for (const [s, r] of roomSrc) if (r.plane && r.m) live.push({ key: s, kind: r.kind, m: r.m, poly: r.src });
  let changed = keep.update(live, now);
  const z = AR.dz;
  if (z) for (const g of [...keep.ghosts]) {
    let th = 0, sup = 0;
    for (const p of g.pts) { const q = dzSeen(z, p); if (!q) continue; if (q[0] > q[1] + 0.25) th++; else if (Math.abs(q[0] - q[1]) < 0.1) sup++; }
    if (th >= 2 && th > sup) changed = keep.vote(g, true) || changed;
    else if (sup) keep.vote(g, false);
  }
  if (changed) { ghostSync(); AR.dirty = true; arFeatUI(); }
}
function ghostSync() {
  const alive = new Set(keep.ghosts);
  for (const [g, o] of ghostObj) if (!alive.has(g)) { roomGroup.remove(o); o.traverse(c => { if (c.geometry) c.geometry.dispose(); }); ghostObj.delete(g); }
  for (const g of keep.ghosts) {
    let o = ghostObj.get(g);
    if (!o) {
      o = new THREE.Group(); o.matrixAutoUpdate = false; o.matrix.fromArray(g.m);
      o.add(...planeObj(g.poly, ghostFill[g.kind], ghostLine[g.kind])); roomGroup.add(o); ghostObj.set(g, o);
    }
    o.children[0].material = (g.fixed ? roomFill : ghostFill)[g.kind];
  }
}
function dzRays(z, L) {                                      // кадр глибини → промені в просторі сеансу: { O, fwd, dirs, dep }
  const P = z.P, V = z.V, asp = P[5] / P[0];                 // ширина / висота кадру: уздовж довшого боку — L променів
  const cols = asp >= 1 ? L : Math.max(8, Math.round(L * asp)), rows = asp >= 1 ? Math.max(8, Math.round(L / asp)) : L;
  const dirs = new Float32Array(cols * rows * 3), dep = new Float32Array(cols * rows);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const u = (c + 0.5) / cols, v = (r + 0.5) / rows, i = r * cols + c;
    const x = (2 * u - 1 + P[8]) / P[0], y = (1 - 2 * v + P[9]) / P[5];   // точка виду на глибині 1 (z = −1) → напрямок у просторі сеансу
    dirs[i * 3] = V[0] * x + V[4] * y - V[8]; dirs[i * 3 + 1] = V[1] * x + V[5] * y - V[9]; dirs[i * 3 + 2] = V[2] * x + V[6] * y - V[10];
    dep[i] = dzAt(z, u, v);
  }
  return { O: [V[12], V[13], V[14]], fwd: [-V[8], -V[9], -V[10]], dirs, dep };
}
function scanIntegrate() { const r = dzRays(AR.dz, SCAN_L); scan.integrate(r.O, r.fwd, r.dirs, r.dep); }
function scanDraw() {                                         // змінені шматки скану → їхні геометрії (раз на секунду)
  for (const { key, tris, nrm, ao, kind } of scan.takeChunks()) {
    let m = scanParts.get(key);
    if (m) m.geometry.dispose();
    if (!kind.length) { if (m) { scanGroup.remove(m); scanParts.delete(key); } continue; }
    const col = new Float32Array(tris.length), g = new THREE.BufferGeometry();
    for (let i = 0; i < kind.length; i++) for (let j = 0; j < 3; j++) {   // колір виду поверхні × затінення кута
      const c = ROOM_RGB[kind[i]], a = ao[i * 3 + j], o = i * 9 + j * 3;
      col[o] = c[0] * a; col[o + 1] = c[1] * a; col[o + 2] = c[2] * a;
    }
    g.setAttribute('position', new THREE.BufferAttribute(tris, 3)); g.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.computeBoundingSphere();                                 // шматок поза кадром не малюється
    if (!m) { m = new THREE.Mesh(g, scanFillM); m.add(new THREE.Mesh(g, scanWireM)); scanGroup.add(m); scanParts.set(key, m); }
    m.geometry = m.children[0].geometry = g;
  }
}
function scanReset() {
  scan.clear();
  for (const m of scanParts.values()) { m.geometry.dispose(); scanGroup.remove(m); }
  scanParts.clear();
}
// Точки тіла для перевірки: вершини його сіток без повторів (5 мм), не більше 120 на тіло.
// Опора кожного тіла — його власний початок координат: це шарнір (вісь A, B, E, пальці циліндрів).
const bodySamples = new WeakMap();
function samplesOf(g) {
  let S = bodySamples.get(g); if (S) return S;
  const seen = new Set(), pts = [];
  g.traverse(o => {
    if (!o.isMesh) return;
    const a = o.geometry.attributes.position.array;
    for (let i = 0; i < a.length; i += 3) {
      const k = `${Math.round(a[i] / 5)},${Math.round(a[i + 1] / 5)},${Math.round(a[i + 2] / 5)}`;
      if (!seen.has(k)) { seen.add(k); pts.push(a[i], a[i + 1], a[i + 2]); }
    }
  });
  const n = pts.length / 3, step = Math.max(1, n / 120);
  S = new Float32Array(Math.min(n, 120) * 3);
  for (let j = 0; j < S.length / 3; j++) { const i = Math.floor(j * step) * 3; S.set(pts.slice(i, i + 3), j * 3); }
  bodySamples.set(g, S);
  return S;
}
const partKey = name => name.startsWith('v_cyl_') ? (name.endsWith('_rod') ? 'kin.rod' : 'kin.barrel') : 'kin.' + name.replace(/^v_/, '');
function arCollide() {                                        // ~10 разів на секунду, не щокадру
  const hits = [], at = [], a = new THREE.Vector3(), p = new THREE.Vector3(), A = [0, 0, 0], P = [0, 0, 0];
  if (AR.coll && room.n && arRoot.visible) {                  // вимкнено — той самий шлях, що й «нічого не зачеплено»: гасить сліди
    arRoot.updateMatrixWorld(true);
    const floorY = arRoot.position.y;
    for (const [name, g] of Object.entries(bodies)) {
      let vis = true; for (let o = g; o; o = o.parent) vis = vis && o.visible;
      if (!vis) continue;
      a.setFromMatrixPosition(g.matrixWorld).toArray(A);
      const S = samplesOf(g);
      let kind = -1;
      for (let i = 0; i < S.length; i += 3) {
        p.set(S[i], S[i + 1], S[i + 2]).applyMatrix4(g.matrixWorld).toArray(P);
        const k = room.hit(A, P, floorY);
        if (k >= 0) { if (kind < 0) kind = k; if (at.length < HIT_MAX) at.push(p.clone()); }
      }
      if (kind >= 0) hits.push([name, kind]);
    }
  }
  const m = new THREE.Matrix4();
  at.forEach((q, i) => hitMarks.setMatrixAt(i, m.makeTranslation(q.x, q.y, q.z)));
  hitMarks.count = at.length; hitMarks.instanceMatrix.needsUpdate = true;
  const hitSet = new Set(hits.map(h => h[0]));
  for (const [name, g] of Object.entries(bodies))
    g.traverse(o => { if (o.isMesh && o.material.emissive) o.material.emissive.copy(hitSet.has(name) ? HIT_TINT : NO_TINT); });
  if (hits.length && !AR.hits.length && navigator.vibrate) navigator.vibrate(80);
  AR.hits = hits;
  const s = hits.length ? t('ar.hit', { what: t('ar.hit.' + KIND[hits[0][1]]),
    part: [...new Set(hits.map(h => t(partKey(h[0]))))].join(', ') }) : '';
  if ($('ar_warn').textContent !== s) $('ar_warn').textContent = s;
}
function arFeatUI() {                                         // що з трьох можливостей дав браузер — видно в накладці
  const f = AR.feat, mark = v => (v ? '✓' : '—');
  if (!f) return;                                             // поза сеансом (тести) — кнопок не видно, малювати нічого
  const k = keep.stats();
  $('ar_feat').textContent = t('ar.feat', { d: mark(f.depth), p: mark(f.planes), m: mark(f.meshes) }) +
    (f.planes ? ' · ' + t('ar.kept', { n: k.fixed, w: k.wait }) : '') +
    (scan.frames ? ' · ' + t(scan.full ? 'ar.scanfull' : 'ar.scann', { n: (scan.nTris / 1000).toFixed(1) }) : '');
  $('ar_occl').hidden = $('ar_scan').hidden = !f.depth; $('ar_room').hidden = $('ar_coll').hidden = !(f.planes || f.meshes);
  $('ar_occl').classList.toggle('on', AR.occl); $('ar_room').classList.toggle('on', AR.room); $('ar_coll').classList.toggle('on', AR.coll);
  $('ar_scan').classList.toggle('on', AR.scan);
  $('ar_scanrow').hidden = !(f.depth && (AR.scan || scan.frames));   // повзунок прозорості — коли є що показувати
}
function arFeatInit(s) {
  const f = s.enabledFeatures || [];                          // Chrome дає список у сеансі; без нього вважаємо, що нічого
  AR.feat = { depth: f.includes('depth-sensing'), planes: f.includes('plane-detection'), meshes: f.includes('mesh-detection') };
  try { AR.depthFmt = AR.feat.depth ? s.depthDataFormat : ''; } catch (e) { AR.feat.depth = false; }
  arFeatUI();
}
function arRoomEnd() {
  for (const r of roomSrc.values()) roomDrop(r);
  roomSrc.clear(); room.clear(); AR.hits = []; AR.dirty = false; AR.feat = null;
  hitMarks.count = 0; occl.visible = false;
  keep.clear(); ghostSync(); AR.dz = null; scanReset();
  if (occlU.depth.value) { occlU.depth.value.dispose(); occlU.depth.value = null; }
  for (const g of Object.values(bodies)) g.traverse(o => { if (o.isMesh && o.material.emissive) o.material.emissive.copy(NO_TINT); });
  $('ar_warn').textContent = ''; $('ar_feat').textContent = '';
}
const zUp2yUp = p => new THREE.Vector3(p.x, p.z, -p.y);
function arWorld() {                                          // машина всередині arRoot
  const s = 0.001 / AR.scale;
  world.scale.setScalar(s); world.rotation.set(-Math.PI / 2, 0, 0);
  // Коло — точка на землі під віссю A (основа стріли): так машину ставлять на край ями.
  // Сама вісь A — на висоті «вісь A над землею», земля моделі лягає на підлогу.
  world.position.set(0, groundZ() * s, 0);
}
function arHint(key) { const s = key ? t(key) : ''; if ($('ar_hint').textContent !== s) $('ar_hint').textContent = s; }
function arScaleLabel() { const b = $('ar_scale'); b.textContent = '1:' + AR.scale; b.title = t('ar.scale', { s: '1:' + AR.scale }); }
function arSyncPlay() {                                       // у накладці підписи коротші: ряд кнопок має влізти в ширину телефона
  const b = $('ar_play'), s = t(playing ? 'ar.stop' : 'ar.play');
  if (b.textContent !== s) { b.textContent = s; b.classList.toggle('on', playing); }
}
function arBuildUI() {
  const box = $('ar_sliders'); box.replaceChildren();
  const a = effAngles();
  for (const [key] of ANG) {
    const l = limits(key) || [-90, 180];
    const inp = el('input', { type: 'range', id: 'ar_' + key, min: l[0], max: l[1], step: 0.5 });
    inp.value = a[key];
    inp.addEventListener('input', () => { ang3[key] = +inp.value; stopPlay(); updatePose(); });
    const row = el('label', { className: 'ar-ang' });
    row.append(el('span', { textContent: t('ang.' + key) }), inp);
    box.appendChild(row);
  }
  arScaleLabel(); arSyncPlay();
}
async function arStart() {
  $('ar_msg').textContent = '';
  try {
    // Глибина — лише на процесорі: з неї ж будується текстура затуляння. Формати — ті, що Chrome знає
    // від початку (невідоме значення переліку зірвало б увесь запит, а не лише цю можливість).
    AR.session = await navigator.xr.requestSession('immersive-ar', {
      requiredFeatures: ['hit-test'],
      optionalFeatures: ['dom-overlay', 'depth-sensing', 'plane-detection', 'mesh-detection'],
      domOverlay: { root: $('ar_ui') },
      depthSensing: { usagePreference: ['cpu-optimized'], dataFormatPreference: ['luminance-alpha', 'float32'] } });
    AR.placing = true;
    AR.saved = { pos: camera.position.clone(), target: controls.target.clone(), bg: scene.background,
                 lights: [hemi, sun, fill].map(l => l.position.clone()) };
    document.body.classList.add('ar');
    scene.background = null; ground.visible = false; envelope.visible = false;
    for (const l of [hemi, sun, fill]) l.position.copy(zUp2yUp(l.position));   // «вгору» тепер — Y
    scene.add(arRoot, reticle, occl, roomGroup, hitMarks, scanGroup); arRoot.add(world); arRoot.visible = false; reticle.visible = false;
    controls.enabled = false;
    arWorld(); arBuildUI(); arHint('ar.find'); arFeatInit(AR.session);
    renderer.xr.enabled = true; renderer.xr.setReferenceSpaceType('local');
    await renderer.xr.setSession(AR.session);
    AR.session.addEventListener('select', arSelect);
    AR.session.addEventListener('squeeze', () => $('ar_play').click());   // окуляри без накладки (Quest): бічна кнопка — цикл копання
    const viewer = await AR.session.requestReferenceSpace('viewer');
    AR.hitSrc = await AR.session.requestHitTestSource({ space: viewer });
  } catch (e) {
    const s = AR.session;
    arEnd();
    if (s) s.end().catch(() => {});
    $('ar_msg').textContent = t('ar.fail', { msg: (e && (e.message || e.name)) || String(e) });
    setTimeout(() => { $('ar_msg').textContent = ''; }, 8000);
  }
}
function arSelect() {                                         // дотик по сцені (не по кнопках) — поставити машину на коло
  // Без накладки (Quest не дає dom-overlay) кнопки «Перенести» немає: курок по поставленій машині — знову шукати місце.
  if (!AR.placing && !AR.session.domOverlayState) { AR.placing = true; return; }
  if (!AR.placing || !reticle.visible) return;
  const p = new THREE.Vector3().setFromMatrixPosition(reticle.matrix);
  const d = p.clone().sub(new THREE.Vector3().setFromMatrixPosition(renderer.xr.getCamera().matrixWorld));
  arRoot.position.copy(p);
  arRoot.rotation.set(0, Math.atan2(-d.x, -d.z), 0);         // вісь X машини (куди тягнеться стріла) — праворуч від погляду: бачиш її збоку, як у виді «Збоку»
  arRoot.visible = true; AR.placing = false; reticle.visible = false;
  arHint('ar.placed');
}
function arFrame(frame, now) {
  const ref = renderer.xr.getReferenceSpace();
  if (AR.placing && AR.hitSrc) {
    const hit = frame.getHitTestResults(AR.hitSrc)[0];
    const pose = hit && hit.getPose(ref);
    reticle.visible = !!pose;
    if (pose) reticle.matrix.fromArray(pose.transform.matrix);
    arHint(pose ? 'ar.tap' : 'ar.find');
  }
  if (AR.feat.depth) arDepth(frame, ref);
  if (AR.feat.planes || AR.feat.meshes) roomSync(frame, ref);
  if (AR.feat.planes && now - AR.tKeep > 250) { keepSync(now); AR.tKeep = now; }
  if (AR.scan && AR.dz && now - AR.tScan > 250) { scanIntegrate(); AR.tScan = now; }   // ~4 кадри на секунду: інтеграція — найдорожче
  if (scan.dirty.size && now - AR.tMesh > 1000) { scan.remesh(150); scanDraw(); arFeatUI(); AR.tMesh = now; }
  // Сітка для зіткнень перебудовується не частіше ніж двічі на секунду: сітка Quest — десятки тисяч трикутників.
  // Тіні зліпка теж ідуть у зіткнення: заради цього їх і тримаємо.
  if (AR.dirty && now - AR.tBuild > 500) { room.build([...[...roomSrc.values()].filter(r => r.tris), ...keep.ghosts]); AR.dirty = false; AR.tBuild = now; }
  if (now - AR.tHit > 100) { arCollide(); AR.tHit = now; }
  arSyncPlay();
}
function arEnd() {                                            // повернути сторінку як було; викликається й після невдалого старту
  const s = AR.saved;
  if (AR.hitSrc) { try { AR.hitSrc.cancel(); } catch (e) { /* сеанс уже закрито */ } }
  AR.hitSrc = null; AR.session = null;
  if (!s) return;
  AR.saved = null;
  renderer.xr.enabled = false;
  arRoomEnd();
  scene.remove(arRoot, reticle, occl, roomGroup, hitMarks, scanGroup); scene.add(world);
  world.position.set(0, 0, 0); world.rotation.set(0, 0, 0); world.scale.setScalar(1);
  [hemi, sun, fill].forEach((l, i) => l.position.copy(s.lights[i]));
  scene.background = s.bg;
  document.body.classList.remove('ar');
  camera.position.copy(s.pos); controls.target.copy(s.target); controls.enabled = !locked; controls.update();
  applyShow(); resize();
}
renderer.xr.addEventListener('sessionend', arEnd);           // «Вийти», кнопка «Назад» телефона або збій сеансу
// Дотик по панелі AR не повинен ставити машину: скасовуємо select, що виник із дотику по кнопках.
$('ar_ui').addEventListener('beforexrselect', e => { if (e.target.closest && e.target.closest('.ar-ctl')) e.preventDefault(); });
$('ar_exit').onclick = () => { if (AR.session) AR.session.end().catch(() => {}); };
$('ar_place').onclick = () => { AR.placing = true; };
$('ar_rotl').onclick = () => { arRoot.rotation.y += 15 * RAD; };
$('ar_rotr').onclick = () => { arRoot.rotation.y -= 15 * RAD; };
$('ar_scale').onclick = () => {
  AR.scale = AR_SCALES[(AR_SCALES.indexOf(AR.scale) + 1) % AR_SCALES.length];
  arWorld(); arScaleLabel();
};
$('ar_play').onclick = () => { $('play').click(); arSyncPlay(); };
$('ar_occl').onclick = () => { AR.occl = !AR.occl; if (!AR.occl) occl.visible = false; arFeatUI(); };
$('ar_room').onclick = () => { AR.room = !AR.room; roomGroup.visible = AR.room; arFeatUI(); };   // зіткнення рахуються й зі схованою сіткою
$('ar_scan').onclick = () => { AR.scan = !AR.scan; scanGroup.visible = AR.scan; arFeatUI(); };
$('ar_scanop').addEventListener('input', e => scanOpacity(+e.target.value / 100));   // вимкнути — пауза: зібране лишається до кінця сеансу
$('ar_coll').onclick = () => { AR.coll = !AR.coll; arCollide(); arFeatUI(); };   // кімнату будуємо й далі — увімкнення діє одразу
function arInit() {                                           // кнопка — лише там, де AR справді є (https, ARCore)
  const b = $('ar_btn');
  b.onclick = () => { if (!AR.session && V) arStart(); };
  if (!window.isSecureContext || !navigator.xr) return;
  navigator.xr.isSessionSupported('immersive-ar').then(ok => { b.hidden = !ok; document.body.classList.toggle('arok', ok); }).catch(() => {});
}
window.__AR__ = () => ({ active: !!AR.session, placing: AR.placing, scale: AR.scale, button: !$('ar_btn').hidden,   // для тестів
                          feat: AR.feat, room: roomSrc.size, tris: room.n, hits: AR.hits, kept: keep.stats(), scan: scan.stats() });
// Для тестів без телефона: машина 1:1 стоїть віссю A над точкою (0, 0, 0) простору сеансу, стріла — уздовж +X,
// поперек стоїть стіна x = wallX м (2 × 3 м). Повертає тіла, що її зачепили, і число червоних точок;
// заразом компілює шейдер затуляння (помилку GLSL видно в консолі). Сцену повертає як було.
window.__ARSIM__ = wallX => {
  const sq = [{ x: -1.5, z: -1.5 }, { x: 1.5, z: -1.5 }, { x: 1.5, z: 1.5 }, { x: -1.5, z: 1.5 }];
  const wallM = [0, 0, 1, 0, -1, 0, 0, 0, 0, -1, 0, 0, wallX, 1.5, 0, 1];
  scene.add(arRoot, occl); arRoot.add(world); arRoot.visible = true; arRoot.position.set(0, 0, 0); arRoot.rotation.set(0, 0, 0); arWorld();
  room.build([{ tris: planeTris(sq, wallM), kind: 0 }]);
  arCollide();
  const out = { hits: AR.hits.map(h => h[0] + ':' + KIND[h[1]]), marks: hitMarks.count, warn: $('ar_warn').textContent };
  renderer.compile(occl, arCam);
  arRoomEnd(); scene.remove(arRoot, occl); scene.add(world);
  world.position.set(0, 0, 0); world.rotation.set(0, 0, 0); world.scale.setScalar(1);
  return out;
};
// Для тестів без телефона: синтетична кімната-коробка x −2…2, y 0…2.6, z −3…2 м зі столом (x 0.3…1.5, висота 0.75,
// z −2.2…−1.4), камера на висоті 1.4 м.
// Скан: 16 кадрів глибини навколо (кожні 45°, погляд на 20° донизу і на 15° догори) → поверхня в parts шматках
// (drawn — трикутників у їхніх геометріях, має дорівнювати tris); onSurface — частка
// вершин ближче за 3 см до стін, підлоги, стелі чи столу (має бути ≈ 1), kinds — трикутників стін · горизонтальних · решти.
// look — прозорість (0.1…1) або { op, from: [x, y, z], at: [x, y, z] }: тоді ще й знімок скану на темному тлі
// (типово — з кута кімнати на стіл), out.png (data:-адреса) — оцінити об'єм.
// Зліпок: площина-стіна 2 × 2 м на z = wallZ видна 6 с, зникає, лишається назавжди; далі 6 перевірок картою
// глибин (−3 — камера бачить саму стіну, −2 — крізь неї видно далі).
window.__ARSCAN__ = (wallZ = -3, look = 0) => {
  const lo = [-2, 0, -3], hi = [2, 2.6, 2], tl = [0.3, 0, -2.2], th = [1.5, 0.75, -1.4], O = [0, 1.4, 0], w = 96, h = 96;
  const P = arCam.projectionMatrix.elements, dir = new THREE.Vector3();
  const frame = (yaw, pitch) => {
    const R = new THREE.Matrix4().makeRotationY(yaw).multiply(new THREE.Matrix4().makeRotationX(pitch)), Vm = R.clone().setPosition(...O);
    const data = new Float32Array(w * h);
    for (let py = 0; py < h; py++) for (let px = 0; px < w; px++) {   // глибина — уздовж осі погляду: точка = O + R·(x, y, −1)·d
      dir.set((2 * (px + 0.5) / w - 1 + P[8]) / P[0], (1 - 2 * (py + 0.5) / h + P[9]) / P[5], -1).applyMatrix4(R);
      let t = Infinity;
      let t0 = 0, t1 = Infinity;                              // стіл — метод плит
      for (let a = 0; a < 3; a++) {
        const d = dir.getComponent(a); if (!d) continue;
        t = Math.min(t, ((d > 0 ? hi : lo)[a] - O[a]) / d);
        const u = (tl[a] - O[a]) / d, v = (th[a] - O[a]) / d; t0 = Math.max(t0, Math.min(u, v)); t1 = Math.min(t1, Math.max(u, v));
      }
      data[py * w + px] = t1 >= t0 && t0 > 0 ? Math.min(t, t0) : t;
    }
    AR.dz = { data, w, h, uvm: new THREE.Matrix4().elements, P: [...P], V: Vm.elements.slice(), Vi: Vm.clone().invert().elements.slice() };
  };
  for (let k = 0; k < 8; k++) for (const p of [-20, 15]) { frame(k * 45 * RAD, p * RAD); scanIntegrate(); }
  while (scan.remesh(1000)); scanDraw();
  const tp = scan.geometry().tris, kinds = [0, 0, 0];
  let on = 0;
  for (let i = 0; i < tp.length; i += 3) {
    const p = [tp[i], tp[i + 1], tp[i + 2]], q = p.map((v, a) => Math.max(tl[a] - v, v - th[a]));   // q — до граней столу
    const table = Math.hypot(...q.map(v => Math.max(v, 0))) + Math.min(Math.max(...q), 0);          // знакова відстань до коробки
    if ([0, 1, 2].some(a => Math.abs(p[a] - lo[a]) < 0.03 || Math.abs(p[a] - hi[a]) < 0.03) || Math.abs(table) < 0.03) on++;
  }
  for (const k of scan.geometry().kind) kinds[k]++;
  const out = { tris: scan.nTris, onSurface: tp.length ? +(on / (tp.length / 3)).toFixed(3) : 0, kinds, frames: scan.frames,
                parts: scanParts.size, drawn: [...scanParts.values()].reduce((n, m) => n + m.geometry.attributes.position.count / 3, 0) };
  renderer.compile(scanGroup, arCam);                        // шейдер затіненої заливки: помилку GLSL видно в консолі
  if (look) {
    const sc = new THREE.Scene(), cv = renderer.domElement, cam = new THREE.PerspectiveCamera(60, cv.width / cv.height, 0.05, 50);
    sc.background = new THREE.Color(0x202428);
    for (const l of [hemi, sun, fill]) { const c = l.clone(); c.position.copy(zUp2yUp(l.position)); sc.add(c); }   // світло — як у сеансі AR
    const L = typeof look === 'number' ? { op: look } : look;
    scanOpacity(L.op || 1); scanGroup.visible = true; sc.add(scanGroup);
    cam.up.set(0, 1, 0);                                     // у сторінці «угору» типово Z (модель у Z-up), а тут простір WebXR
    cam.position.set(...(L.from || [-1.85, 2.45, 1.85])); cam.lookAt(...(L.at || [0.6, 0.2, -2.4]));
    renderer.render(sc, cam); out.png = cv.toDataURL('image/png');
    if (L.points) out.px = L.points.map(q => { const v = new THREE.Vector3(...q).project(cam); return [Math.round((v.x + 1) / 2 * cv.width), Math.round((1 - v.y) / 2 * cv.height)]; });
    sc.remove(scanGroup); scanGroup.visible = AR.scan; scanOpacity(+$('ar_scanop').value / 100);
  }
  frame(0, -15 * RAD);
  const s = { planeSpace: {}, orientation: 'vertical', lastChangedTime: 0, polygon: [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([x, z]) => ({ x, y: 0, z })) };
  const r = roomMake(s); r.m = Float32Array.from([1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 1.4, wallZ, 1]); roomSrc.set(s, r);
  keepSync(0); roomDrop(r); roomSrc.delete(s); keepSync(6000); keepSync(12000);
  out.kept = keep.stats().fixed; out.objs = ghostObj.size;
  for (let i = 1; i <= 6; i++) keepSync(12000 + i * 250);
  out.afterVotes = keep.stats().fixed;
  arRoomEnd();
  return out;
};
window.__ARUI__ = key => { document.body.classList.add('ar'); arBuildUI(); arHint(key || 'ar.placed'); };   // лише накладка, без сеансу й без руху сцени — для знімка

let tPrev = performance.now();
renderer.setAnimationLoop((time, frame) => {                  // у сеансі AR цей самий цикл отримує кадри WebXR
  const now = performance.now();
  for (const f of frameQ.splice(0)) f(now);
  if (AR.session && renderer.xr.isPresenting) { if (frame) arFrame(frame, now); tPrev = now; renderer.render(scene, arCam); return; }
  smTick(Math.min(0.05, (now - tPrev) / 1000)); tPrev = now; controls.update(); renderer.render(scene, camera);
});

// ---------------------------------------------------------------- мова сторінки
function applyStatic() {                                      // статичні підписи index.html: data-i18n / data-i18n-title
  document.documentElement.lang = getLang();
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll('[data-i18n-title]')) el.title = t(el.dataset.i18nTitle);
  for (const el of document.querySelectorAll('[data-i18n-aria]')) el.setAttribute('aria-label', t(el.dataset.i18nAria));   // елементи без тексту
  // applyStatic щойно повернув довгий заголовок — на телефоні він знову короткий
  if (matchMedia('(max-width: 900px), (pointer: coarse)').matches)
    $('h2ang').firstElementChild.textContent = t('h2.angles.short');
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
  buildLangUI(); applyStatic(); buildAngleUI(); buildPoseUI(); buildViewUI(); buildToggleUI(); buildLegend(); smUI();
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
    arInit();                                  // кнопка AR — коли є що ставити
    window.__READY__ = true;
  } catch (e) { $('load').hidden = true; status('st.load', { msg: e.message }, 'err'); }
})();
