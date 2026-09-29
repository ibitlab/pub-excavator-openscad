// Димовий тест без браузера: `npm test`
//  1) рушій openscad-wasm-prebuilt (він старіший за настільний OpenSCAD!) будує модель у режимі part="view_all" без помилок;
//  2) усі деталі зі списку view_parts непорожні, echo(VIEW) читається, схема параметрів розбирається;
//  3) блок //<pose> однаковий у цій сторінці та в web/viewer/index.html (поза рахується однаково в обох версіях);
//  4) поза з JavaScript збігається з echo самої моделі ("ЗУБ КОВША: x=… z=…");
//  5) переклад повний: обидві мови мають однакові ключі, усі групи й описані параметри моделі є у словнику,
//     і кожен ключ, який викликає main.js, у словнику існує.
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createOpenSCAD } from 'openscad-wasm-prebuilt';
import { splitOff } from '../src/offmesh.js';
import { readSchema, scadLiteral } from '../src/schema.js';
import { UI, LANGS, GROUPS_EN, PARAMS_EN } from '../src/i18n.js';
import { LEGEND } from '../src/legend.js';
import { armFromTip, armFromBucket } from '../src/ik.js';
import { Room, KIND, planeTris, meshTris } from '../src/room.js';
import { Keep } from '../src/keep.js';
import { Scan } from '../src/scan.js';

const here = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(here, '../../..');
const source = readFileSync(path.join(root, 'scad/excavator_boom.scad'), 'utf8');
const fail = m => { console.error('✗ ' + m); process.exitCode = 1; }, ok = m => console.log('✓ ' + m);

const schema = readSchema(source), all = schema.flatMap(g => g.params);
all.length > 80 ? ok(`схема: ${schema.length} груп, ${all.length} параметрів`) : fail(`схема підозріло мала: ${all.length}`);
const L1 = all.find(p => p.name === 'boom_L1'); scadLiteral(L1, 950) === '950' ? ok('літерали параметрів') : fail('scadLiteral');

