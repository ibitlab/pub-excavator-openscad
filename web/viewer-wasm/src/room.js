// Кімната для перевірки зіткнень в AR: трикутники площин (plane-detection) і сіток
// (mesh-detection) WebXR у метрах простору сеансу (Y догори) плюс рівномірна сітка
// комірок, щоб на кожну точку машини не перебирати всі трикутники. Без DOM і без
// three.js — перевіряється в `npm test` числами, бо справжній сеанс є лише на телефоні.

export const KIND = ['wall', 'top', 'obj'];                  // стіна · горизонтальна поверхня над підлогою · предмет

// m — матриця пози з XRRigidTransform.matrix (16 чисел, по стовпцях)
const xf = (m, x, y, z, out, o) => {
  out[o] = m[0] * x + m[4] * y + m[8] * z + m[12];
  out[o + 1] = m[1] * x + m[5] * y + m[9] * z + m[13];
  out[o + 2] = m[2] * x + m[6] * y + m[10] * z + m[14];
};
// XRPlane.polygon — опукла ламана в просторі площини (y = 0, нормаль — вісь Y): віяло з першої вершини
export function planeTris(poly, m) {
  const n = poly.length, out = new Float32Array(Math.max(0, n - 2) * 9);
  for (let i = 1; i < n - 1; i++)
    for (const [j, p] of [poly[0], poly[i], poly[i + 1]].entries()) xf(m, p.x, p.y || 0, p.z, out, (i - 1) * 9 + j * 3);
  return out;
}
export function meshTris(v, idx, m) {                         // XRMesh.vertices / .indices
  const out = new Float32Array(idx.length * 3);
  for (let i = 0; i < idx.length; i++) { const j = idx[i] * 3; xf(m, v[j], v[j + 1], v[j + 2], out, i * 3); }
  return out;
}

const OFF = 1024, SPAN = 2048;                                // ±1024 комірок — ±256 м при комірці 0.25 м
const key = (x, y, z) => ((x + OFF) * SPAN + (y + OFF)) * SPAN + (z + OFF);

