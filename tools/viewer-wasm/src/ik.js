// Зворотна задача: куди поставити стрілу й рукоять, щоб зуб опинився в заданій точці.
//
// Розв'язок ТОЧНИЙ і без ітерацій. При незмінному куті ковша вектор B→зуб жорсткий
// у системі рукояті, тож шарнір B лежить на перетині двох кіл: радіуса |A→B| навколо
// осі A і радіуса |B→зуб| навколо цілі. Далі кути читаються просто з напрямків.
// `npm test` жене це через пряму задачу туди й назад: похибка зуба — нулі.
//
// Вектори тут — [x, z] у площині машини, як і в блоці //<pose>. Дрібні помічники
// свідомо свої, а не з того блоку: блок мусить лишатися байт-у-байт однаковим у
// двох сторінках, а цей модуль є лише у WASM-версії.
const RAD = Math.PI / 180;
const rot = (v, a) => [v[0] * Math.cos(a * RAD) - v[1] * Math.sin(a * RAD),
                       v[0] * Math.sin(a * RAD) + v[1] * Math.cos(a * RAD)];
const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const ang = v => Math.atan2(v[1], v[0]) / RAD;
const len = v => Math.hypot(v[0], v[1]);
const n180 = a => ((a % 360) + 540) % 360 - 180;
const n360 = a => ((a % 360) + 360) % 360;

function circX(p0, r0, p1, r1, side) {
  const d = len(sub(p1, p0));
  if (d < 1e-9 || d > r0 + r1 || d < Math.abs(r0 - r1)) return null;
  const a = (r0 * r0 - r1 * r1 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, r0 * r0 - a * a));
  const u = [(p1[0] - p0[0]) / d, (p1[1] - p0[1]) / d];
  return [p0[0] + u[0] * a - u[1] * side * h, p0[1] + u[1] * a + u[0] * side * h];
}

/** Радіуси двох ланок при заданому куті ковша: [|A→B|, |B→зуб|]. */
export function links(V, om) {
  const W = add(V.E_s, rot([V.tip, 0], -om));
  return [len(V.B_l), len(W), ang(W)];
}

/**
 * Кути стріли й рукояті, за яких зуб стане в `target` ([x, z], вісь A у нулі).
 * `om` — поточний кут ковша, `cur` — поточні кути (щоб не перекидати лікоть).
 * Недосяжна ціль підтягується до межі кільця досяжності: рука йде за пальцем
 * до краю робочої зони, а не завмирає на місці.
 */
export function armFromTip(V, target, om, cur) {
  const [r1, r2, aW] = links(V, om);
  let t = target;
  const d = len(t), lo = Math.abs(r1 - r2) + 1e-6, hi = r1 + r2 - 1e-6;
  if (d > 1e-9 && (d > hi || d < lo)) {
    const k = Math.min(hi, Math.max(lo, d)) / d;
    t = [t[0] * k, t[1] * k];
  }
  let best = null;
  for (const side of [1, -1]) {
    const B = circX([0, 0], r1, t, r2, side);
    if (!B) continue;
    const boom = n180(ang(B) - ang(V.B_l));
    const stick = n360(ang(sub(t, B)) - aW - ang([-B[0], -B[1]]));
    const cost = Math.abs(n180(boom - cur.boom)) + Math.abs(n180(stick - cur.stick));
    if (!best || cost < best.cost) best = { boom, stick, cost };
  }
  return best;
}