// Легенда кольорів мусить показувати ТІ САМІ кольори, що стоять у color(...) моделі:
// інакше вона тихо почне брехати після першої ж зміни палітри.
{
  // Беремо ВСІ трійки 0..1 у тексті, а не лише ті, що стоять прямо в color():
  // колір гільзи приходить через типове значення параметра col_body.
  const nums = [...source.matchAll(/\[\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\]/g)]
    .map(m => m.slice(1, 4).map(Number))
    .filter(v => v.every(x => x >= 0 && x <= 1))
    .map(v => v.join(','));
  const names = [...source.matchAll(/color\(\s*"([^"]+)"/g)].map(m => m[1]);
  const lost = LEGEND.filter(l => typeof l.scad === 'string'
    ? !names.includes(l.scad)
    : !nums.includes(l.scad.join(',')));
  lost.length ? fail('легенда розійшлася з моделлю: ' + lost.map(l => l.key).join(', '))
              : ok(`легенда: ${LEGEND.length} кольорів, усі є в моделі`);
}

// Маркери мають стояти НА ПОЧАТКУ рядка: інакше згадка тегу в коментарі вище зсуває межу блоку і ховає розходження.
const poseBlock = f => (readFileSync(f, 'utf8').match(/^\/\/<pose>[^\n]*\n([\s\S]*?)^\/\/<\/pose>/m) || [])[1];
const p1 = poseBlock(path.join(here, '../src/main.js')), p2 = poseBlock(path.join(root, 'web/viewer/index.html'));
const smBlock = f => (readFileSync(f, 'utf8').match(/^\/\/<spacemouse>[^\n]*\n([\s\S]*?)^\/\/<\/spacemouse>/m) || [])[1];
const s1 = smBlock(path.join(here, '../src/main.js')), s2 = smBlock(path.join(root, 'web/viewer/index.html'));
s1 && s1 === s2 ? ok('блок //<spacemouse> однаковий в обох версіях сторінки') : fail('блок //<spacemouse> у двох версіях сторінки розійшовся');
p1 && p1 === p2 ? ok('блок //<pose> однаковий в обох версіях сторінки') : fail('блок //<pose> у web/viewer-wasm/src/main.js і web/viewer/index.html розійшовся');
const vjBlock = f => (readFileSync(f, 'utf8').match(/^\/\/<viewjson>[^\n]*\n([\s\S]*?)^\/\/<\/viewjson>/m) || [])[1];
const v1 = vjBlock(path.join(here, '../src/main.js')), v2 = vjBlock(path.join(root, 'web/viewer/index.html'));
v1 && v1 === v2 ? ok('блок //<viewjson> однаковий в обох версіях сторінки') : fail('блок //<viewjson> у двох версіях сторінки розійшовся');

// Зіткнення в AR: сеанс є лише на телефоні, тож геометрію кімнати перевіряємо тут числами.
// Стіна — площина WebXR на x = 1 (нормаль площини, її вісь Y, дивиться в −X), підлога — на y = 0.
{
  const wallM = [0, 0, 1, 0, -1, 0, 0, 0, 0, -1, 0, 0, 1, 1, 0, 1];          // по стовпцях: x→+Z, y→−X, z→−Y
  const sq = [{ x: -1, z: -1 }, { x: 1, z: -1 }, { x: 1, z: 1 }, { x: -1, z: 1 }];
  const floorM = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const big = sq.map(p => ({ x: p.x * 5, z: p.z * 5 }));
  const wall = planeTris(sq, wallM), floor = planeTris(big, floorM);
  const r = new Room(); r.build([{ tris: wall, kind: 0 }, { tris: floor, kind: 1 }]);
  const A = [0, 0.6, 0], KI = k => (k < 0 ? '—' : KIND[k]);
  const cases = [
    ['точка за стіною', A, [1.2, 0.6, 0.3], 0, 0],
    ['точка перед стіною', A, [0.9, 0.6, 0.3], 0, -1],
    ['ближче за 3 см до стіни', A, [0.98, 0.6, 0.3], 0, 0],
    ['стіна вище за свій край — мимо', A, [1.2, 2.3, 0], 0, -1],
    ['ківш нижче підлоги, на якій стоїть машина', A, [0.5, -0.3, 0], 0, -1],
    ['машина на столі (0.75 м): підлога кімнати — перешкода', [0, 1.3, 0], [0.5, -0.1, 0], 0.75, 1],
    ['довгий відрізок через кілька комірок', [-3, 0.6, -2], [3, 0.7, 0.5], 0, 0],
  ];
  const bad = cases.filter(([, a, p, fy, want]) => r.hit(a, p, fy) !== want).map(([n, a, p, fy, want]) => `${n}: ${KI(r.hit(a, p, fy))} замість ${KI(want)}`);
  const m = meshTris(new Float32Array([2, 0, -1, 2, 2, -1, 2, 0, 1]), new Uint32Array([0, 1, 2]), floorM);
  r.build([{ tris: m, kind: 2 }]);
  if (r.hit(A, [2.5, 0.5, 0], 0) !== 2) bad.push('трикутник сітки не зупинив відрізок');
  bad.length ? fail('зіткнення AR: ' + bad.join('; ')) : ok(`зіткнення AR: ${cases.length + 1} випадків (стіна, підлога, стіл, сітка)`);
}

// Зліпок кімнати: зникла площина → тінь; повторна поява підтверджує; підтверджена лишається назавжди.
{
  const wallM = x => [0, 0, 1, 0, -1, 0, 0, 0, 0, -1, 0, 0, x, 1, 0, 1];
  const sq = s => [{ x: -s, z: -s }, { x: s, z: -s }, { x: s, z: s }, { x: -s, z: s }];
  const bad = [], st = k => JSON.stringify(k.stats());
  let k = new Keep();
  k.update([{ key: 'a', kind: 0, m: wallM(1), poly: sq(0.3) }], 0); k.update([], 1000);
  if (k.stats().wait !== 1) bad.push('зникла площина не стала тінню: ' + st(k));
  k.update([], 7000); if (k.ghosts.length) bad.push('мала площина без повторної появи лишилась: ' + st(k));
  k = new Keep();                                              // з'явилась → зникла → знову (новий XRPlane) → зникла
  k.update([{ key: 'a', kind: 0, m: wallM(1), poly: sq(0.3) }], 0); k.update([], 500);
  k.update([{ key: 'b', kind: 0, m: wallM(1.03), poly: sq(0.4) }], 1000);
  if (k.ghosts.length || k.live.get('b').conf !== 2) bad.push('повторна поява не підтвердила: ' + st(k));
  k.update([], 2000); k.update([], 8000);
  if (k.stats().fixed !== 1) bad.push('підтверджена площина не лишилась назавжди: ' + st(k));
  k.update([], 600000); if (k.stats().fixed !== 1) bad.push('«назавжди» минуло: ' + st(k));
  for (let i = 0; i < 5; i++) k.vote(k.ghosts[0], true);
  k.vote(k.ghosts[0], false); for (let i = 0; i < 5; i++) k.vote(k.ghosts[0], true);
  if (k.ghosts.length !== 1) bad.push('перерваний ряд голосів «крізь» прибрав площину');
  k.vote(k.ghosts[0], true); if (k.ghosts.length) bad.push('карта глибин не прибрала хибну площину');
  k = new Keep();                                              // злиття: мала зникла, бо її поглинула більша
  k.update([{ key: 'a', kind: 0, m: wallM(1), poly: sq(0.3) }, { key: 'b', kind: 0, m: wallM(1), poly: sq(1.5) }], 0);
  k.update([{ key: 'b', kind: 0, m: wallM(1), poly: sq(1.5) }], 500);
  if (k.ghosts.length || k.live.get('b').conf !== 2) bad.push('злиття не розпізнано: ' + st(k));
  k = new Keep();                                              // інша площина поруч не «покриває»: паралельна за 0.5 м
  k.update([{ key: 'a', kind: 0, m: wallM(1), poly: sq(0.3) }], 0); k.update([{ key: 'b', kind: 0, m: wallM(1.5), poly: sq(1.5) }], 500);
  if (k.ghosts.length !== 1) bad.push('паралельна площина за 0.5 м поглинула тінь');
  k = new Keep();                                              // велика й довго видна — лишається й без повторної появи
  k.update([{ key: 'a', kind: 0, m: wallM(1), poly: sq(0.8) }], 0); k.update([], 6000); k.update([], 12000);
  if (k.stats().fixed !== 1) bad.push('велика стіна, видна 6 с, не лишилась: ' + st(k));
  bad.length ? fail('зліпок кімнати: ' + bad.join('; ')) : ok('зліпок кімнати: тінь, повторна поява, злиття, назавжди, карта глибин');
}

// Скан кімнати з карт глибин: кімната-коробка x −2…2, y 0…2.6, z −3…2 м, камера на висоті 1.4 м крутиться на місці
// (кожні 22.5°, погляд на 20° донизу і на 15° догори), три проходи; у першому посеред кімнати стоїть «людина»-стовп.
{
  const lo = [-2, 0, -3], hi = [2, 2.6, 2], O = [0, 1.4, 0], pl = [0.8, 0, -1.7], ph = [1.2, 1.8, -1.3];
  const frame = (yaw, pitch, person) => {
    const cols = 96, rows = 72, tx = Math.tan(30 * Math.PI / 180), ty = Math.tan(23 * Math.PI / 180);
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const R = v => { const y1 = v[1] * cp - v[2] * sp, z1 = v[1] * sp + v[2] * cp; return [v[0] * cy + z1 * sy, y1, -v[0] * sy + z1 * cy]; };
    const dirs = new Float32Array(cols * rows * 3), dep = new Float32Array(cols * rows);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const d = R([(2 * c / (cols - 1) - 1) * tx, (1 - 2 * r / (rows - 1)) * ty, -1]), i = r * cols + c;
      dirs.set(d, i * 3);
      let t = Infinity;
      for (let a = 0; a < 3; a++) if (d[a]) t = Math.min(t, ((d[a] > 0 ? hi : lo)[a] - O[a]) / d[a]);
      if (person) {                                            // перетин променя з коробкою «людини» (метод плит)
        let t0 = 0, t1 = Infinity;
        for (let a = 0; a < 3; a++) {
          if (!d[a]) { if (O[a] < pl[a] || O[a] > ph[a]) t1 = -1; continue; }
          let u = (pl[a] - O[a]) / d[a], v = (ph[a] - O[a]) / d[a]; if (u > v) [u, v] = [v, u];
          t0 = Math.max(t0, u); t1 = Math.min(t1, v);
        }
        if (t1 >= t0 && t0 > 0) t = Math.min(t, t0);
      }
      dep[i] = t;
    }
    return [O, R([0, 0, -1]), dirs, dep];
  };
  const sc = new Scan(), bad = [];
  for (let pass = 0; pass < 3; pass++) for (let k = 0; k < 16; k++) for (const p of [-20, 15]) sc.integrate(...frame(k * Math.PI / 8, p * Math.PI / 180, pass === 0));
  while (sc.remesh(1000));
  const { tris, kind } = sc.geometry();
  const parts = sc.takeChunks(), inParts = parts.reduce((n, c) => n + c.kind.length, 0);
  if (inParts !== kind.length || sc.takeChunks().length) bad.push(`шматки: ${inParts} трикутників замість ${kind.length}, або віддаються вдруге`);
  let far = 0, ghost = 0;
  for (let i = 0; i < tris.length; i += 3) {
    const p = [tris[i], tris[i + 1], tris[i + 2]];
    if (Math.min(...[0, 1, 2].flatMap(a => [Math.abs(p[a] - lo[a]), Math.abs(p[a] - hi[a])])) > 0.04) far++;
    if (p[0] > pl[0] && p[0] < ph[0] && p[2] > pl[2] && p[2] < ph[2] && p[1] > 0.15 && p[1] < ph[1]) ghost++;
  }
  const kinds = [0, 0, 0]; for (const k of kind) kinds[k]++;
  // затінення: лице трикутника дивиться туди ж, куди гладкі нормалі (у порожнечу), нормалі рівних стін — як грані,
  // затінення кутів — ≈ 1 посеред стіни і темніше біля кута стіни й підлоги
  const { nrm, ao } = sc.geometry();
  let wind = 0, agree = 0; const aoMid = [], aoFoot = [];
  for (let i = 0; i < kind.length; i++) {
    const T = tris.subarray(i * 9, i * 9 + 9), N = nrm.subarray(i * 9, i * 9 + 9);
    const ux = T[3] - T[0], uy = T[4] - T[1], uz = T[5] - T[2], vx = T[6] - T[0], vy = T[7] - T[1], vz = T[8] - T[2];
    const fx = uy * vz - uz * vy, fy = uz * vx - ux * vz, fz = ux * vy - uy * vx, fl = Math.hypot(fx, fy, fz) || 1;
    const d = (fx * (N[0] + N[3] + N[6]) + fy * (N[1] + N[4] + N[7]) + fz * (N[2] + N[5] + N[8])) / fl / 3;
    if (d > 0) wind++; if (d > 0.9) agree++;
    for (let j = 0; j < 3; j++) {
      const x = T[j * 3], y = T[j * 3 + 1], z = T[j * 3 + 2];
      if (Math.abs(z + 3) < 0.05 && Math.abs(x) < 1 && y > 1 && y < 2) aoMid.push(ao[i * 3 + j]);
      if (y < 0.06 && z < -2.9 && x < -0.3) aoFoot.push(ao[i * 3 + j]);
    }
  }
  const mean = a => a.reduce((s, v) => s + v, 0) / (a.length || 1);
  if (wind < kind.length) bad.push(`${kind.length - wind} трикутників лицем від гладких нормалей`);
  if (agree < kind.length * 0.95) bad.push(`нормалі збігаються з гранями лише в ${(agree / kind.length * 100).toFixed(1)} %`);
  if (mean(aoMid) < 0.97) bad.push(`рівна стіна затінена як кут: ${mean(aoMid).toFixed(2)}`);
  if (!(Math.min(...aoFoot) < 0.8)) bad.push(`кут стіни й підлоги не темніший: найменше ${Math.min(...aoFoot).toFixed(2)}`);
  if (kind.length < 20000) bad.push(`замало трикутників: ${kind.length}`);
  if (far > tris.length / 3 * 0.001) bad.push(`${far} з ${tris.length / 3} вершин далі за 4 см від стін`);
  if (ghost) bad.push(`від «людини», що пішла, лишилось ${ghost} вершин`);
  if (!kinds[0] || !kinds[1]) bad.push('немає стін або підлоги: ' + kinds.join('/'));
  const empty = new Scan(); empty.integrate(O, [0, 0, -1], new Float32Array(30), new Float32Array(10)); empty.remesh();
  if (empty.geometry().kind.length) bad.push('без глибини з\'явилась поверхня');
  bad.length ? fail('скан кімнати: ' + bad.join('; '))
             : ok(`скан кімнати: ${sc.frames} кадрів → ${kind.length} трикутників у ${parts.length} шматках (стіни ${kinds[0]}, горизонтальні ${kinds[1]}), усі в межах 4 см, «людину» вичищено; затінення: лице й нормалі узгоджені, AO стіни ${mean(aoMid).toFixed(2)}, кута до ${Math.min(...aoFoot).toFixed(2)}`);
}

