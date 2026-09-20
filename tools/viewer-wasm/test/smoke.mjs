// Димовий тест без браузера: `npm test`
//  1) рушій openscad-wasm (він старіший за настільний OpenSCAD!) будує модель у режимі part="view_all" без помилок;
//  2) усі деталі зі списку view_parts непорожні, echo(VIEW) читається, схема параметрів розбирається;
//  3) блок //<pose> однаковий у цій сторінці та в tools/viewer/index.html (поза рахується однаково в обох версіях);
//  4) поза з JavaScript збігається з echo самої моделі ("ЗУБ КОВША: x=… z=…").
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createOpenSCAD } from 'openscad-wasm';
import { splitOff } from '../src/offmesh.js';
import { readSchema, scadLiteral } from '../src/schema.js';

const here = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(here, '../../..');
const source = readFileSync(path.join(root, 'scad/excavator_boom.scad'), 'utf8');
const fail = m => { console.error('✗ ' + m); process.exitCode = 1; }, ok = m => console.log('✓ ' + m);

const schema = readSchema(source), all = schema.flatMap(g => g.params);
all.length > 80 ? ok(`схема: ${schema.length} груп, ${all.length} параметрів`) : fail(`схема підозріло мала: ${all.length}`);
const L1 = all.find(p => p.name === 'boom_L1'); scadLiteral(L1, 950) === '950' ? ok('літерали параметрів') : fail('scadLiteral');

const poseBlock = f => (readFileSync(f, 'utf8').match(/\/\/<pose>[^\n]*\n([\s\S]*?)\/\/<\/pose>/) || [])[1];
const p1 = poseBlock(path.join(here, '../src/main.js')), p2 = poseBlock(path.join(root, 'tools/viewer/index.html'));
const smBlock = f => (readFileSync(f, 'utf8').match(/\/\/<spacemouse>[^\n]*\n([\s\S]*?)\/\/<\/spacemouse>/) || [])[1];
const s1 = smBlock(path.join(here, '../src/main.js')), s2 = smBlock(path.join(root, 'tools/viewer/index.html'));
s1 && s1 === s2 ? ok('блок //<spacemouse> однаковий в обох версіях сторінки') : fail('блок //<spacemouse> у двох версіях сторінки розійшовся');
p1 && p1 === p2 ? ok('блок //<pose> однаковий в обох версіях сторінки') : fail('блок //<pose> у tools/viewer-wasm/src/main.js і tools/viewer/index.html розійшовся');

const err = [], t0 = performance.now();
const os = (await createOpenSCAD({ noInitialRun: true, print: s => err.push(s), printErr: s => err.push(s) })).getInstance();
os.FS.writeFile('/model.scad', source);
const rc = os.callMain(['/model.scad', '-o', '/out.off', '--backend=manifold', '-D', 'part="view_all"']);
const ms = Math.round(performance.now() - t0);
const bad = err.filter(l => /^(WARNING|ERROR)/.test(l.trim()));
rc === 0 && !bad.length ? ok(`OpenSCAD-WASM: код 0, без попереджень, ${ms} мс`) : fail(`OpenSCAD-WASM: код ${rc}; ${bad.slice(0, 3).join(' | ')}`);
const vm = err.map(l => l.trim().match(/^ECHO: VIEW = (.*)$/)).find(Boolean);
if (!vm) fail('немає echo(VIEW = …)');
else {
  const V = Object.fromEntries(JSON.parse(vm[1].replace(/\b(undef|nan|-?inf)\b/g, 'null')));
  const { parts } = splitOff(os.FS.readFile('/out.off', { encoding: 'utf8' }), V.parts, V.spacing);
  const empty = V.parts.filter(n => !parts[n] || parts[n].pos.length < 9);
  empty.length ? fail('порожні деталі: ' + empty.join(', ')) : ok(`деталей: ${V.parts.length}, вершин: ${Object.values(parts).reduce((s, p) => s + p.pos.length / 3, 0)}`);
  const wide = Object.entries(parts).filter(([, p]) => { let m = 0; for (let i = 1; i < p.pos.length; i += 3) m = Math.max(m, Math.abs(p.pos[i])); return m > V.spacing / 2; });
  wide.length ? fail('деталь ширша за view_spacing/2 — розрізання за Y зламається: ' + wide.map(w => w[0])) : ok('розрізання за Y коректне');
  const { pose } = await import('data:text/javascript,' + encodeURIComponent(p1 + '\nexport { pose };'));
  const [th, psi, om] = V.angles, P = pose(V, th, psi, om), tm = err.join('\n').match(/ЗУБ КОВША: x=(-?\d+) z=(-?\d+)/);
  tm && Math.abs(P.T[0] - tm[1]) <= 1 && Math.abs(P.T[1] - tm[2]) <= 1 ? ok(`поза JS = echo моделі: зуб (${P.T[0].toFixed(1)}, ${P.T[1].toFixed(1)})`) : fail(`поза JS (${P.T}) ≠ echo моделі (${tm && tm.slice(1)})`);
}