export class Room {
  constructor(cell = 0.25) { this.h = cell; this.clear(); }
  clear() { this.n = 0; this.T = new Float32Array(0); this.kind = new Uint8Array(0); this.flat = new Float32Array(0); this.cells = new Map(); this.stamp = new Uint32Array(0); this.q = 0; }
  // parts: [{ tris: Float32Array (по 9 чисел на трикутник), kind: індекс у KIND }]
  build(parts) {
    const n = parts.reduce((s, p) => s + p.tris.length / 9, 0), h = this.h;
    const T = new Float32Array(n * 9), kind = new Uint8Array(n), flat = new Float32Array(n).fill(NaN), cells = new Map();
    let k = 0;
    for (const p of parts) { T.set(p.tris, k * 9); kind.fill(p.kind, k, k + p.tris.length / 9); k += p.tris.length / 9; }
    for (let i = 0; i < n; i++) {
      const o = i * 9;
      const ux = T[o + 3] - T[o], uy = T[o + 4] - T[o + 1], uz = T[o + 5] - T[o + 2];
      const vx = T[o + 6] - T[o], vy = T[o + 7] - T[o + 1], vz = T[o + 8] - T[o + 2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, nl = Math.hypot(nx, ny, nz);
      if (nl > 0 && Math.abs(ny) / nl > 0.9) flat[i] = (T[o + 1] + T[o + 4] + T[o + 7]) / 3;   // горизонтальний: пам'ятаємо висоту
      const lo = [0, 1, 2].map(a => Math.floor(Math.min(T[o + a], T[o + 3 + a], T[o + 6 + a]) / h));
      const hi = [0, 1, 2].map(a => Math.floor(Math.max(T[o + a], T[o + 3 + a], T[o + 6 + a]) / h));
      for (let x = lo[0]; x <= hi[0]; x++) for (let y = lo[1]; y <= hi[1]; y++) for (let z = lo[2]; z <= hi[2]; z++) {
        const c = key(x, y, z), l = cells.get(c); if (l) l.push(i); else cells.set(c, [i]);
      }
    }
    Object.assign(this, { n, T, kind, flat, cells, stamp: new Uint32Array(n), q: 0 });
  }
  // p — точка тіла машини, a — опорна точка того самого тіла (його шарнір, стоїть у вільному просторі).
  // Зіткнення: відрізок a→p перетинає трикутник (p уже за поверхнею) або p ближче до нього за margin.
  // Підлога під машиною (горизонтальні трикутники на висоті floorY) не рахується: ківш і має копати нижче неї.
  // Повертає індекс у KIND або −1.
  hit(a, p, floorY, margin = 0.03, floorTol = 0.06) {
    if (!this.n) return -1;
    if (++this.q >= 0xffffffff) { this.stamp.fill(0); this.q = 1; }
    const h = this.h, q = this.q, found = { k: -1 };
    const test = c => {
      const l = this.cells.get(c); if (!l) return false;
      for (const i of l) {
        if (this.stamp[i] === q) continue; this.stamp[i] = q;
        const f = this.flat[i]; if (f === f && Math.abs(f - floorY) < floorTol) continue;   // f === f — не NaN
        if (this.#cross(i, a, p) || this.#near(i, p, margin)) { found.k = this.kind[i]; return true; }
      }
      return false;
    };
    // комірки вздовж відрізка — 3D DDA (Amanatides–Woo): жодна зачеплена кутом комірка не випадає
    const cell = a.map(v => Math.floor(v / h)), d = [0, 1, 2].map(i => p[i] - a[i]);
    const step = d.map(Math.sign), tMax = [0, 0, 0], tDel = [0, 0, 0];
    for (let i = 0; i < 3; i++) {
      tDel[i] = d[i] ? h / Math.abs(d[i]) : Infinity;
      tMax[i] = d[i] ? ((cell[i] + (step[i] > 0 ? 1 : 0)) * h - a[i]) / d[i] : Infinity;
    }
    if (test(key(...cell))) return found.k;
    for (let guard = 0; guard < 4096; guard++) {
      const i = tMax[0] < tMax[1] ? (tMax[0] < tMax[2] ? 0 : 2) : (tMax[1] < tMax[2] ? 1 : 2);
      if (tMax[i] > 1) break;
      cell[i] += step[i]; tMax[i] += tDel[i];
      if (test(key(...cell))) return found.k;
    }
    // комірки навколо самої точки — для перевірки «ближче за margin»
    const lo = p.map(v => Math.floor((v - margin) / h)), hi = p.map(v => Math.floor((v + margin) / h));
    for (let x = lo[0]; x <= hi[0]; x++) for (let y = lo[1]; y <= hi[1]; y++) for (let z = lo[2]; z <= hi[2]; z++)
      if (test(key(x, y, z))) return found.k;
    return -1;
  }
  #cross(i, a, p) {                                           // Меллер–Трумбор, t у [0, 1]
    const T = this.T, o = i * 9;
    const e1x = T[o + 3] - T[o], e1y = T[o + 4] - T[o + 1], e1z = T[o + 5] - T[o + 2];
    const e2x = T[o + 6] - T[o], e2y = T[o + 7] - T[o + 1], e2z = T[o + 8] - T[o + 2];
    const dx = p[0] - a[0], dy = p[1] - a[1], dz = p[2] - a[2];
    const px = dy * e2z - dz * e2y, py = dz * e2x - dx * e2z, pz = dx * e2y - dy * e2x;
    const det = e1x * px + e1y * py + e1z * pz; if (Math.abs(det) < 1e-12) return false;
    const inv = 1 / det, sx = a[0] - T[o], sy = a[1] - T[o + 1], sz = a[2] - T[o + 2];
    const u = (sx * px + sy * py + sz * pz) * inv; if (u < 0 || u > 1) return false;
    const qx = sy * e1z - sz * e1y, qy = sz * e1x - sx * e1z, qz = sx * e1y - sy * e1x;
    const v = (dx * qx + dy * qy + dz * qz) * inv; if (v < 0 || u + v > 1) return false;
    const t = (e2x * qx + e2y * qy + e2z * qz) * inv;
    return t >= 0 && t <= 1;
  }
  #near(i, p, margin) {                                       // до площини трикутника ближче за margin і проєкція всередині
    const T = this.T, o = i * 9;
    const e1x = T[o + 3] - T[o], e1y = T[o + 4] - T[o + 1], e1z = T[o + 5] - T[o + 2];
    const e2x = T[o + 6] - T[o], e2y = T[o + 7] - T[o + 1], e2z = T[o + 8] - T[o + 2];
    let nx = e1y * e2z - e1z * e2y, ny = e1z * e2x - e1x * e2z, nz = e1x * e2y - e1y * e2x;
    const nl = Math.hypot(nx, ny, nz); if (!nl) return false; nx /= nl; ny /= nl; nz /= nl;
    const wx = p[0] - T[o], wy = p[1] - T[o + 1], wz = p[2] - T[o + 2], dist = wx * nx + wy * ny + wz * nz;
    if (Math.abs(dist) > margin) return false;
    const rx = wx - dist * nx, ry = wy - dist * ny, rz = wz - dist * nz;   // барицентричні координати проєкції
    const d00 = e1x * e1x + e1y * e1y + e1z * e1z, d01 = e1x * e2x + e1y * e2y + e1z * e2z, d11 = e2x * e2x + e2y * e2y + e2z * e2z;
    const d20 = rx * e1x + ry * e1y + rz * e1z, d21 = rx * e2x + ry * e2y + rz * e2z, den = d00 * d11 - d01 * d01;
    if (!den) return false;
    const v = (d11 * d20 - d01 * d21) / den, w = (d00 * d21 - d01 * d20) / den;
    return v >= 0 && w >= 0 && v + w <= 1;
  }
}
