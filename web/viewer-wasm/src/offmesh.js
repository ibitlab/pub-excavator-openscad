// OFF з кольорами граней (експорт OpenSCAD) → деталі. Модель у режимі part="view_all" кладе i-ту деталь зі зсувом
// i·spacing уздовж Y — тут сітка розрізається назад за координатою Y, а грані групуються за кольором.
export function splitOff(text, names, spacing) {
  const lines = text.split('\n'); let i = 0;
  const next = () => { while (i < lines.length) { const l = lines[i++].trim(); if (l && l[0] !== '#') return l; } return null; };
  let head = next(); let counts = head.slice(3).trim().split(/\s+/).filter(Boolean);
  if (counts.length < 2) counts = next().split(/\s+/);
  const nv = +counts[0], nf = +counts[1];
  const vx = new Float32Array(nv * 3), owner = new Int16Array(nv);
  for (let k = 0; k < nv; k++) {
    const a = next().split(/\s+/), y = +a[1], o = Math.max(0, Math.min(names.length - 1, Math.round(y / spacing)));
    vx[3 * k] = +a[0]; vx[3 * k + 1] = y - o * spacing; vx[3 * k + 2] = +a[2]; owner[k] = o;
  }
  const parts = names.map(() => ({ remap: new Map(), pos: [], groups: new Map() }));
  for (let k = 0; k < nf; k++) {
    const a = next().split(/\s+/), n = +a[0], P = parts[owner[+a[1]]];
    const col = a.length >= n + 4 ? `${a[n + 1]},${a[n + 2]},${a[n + 3]}` : '230,200,60';
    let g = P.groups.get(col); if (!g) P.groups.set(col, g = []);
    const loc = j => { const v = +a[1 + j]; let r = P.remap.get(v); if (r === undefined) { r = P.pos.length / 3; P.remap.set(v, r); P.pos.push(vx[3 * v], vx[3 * v + 1], vx[3 * v + 2]); } return r; };
    for (let t = 1; t < n - 1; t++) g.push(loc(0), loc(t), loc(t + 1));
  }
  const out = {}, transfer = [];
  names.forEach((name, k) => {
    const P = parts[k]; if (!P.pos.length) return;
    const pos = new Float32Array(P.pos); transfer.push(pos.buffer);
    out[name] = { pos, groups: [...P.groups].map(([c, idx]) => { const ix = new Uint32Array(idx); transfer.push(ix.buffer); return { color: c.split(',').map(Number), idx: ix }; }) };
  });
  return { parts: out, transfer };
}
