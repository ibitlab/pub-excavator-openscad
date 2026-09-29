// Зліпок кімнати: площини, які браузер (ARCore) перестав віддавати, не зникають одразу.
// ARCore зливає сусідні площини в одну або губить площину, коли камера відвернулася, —
// для перевірки зіткнень це «стіни немає». Тому зникла площина стає «тінню» і далі:
//  • її покрила жива площина (та сама площина, ≥ 60 % тіні всередині живої) — це злиття або
//    повторна поява: тінь прибирається, а жива площина отримує лічильник підтверджень тіні + 1;
//  • ніхто не покрив за GRACE мс — рішення: площина, що вже з'являлася повторно (conf ≥ 2),
//    або велика (≥ 1 м²) і видна довго (≥ 5 с), лишається назавжди (fixed); решта — шум, прибирається;
//  • назавжди — до кінця сеансу або доки карта глибин кілька разів поспіль не покаже, що крізь
//    неї видно далі (vote): тоді площина хибна.
// Без DOM і без three.js — перевіряється в `npm test`.
import { planeTris } from './room.js';

const COS10 = Math.cos(10 * Math.PI / 180);

// m — 16 чисел по стовпцях (XRRigidTransform.matrix), poly — [{x, z}] у просторі площини (y = 0)
function world(m, poly) {
  return poly.map(p => [m[0] * p.x + m[8] * p.z + m[12], m[1] * p.x + m[9] * p.z + m[13], m[2] * p.x + m[10] * p.z + m[14]]);
}
function area(poly) {
  let s = 0;
  for (let i = 0; i < poly.length; i++) { const a = poly[i], b = poly[(i + 1) % poly.length]; s += a.x * b.z - b.x * a.z; }
  return s / 2;                                               // зі знаком: напрямок обходу потрібен для «всередині»
}
// точки тіні для перевірок: центр і вершини, підтягнуті на 20 % до центру (краї площини ARCore — найменш певні)
function samples(m, poly) {
  const W = world(m, poly), c = [0, 1, 2].map(k => W.reduce((s, p) => s + p[k], 0) / W.length);
  return [c, ...W.map(p => p.map((v, k) => c[k] + 0.8 * (v - c[k])))];
}
// частка точок pts, що лежать у площині L (±8 см) і всередині її опуклого многокутника (з запасом 10 см)
function cover(g, L) {
  const m = L.m;
  if (Math.abs(g.m[4] * m[4] + g.m[5] * m[5] + g.m[6] * m[6]) < COS10) return 0;
  const s = Math.sign(area(L.poly)) || 1, P = L.poly;
  let n = 0;
  for (const p of g.pts) {
    const dx = p[0] - m[12], dy = p[1] - m[13], dz = p[2] - m[14];
    if (Math.abs(dx * m[4] + dy * m[5] + dz * m[6]) > 0.08) continue;
    const x = dx * m[0] + dy * m[1] + dz * m[2], z = dx * m[8] + dy * m[9] + dz * m[10];
    let inside = true;
    for (let i = 0; i < P.length && inside; i++) {
      const a = P[i], b = P[(i + 1) % P.length], ex = b.x - a.x, ez = b.z - a.z, l = Math.hypot(ex, ez);
      if (l && s * (ex * (z - a.z) - ez * (x - a.x)) / l < -0.1) inside = false;
    }
    if (inside) n++;
  }
  return n / g.pts.length;
}

export class Keep {
  constructor(o = {}) {
    Object.assign(this, { grace: 5000, bigArea: 1, bigAge: 5000, max: 200, badMax: 6 }, o);
    this.clear();
  }
  clear() { this.live = new Map(); this.ghosts = []; }
  // live — площини, які браузер віддає зараз: [{ key, kind, m, poly }]; key — будь-що стале (сам XRPlane).
  // Повертає true, якщо набір тіней змінився (треба перемалювати й перебудувати кімнату).
  update(live, now) {
    const seen = new Set();
    let changed = false;
    for (const p of live) {
      let r = this.live.get(p.key);
      if (!r) { r = { conf: 1, t0: now }; this.live.set(p.key, r); }
      Object.assign(r, { kind: p.kind, m: p.m, poly: p.poly });
      seen.add(p.key);
    }
    for (const [k, r] of this.live) if (!seen.has(k)) {
      this.live.delete(k);
      this.ghosts.push({ kind: r.kind, m: r.m, poly: r.poly, pts: samples(r.m, r.poly), tris: planeTris(r.poly, r.m),
                         conf: r.conf, age: now - r.t0, area: Math.abs(area(r.poly)), lost: now, fixed: false, bad: 0 });
      changed = true;
    }
    for (let i = this.ghosts.length - 1; i >= 0; i--) {
      const g = this.ghosts[i];
      let by = null;
      for (const r of this.live.values()) if (cover(g, r) >= 0.6) { by = r; break; }
      if (by) { by.conf = Math.max(by.conf, g.conf + 1); this.ghosts.splice(i, 1); changed = true; continue; }
      if (!g.fixed && now - g.lost > this.grace) {
        if (g.conf >= 2 || (g.area >= this.bigArea && g.age >= this.bigAge)) g.fixed = true;
        else this.ghosts.splice(i, 1);
        changed = true;
      }
    }
    if (this.ghosts.length > this.max) { this.ghosts.splice(0, this.ghosts.length - this.max); changed = true; }
    return changed;
  }
  // Карта глибин щодо тіні g: through — крізь неї видно далі (true), бачимо саму поверхню (false).
  // badMax голосів «крізь» поспіль — площина хибна, прибирається. Повертає true, якщо прибрано.
  vote(g, through) {
    g.bad = through ? g.bad + 1 : 0;
    if (g.bad < this.badMax) return false;
    const i = this.ghosts.indexOf(g); if (i >= 0) this.ghosts.splice(i, 1);
    return true;
  }
  stats() { const fixed = this.ghosts.filter(g => g.fixed).length; return { live: this.live.size, wait: this.ghosts.length - fixed, fixed }; }
}
