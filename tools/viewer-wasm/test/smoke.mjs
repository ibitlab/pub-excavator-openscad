// Димовий тест без браузера: `npm test`
//  1) рушій openscad-wasm-prebuilt (він старіший за настільний OpenSCAD!) будує модель у режимі part="view_all" без помилок;
//  2) усі деталі зі списку view_parts непорожні, echo(VIEW) читається, схема параметрів розбирається;
//  3) блок //<pose> однаковий у цій сторінці та в tools/viewer/index.html (поза рахується однаково в обох версіях);
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
import { armFromTip } from '../src/ik.js';

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
const p1 = poseBlock(path.join(here, '../src/main.js')), p2 = poseBlock(path.join(root, 'tools/viewer/index.html'));
const smBlock = f => (readFileSync(f, 'utf8').match(/^\/\/<spacemouse>[^\n]*\n([\s\S]*?)^\/\/<\/spacemouse>/m) || [])[1];
const s1 = smBlock(path.join(here, '../src/main.js')), s2 = smBlock(path.join(root, 'tools/viewer/index.html'));
s1 && s1 === s2 ? ok('блок //<spacemouse> однаковий в обох версіях сторінки') : fail('блок //<spacemouse> у двох версіях сторінки розійшовся');
p1 && p1 === p2 ? ok('блок //<pose> однаковий в обох версіях сторінки') : fail('блок //<pose> у tools/viewer-wasm/src/main.js і tools/viewer/index.html розійшовся');
const vjBlock = f => (readFileSync(f, 'utf8').match(/^\/\/<viewjson>[^\n]*\n([\s\S]*?)^\/\/<\/viewjson>/m) || [])[1];
const v1 = vjBlock(path.join(here, '../src/main.js')), v2 = vjBlock(path.join(root, 'tools/viewer/index.html'));
v1 && v1 === v2 ? ok('блок //<viewjson> однаковий в обох версіях сторінки') : fail('блок //<viewjson> у двох версіях сторінки розійшовся');

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

  const [th, psi, om] = V.angles, P = pose(V, th, psi, om), tm = err.join('\n').match(/ЗУБ КОВША: x=(-?\d+) z=(-?\d+)/);
  tm && Math.abs(P.T[0] - tm[1]) <= 1 && Math.abs(P.T[1] - tm[2]) <= 1 ? ok(`поза JS = echo моделі: зуб (${P.T[0].toFixed(1)}, ${P.T[1].toFixed(1)})`) : fail(`поза JS (${P.T}) ≠ echo моделі (${tm && tm.slice(1)})`);
}
