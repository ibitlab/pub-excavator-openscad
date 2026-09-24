// Рендери вузлів для аркушів розкладки (make_sheets.py): кожна деталь вузла —
// своїм кольором, щоб скрипт знайшов її на знімку за відтінком і поставив виноску.
// Модель підключається як бібліотека через parts.scad і НЕ змінюється.
//
//   openscad --preview -o boom.png -D 'node="boom"' -D 'keys=["gusset","cover"]' sheets.scad
//   ... -D 'hi="cover"'          — крок складання: усе сіре, лише hi — помаранчева
//   ... -D 'node="pins"'          — уся машина сіра, пальці — кольорами
//
// Зовнішній color() у прев'ю перекриває внутрішні — саме тому деталі можна
// перефарбувати, не чіпаючи моделі. Відтінки рознесені рівномірно по колу:
// i-та деталь зі списку keys має hue = i·360/len(keys).
include <../parts.scad>

node = "boom";     // вузол: boom, stick, bucket, rocker, link, post, cyl_boom, cyl_stick, cyl_bucket, pins
keys = [];         // ключі деталей (з parts.tsv) у порядку кольорів
hi = "";           // ключ деталі, яку підсвітити (решта з keys — сірі, деталей після неї немає)
upto = -1;         // якщо >= 0: малювати лише keys[0..upto] (крок складання)
GREY = [0.80, 0.80, 0.80];
HI = [1.0, 0.45, 0.05];

function hsv(h, s = 0.85, v = 0.95) =
    let(hh = (h % 360) / 60, i = floor(hh), f = hh - i,
        p = v * (1 - s), q = v * (1 - s * f), t = v * (1 - s * (1 - f)))
    i == 0 ? [v, t, p] : i == 1 ? [q, v, p] : i == 2 ? [p, v, t] :
    i == 3 ? [p, q, v] : i == 4 ? [t, p, v] : [v, p, q];
function key_color(i) = hsv(i * 360 / max(len(keys), 1));
function col_of(i) = hi == "" ? key_color(i) : (keys[i] == hi ? HI : GREY);
function visible(i) = upto < 0 || i <= upto;

// Одна деталь вузла у власній системі вузла (не на столі — у зборці).
module node_part(k) {
    if      (k == "tube_boom_seg1") boom_seg1();
    else if (k == "tube_boom_seg2") boom_seg2();
    else if (k == "tube_stick")     stick_body();
    else if (k == "post_plate")     for (s = [-1, 1]) translate([0, s*((boom_foot_boss_len + 2)/2 + 6), 0]) make_post_plate();
    else if (k == "washer_B")       { $sel = ""; $one = false; washers_B(); }
    // боковини ковша в наборі — два файли (логотип назовні), у моделі — один ключ bk_side
    else if (k == "bk_side_L")      bk_side_one();
    else if (k == "bk_side_R")      mirror([0, 1, 0]) bk_side_one();
    else if (k == "cyl_boom_body")   cyl_part("boom", "body");
    else if (k == "cyl_boom_rod")    cyl_part("boom", "rod");
    else if (k == "cyl_stick_body")  cyl_part("stick", "body");
    else if (k == "cyl_stick_rod")   cyl_part("stick", "rod");
    else if (k == "cyl_bucket_body") cyl_part("bucket", "body");
    else if (k == "cyl_bucket_rod")  cyl_part("bucket", "rod");
    else { $sel = k; $one = false; part_by_name(node_of(k)); }
}
// Три циліндри поруч (уздовж Y), кожен трохи висунутий, щоб шток було видно.
// Шток стоїть так само, як у hyd_cylinder(): вушко на відстані L від бази,
// видима довжина штока — до самої гільзи.
function cyl_dy(w) = w == "boom" ? 260 : w == "stick" ? 0 : -260;
module cyl_part(w, which) {
    bore   = w == "boom" ? boom_cyl_bore   : w == "stick" ? stick_cyl_bore   : bucket_cyl_bore;
    rod    = w == "boom" ? boom_cyl_rod    : w == "stick" ? stick_cyl_rod    : bucket_cyl_rod;
    closed = w == "boom" ? boom_cyl_closed : w == "stick" ? stick_cyl_closed : bucket_cyl_closed;
    stroke = w == "boom" ? boom_cyl_stroke : w == "stick" ? stick_cyl_stroke : bucket_cyl_stroke;
    pin    = w == "boom" ? boom_cyl_pin    : w == "stick" ? stick_cyl_pin    : bucket_cyl_pin;
    wall   = w == "boom" ? 6.5 : 5;
    L = closed + 0.3 * stroke;
    body_L = closed - 2*45 - 30;
    translate([0, cyl_dy(w), 0])
        if (which == "body") hyd_cyl_part("body", bore, rod, closed, stroke, pin, wall);
        else translate([L, 0, 0]) hyd_cyl_part("rod", bore, rod, closed, stroke, pin, wall, rod_vis = L - 2*45 - body_L + 1);
}
// У якому вузлі моделі живе деталь (для $sel). Коромисло і тяга — у власних системах (v_*).
function node_of(k) =
    node == "rocker" ? "v_rocker" : node == "link" ? "v_link" : node;