// --- переклад -------------------------------------------------------------------------------------
const mainJs = readFileSync(path.join(here, '../src/main.js'), 'utf8');
const miss = (what, list) => list.length ? fail(`${what}: ${list.length} — ${list.slice(0, 8).join(', ')}${list.length > 8 ? ' …' : ''}`) : ok(what + ': повний');

const keysUk = Object.keys(UI.uk);
for (const l of LANGS.filter(l => l !== 'uk')) {
  const mine = new Set(Object.keys(UI[l]));
  miss(`переклад ${l}: немає ключів`, keysUk.filter(k => !mine.has(k)));
  miss(`переклад ${l}: зайві ключі`, [...mine].filter(k => !keysUk.includes(k)));
}
// кожен цілий t('ключ') із main.js має бути у словнику (далі — окремо ключі, які код складає з id)
const used = [...mainJs.matchAll(/\bt\(\s*'([\w.]+)'\s*[),]/g)].map(m => m[1]);
miss('ключі t() з main.js у словнику', [...new Set(used)].filter(k => !(k in UI.uk)));
// id поз, виглядів, перемикачів і кутів беруться з самого main.js — на них зав'язана розмітка панелі
const ids = (re, split) => { const m = mainJs.match(re); return m ? split(m[1]) : []; };
const objKeys = s => [...s.matchAll(/(\w+)\s*:/g)].map(m => m[1]);
const built = [
  ...ids(/const POSES = \{([^}]*)\}/, objKeys).map(k => 'pose.' + k),
  ...ids(/const VIEWS = \{([^}]*)\}/, objKeys).map(k => 'view.' + k),
  ...ids(/const TOG = \[([^\]]*)\]/, s => [...s.matchAll(/'(\w+)'/g)].map(m => m[1])).map(k => 'tog.' + k),
  ...ids(/const ANG = \[([^;]*)\];/, s => [...s.matchAll(/\['(\w+)'/g)].map(m => m[1])).flatMap(k => ['ang.' + k, `ang.${k}.hint`]),
];
built.length > 20 ? ok(`складені ключі: ${built.length}`) : fail(`id поз/виглядів/перемикачів не вичитались із main.js: ${built.length}`);
miss('складені ключі у словнику', built.filter(k => !(k in UI.uk)));
// групи й описані параметри моделі мають англійський двійник
miss('англійські назви груп', schema.map(g => g.name).filter(n => !(n in GROUPS_EN)));
miss('англійські описи параметрів', all.filter(p => p.desc && !(p.name in PARAMS_EN)).map(p => p.name));
miss('зайві записи у словнику параметрів', Object.keys(PARAMS_EN).filter(n => !all.some(p => p.name === n)));

