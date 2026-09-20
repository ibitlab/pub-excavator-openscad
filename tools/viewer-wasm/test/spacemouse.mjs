// Перевірка навігації SpaceMouse БЕЗ заліза: підставні Gamepad API і WebHID у headless Chrome.
// Запуск: спершу підніміть сторінку (npm run preview або tools/viewer.sh), потім
//   npm run test:spacemouse -- http://localhost:8767/            (CHROME=/шлях/до/chrome, якщо Chrome не в типовому місці)
// puppeteer-core свідомо НЕ в package.json (тягне залежність із зауваженням npm audit): перед запуском — npm i --no-save puppeteer-core
let puppeteer; try { puppeteer = (await import('puppeteer-core')).default; } catch (e) { console.error('Спершу: npm i --no-save puppeteer-core'); process.exit(2); }
import { existsSync } from 'node:fs';
const url = process.argv[2] || 'http://localhost:8767/';
const CHROME = process.env.CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(existsSync);
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--window-size=1300,800'] });
const p = await b.newPage(); await p.setViewport({ width: 1300, height: 800 });
p.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 300)));
p.on('console', m => { if (m.type() === 'error') console.log('[console.error]', m.text().slice(0, 200)); });
await p.evaluateOnNewDocument(() => {
  window.__PAD__ = null;
  navigator.getGamepads = () => window.__PAD__ ? [{ id: '3Dconnexion SpaceMouse Compact (Vendor: 256f Product: c635)', axes: window.__PAD__, buttons: [{ pressed: false }, { pressed: false }] }] : [];
  const listeners = [];
  window.__HIDDEV__ = { productName: 'SpaceMouse Wireless (mock)', vendorId: 0x256f, opened: false, async open() { this.opened = true; }, addEventListener: (t, f) => listeners.push(f) };
  window.__HIDSEND__ = (reportId, vals) => { const d = new DataView(new ArrayBuffer(vals.length * 2)); vals.forEach((v, i) => d.setInt16(i * 2, v, true)); listeners.forEach(f => f({ reportId, data: d })); };
  Object.defineProperty(navigator, 'hid', { value: { getDevices: async () => [], requestDevice: async () => [window.__HIDDEV__], addEventListener() {} }, configurable: true });
});
await p.goto(url, { waitUntil: 'load' }); await p.waitForFunction('window.__READY__ === true', { timeout: 120000 });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const cam = async () => { const c = await p.evaluate(() => window.__CAM__()); const o = c.p.map((v, i) => v - c.t[i]), r = Math.hypot(...o);
  return { az: Math.atan2(o[1], o[0]) * 180 / Math.PI, el: 90 - Math.acos(o[2] / r) * 180 / Math.PI, r, t: c.t }; };
const fmt = c => `азимут ${c.az.toFixed(1)}° підйом ${c.el.toFixed(1)}° відстань ${c.r.toFixed(0)} ціль [${c.t.map(v => v.toFixed(0))}]`;
let ok = true; const check = (name, cond, a, b2) => { console.log((cond ? '✓ ' : '✗ ') + name + '\n    ' + fmt(a) + '\n    ' + fmt(b2)); ok = ok && cond; };
// --- Gamepad API
await p.evaluate(() => window.__PAD__ = [0, 0, 0, 0, 0, 0]); await sleep(1200);      // прогрів: перші кадри після побудови сцени повільні
let c0 = await cam();
await p.evaluate(() => window.__PAD__ = [0, 0, 0, 0, 0, 0.8]); await sleep(800); await p.evaluate(() => window.__PAD__ = [0, 0, 0, 0, 0, 0]); await sleep(150);
let c1 = await cam(); check('Gamepad: скрут (Rz+) крутить камеру довкола вертикалі, відстань та підйом ті самі', c1.az - c0.az > 5 && Math.abs(c1.r - c0.r) < 1 && Math.abs(c1.el - c0.el) < 0.5, c0, c1);
console.log('    статус:', await p.$eval('#sm_st', e => e.textContent));
await p.evaluate(() => window.__PAD__ = [0, 0.8, 0, 0, 0, 0]); await sleep(500); await p.evaluate(() => window.__PAD__ = [0, 0, 0, 0, 0, 0]); await sleep(150);
let c2 = await cam(); check('Gamepad: до себе (Y+) наближає', c2.r < c1.r * 0.8, c1, c2);
await p.evaluate(() => window.__PAD__ = [0.8, 0, 0, 0, 0, 0]); await sleep(500); await p.evaluate(() => window.__PAD__ = null); await sleep(150);
let c3 = await cam(); check('Gamepad: праворуч (X+) зсуває ціль, відстань та сама', Math.hypot(c3.t[0] - c2.t[0], c3.t[1] - c2.t[1]) > 50 && Math.abs(c3.r - c2.r) < 1, c2, c3);
// --- WebHID
await p.click('#sm_btn'); await sleep(200);
console.log('    статус:', await p.$eval('#sm_st', e => e.textContent));
for (let i = 0; i < 25; i++) { await p.evaluate(() => window.__HIDSEND__(2, [250, 0, 0])); await sleep(20); }       // звіт 2: оберт Rx+
await p.evaluate(() => window.__HIDSEND__(2, [0, 0, 0])); await sleep(100);
let c4 = await cam(); check('WebHID: нахил до себе (Rx+, звіт 2) піднімає камеру над моделлю', c4.el - c3.el > 5 && Math.abs(c4.r - c3.r) < 1, c3, c4);
for (let i = 0; i < 25; i++) { await p.evaluate(() => window.__HIDSEND__(1, [0, 0, 0, 0, 0, -250])); await sleep(20); } // звіт 1 на 12 байт: зсув + оберт
await p.evaluate(() => window.__HIDSEND__(1, [0, 0, 0, 0, 0, 0])); await sleep(100);
let c5 = await cam(); check('WebHID: 12-байтний звіт 1 (Rz−) крутить у зворотний бік', c5.az - c4.az < -5, c4, c5);
const before = await cam(); await p.evaluate(() => window.__HIDSEND__(3, [1])); await sleep(300); const after = await cam();
check('WebHID: кнопка 1 → «Вписати»', Math.abs(after.r - before.r) > 1 || Math.hypot(...after.t.map((v, i) => v - before.t[i])) > 1, before, after);
if (process.argv[3]) await p.screenshot({ path: process.argv[3] }); await b.close(); console.log(ok ? 'УСІ ПЕРЕВІРКИ ПРОЙДЕНО' : 'Є ПОМИЛКИ'); process.exit(ok ? 0 : 1);
