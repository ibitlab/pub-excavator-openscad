// Веб-воркер: OpenSCAD-WASM (пакет openscad-wasm, рушій Manifold). Один запуск part="view_all" → OFF з кольорами →
// деталі у власних системах координат + echo(VIEW = …) з точками шарнірів. Кожна побудова — свіжий екземпляр (callMain одноразовий).
import { createOpenSCAD } from 'openscad-wasm';
import { splitOff } from './offmesh.js';

self.onmessage = async ({ data: { id, source, defs } }) => {
  const t0 = performance.now(), err = [];
  try {
    const w = await createOpenSCAD({ noInitialRun: true, print: s => err.push(s), printErr: s => err.push(s) });
    const os = w.getInstance();
    os.FS.writeFile('/model.scad', source);
    const args = ['/model.scad', '-o', '/out.off', '--backend=manifold', '-D', 'part="view_all"'];
    for (const d of defs) args.push('-D', d);
    let rc; try { rc = os.callMain(args); } catch (e) { rc = String(e); }
    let view = null; const log = [];
    for (const raw of err) {
      const line = raw.trim(), m = line.match(/^ECHO: VIEW = (.*)$/);
      if (m) view = Object.fromEntries(JSON.parse(m[1].replace(/\b(undef|nan|-?inf)\b/g, 'null')));
      else if (line.startsWith('ECHO: "') && (line.includes('!!!') || line.includes('==='))) log.push(line.slice(7, -1));
      else if (/^(WARNING|ERROR)/.test(line)) log.push(line);
    }
    let off = null; try { off = os.FS.readFile('/out.off', { encoding: 'utf8' }); } catch (e) { /* немає файлу — геометрія порожня або помилка */ }
    if (!off || !view) { self.postMessage({ id, error: `OpenSCAD завершився з кодом ${rc}` + (log.length ? ': ' + log.slice(-3).join(' · ') : ''), log }); return; }
    const { parts, transfer } = splitOff(off, view.parts, view.spacing);
    self.postMessage({ id, view, parts, log, ms: Math.round(performance.now() - t0) }, transfer);
  } catch (e) {
    self.postMessage({ id, error: String(e && e.message || e), log: err.slice(-5) });
  }
};
