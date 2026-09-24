// Кадри «туру» 3D-сторінки для README: кілька режимів і ракурсів одним роликом —
// щоб з першого погляду було видно, що за посиланням. Знімає WASM-сторінку (вона двомовна
// і свіжіша за опубліковану), кадри → tools/media/readme_media.sh → GIF у docs/img/.
//
//   cd tools/viewer-wasm && npx vite build && npx vite preview --port 8797 --strictPort &
//   node tools/media/page_tour.mjs "http://localhost:8797/?lang=en" --lang en --frames /tmp/tour_en --fps 10
//
// Сцени: ізометрія + цикл копання → збоку з робочою зоною, пози «виліт / глибина» →
// ззаду-збоку, «що з чим зварене», обертання камери → згори → назад в ізометрію.
// Кути — з POSES сторінки (tools/viewer-wasm/src/main.js), між ними — плавна інтерполяція.
// Код виходу 3 = на сторінці були помилки JS.
import { existsSync, mkdirSync, rmSync } from 'node:fs';
let puppeteer; try { puppeteer = (await import('puppeteer-core')).default; } catch (e) { console.error('Спершу: npm i --no-save --prefix tools/media puppeteer-core'); process.exit(2); }
const argv = process.argv.slice(2), url = argv[0], opt = { size: '1280x800', fps: '10', lang: 'en' };
for (let i = 1; i < argv.length; i++) opt[argv[i].replace(/^--/, '')] = argv[++i];
if (!url || !opt.frames) { console.error('Використання: page_tour.mjs URL --frames ТЕКА [--lang en|uk] [--fps 10] [--size 1280x800]'); process.exit(1); }
const L = {
  en: { side: 'Side', iso: 'Isometric', rear: 'Rear-side', top: 'Top', env: 'work envelope', kin: 'what is welded to what' },
  uk: { side: 'Збоку', iso: 'Ізометрія', rear: 'Ззаду-збоку', top: 'Зверху', env: 'робоча зона', kin: 'що з чим зварене' },
}[opt.lang];
const POSE = { work: [15, 100, 60], reach: [-5, 156, -17], deep: [-38, 90, 60], high: [58, 156, 0], dump: [45, 140, -17] };
const DIG = [[12, 145, 0], [-22, 142, 5], [-26, 95, 45], [-22, 78, 125], [38, 80, 135], [42, 140, 120], [42, 142, -17], [15, 100, 60]];

const CHROME = process.env.CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].find(existsSync);
const [W, H] = opt.size.split('x').map(Number), fps = +opt.fps, sleep = ms => new Promise(r => setTimeout(r, ms));
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--force-color-profile=srgb'] });
const p = await b.newPage(); let errors = 0;
p.on('pageerror', e => { errors++; console.log('[pageerror]', String(e).slice(0, 300)); });
p.on('console', m => { if (m.type() === 'error') { errors++; console.log('[console.error]', m.text().slice(0, 300)); } });
await p.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
await p.goto(url, { waitUntil: 'load' });
await p.waitForFunction('window.__READY__ === true', { timeout: 180000 });
await p.evaluate(() => { const x = document.querySelector('#tip button, #tip .x'); if (x) x.click(); const t = document.querySelector('#tip'); if (t) t.hidden = true; });   // підказка «потягніть ківш» — не для ролика

const setAngles = v => p.evaluate(v => ['boom', 'stick', 'bucket'].forEach((k, i) => { const e = document.getElementById('sl_' + k); e.value = v[i]; e.dispatchEvent(new Event('input')); }), v);
const click = t => p.evaluate(t => { const el = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === t); if (!el) throw new Error('немає кнопки: ' + t); el.click(); }, t);
const toggle = (t, on) => p.evaluate(([t, on]) => { const l = [...document.querySelectorAll('#toggles label')].find(x => x.textContent.includes(t)); if (!l) throw new Error('немає прапорця: ' + t);
  const c = l.querySelector('input'); if (c.checked !== on) c.click(); }, [t, on]);

rmSync(opt.frames, { recursive: true, force: true }); mkdirSync(opt.frames, { recursive: true });
let f = 0;
const frame = async () => { await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  await p.screenshot({ path: `${opt.frames}/f${String(f++).padStart(4, '0')}.png` }); };
const hold = async s => { for (let i = 0; i < Math.round(s * fps); i++) await frame(); };
const move = async (a, z, s) => { const n = Math.max(1, Math.round(s * fps));             // кути a → z за s секунд, згладжено
  for (let j = 1; j <= n; j++) { const t = j / n, e = t * t * (3 - 2 * t); await setAngles(a.map((v, q) => v + (z[q] - v) * e)); await frame(); } };
const orbit = async (dx, s) => {                                                            // обертання камери: тягнемо по порожньому небу
  const r = await p.evaluate(() => { const c = document.getElementById('c').getBoundingClientRect(); return [c.left + c.width * 0.5, c.top + c.height * 0.12]; });
  const n = Math.round(s * fps); await p.mouse.move(r[0], r[1]); await p.mouse.down();
  for (let j = 1; j <= n; j++) { await p.mouse.move(r[0] + dx * j / n, r[1], { steps: 2 }); await frame(); }
  await p.mouse.up(); };
// Вигляд вписується за ПОТОЧНОЮ позою — тому вписуємо за найбільшою (виліт), а тоді повертаємо позу:
// інакше на «макс. виліт» стріла виходить за кадр.
// Виліт — найширша поза, а висота — найвища, тож після вписування ще wheel кроків коліщатка назад.
const wheelOut = async n => { const r = await p.evaluate(() => { const c = document.getElementById('c').getBoundingClientRect(); return [c.left + c.width / 2, c.top + c.height / 2]; });
  await p.mouse.move(r[0], r[1]); for (let i = 0; i < n; i++) { await p.mouse.wheel({ deltaY: 120 }); await sleep(60); } await sleep(400); };
const view = async (t, back, wheel = 0) => { await setAngles(POSE.reach); await click(t); await sleep(350); await setAngles(back); if (wheel) await wheelOut(wheel); await sleep(150); };

// 1. ізометрія, цикл копання
await view(L.iso, POSE.work, 2); await hold(0.6);
for (let i = 0; i < DIG.length - 1; i++) await move(DIG[i], DIG[i + 1], 0.55);
// 2. збоку з робочою зоною: крайні пози
await toggle(L.env, true); await view(L.side, POSE.work, 6); await hold(0.5);
await move(POSE.work, POSE.reach, 0.9); await hold(0.3);
await move(POSE.reach, POSE.deep, 0.9); await hold(0.4);
await move(POSE.deep, POSE.work, 0.9);   // «макс. висоту» не показуємо: у кадрі збоку вона впирається під табло, висоту й так видно з робочої зони
// 3. ззаду-збоку: що з чим зварене, обертання камери
await toggle(L.env, false); await toggle(L.kin, true); await view(L.rear, POSE.work); await hold(0.5);
await orbit(-260, 2.2); await hold(0.4);
// 4. згори, і назад в ізометрію
await toggle(L.kin, false); await view(L.top, POSE.work); await hold(0.9);
await view(L.iso, POSE.work); await hold(0.6);
console.log(`кадрів: ${f} (${(f / fps).toFixed(1)} с при ${fps} к/с) → ${opt.frames}`);
await b.close(); process.exit(errors ? 3 : 0);
