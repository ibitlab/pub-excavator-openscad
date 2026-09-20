// Параметри Customizer з тексту .scad (те саме, що read_schema() у tools/viewer.py):
// групи /* [Назва] */, присвоєння `name = value; // [min:step:max] | [a, b, c] | коментар`, рядки-коментарі над параметром = опис.
const CLIENT = new Set(['boom_angle', 'stick_angle', 'bucket_angle', 'clamp_to_cylinders', 'ground_below_A']);

export function parseValue(txt) {
  txt = txt.trim();
  if (txt === 'true' || txt === 'false') return txt === 'true';
  if (txt.startsWith('"') && txt.endsWith('"')) return txt.slice(1, -1);
  if (txt.startsWith('[')) return txt.slice(1, -1).split(',').filter(x => x.trim()).map(parseValue);
  const n = Number(txt); return txt !== '' && Number.isFinite(n) ? n : null;
}

export function readSchema(source) {
  const groups = []; let cur = null, desc = [];
  for (const line of source.split('\n')) {
    const s = line.trim();
    if (s.startsWith('module __end_of_params')) break;
    let m = s.match(/^\/\*\s*\[(.+?)\]\s*\*\//);
    if (m) { cur = { name: m[1], params: [] }; groups.push(cur); desc = []; continue; }
    if (s.startsWith('//')) { desc.push(s.replace(/^\/+/, '').trim()); continue; }
    m = s.match(/^(\$?\w+)\s*=\s*(.+?);\s*(?:\/\/\s*(.*))?$/);
    if (m && cur) {
      const value = parseValue(m[2]), tail = (m[3] || '').trim(), p = { name: m[1], value, desc: desc.join(' ') }; desc = [];
      const r = tail.match(/^\[(.*)\]$/);
      if (r) {
        if (r[1].includes(':')) { const n = r[1].split(':').map(Number); p.min = n[0]; p.max = n[n.length - 1]; p.step = n.length === 3 ? n[1] : 1; }
        else p.options = r[1].split(',').map(x => x.trim());
      } else if (tail) p.desc = (p.desc + ' ' + tail).trim();
      if (value !== null && !(Array.isArray(value) && value.some(v => v === null))) cur.params.push(p);
    } else if (!s) desc = [];
  }
  for (const g of groups) for (const p of g.params) p.client = CLIENT.has(p.name) || p.name.startsWith('show_');
  return groups.filter(g => !g.name.startsWith('0.'));
}

// Значення зі сторінки → літерал OpenSCAD; тип береться зі схеми (довільний текст у -D не потрапляє)
export function scadLiteral(p, v) {
  const d = p.value;
  if (typeof d === 'boolean') return v ? 'true' : 'false';
  if (typeof d === 'number') { if (!Number.isFinite(+v)) throw new Error(p.name); return String(+v); }
  if (Array.isArray(d)) { if (!Array.isArray(v) || v.length !== d.length || v.some(x => !Number.isFinite(+x))) throw new Error(p.name); return '[' + v.map(Number).join(',') + ']'; }
  if (typeof d === 'string') { if (!(p.options || [d]).includes(v)) throw new Error(p.name); return JSON.stringify(v); }
  throw new Error(p.name);
}
