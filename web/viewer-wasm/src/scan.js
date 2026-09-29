// Скан кімнати з карт глибин: кадри глибини зливаються в одну 3D-модель простору сеансу.
// Кожен кадр прив'язаний до простору позою камери, яку щокадру дає трекінг ARCore (той самий,
// що ставить машину на підлогу), тож окремі точки різних кадрів лягають в одні координати.
//
// Як у KinectFusion: простір — розріджена сітка вокселів (блоки 8×8×8, створюються лише там,
// де була поверхня); у кожному вокселі — усічена знакова відстань до поверхні (TSDF, + перед
// поверхнею, − за нею, ±1 = trunc і далі) і вага. Кожен кадр додається зваженим середнім, тож шум
// окремих кадрів розчиняється; вага обмежена wmax — старе поступово поступається новому. Уздовж
// половини променів простір перед поверхнею «вичищається» (тягне до +1 і знижує вагу): так зникає людина, що пройшла.
// Поверхня — там, де TSDF міняє знак; сітку з неї будує Surface Nets (вершина в кожній комірці зі
// зміною знака, чотирикутник на кожне ребро зі зміною знака). Для об'єму в затіненні те саме поле дає ще
// дві речі на кожну вершину: гладку нормаль (градієнт TSDF — без «ряботиння» граней) і затінення кутів
// (ambient occlusion): крок уздовж нормалі, і якщо поверхня ближча, ніж пройдено, — поруч інша поверхня,
// вершина в заглибині (кут стіни й підлоги, під столом) і темніша. Далі за trunc поле не знає, тож AO — лише на ~15 см.
// Без DOM і без three.js — перевіряється в `npm test`.

const B = 8, B3 = B * B * B, OFF = 512, SPAN = 1024;          // ±512 блоків — ±205 м при вокселі 5 см
const CH = 4;                                                 // шматок для малювання — 4×4×4 блоки (1.6 м): перемальовуються лише змінені
const bkey = (x, y, z) => ((x + OFF) * SPAN + (y + OFF)) * SPAN + (z + OFF);
const vkey = (x, y, z) => ((x + 4096) * 8192 + (y + 4096)) * 8192 + (z + 4096);

