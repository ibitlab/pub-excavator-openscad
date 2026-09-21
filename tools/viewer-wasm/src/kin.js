// Кінематичне фарбування: кожне ЖОРСТКЕ ТІЛО — одним кольором.
//
// Звичайна палітра каже, З ЧОГО деталь зроблена (труба, пластина, втулка). Це не
// відповідає на питання «що з чим зварене, а де крутиться»: бобишка тяги й сама
// тяга — один зварний вузол, але кольори в них різні, бо різні заготовки.
//
// Тут навпаки: однаковий колір = зварено в одне тіло, межа кольорів = шарнір,
// а палець має власний, не схожий ні на що колір — він не належить жодному тілу,
// він і є те, навколо чого все крутиться.
//
// Ключі — ті самі, що в `bodies` сторінки (вони ж view_parts моделі), тож
// групувати нічого не треба: модель уже розрізана саме по жорстких тілах.
//
// Кольори підібрані не на око: зміряно ΔE в CIE Lab на ОДИНАДЦЯТИ парах, які
// реально дотикаються в шарнірах (колона↔стріла, рукоять↔коромисло, коромисло↔тяга
// і так далі). Мінімум — 30 (нижче 25 око вже плутає).
export const KIN = {
  post:               { key: 'kin.post',   hex: '#6b7a8f' },
  boom:               { key: 'kin.boom',   hex: '#e0a021' },
  v_stick:            { key: 'kin.stick',  hex: '#2f8f6b' },
  bucket:             { key: 'kin.bucket', hex: '#c0533f' },
  v_rocker:           { key: 'kin.rocker', hex: '#7d5ba6' },
  v_link:             { key: 'kin.link',   hex: '#3f7fc0' },
  v_cyl_boom_body:    { key: 'kin.barrel', hex: '#2c3137' },
  v_cyl_stick_body:   { key: 'kin.barrel', hex: '#2c3137' },
  v_cyl_bucket_body:  { key: 'kin.barrel', hex: '#2c3137' },
  v_cyl_boom_rod:     { key: 'kin.rod',    hex: '#dfe5ea' },
  v_cyl_stick_rod:    { key: 'kin.rod',    hex: '#dfe5ea' },
  v_cyl_bucket_rod:   { key: 'kin.rod',    hex: '#dfe5ea' },
};

export const PIN_HEX = '#e6194b';                 // палець — окремо від усіх тіл

/** Легенда режиму: по одному рядку на РІЗНИЙ колір, а не на кожне тіло. */
export function kinLegend() {
  const seen = new Set(), out = [];
  for (const { key, hex } of Object.values(KIN)) {
    if (seen.has(hex)) continue;
    seen.add(hex); out.push({ key, hex });
  }
  out.push({ key: 'kin.pin', hex: PIN_HEX });
  return out;
}
