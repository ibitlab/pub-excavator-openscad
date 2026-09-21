// Знімає зі сторінки поточний ракурс (JSON) і чисту канву — щоб порівняти з рендером OpenSCAD.
// Це перевірка перерахунку камери: сторінка має 32° по вертикалі, OpenSCAD 22.5°, і views.py
// відсуває око на tan(16°)/tan(11.25°). Перевіряти треба саме так — числом, а не оком.
//
//   python3 tools/viewer.py --port 8791 &
//   node tools/media/view_roundtrip.mjs http://127.0.0.1:8791/ /tmp/rt
//   tools/views.py check круговий-тест --file /tmp/rt.json --page /tmp/rt.png
//
// puppeteer-core свідомо не в package.json: один раз npm i --no-save --prefix tools/media puppeteer-core
import { writeFileSync } from 'node:fs';
let puppeteer; try { puppeteer = (await import('puppeteer-core')).default; }
catch { console.error('Спершу: npm i --no-save --prefix tools/media puppeteer-core'); process.exit(2); }

const url = process.argv[2] || 'http://127.0.0.1:8791/';
const out = process.argv[3] || '/tmp/rt';
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--no-sandbox'] });
const p = await b.newPage();
await p.setViewport({ width: 1400, height: 1000 });
await p.goto(url, { waitUntil: 'networkidle2' });
await p.waitForFunction('window.__READY__ === true', { timeout: 120000 });
// Земля й робоча зона — площини на весь кадр: силует із ними порівнювати безглуздо.
await p.evaluate(() => {
  for (const inp of document.querySelectorAll('#toggles input[type=checkbox]')) {
    const lab = inp.parentElement.textContent.toLowerCase();
    if ((lab.includes('земл') || lab.includes('зона')) && inp.checked) inp.click();
  }
});
// Панель і написи поверх канви теж потрапляють у знімок елемента — ховаємо, як --clean.
await p.addStyleTag({ content: '#side,#hud,#help{display:none!important}' });
await p.evaluate(() => window.dispatchEvent(new Event('resize')));
await new Promise(r => setTimeout(r, 1500));

const v = await p.evaluate(() => window.__VIEW__('круговий-тест'));
writeFileSync(`${out}.json`, JSON.stringify({ views: [v] }, null, 2));
const c = await p.$('#c'); const box = await c.boundingBox();
await c.screenshot({ path: `${out}.png` });
console.log(`  ${out}.json + ${out}.png · канва ${Math.round(box.width)}x${Math.round(box.height)} · ${v.camera.projection}`);
await b.close();