export class Scan {
  constructor(o = {}) {
    Object.assign(this, { h: 0.05, trunc: 0.15, wmax: 30, minW: 2, maxBlocks: 20000, near: 0.2, far: 4, carve: 2 }, o);
    this.clear();
  }
  clear() { this.blocks = new Map(); this.dirty = new Set(); this.chunks = new Map(); this.changed = new Set(); this.full = false; this.frames = 0; this.nTris = 0; }
  #block(bx, by, bz, make) {
    const k = bkey(bx, by, bz);
    let b = this.blocks.get(k);
    if (!b && make) {
      if (this.blocks.size >= this.maxBlocks) { this.full = true; return null; }   // пам'ять скану вичерпано — нове не додається
      b = { bx, by, bz, d: new Float32Array(B3).fill(1), w: new Uint8Array(B3), tris: null, kind: null,
            ck: bkey(Math.floor(bx / CH), Math.floor(by / CH), Math.floor(bz / CH)) };
      this.blocks.set(k, b);
      (this.chunks.get(b.ck) || this.chunks.set(b.ck, new Set()).get(b.ck)).add(b);
    }
    return b;
  }
  // TSDF вокселя за глобальними індексами; NaN — ще не бачили (або бачили замало)
  val(x, y, z) {
    const bx = Math.floor(x / B), by = Math.floor(y / B), bz = Math.floor(z / B), b = this.blocks.get(bkey(bx, by, bz));
    if (!b) return NaN;
    const i = ((x - bx * B) * B + (y - by * B)) * B + (z - bz * B);
    return b.w[i] >= this.minW ? b.d[i] : NaN;
  }
  // O — камера, fwd — одиничний напрямок погляду; для кожного променя dirs — напрямок, розтягнутий так,
  // що O + dir·d — точка на глибині d (глибина WebXR — уздовж осі погляду), dep — глибина, 0 — невідомо.
  integrate(O, fwd, dirs, dep) {
    const h = this.h, tr = this.trunc, touched = new Set();
    const put = (px, py, pz, d, make, free) => {
      const x = Math.floor(px / h), y = Math.floor(py / h), z = Math.floor(pz / h);
      const bx = Math.floor(x / B), by = Math.floor(y / B), bz = Math.floor(z / B), b = this.#block(bx, by, bz, make);
      if (!b) return;
      const i = ((x - bx * B) * B + (y - by * B)) * B + (z - bz * B), w = b.w[i];
      if (free && !w) return;                                   // вичищаємо лише вже бачене
      touched.add(b);
      if (free) { b.d[i] = (b.d[i] * w + 1) / (w + 1); b.w[i] = w - 1; return; }   // порожньо: і тягне до +1, і знижує довіру
      const zc = ((x + 0.5) * h - O[0]) * fwd[0] + ((y + 0.5) * h - O[1]) * fwd[1] + ((z + 0.5) * h - O[2]) * fwd[2];
      b.d[i] = (b.d[i] * w + Math.max(-1, Math.min(1, (d - zc) / tr))) / (w + 1);
      if (w < this.wmax) b.w[i] = w + 1;
    };
    for (let i = 0; i < dep.length; i++) {
      const d = dep[i]; if (!(d > this.near && d < this.far)) continue;
      const dx = dirs[i * 3], dy = dirs[i * 3 + 1], dz = dirs[i * 3 + 2], L = Math.hypot(dx, dy, dz);
      const step = 0.7 * h / L;                                 // крок уздовж променя — менший за воксель
      for (let t = d - tr; t <= d + tr; t += step) put(O[0] + dx * t, O[1] + dy * t, O[2] + dz * t, d, true, false);
      if (i % this.carve === 0)                                 // вичищення — лише на частині променів: воно найдорожче
        for (let t = this.near; t < d - tr; t += h / L) put(O[0] + dx * t, O[1] + dy * t, O[2] + dz * t, d, false, true);
    }
    // поверхня блоку залежить від сусідів (ребра й комірки на межі): перебудувати й їх
    for (const b of touched) for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (let k = -1; k <= 1; k++) {
      const n = this.#block(b.bx + i, b.by + j, b.bz + k, false); if (n) this.dirty.add(n);
    }
    this.frames++;
  }
  #tri(px, py, pz) {                                          // TSDF у точці (метри), трилінійно; небачене — порожньо (+1)
    const h = this.h, u = px / h - 0.5, v = py / h - 0.5, w = pz / h - 0.5;
    const x = Math.floor(u), y = Math.floor(v), z = Math.floor(w), fx = u - x, fy = v - y, fz = w - z;
    let s = 0;
    for (let k = 0; k < 8; k++) {
      const a = k & 1, b = (k >> 1) & 1, c = (k >> 2) & 1, d = this.val(x + a, y + b, z + c);
      s += (d === d ? d : 1) * (a ? fx : 1 - fx) * (b ? fy : 1 - fy) * (c ? fz : 1 - fz);
    }
    return s;
  }
  // вершина комірки (кути cx..cx+1): [x, y, z, nx, ny, nz, ao] або null — у комірці поверхні немає
  #cell(cx, cy, cz, cache) {
    const key = vkey(cx, cy, cz);
    if (cache.has(key)) return cache.get(key);
    const v = new Float64Array(8);
    let neg = 0, out = null;
    for (let k = 0; k < 8; k++) {
      v[k] = this.val(cx + (k & 1), cy + ((k >> 1) & 1), cz + ((k >> 2) & 1));
      if (v[k] !== v[k]) { cache.set(key, null); return null; }   // хоч один кут не бачили — поверхні тут не вигадуємо
      if (v[k] < 0) neg++;
    }
    if (neg > 0 && neg < 8) {
      let sx = 0, sy = 0, sz = 0, n = 0;
      for (let k = 0; k < 8; k++) for (const bit of [1, 2, 4]) {
        if (k & bit) continue;
        const k2 = k | bit; if ((v[k] < 0) === (v[k2] < 0)) continue;
        const t = v[k] / (v[k] - v[k2]);                       // де на ребрі TSDF = 0
        sx += (k & 1) + (bit === 1 ? t : 0); sy += ((k >> 1) & 1) + (bit === 2 ? t : 0); sz += ((k >> 2) & 1) + (bit === 4 ? t : 0); n++;
      }
      const h = this.h, x = (cx + 0.5 + sx / n) * h, y = (cy + 0.5 + sy / n) * h, z = (cz + 0.5 + sz / n) * h;   // центр вокселя x — (x + ½)·h
      let nx = this.#tri(x + h, y, z) - this.#tri(x - h, y, z), ny = this.#tri(x, y + h, z) - this.#tri(x, y - h, z), nz = this.#tri(x, y, z + h) - this.#tri(x, y, z - h);
      const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;   // градієнт — від поверхні в порожнечу
      // AO: три кроки до 0.9·trunc (далі поле усічене й нічого не скаже), у кожному — яку частку пройденого
      // «з'їла» сусідня поверхня. Перший, найкоротший крок пропускаємо, а 1.2 см прощаємо: інакше шум глибини
      // в кілька міліметрів темнить і рівну стіну. Біля кута стіни й підлоги темна смуга виходить завширшки ~12 см.
      let occ = 0;
      for (let k = 2; k <= 4; k++) {
        const dd = k * this.trunc * 0.225, sd = this.#tri(x + nx * dd, y + ny * dd, z + nz * dd) * this.trunc;
        occ += Math.max(0, dd - sd - 0.012) / dd / 3;
      }
      out = [x, y, z, nx, ny, nz, Math.max(0.35, 1 - 2.5 * occ)];
    }
    cache.set(key, out);
    return out;
  }
  #mesh(b, cache) {
    const tris = [], nrm = [], ao = [], kind = [], x0 = b.bx * B, y0 = b.by * B, z0 = b.bz * B;
    const AX = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    for (let x = x0; x < x0 + B; x++) for (let y = y0; y < y0 + B; y++) for (let z = z0; z < z0 + B; z++) {
      const v0 = this.val(x, y, z); if (v0 !== v0) continue;
      for (let a = 0; a < 3; a++) {
        const e = AX[a], v1 = this.val(x + e[0], y + e[1], z + e[2]);
        if (v1 !== v1 || (v0 < 0) === (v1 < 0)) continue;
        const u = AX[(a + 1) % 3], w = AX[(a + 2) % 3], q = [];
        for (const [i, j] of [[0, 0], [1, 0], [1, 1], [0, 1]]) {   // чотири комірки навколо ребра
          const p = this.#cell(x - u[0] * i - w[0] * j, y - u[1] * i - w[1] * j, z - u[2] * i - w[2] * j, cache);
          if (!p) break; q.push(p);
        }
        if (q.length < 4) continue;
        let [p0, p1, p2, p3] = q;
        const ax = p2[0] - p0[0], ay = p2[1] - p0[1], az = p2[2] - p0[2], bx = p3[0] - p1[0], by = p3[1] - p1[1], bz = p3[2] - p1[2];
        const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx, ny1 = Math.abs(ny) / (Math.hypot(nx, ny, nz) || 1);
        // лицем — у бік гладких нормалей (у порожнечу): інакше двобічне затінення візьме нормаль навиворіт і грань почорніє
        if (nx * (p0[3] + p1[3] + p2[3] + p3[3]) + ny * (p0[4] + p1[4] + p2[4] + p3[4]) + nz * (p0[5] + p1[5] + p2[5] + p3[5]) < 0) [p1, p3] = [p3, p1];
        for (const p of [p0, p1, p2, p0, p2, p3]) { tris.push(p[0], p[1], p[2]); nrm.push(p[3], p[4], p[5]); ao.push(p[6]); }
        const k = ny1 > 0.9 ? 1 : ny1 < 0.35 ? 0 : 2;            // горизонтальна · стіна · решта — як KIND кімнати
        kind.push(k, k);
      }
    }
    this.nTris += kind.length - (b.kind ? b.kind.length : 0);
    b.tris = Float32Array.from(tris); b.nrm = Float32Array.from(nrm); b.ao = Float32Array.from(ao); b.kind = Uint8Array.from(kind);
    this.changed.add(b.ck);
  }
  // перебудувати поверхню не більше ніж budget змінених блоків; повертає, скільки перебудовано
  remesh(budget = 150) {
    const cache = new Map();
    let n = 0;
    for (const b of this.dirty) { if (n >= budget) break; this.dirty.delete(b); this.#mesh(b, cache); n++; }
    return n;
  }
  // Поверхня блоків bs одним шматком: трикутники по 9 чисел (як частини Room.build), нормалі вершин по 9,
  // затінення кутів по 3 (1 — відкрито, 0.3 — глибока заглибина) і вид кожного трикутника (індекс у KIND)
  #join(bs) {
    bs = bs.filter(b => b.kind && b.kind.length);
    const n = bs.reduce((s, b) => s + b.kind.length, 0);
    const tris = new Float32Array(n * 9), nrm = new Float32Array(n * 9), ao = new Float32Array(n * 3), kind = new Uint8Array(n);
    let k = 0;
    for (const b of bs) { tris.set(b.tris, k * 9); nrm.set(b.nrm, k * 9); ao.set(b.ao, k * 3); kind.set(b.kind, k); k += b.kind.length; }
    return { tris, nrm, ao, kind };
  }
  geometry() { return this.#join([...this.blocks.values()]); }   // уся поверхня
  // шматки, поверхня яких змінилась після попереднього виклику: [{ key, tris, nrm, ao, kind }] (порожні — щоб прибрати)
  takeChunks() {
    const out = [...this.changed].map(key => ({ key, ...this.#join([...this.chunks.get(key)]) }));
    this.changed.clear();
    return out;
  }
  stats() { return { blocks: this.blocks.size, tris: this.nTris, frames: this.frames, full: this.full, pending: this.dirty.size }; }
}
