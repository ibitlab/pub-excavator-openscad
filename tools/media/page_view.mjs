// Ставить сторінку в заданий ракурс (views.json або один об'єкт), знімає канву й друкує
// те, що сторінка сама каже про положення зуба. Потрібне, щоб порівнювати рендер не
// «з чимось схожим», а з тим самим видом.
//   node tools/media/page_view.mjs http://127.0.0.1:8791/ view.json out.png
import { readFileSync } from 'node:fs';
let puppeteer; try { puppeteer = (await import('puppeteer-core')).default; }
catch { console.error('Спершу: npm i --no-save --prefix tools/media puppeteer-core'); process.exit(2); }
const [url, viewFile, out] = process.argv.slice(2);
const d = JSON.parse(readFileSync(viewFile, 'utf8'));
const v = d.views ? d.views[0] : d;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--no-sandbox'] });
const p = await b.newPage();
const h = Math.round(1400 / (v.camera.aspect || 1.4));
await p.setViewport({ width: 1400, height: h });
await p.goto(url, { waitUntil: 'networkidle2' });
await p.waitForFunction('window.__READY__ === true', { timeout: 120000 });
await p.addStyleTag({ content: '#side{display:none!important}' });   // #hud лишаємо: він і є відповідь
await p.evaluate(() => window.dispatchEvent(new Event('resize')));
await p.evaluate(vv => window.__SETVIEW__(vv), v);
await new Promise(r => setTimeout(r, 1200));
const hud = await p.evaluate(() => document.getElementById('hud')?.innerText || '(немає)');
console.log('СТОРІНКА КАЖЕ:\n' + hud.split('\n').map(s => '  ' + s).join('\n'));
await (await p.$('#c')).screenshot({ path: out });
console.log('  ' + out);
await b.close();