const err = [], t0 = performance.now();
const os = (await createOpenSCAD({ noInitialRun: true, print: s => err.push(s), printErr: s => err.push(s) })).getInstance();
os.FS.writeFile('/model.scad', source);
// модель підключає полігони логотипа `include <brand/…>` — сторінка кладе їх поруч так само (main.js → воркер)
os.FS.mkdir('/brand');
for (const f of readdirSync(path.join(root, 'scad/brand'))) os.FS.writeFile('/brand/' + f, readFileSync(path.join(root, 'scad/brand', f), 'utf8'));
if (!/import\.meta\.glob\('\.\.\/\.\.\/\.\.\/scad\/brand\/\*\.scad'/.test(mainJs) || !/files: scadBrand/.test(mainJs))
  fail('main.js не передає воркеру scad/brand/*.scad — модель без них не збереться');
const rc = os.callMain(['/model.scad', '-o', '/out.off', '--backend=manifold', '-D', 'part="view_all"']);
const ms = Math.round(performance.now() - t0);
const bad = err.filter(l => /^(WARNING|ERROR)/.test(l.trim()));
rc === 0 && !bad.length ? ok(`OpenSCAD-WASM: код 0, без попереджень, ${ms} мс`) : fail(`OpenSCAD-WASM: код ${rc}; ${bad.slice(0, 3).join(' | ')}`);
// Сторінка перебудовує модель на КОЖНУ зміну параметра. Нормально ≈ 3.5 с (з лого); лого з сотнями
// скалок-полігонів колись дало 8.5 с, і помітили це лише ручним заміром. Попередження, не падіння:
// на іншій машині інший час — але стрибок удвічі видно завжди.
const SLOW_MS = 6000;
if (ms > SLOW_MS) console.log(`⚠ OpenSCAD-WASM будує модель ${ms} мс (> ${SLOW_MS}): що нового в моделі? Перевір складність доданої геометрії (tools/brand_merge.py — приклад)`);
const vm = err.map(l => l.trim().match(/^ECHO: VIEW = (.*)$/)).find(Boolean);
if (!vm) fail('немає echo(VIEW = …)');
else {
  const V = Object.fromEntries(JSON.parse(vm[1].replace(/\b(undef|nan|-?inf)\b/g, 'null')));
  const { parts } = splitOff(os.FS.readFile('/out.off', { encoding: 'utf8' }), V.parts, V.spacing);
  const empty = V.parts.filter(n => !parts[n] || parts[n].pos.length < 9);
  empty.length ? fail('порожні деталі: ' + empty.join(', ')) : ok(`деталей: ${V.parts.length}, вершин: ${Object.values(parts).reduce((s, p) => s + p.pos.length / 3, 0)}`);
  const wide = Object.entries(parts).filter(([, p]) => { let m = 0; for (let i = 1; i < p.pos.length; i += 3) m = Math.max(m, Math.abs(p.pos[i])); return m > V.spacing / 2; });
  wide.length ? fail('деталь ширша за view_spacing/2 — розрізання за Y зламається: ' + wide.map(w => w[0])) : ok('розрізання за Y коректне');
  // логотип (show_brand, BRAND_ON_YELLOW / BRAND_ON_DARK моделі) має дійти до сторінки своїм кольором
  const brandCol = c => c.every(v => v <= 20) || c.every(v => v >= 240);
  const noBrand = ['boom', 'v_stick', 'bucket', 'post'].filter(n => !parts[n] || !parts[n].groups.some(g => brandCol(g.color) && g.idx.length));
  noBrand.length ? fail('немає граней логотипа у: ' + noBrand.join(', ')) : ok('логотип на стрілі, рукояті, ковші й колоні');
  const { pose } = await import('data:text/javascript,' + encodeURIComponent(p1 + '\nexport { pose };'));
  // Зворотна задача мусить бути точним оберненням прямої: ставимо зуб туди, де він
  // щойно був, і кути мають повернутися ті самі. Без цього перетягування за ківш
  // тихо «попливе» після будь-якої зміни геометрії.
  {
    let worst = 0, миші = 0;
    for (const [b, s2, o] of [[15, 100, 60], [-20, 140, 20], [40, 80, 90], [5, 120, 45], [0, 158, 0]]) {
      const Q = pose(V, b, s2, o);
      const r = armFromTip(V, Q.T, o, { boom: b, stick: s2 });
      if (!r) { миші++; continue; }
      const back = pose(V, r.boom, r.stick, o);
      worst = Math.max(worst, Math.hypot(back.T[0] - Q.T[0], back.T[1] - Q.T[1]));
    }
    миші === 0 && worst < 0.01
      ? ok(`зворотна задача: зуб стає на місце, похибка ${worst.toExponential(1)} мм`)
      : fail(`зворотна задача: без розв'язку ${миші}, похибка до ${worst.toFixed(3)} мм`);
  }

  // Те саме для ковша, що йде не повертаючись (SpaceMouse при замку камери): ті самі
  // зуб і напрям ковша мають повернути ті самі три кути.
  {
    let worst = 0, нема = 0;
    for (const [b, s2, o] of [[15, 100, 60], [-20, 140, 20], [40, 80, 90], [5, 120, 45], [0, 158, 0]]) {
      const Q = pose(V, b, s2, o), r = armFromBucket(V, Q.T, Q.bdir, { boom: b, stick: s2 });
      if (!r) { нема++; continue; }
      worst = Math.max(worst, Math.abs(r.boom - b), Math.abs(r.stick - s2), Math.abs(r.bucket - o));
    }
    нема === 0 && worst < 1e-6
      ? ok(`ківш без повороту: кути повертаються ті самі, похибка ${worst.toExponential(1)}°`)
      : fail(`ківш без повороту: без розв'язку ${нема}, похибка кутів до ${worst.toFixed(4)}°`);
  }

  const [th, psi, om] = V.angles, P = pose(V, th, psi, om), tm = err.join('\n').match(/ЗУБ КОВША: x=(-?\d+) z=(-?\d+)/);
  tm && Math.abs(P.T[0] - tm[1]) <= 1 && Math.abs(P.T[1] - tm[2]) <= 1 ? ok(`поза JS = echo моделі: зуб (${P.T[0].toFixed(1)}, ${P.T[1].toFixed(1)})`) : fail(`поза JS (${P.T}) ≠ echo моделі (${tm && tm.slice(1)})`);
}