// Пальці: уся машина сірим, кожен палець — у своєму кольорі, трохи товщий за модельний,
// щоб перекрити сірий палець моделі. Положення — ті самі функції pt_*(), що й у assembly().
function pin_at(k) =
    let(th = th_eff, psi = psi_eff, om = om_eff)
    k == "pin_A" ? [[0, 0, 0],            pin_A,          boom_foot_boss_len + 2 + 40] :
    k == "pin_C" ? [p3(C_w),              boom_cyl_pin,   boom_foot_boss_len + 2 + 40] :
    k == "pin_B" ? [p3(pt_B(th)),         pin_B,          boom_tube_w + 2*plate_clevis + 24] :
    k == "pin_D" ? [p3(pt_D(th)),         boom_cyl_pin,   clevis_gap_30 + 2*plate_clevis + 20] :
    k == "pin_E" ? [p3(pt_E(th, psi)),    pin_E,          pin_E_len] :
    k == "pin_F" ? [p3(pt_F(th)),         stick_cyl_pin,  clevis_gap_25 + 2*plate_clevis + 20] :
    k == "pin_G" ? [p3(pt_G(th, psi)),    stick_cyl_pin,  stick_pack_w + 20] :
    k == "pin_H" ? [p3(pt_H(th, psi)),    bucket_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20] :
    k == "pin_J" ? [p3(pt_J(th, psi, om)), pin_JQ,        pin_JQ_len] :
    k == "pin_Q" ? [p3(pt_Q(th, psi, om)), pin_JQ,        pin_JQ_len] :
    k == "pin_R" ? [p3(pt_R(th, psi)),    pin_R,          link_w_in + 20] :
    k == "washer_B" ? [p3(pt_B(th)),      bush_od_main + 10, boom_tube_w + 2] : undef;

// fat = true — палець потовщений і подовжений, щоб його було видно на рендері всієї
// машини (на загальному плані Ø30 — це дві крапки). У крупному плані шарніра — справжній.
fat = false;
module machine_pin(k) {
    q = pin_at(k);
    if (!is_undef(q)) translate(q[0]) rotate([90, 0, 0])
        cylinder(d = q[1] + (fat ? 24 : 6), h = q[2] + (fat ? 60 : 4), center = true, $fn = 48);
}
// Координати шарнірів у світовій системі — для крупних планів кроків (make_sheets.py читає echo)
if (node == "pins") echo(PINPOS = [for (k = keys) [k, pin_at(k)[0]]]);

// Для node="pins" запускати з -D show_ground=false -D show_envelope=false:
// змінні моделі читаються з її власної області, з цього файлу їх не перекрити.
if (node == "pins") color(GREY) assembly();
if (node == "post") color(GREY) { machine_pin("pin_A"); machine_pin("pin_C"); }   // пальці лише як контекст
for (i = [0 : len(keys) - 1]) if (visible(i)) color(col_of(i))
    if (node == "pins") machine_pin(keys[i]); else node_part(keys[i]);

// Логотип — наліпка моделі (brand_marks) на тих самих деталях і в тих самих системах, що
// node_part(). Малюється ПОЗА color() деталі: зовнішній колір перефарбував би його в
// колір деталі, і знак зник би. Чорне/біле (S ≈ 0) у маски виносок не потрапляє.
module node_brand(k) {
    if      (k == "tube_boom_seg1") rotate([0, -boom_alpha1, 0]) brand_decal("boom_seg1");
    else if (k == "tube_stick")     brand_decal("stick");
    else if (k == "post_plate")     for (s = [-1, 1]) translate([0, s*((boom_foot_boss_len + 2)/2 + 6), 0]) brand_decal("post_plate");
    else if (k == "bk_side_L")      brand_decal("bk_side", 1);
    else if (k == "bk_side_R")      brand_decal("bk_side", -1);
}
if (node != "pins") for (i = [0 : len(keys) - 1]) if (visible(i)) node_brand(keys[i]);
