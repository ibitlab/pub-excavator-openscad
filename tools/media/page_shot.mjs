// Знімок або кадри 3D-сторінки у headless Chrome (для перевірки сторінок і для матеріалів до публікацій).
// puppeteer-core свідомо не в package.json (зауваження npm audit у його залежностях): один раз
//   npm i --no-save --prefix tools/media puppeteer-core
// Приклади (сторінка вже має працювати: tools/viewer.sh або npm run preview):
//   node tools/media/page_shot.mjs http://127.0.0.1:8765/ --out hero.png --size 1200x1200 --dsf 2 --clean --angles -12,92,48 --view Ізометрія
//   node tools/media/page_shot.mjs URL --out ui.png --toggle "робоча зона" --view Збоку --meta cam.json
//   node tools/media/page_shot.mjs URL --cycle frames/ --size 1280x720 --dsf 1.5 --toggle "робоча зона" --view Ззаду-збоку --wheel 11
// Опції: --clean (сховати панель і написи) · --ortho · --angles стріла,рукоять,ківш · --view "текст кнопки вигляду" · --toggle/--untoggle "частина назви прапорця"
//        --wheel N (віддалити на N кроків коліщатка) · --meta файл.json (положення камери window.__CAM__) · --cycle ТЕКА (кадри циклу копання, --fps 25)
//        --eval "js" (довільний код у сторінці перед знімком) · CHROME=/шлях/до/chrome
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
let puppeteer; try { puppeteer = (await import('puppeteer-core')).default; } catch (e) { console.error('Спершу: npm i --no-save --prefix tools/media puppeteer-core'); process.exit(2); }
const argv = process.argv.slice(2), url = argv[0], opt = { size: '1280x720', dsf: '1', fps: '25', toggle: [], untoggle: [] };
for (let i = 1; i < argv.length; i++) { const k = argv[i].replace(/^--/, '');
  if (['clean', 'ortho'].includes(k)) opt[k] = true; else if (k === 'toggle' || k === 'untoggle') opt[k].push(argv[++i]); else opt[k] = argv[++i]; }
if (!url || !(opt.out || opt.cycle)) { console.error('Використання: page_shot.mjs URL --out файл.png | --cycle ТЕКА [опції — див. шапку файлу]'); process.exit(1); }
const CHROME = process.env.CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(existsSync);
const [W, H] = opt.size.split('x').map(Number), sleep = ms => new Promise(r => setTimeout(r, ms));
// swiftshader — програмний WebGL: працює без відеокарти і в headless. НЕ використовувати --virtual-time-budget (не чекає веб-воркерів) і --dump-dom (зависає на сторінці з requestAnimationFrame).
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--force-color-profile=srgb'] });
const p = await b.newPage(); let errors = 0;
p.on('pageerror', e => { errors++; console.log('[pageerror]', String(e).slice(0, 300)); });
p.on('console', m => { if (m.type() === 'error') { errors++; console.log('[console.error]', m.text().slice(0, 300)); } });
await p.setViewport({ width: W, height: H, deviceScaleFactor: +opt.dsf }); await p.goto(url, { waitUntil: 'load' });
await p.waitForFunction('window.__READY__ === true', { timeout: 180000 });        // сторінка сама ставить прапорець після першої побудови моделі
if (opt.clean) { await p.addStyleTag({ content: '#side,#hud,#help{display:none!important}' }); await p.evaluate(() => window.dispatchEvent(new Event('resize'))); }
const angles = v => p.evaluate(v => ['boom', 'stick', 'bucket'].forEach((k, i) => { const e = document.getElementById('sl_' + k); e.value = v[i]; e.dispatchEvent(new Event('input')); }), v);
const click = t => p.evaluate(t => { const el = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === t); if (!el) throw new Error('немає кнопки: ' + t); el.click(); }, t);
const setToggle = (t, on) => p.evaluate(([t, on]) => { const l = [...document.querySelectorAll('#toggles label')].find(x => x.textContent.includes(t)); if (!l) throw new Error('немає прапорця: ' + t);
  const c = l.querySelector('input'); if (c.checked !== on) c.click(); }, [t, on]);
for (const t of opt.toggle) await setToggle(t, true); for (const t of opt.untoggle) await setToggle(t, false);
const K = [[12, 145, 0, 1.0], [-22, 142, 5, 1.2], [-26, 95, 45, 1.6], [-22, 78, 125, 1.1], [38, 80, 135, 1.5], [42, 140, 120, 1.2], [42, 142, -17, 1.0], [12, 145, 0, 1.1]];   // цикл копання: кути + тривалість, с
if (opt.angles) await angles(opt.angles.split(',').map(Number)); else if (opt.cycle) await angles([-5, 156, -17]);   // для відео камера вписується за найбільшою позою
if (opt.ortho) await click('Ортогонально');
if (opt.view) await click(opt.view);                                              // вигляд вписується за поточною позою — тому після кутів
await sleep(300);
if (opt.wheel) { const r = await p.evaluate(() => { const c = document.getElementById('c').getBoundingClientRect(); return [c.left + c.width / 2, c.top + c.height / 2]; });
  await p.mouse.move(r[0], r[1]); for (let i = 0; i < +opt.wheel; i++) { await p.mouse.wheel({ deltaY: 120 }); await sleep(80); } }
if (opt.eval) await p.evaluate(opt.eval);
await sleep(500);                                                                  // згасання інерції камери
if (opt.meta) writeFileSync(opt.meta, JSON.stringify(await p.evaluate(() => window.__CAM__())));
if (opt.out) { await p.screenshot({ path: opt.out }); console.log('знімок:', opt.out); }
if (opt.cycle) {
  rmSync(opt.cycle, { recursive: true, force: true }); mkdirSync(opt.cycle, { recursive: true }); let f = 0;
  for (let i = 0; i < K.length - 1; i++) { const n = Math.round(K[i + 1][3] * +opt.fps);
    for (let j = 0; j < n; j++) { const t = j / n, e = t * t * (3 - 2 * t); await angles([0, 1, 2].map(q => K[i][q] + (K[i + 1][q] - K[i][q]) * e));
      await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))); await p.screenshot({ path: `${opt.cycle}/f${String(f++).padStart(4, '0')}.png` }); } }
  console.log('кадрів:', f, '→ ffmpeg -framerate', opt.fps, `-i ${opt.cycle}/f%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 out.mp4`);
}
await b.close(); process.exit(errors ? 3 : 0);
