// Проба сторінки: підняти в headless Chrome, поштовхати, ПОВЕРНУТИ ЧИСЛО.
//
// ЧОМУ ОКРЕМО ВІД page_shot.mjs. Той дає картинку: у нього є --eval, але результат
// викидається, і без --out він не запускається. А більшість питань до сторінки —
// числові («чи перекриває ручка HUD», «чи лишилася кнопка підсвіченою», «яка
// яскравість пікселя»), і колись кожне таке питання коштувало окремого скрипта на
// 20 рядків, де 8 — однакова обгортка. Тут обгортка одна, а питання — аргумент.
//
// puppeteer-core свідомо не в package.json (зауваження npm audit): один раз
//   npm i --no-save --prefix tools/media puppeteer-core
//
//   node tools/media/probe.mjs http://localhost:8797/ --js "__ONSCREEN__()"
//   node tools/media/probe.mjs URL --phone --js "document.querySelector('#grab').getBoundingClientRect()"
//   node tools/media/probe.mjs URL --phone --tap "#warn_btn" --js "!!document.querySelector('#warn.open')"
//   node tools/media/probe.mjs URL --set sl_boom=40 --js "__CAM__()" --shot "/tmp/x.png 0,0,372,330"
//
// Кроки виконуються В ПОРЯДКУ АРГУМЕНТІВ, тож послідовність «тап → міряю → тап → міряю»
// пишеться одним рядком:
//   --js "вираз"            надрукувати JSON результату (можна кілька разів)
//   --tap ЦІЛЬ              тап (при --phone — справжній дотик); ЦІЛЬ = "x,y" | "#sel" | "js:вираз→[x,y]"
//   --drag "ЦІЛЬ ЦІЛЬ"      перетягнути з першої точки в другу (миша, 12 кроків)
//   --set "id=значення"     значення у поле/повзунок + події input і change
//   --shot "файл.png"       знімок; "файл.png x,y,w,h" — лише прямокутник
//   --wait МС               пауза
// Прапорці: --phone (390×844, isMobile, hasTouch, dsf 2; інакше 1440×900) · --size WxH · --dsf N
//           --fresh (окремий контекст: порожній localStorage — мова, згорнуте попередження, лічильник підказки)
//           --settle МС (пауза після готовності, типово 600) · CHROME=/шлях/до/chrome
// Код виходу 3 = на сторінці були помилки JS (їх видно в [pageerror]/[console.error]).
import { existsSync } from 'node:fs';
let puppeteer; try { puppeteer = (await import('puppeteer-core')).default; } catch (e) { console.error('Спершу: npm i --no-save --prefix tools/media puppeteer-core'); process.exit(2); }
const argv = process.argv.slice(2), url = argv[0];
if (!url || url.startsWith('--')) { console.error('Використання: probe.mjs URL крок…  (кроки — див. шапку файлу)'); process.exit(1); }
const has = n => argv.includes('--' + n);
const val = (n, d) => { const i = argv.indexOf('--' + n); return i < 0 ? d : argv[i + 1]; };
const phone = has('phone'), sleep = ms => new Promise(r => setTimeout(r, ms));
const [W, H] = String(val('size', phone ? '390x844' : '1440x900')).split('x').map(Number);
const CHROME = process.env.CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium',
  '/usr/bin/chromium-browser', 'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(existsSync);
// swiftshader — програмний WebGL (у headless відеокарти немає). --virtual-time-budget і --dump-dom НЕ вмикати.
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--force-color-profile=srgb'] });
const ctx = has('fresh') ? await b.createBrowserContext() : b.defaultBrowserContext();
const p = await ctx.newPage(); let errors = 0;
p.on('pageerror', e => { errors++; console.log('[pageerror]', String(e).slice(0, 300)); });
p.on('console', m => { if (m.type() === 'error') { errors++; console.log('[console.error]', m.text().slice(0, 300)); } });
await p.setViewport({ width: W, height: H, deviceScaleFactor: +val('dsf', phone ? 2 : 1), isMobile: phone, hasTouch: phone });
await p.goto(url, { waitUntil: 'domcontentloaded' });
await p.waitForFunction('window.__READY__ === true', { timeout: 180000 });   // сторінка ставить прапорець після першої побудови
await sleep(+val('settle', 600));                                            // перші кадри swiftshader і згасання інерції камери

/**
 * Куди тиснути: "x,y" — точка, "#sel" — центр елемента, "js:вираз" — вираз у
 * сторінці, що дає [x, y]. Третє потрібне тому, що метал на екрані не там, де
 * здається: тапати по ковшу треба в `js:__ONSCREEN__().body` (центр габариту),
 * а не між віссю E і зубом — там порожнеча всередині пащі.
 */
const at = async v => {
  v = v.trim();
  if (/^[-\d.]+,[-\d.]+$/.test(v)) return v.split(',').map(Number);
  if (v.startsWith('js:')) return await p.evaluate(`(()=>(${v.slice(3)}))()`);
  return await p.evaluate(s => { const e = document.querySelector(s); if (!e) throw new Error('немає елемента: ' + s);
    const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }, v);
};

for (let i = 1; i < argv.length; i++) {
  const k = argv[i].replace(/^--/, ''), v = argv[i + 1];
  if (k === 'js') { i++;
    // Вираз або тіло функції (якщо є return). JSON робиться В СТОРІНЦІ: інакше DOMRect
    // та інші об'єкти з геттерами на прототипі приїжджають порожніми.
    const src = /\breturn\b/.test(v) ? `(()=>{${v}})()` : `(()=>(${v}))()`;
    console.log(await p.evaluate(`JSON.stringify(${src} ?? null)`));
  } else if (k === 'tap') { i++; const [x, y] = await at(v);
    if (phone) await p.touchscreen.tap(x, y); else await p.mouse.click(x, y);
    await sleep(150);
  } else if (k === 'drag') { i++; const [A, B] = v.trim().split(/\s+/);
    const [x1, y1] = await at(A), [x2, y2] = await at(B);
    await p.mouse.move(x1, y1); await p.mouse.down();
    for (let s = 1; s <= 12; s++) { await p.mouse.move(x1 + (x2 - x1) * s / 12, y1 + (y2 - y1) * s / 12); await sleep(16); }
    await p.mouse.up(); await sleep(250);
  } else if (k === 'set') { i++; const j = v.indexOf('='), id = v.slice(0, j), num = v.slice(j + 1);
    await p.evaluate(([id, num]) => { const e = document.getElementById(id); if (!e) throw new Error('немає #' + id);
      e.value = num; for (const ev of ['input', 'change']) e.dispatchEvent(new Event(ev, { bubbles: true })); }, [id, num]);
    await sleep(250);
  } else if (k === 'shot') { i++; const [file, box] = v.trim().split(/\s+/);
    const clip = box ? (([x, y, width, height]) => ({ x, y, width, height }))(box.split(',').map(Number)) : undefined;
    await p.screenshot({ path: file, clip }); console.log('знімок:', file);
  } else if (k === 'wait') { i++; await sleep(+v); }
}
await b.close(); process.exit(errors ? 3 : 0);
