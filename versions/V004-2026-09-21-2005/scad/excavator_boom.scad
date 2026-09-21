// =============================================================================
//  Параметрична модель робочого обладнання міні-екскаватора: стріла + рукоять
//  + важільна система ковша + ківш (зварний, 300 мм).
//
//  Система координат: X — вперед (до ковша), Z — вгору, Y — вбік (вліво).
//  Вісь повороту стріли A = початок координат. Довжини — мм, кути — градуси.
//
//  Первинні параметри — кути розкриття кожного плеча. Діапазони кутів
//  ОБЧИСЛЮЮТЬСЯ з довжин закуплених циліндрів (зведена/розкрита) — див. echo().
//
//  Перевірка кінематики: tools/kinematics.py (та сама геометрія, незалежний код).
//  OpenSCAD >= 2021.01 (function literals). Перевірено на 2026.09.
// =============================================================================

/* [0. Що показувати / експортувати] */
// Деталь для показу або експорту STL (tools/build_version.sh експортує всі)
part = "assembly"; // [assembly, flat, tubeface, boom, boom_tubes, boom_gussets, boom_bracket_D, boom_bracket_F, boom_foot_boss, boom_fork_B, stick, stick_tube, stick_cheeks, stick_bracket_H, stick_tip, rocker, link, bucket, bucket_sides, bucket_shell, bucket_top, bucket_edge, bucket_ears, bucket_wear, post, overlap, collide, view_all]
// Для part="overlap": показати перетин двох вузлів (має бути порожньо). Для part="collide": перетин двох РУХОМИХ
// вузлів у світовій системі при заданих кутах (m_boom, m_stick, m_bucket, m_rocker, m_link, m_post, циліндри m_bmcyl, m_scyl, m_bcyl) — tools/check_motion.sh
ov_a = "boom_tubes";
ov_b = "boom_gussets";
// Для part="flat": ключ окремої пластини (плоский контур для DXF/ескізу) — див. flat_parts нижче
flat_name = "gusset";
// Для part="tubeface": труба (boom_seg1, boom_seg2, stick) і її стінка (top, bottom, left, right) — розгортка для ескізів
tube_name = "boom_seg1";
tube_face = "top";

/* [1. Кути (первинні параметри)] */
// Кут хорди стріли (вісь A → вісь B) до горизонту, ° (+ вгору). Обмежується циліндром стріли.
boom_angle = 15;        // [-40:1:75]
// Внутрішній кут стріла–рукоять у шарнірі B (між B→A і B→E), °. ~55° складено … ~158° розкрито.
stick_angle = 100;      // [30:1:180]
// Кут ковша відносно осі рукояті, °. 0 = вісь ковша продовжує рукоять; + = підкручування (закривання).
bucket_angle = 60;      // [-60:1:160]
// Обмежувати кути можливостями циліндрів (true) чи показувати як задано (false, з попередженням)
clamp_to_cylinders = true;

/* [2. Закуплені гідроциліндри] */
// --- Циліндр стріли ГЦ 63.40.500.700 (ШС-30): міжосьова довжина зведеного, мм
boom_cyl_closed = 700;
boom_cyl_stroke = 500;
boom_cyl_bore   = 63;
boom_cyl_rod    = 40;
boom_cyl_pin    = 30;   // отвір сферичного шарніра ШС-30
// --- Циліндр рукояті ГЦ ЦС50.25.400.600 (ШС-25)
stick_cyl_closed = 600;
stick_cyl_stroke = 400;
stick_cyl_bore   = 50;
stick_cyl_rod    = 25;
stick_cyl_pin    = 25;
// --- Циліндр ковша ГЦ ЦС50.25.300.510 (ШС-25). На сайті ≈500 — ВИМІРЯТИ реальний!
bucket_cyl_closed = 510;
bucket_cyl_stroke = 300;
bucket_cyl_bore   = 50;
bucket_cyl_rod    = 25;
bucket_cyl_pin    = 25;

/* [3. Стріла] */
// Довжина 1-го сегмента (вісь A → точка перелому K), мм
boom_L1 = 900;
// Довжина 2-го сегмента (K → вісь B), мм
boom_L2 = 700;
// Кут перелому між сегментами, ° (0 = пряма стріла)
boom_bend = 35;
// Профільна труба стріли: висота (у площині згину), ширина, стінка
boom_tube_h = 120;
boom_tube_w = 80;
boom_tube_t = 5;
// База циліндра стріли C на поворотній колоні відносно A: [вперед, вгору]
boom_cyl_base = [150, -300];
// Кронштейн D (шток циліндра стріли): відстань від A вздовж осі стріли (ламаної A→K→B; > L1 → на 2-му сегменті)
boom_cyl_sD = 1050;
// Виліт осі D під нижню полицю труби (від осі труби = h/2 + виліт)
boom_cyl_bracket = 60;
// Довжина бобишки осі A (ширша за трубу: сприймає бокові навантаження; дві втулки по краях)
boom_foot_boss_len = 140;
// Виступ труби 1-го сегмента за вісь A назад (щоб вмістити втулку)
boom_foot_ext = 90;
// Виліт вилки стріли за вісь B (нижня кромка торця труби 2-го сегмента не доходить до B на цю величину;
// має бути більший за радіус обертання заднього кута рукояті ≈ 80 мм)
boom_fork_reach = 120;
// Скіс торця труби стріли: верхня полиця зрізана назад ще на стільки (місце для п'яти рукояті при розкритті)
boom_nose_cut = 160;

/* [4. Рукоять] */
// Довжина рукояті: вісь B → вісь ковша E, мм
stick_L = 950;
stick_tube_h = 100;
stick_tube_w = 60;
stick_tube_t = 5;
// База циліндра рукояті F на верхній полиці стріли: відстань від B назад вздовж осі стріли (> L2 → на 1-му сегменті)
stick_cyl_sF = 715;
// Виліт осі F над верхньою полицею стріли (високий кронштейн на вершині перелому: корпус циліндра має пройти над переломом)
stick_cyl_bracket = 98;
// П'ята рукояті G (шток циліндра рукояті): назад від B вздовж осі рукояті / до зовнішнього боку
stick_heel_x = 215;
stick_heel_y = 132;
// Виступ труби рукояті за вісь E вперед (короткий: торець рукояті обертається всередині вух ковша)
stick_tip_ext = 50;
// Фаска кутів торця рукояті біля осі E (труба і накладки) — зменшує радіус, який торець описує довкола E
stick_tip_chamfer = 25;
// Виступ труби рукояті назад за вісь B (малий, щоб задній кут не зачіпав торець труби стріли)
stick_rear_ext = 50;

/* [5. Важільна система ковша] */
// База циліндра ковша H: вперед від B вздовж рукояті / виліт над верхньою полицею
bucket_cyl_sH = 246;
bucket_cyl_bracket = 70;
// Вісь коромисла R: назад від E вздовж рукояті / виліт над верхньою полицею
rocker_rx = 152;
rocker_bracket = 25;
// Довжина коромисла R→J і тяги J→Q
rocker_L = 289;
link_L = 327;
// Вушко ковша Q у системі ковша (початок E, x — до зуба, y — зовнішній бік)
bucket_ear = [27, 121];

/* [5б. Ківш (система ковша: E = 0, x — до вістря зуба, y — зовнішній бік, де вушко Q)] */
// Радіус копання: вісь E → вістря зуба
bucket_tip = 480;
// Зовнішня ширина ковша (по боковинах)
bucket_width = 300;
// Товщини: боковини / обичайка (верх–спинка–п'ята–дно однією смугою) / накладка під вуха
bucket_side_t = 6;
bucket_shell_t = 5;
bucket_top_t = 8;
// Відстань від осі E до зовнішньої поверхні накладки під вуха (= висота вух). Має бути більша за радіус,
// який описує торець рукояті довкола E (≈ 56 мм), + зазор
bucket_top_x = 76;
// Передня кромка верху ("губа") по осі y: при повному підкручуванні під неї підходить нижня полиця рукояті
bucket_lip_y = 16;
// Довжина прямої верхньої полиці (під вухами)
bucket_top_len = 170;
// Перехід верх → спинка: зовнішній радіус і кут
bucket_back_r = 60;
bucket_back_turn = 45;
// Зовнішній радіус п'яти (спинка → дно)
bucket_heel_r = 120;
// Кут між лінією "вістря зуба → E" і дном (більший кут → глибший ківш, менший кут різання)
bucket_floor_angle = 50;
// Ніж (різальна кромка): ширина смуги × товщина. Зносостійка сталь (Hardox 400/450, 65Г, ніж грейдера), НЕ Ст3
bucket_edge_w = 100;
bucket_edge_t = 12;
// Зуби: виліт за ніж, повна довжина, ширина, кількість
bucket_tooth_out = 70;
bucket_tooth_len = 160;
bucket_tooth_w = 40;
bucket_tooth_n = 3;
// Вуха ковша: товщина, радіуси довкола осей E і Q
bucket_ear_t = 12;
bucket_ear_r_E = 40;
bucket_ear_r_Q = 35;
// Зовнішні бобишки вух на осі E (палець E зафіксований у вухах, обертається у втулці рукояті)
bucket_boss_E_od = 60;
bucket_boss_E_len = 10;
// Ребро губи: смуга [ширина, товщина] на ребро під передньою кромкою верху
bucket_lip_rib = [40, 8];
// Смуги зносу на п'яті: [ширина, товщина], кількість
bucket_wear = [40, 6];
bucket_wear_n = 2;

/* [6. Пальці, втулки, пластини] */
pin_A = 30;   // вісь стріли на колоні (шкворінь ГАЗ-53 Ø30)
pin_B = 30;   // стріла–рукоять
pin_E = 30;   // рукоять–ківш (бобишка 66×33, як на A і B)
pin_R = 30;   // вісь коромисла (сила в тязі до 2.3× сили циліндра ковша)
pin_JQ = 25;  // тяга
// Зовнішній діаметр втулок головних шарнірів (труба 66×33 зі складу → OD 66; для 28 мм — OD 45)
bush_od_main = 66;
bush_od_small = 45;
// Товщини пластин: накладки біля втулок / вилки під циліндри / накладки перелому
plate_boss = 10;
plate_clevis = 12;
plate_gusset = 8;
// Щоки п'яти рукояті: 8 мм, щоб пакет рукояті (60 + 2×8 = 76) + 2 шайби по 2 мм = 80 = проміжок вилки стріли
plate_cheek = 8;
// Проміжок вилки під вушко циліндра = ширина вушка + 2 мм (вушко ЦС50 ≈ 25, ЦС63 ≈ 28 — ВИМІРЯТИ).
// Палець затискає внутрішнє кільце ШС (20 / 22 мм) через дистанційні шайби.
clevis_gap_25 = 27;
clevis_gap_30 = 30;
// Бобишки тяг на осях J і Q (приварені зовні до пластин тяг): довжина опори пальця 10 + 25 = 35 мм на бік → тиск < 30 МПа
link_boss_od = 50;
link_boss_len = 25;
// Ширина вушок циліндрів (для зображення)
cyl_eye_w_25 = 25;
cyl_eye_w_30 = 28;

/* [7. Відображення] */
show_boom = true;
show_stick = true;
show_cylinders = true;
show_bucket_linkage = true;
show_bucket = true;
show_post = true;
show_ground = true;
// Показати робочу зону (точки різальної кромки для сітки кутів)
show_envelope = false;
// Висота осі A над землею, мм
ground_below_A = 650;
// Сторона площини землі, мм. 9000 — як у 3D-сторінці; у видах з --viewall велика
// площина зменшує машину, тому для них передають менше (напр. 3000).
// Сторінка малює свою землю сама (buildGround) і цього параметра не бачить.
ground_span = 9000;
$fn = 48;

// =============================================================================
//  ДАЛІ — обчислення. Нижче цієї межі параметрів Customizer немає.
// =============================================================================
module __end_of_params() {}

// ---- 2D-вектори (площина XZ; [x, z]) ----
function rot2(v, a) = [v[0]*cos(a) - v[1]*sin(a), v[0]*sin(a) + v[1]*cos(a)];
function ang2(v) = atan2(v[1], v[0]);
function unit2(v) = v / norm(v);
function cross2(a, b) = a[0]*b[1] - a[1]*b[0];
function p3(p) = [p[0], 0, p[1]];
function clamp(x, lo, hi) = max(lo, min(hi, x));

// ---- Похідні розміри ----
boom_cyl_open   = boom_cyl_closed + boom_cyl_stroke;
stick_cyl_open  = stick_cyl_closed + stick_cyl_stroke;
bucket_cyl_open = bucket_cyl_closed + bucket_cyl_stroke;
boom_cyl_eD  = boom_tube_h/2 + boom_cyl_bracket;      // зміщення D від осі 1-го сегмента вниз
stick_cyl_eF = boom_tube_h/2 + stick_cyl_bracket;     // зміщення F від осі 2-го сегмента вгору
bucket_cyl_eH = stick_tube_h/2 + bucket_cyl_bracket;  // зміщення H від осі рукояті до зовнішнього боку
rocker_ry = stick_tube_h/2 + rocker_bracket;

// ---- Форма стріли: кут 1-го сегмента над хордою і довжина хорди ----
boom_alpha1 = atan2(boom_L2*sin(boom_bend), boom_L1 + boom_L2*cos(boom_bend));
boom_Lb = sqrt(boom_L1*boom_L1 + boom_L2*boom_L2 + 2*boom_L1*boom_L2*cos(boom_bend));
u1_l = [cos(boom_alpha1), sin(boom_alpha1)];                        // напрямок 1-го сегмента у системі стріли (хорда = +X)
u2_l = [cos(boom_alpha1 - boom_bend), sin(boom_alpha1 - boom_bend)];
n1_l = [-u1_l[1], u1_l[0]];  n2_l = [-u2_l[1], u2_l[0]];             // ліві нормалі ("верх")
// Точки у системі стріли (A = 0, хорда вздовж +X)
K_l = boom_L1 * u1_l;
B_l = K_l + boom_L2 * u2_l;
// Точка на осі стріли (ламана A→K→B) на відстані s від A: [точка, напрямок сегмента, "верхня" нормаль]
function boom_axis_pt(s) = s <= boom_L1 ? [s * u1_l, u1_l, n1_l] : [K_l + (s - boom_L1) * u2_l, u2_l, n2_l];
_Dax = boom_axis_pt(boom_cyl_sD);                       // кронштейн D може бути на 1-му або 2-му сегменті
D_org = _Dax[0]; D_u = _Dax[1]; D_n = _Dax[2];
D_l = D_org - boom_cyl_eD * D_n;
_Fax = boom_axis_pt(boom_L1 + boom_L2 - stick_cyl_sF);   // база F: відстань назад від B уздовж ламаної
F_org = _Fax[0]; F_u = _Fax[1]; F_n = _Fax[2];
F_l = F_org + stick_cyl_eF * F_n;
C_w = boom_cyl_base;                                                  // світова (на колоні)
// Точки у системі рукояті (B = 0, вісь B→E вздовж +X, +Y = зовнішній бік)
E_s = [stick_L, 0];
G_s = [-stick_heel_x, stick_heel_y];
H_s = [bucket_cyl_sH, bucket_cyl_eH];
R_s = [stick_L - rocker_rx, rocker_ry];

// ---- Світові точки як функції кутів ----
function pt_K(th) = rot2(K_l, th);
function pt_B(th) = rot2(B_l, th);
function pt_D(th) = rot2(D_l, th);
function pt_F(th) = rot2(F_l, th);
function stick_dir(th, psi) = ang2(-pt_B(th)) + psi;                 // напрямок B→E у світі
function stick_pt(th, psi, p_s) = pt_B(th) + rot2(p_s, stick_dir(th, psi));
function pt_E(th, psi) = stick_pt(th, psi, E_s);
function pt_G(th, psi) = stick_pt(th, psi, G_s);
function pt_H(th, psi) = stick_pt(th, psi, H_s);
function pt_R(th, psi) = stick_pt(th, psi, R_s);
function bucket_dir(th, psi, om) = stick_dir(th, psi) - om;          // напрямок осі ковша E→зуб
function pt_Q(th, psi, om) = pt_E(th, psi) + rot2(bucket_ear, bucket_dir(th, psi, om));
function pt_tip(th, psi, om) = pt_E(th, psi) + rot2([bucket_tip, 0], bucket_dir(th, psi, om));

// Перетин кіл (p0,r0) і (p1,r1); side=+1 — точка ліворуч від напрямку p0→p1
function circ_x(p0, r0, p1, r1, side) =
    let(d = norm(p1 - p0))
    (d < 1e-9 || d > r0 + r1 || d < abs(r0 - r1)) ? undef :
    let(a = (r0*r0 - r1*r1 + d*d) / (2*d), h = sqrt(max(0, r0*r0 - a*a)),
        u = unit2(p1 - p0), n = [-u[1], u[0]])
    p0 + u*a + n*side*h;

// J — шарнір шток/коромисло/тяга: перетин кола (R, rocker_L) і кола (Q, link_L).
// Робоча гілка: "лікоть" R–J–Q відігнутий назовні, тобто J ліворуч від напрямку R→Q (cross(Q−R, J−R) > 0).
function pt_J(th, psi, om) =
    let(R = pt_R(th, psi), Q = pt_Q(th, psi, om)) circ_x(R, rocker_L, Q, link_L, +1);

// ---- Довжини циліндрів як функції кутів ----
function boom_cyl_len(th) = norm(pt_D(th) - C_w);
function stick_cyl_len(th, psi) = norm(pt_G(th, psi) - pt_F(th));
function bucket_cyl_len(th, psi, om) = let(J = pt_J(th, psi, om)) is_undef(J) ? undef : norm(J - pt_H(th, psi));

// ---- Бісекція (монотонна f) ----
function _bis(f, target, lo, hi, flo, n) =
    n == 0 ? (lo + hi)/2 :
    let(mid = (lo + hi)/2, fm = f(mid))
    ((fm - target) * (flo - target) <= 0) ? _bis(f, target, lo, mid, flo, n - 1) : _bis(f, target, mid, hi, fm, n - 1);
function bisect(f, target, lo, hi) =
    let(flo = f(lo), fhi = f(hi)) ((flo - target) * (fhi - target) > 0) ? undef : _bis(f, target, lo, hi, flo, 50);

// ---- Діапазони кутів з довжин циліндрів ----
// Якщо циліндр не може досягти зведеної/розкритої довжини за жодного кута (геометрія кріплень "не лягає"),
// межа береться за екстремумом досяжної довжини і виводиться попередження — змініть положення кріплень.
function _argext(f, lo, hi, want_min, n = 360) =
    let(xs = [for (i = [0 : n]) lo + (hi - lo) * i / n], ys = [for (x = xs) f(x)],
        ext = want_min ? min(ys) : max(ys), idx = search(ext, ys)[0]) [xs[idx], ext];
function _limit(f, target, lo, hi, want_min, what) =
    let(b = bisect(f, target, lo, hi))
    !is_undef(b) ? b :
    let(e = _argext(f, lo, hi, want_min))
    echo(str("!!! ", what, ": циліндр не досягає довжини ", target, " (досяжний екстремум ", round(e[1]), " мм при куті ",
             round(e[0]*10)/10, "°). Межа взята за екстремумом — змініть положення кріплень.")) e[0];
boom_angle_min = _limit(function(t) boom_cyl_len(t), boom_cyl_closed, -90, 120, true,  "стріла, зведений");
boom_angle_max = _limit(function(t) boom_cyl_len(t), boom_cyl_open,   -90, 120, false, "стріла, розкритий");
// Довжина циліндра рукояті не залежить від кута стріли (відносна геометрія) — рахуємо при th=0
stick_angle_max = _limit(function(p) stick_cyl_len(0, p), stick_cyl_closed, 5, 179, true,  "рукоять, зведений");
stick_angle_min = _limit(function(p) stick_cyl_len(0, p), stick_cyl_open,   5, 179, false, "рукоять, розкритий");
// Ківш: L(omega) сканується з кроком, обхід від середини ходу в обидва боки за НЕПЕРЕРВНІСТЮ
// (L має монотонно зростати з omega; розрив/немонотонність = мертва точка або інша гілка механізму).
_om_step = 0.25;
_om_list = [for (o = [-90 : _om_step : 180]) o];
_om_L = [for (o = _om_list) let(L = bucket_cyl_len(0, 120, o)) is_undef(L) ? undef : L];
// Робоча гілка = найдовший відрізок індексів, де L визначена і СТРОГО зростає з omega, і який перекриває [closed, open].
function _pick(best, s, e, L) =
    (s >= 0 && e >= s && L[e] >= bucket_cyl_closed && L[s] <= bucket_cyl_open && (e - s) > (best[1] - best[0])) ? [s, e] : best;
function _best_run(L, i = 0, s = -1, best = [-1, -2]) =
    i >= len(L) ? _pick(best, s, i - 1, L) :
    let(ok = !is_undef(L[i]) && (s < 0 || L[i] > L[i - 1]))
    ok ? _best_run(L, i + 1, s < 0 ? i : s, best)
       : _best_run(L, i + 1, is_undef(L[i]) ? -1 : i, _pick(best, s, i - 1, L));
_run = _best_run(_om_L);
function _first_ge(L, i, e, t) = (i > e) ? undef : (L[i] >= t ? i : _first_ge(L, i + 1, e, t));
function _last_le(L, i, s, t)  = (i < s) ? undef : (L[i] <= t ? i : _last_le(L, i - 1, s, t));
_i_lo = _run[0] < 0 ? undef : _first_ge(_om_L, _run[0], _run[1], bucket_cyl_closed);
_i_hi = _run[0] < 0 ? undef : _last_le(_om_L, _run[1], _run[0], bucket_cyl_open);
// уточнення межі лінійною інтерполяцією до сусіднього зразка тієї ж гілки, якщо він перетинає межу ходу
function _refine(i, dir, target) =
    let(j = i + dir)
    (j < _run[0] || j > _run[1] || is_undef(_om_L[j]) || (dir < 0 ? _om_L[j] >= target : _om_L[j] <= target)) ? _om_list[i] :
    _om_list[i] + (target - _om_L[i]) * (_om_list[j] - _om_list[i]) / (_om_L[j] - _om_L[i]);
bucket_angle_min = is_undef(_i_lo) ? undef : _refine(_i_lo, -1, bucket_cyl_closed);
bucket_angle_max = is_undef(_i_hi) ? undef : _refine(_i_hi, +1, bucket_cyl_open);
if (is_undef(bucket_angle_min) || is_undef(bucket_angle_max))
    echo("!!! КІВШ: важільна система не збирається для жодного кута у межах ходу циліндра — змініть sH/rx/rocker_L/link_L/bucket_ear");
else if (_om_L[_run[0]] > bucket_cyl_closed + 0.5 || _om_L[_run[1]] < bucket_cyl_open - 0.5)
    echo(str("!!! КІВШ: мертва точка важільної системи всередині ходу циліндра (досяжно L=", round(_om_L[_run[0]]), "…",
             round(_om_L[_run[1]]), " з ", bucket_cyl_closed, "…", bucket_cyl_open, ") — циліндр упреться у важелі; змініть геометрію"));

// ---- Робочі кути (з обмеженням) ----
th_eff  = (clamp_to_cylinders && !is_undef(boom_angle_min))   ? clamp(boom_angle,   boom_angle_min,   boom_angle_max)   : boom_angle;
psi_eff = (clamp_to_cylinders && !is_undef(stick_angle_min))  ? clamp(stick_angle,  stick_angle_min,  stick_angle_max)  : stick_angle;
om_eff  = (clamp_to_cylinders && !is_undef(bucket_angle_min)) ? clamp(bucket_angle, bucket_angle_min, bucket_angle_max) : bucket_angle;

L_boom_now   = boom_cyl_len(th_eff);
L_stick_now  = stick_cyl_len(th_eff, psi_eff);
L_bucket_now = bucket_cyl_len(th_eff, psi_eff, om_eff);

// ---- Плечі моментів (для інформації) ----
function moment_arm(joint, rod_end, base) = abs(cross2(rod_end - joint, unit2(rod_end - base)));
arm_boom_now  = moment_arm([0,0], pt_D(th_eff), C_w);
arm_stick_now = moment_arm(pt_B(th_eff), pt_G(th_eff, psi_eff), pt_F(th_eff));

echo(str("=== СТРІЛА: хорда Lb=", round(boom_Lb), " мм, alpha1=", round(boom_alpha1*10)/10, "°, кут стріли ∈ [",
         round(boom_angle_min*10)/10, "°, ", round(boom_angle_max*10)/10, "°] (циліндр ", boom_cyl_closed, "…", boom_cyl_open, ")"));
echo(str("=== РУКОЯТЬ: кут ∈ [", round(stick_angle_min*10)/10, "°, ", round(stick_angle_max*10)/10, "°] (циліндр ",
         stick_cyl_closed, "…", stick_cyl_open, ")"));
echo(str("=== КІВШ: кут ∈ [", bucket_angle_min, "°, ", bucket_angle_max, "°] (циліндр ", bucket_cyl_closed, "…", bucket_cyl_open, ")"));
echo(str("=== ПОТОЧНЕ: стріла ", th_eff, "° → L=", round(L_boom_now), " (плече ", round(arm_boom_now), " мм); рукоять ", psi_eff,
         "° → L=", round(L_stick_now), " (плече ", round(arm_stick_now), " мм); ківш ", om_eff, "° → L=",
         is_undef(L_bucket_now) ? "недосяжно" : round(L_bucket_now)));
if (th_eff != boom_angle)   echo(str("!!! boom_angle=", boom_angle, " поза межами циліндра → обмежено до ", th_eff));
if (psi_eff != stick_angle) echo(str("!!! stick_angle=", stick_angle, " поза межами циліндра → обмежено до ", psi_eff));
if (om_eff != bucket_angle) echo(str("!!! bucket_angle=", bucket_angle, " поза межами циліндра → обмежено до ", om_eff));
echo(str("=== ЗУБ КОВША: x=", round(pt_tip(th_eff, psi_eff, om_eff)[0]), " z=", round(pt_tip(th_eff, psi_eff, om_eff)[1]),
         " (земля z=", -ground_below_A, ")"));

// =============================================================================
//  Примітиви
// =============================================================================
// Профільна труба вздовж +X від 0 до L; переріз: Y ∈ ±w/2, Z ∈ ±h/2
module rect_tube(L, h, w, t, r_out = 8) {
    difference() {
        rounded_box(L, w, h, r_out);
        translate([-1, 0, 0]) rounded_box(L + 2, w - 2*t, h - 2*t, max(1, r_out - t));
    }
}
module rounded_box(L, w, h, r) {
    // призма вздовж X з заокругленими ребрами (як у профільної труби)
    translate([0, 0, 0]) rotate([90, 0, 90]) linear_extrude(L)
        offset(r = r) offset(delta = -r) square([w, h], center = true);
}
// Напівпростір: усе з боку (P − K)·n ≥ 0 (n — 2D у площині XZ)
module halfspace(K2, n2, big = 5000) {
    translate(p3(K2)) rotate([0, -ang2(n2), 0]) translate([0, -big/2, -big/2]) cube(big);
}
// Втулка (труба) уздовж Y, центр у 3D точці p, довжина len
module bushing(p, od, id, len) {
    translate(p) rotate([90, 0, 0]) difference() {
        cylinder(d = od, h = len, center = true);
        cylinder(d = id, h = len + 2, center = true);
    }
}
module pin(p, d, len) { color([0.86, 0.88, 0.90]) translate(p) rotate([90, 0, 0]) cylinder(d = d, h = len, center = true); }

// Пластина заданого 2D-контуру (у площині XZ), товщина t уздовж Y, центр по Y = y0
// УВАГА: пластина займає Y ∈ [y0, y0 + t] (rotate([90,0,0]) витягує у −Y, тому зсув на +t)
module plate_xz(pts, t, y0 = 0) {
    translate([0, y0 + t, 0]) rotate([90, 0, 0]) linear_extrude(t) polygon(pts);
}
module ring_plate_xz(center2, r_out, r_in, t, y0 = 0) {
    translate([center2[0], y0 + t, center2[1]]) rotate([90, 0, 0]) linear_extrude(t)
        difference() { circle(r = r_out); circle(r = r_in); }
}

// Половина циліндра у власній системі (вісь уздовж +X): "body" — вушко бази у початку координат, корпус, порти;
// "rod" — вушко штока у початку координат, шток тягнеться у −X на rod_vis (за замовчуванням — увесь хід + запас,
// для інтерактивного перегляду tools/viewer.py: зайва довжина ховається всередині корпусу)
module hyd_cyl_part(which, bore, rod, closed, stroke, pin, wall = 5, eye_len = 45, rod_vis = undef, col_body = [0.13, 0.13, 0.14]) {
    body_od = bore + 2*wall;
    body_L = closed - 2*eye_len - 30;               // корпус (гільза + кришки)
    eye_od = pin + 2*14;                              // вушко зі сферичним шарніром
    eye_w = pin >= 30 ? cyl_eye_w_30 : cyl_eye_w_25;  // реальна ширина вушка
    if (which == "body") {
        // вушко бази
        color([0.13, 0.13, 0.14]) rotate([90, 0, 0]) difference() { cylinder(d = eye_od, h = eye_w, center = true); cylinder(d = pin, h = 100, center = true); }
        // шийка вушка — плоска, завширшки як вушко (входить у вилку); корпус Ø починається на відстані eye_len від осі пальця
        color([0.13, 0.13, 0.14]) translate([pin/2, -eye_w/2, -eye_od*0.35]) cube([eye_len - pin/2 + 1, eye_w, eye_od*0.7]);
        // корпус
        color(col_body) translate([eye_len, 0, 0]) rotate([0, 90, 0]) cylinder(d = body_od, h = body_L);
        // порти
        color([0.54, 0.29, 0.12]) for (x = [eye_len + 25, eye_len + body_L - 25]) translate([x, 0, body_od/2]) cylinder(d = 16, h = 14);
    } else {
        rv = is_undef(rod_vis) ? stroke + 50 : rod_vis;
        // шток
        color([0.88, 0.90, 0.93]) translate([-eye_len - rv, 0, 0]) rotate([0, 90, 0]) cylinder(d = rod, h = rv + 1);
        // вушко штока
        color([0.13, 0.13, 0.14]) rotate([90, 0, 0]) difference() { cylinder(d = eye_od, h = eye_w, center = true); cylinder(d = pin, h = 100, center = true); }
        color([0.13, 0.13, 0.14]) translate([-eye_len, -eye_w/2, -eye_od*0.35]) cube([eye_len - pin/2, eye_w, eye_od*0.7]);
    }
}
// Гідроциліндр між 2D точками P1 (база, кришка) і P2 (шток). Показує реальне висування.
module hyd_cylinder(P1, P2, bore, rod, closed, stroke, pin, wall = 5, eye_len = 45) {
    L = norm(P2 - P1); a = ang2(P2 - P1); ext = L - closed;
    body_L = closed - 2*eye_len - 30;
    ok = (ext >= -0.5 && ext <= stroke + 0.5);
    translate(p3(P1)) rotate([0, -a, 0]) {
        hyd_cyl_part("body", bore, rod, closed, stroke, pin, wall, eye_len, col_body = ok ? [0.13, 0.13, 0.14] : [0.9, 0.2, 0.2]);
        translate([L, 0, 0]) hyd_cyl_part("rod", bore, rod, closed, stroke, pin, wall, eye_len, rod_vis = L - 2*eye_len - body_L + 1);
    }
    if (!ok) echo(str("!!! Циліндр між ", P1, " і ", P2, ": L=", round(L), " поза [", closed, ", ", closed + stroke, "]"));
}

// =============================================================================
//  СТРІЛА (у власній системі: A = 0, хорда вздовж +X; потім повертається на th)
//  Правило моделі: деталі ПРИЛЯГАЮТЬ одна до одної (спільна грань = зварний шов), але НЕ перекриваються.
//  Перевірка: tools/check_overlaps.sh (режим part="overlap").
// =============================================================================
// Вибір окремої деталі всередині вузла: $sel = ключ ("" = усі), $one = лише одна з дзеркальної пари
$sel = ""; $one = false;
function sel(k) = ($sel == "" || $sel == k);
function sides() = $one ? [1] : [-1, 1];
gusset_over = plate_boss;      // щоки перелому виступають за полиці рівно на товщину сідла → сідло лягає між ними врівень
cover_half  = 150;             // пів довжини верхньої накладки перелому (уздовж кожного сегмента від K)
tower_fwd   = -12;             // передній край основи вежі F відносно перелому K: < 0 — на 1-му сегменті (назад вежа тягнеться на cover_half).
                               // Уперед вежу продовжувати не можна: там над накладкою лежить корпус циліндра рукояті (Ø60 ширший за проміжок вилки)
bushE_od = pin_E >= 30 ? bush_od_main : bush_od_small;
stick_pack_w = stick_tube_w + 2*plate_cheek;     // ширина пакета рукояті у вилці стріли (+ 2 шайби = boom_tube_w)
// Шари по ширині біля осі E: пакет рукояті (труба + 2 накладки) → [зазор 1] → вуха ковша і пластини коромисла (один шар:
// у вигляді збоку вони не повинні перетинатися) → [зазор 1–3] → тяги (зовні) і зовнішні бобишки вух на осі E
link_w_in  = stick_tube_w + 2*plate_boss + 2;                       // проміжок між вухами ковша = між пластинами коромисла
link_w_out = link_w_in + 2*max(plate_boss, bucket_ear_t) + 2;       // проміжок між тягами
pin_E_len  = link_w_in + 2*bucket_ear_t + 2*bucket_boss_E_len + 24;
pin_JQ_len = link_w_out + 2*plate_boss + 2*link_boss_len + 20;

module y_hole(p2, d, len = 400) { translate(p3(p2)) rotate([90, 0, 0]) cylinder(d = d, h = len, center = true); }

module boom_seg1() {   // сегмент 1: від A − foot_ext до K (обрізаний бісектрисою); отвір під втулку осі A
    n_bis = unit2(u1_l + u2_l);                        // нормаль площини косого стику в K
    difference() {
        rotate([0, -boom_alpha1, 0]) translate([-boom_foot_ext, 0, 0]) rect_tube(boom_L1 + boom_foot_ext + 200, boom_tube_h, boom_tube_w, boom_tube_t);
        halfspace(K_l, n_bis);
        y_hole([0, 0], bush_od_main);
    }
}
module boom_seg2() {   // сегмент 2: від K до B − fork_reach (низ); торець скошений — верхня полиця коротша на boom_nose_cut
    n_bis = unit2(u1_l + u2_l);
    nose_bot = B_l - boom_fork_reach*u2_l - (boom_tube_h/2)*n2_l;
    nose_top = B_l - (boom_fork_reach + boom_nose_cut)*u2_l + (boom_tube_h/2)*n2_l;
    nose_d = nose_top - nose_bot;
    difference() {
        translate(p3(K_l)) rotate([0, -(boom_alpha1 - boom_bend), 0]) translate([-200, 0, 0]) rect_tube(boom_L2 - boom_fork_reach + 200, boom_tube_h, boom_tube_w, boom_tube_t);
        halfspace(K_l, -n_bis);
        halfspace(nose_bot, [nose_d[1], -nose_d[0]]);
    }
}
module boom_body() {
    if (sel("tube")) color([0.92, 0.72, 0.12]) { boom_seg1(); boom_seg2(); }
}

// Щоки перелому — з обох боків труби; охоплюють стик, базу F і кронштейн D. Верхня накладка — між щоками.
function gusset_back() = max(250, boom_L1 - boom_cyl_sD + 150, boom_L1 - (boom_L1 + boom_L2 - stick_cyl_sF) + cover_half + 10);
function gusset_fwd()  = max(250, boom_cyl_sD - boom_L1 + 150, cover_half + 10);
module boom_bend_gussets() {
    h = boom_tube_h/2 + gusset_over;
    back = gusset_back(); fwd = gusset_fwd();
    p1 = K_l - u1_l*back; p2 = K_l + u2_l*fwd;
    pts = [p1 + n1_l*h, K_l + n1_l*h + u1_l*(h*tan(boom_bend/2)), p2 + n2_l*h, p2 - n2_l*h,
           K_l - n1_l*h - u1_l*(h*tan(boom_bend/2)) , p1 - n1_l*h];
    if (sel("gusset")) color([0.74, 0.76, 0.78]) for (s = sides()) plate_xz(pts, plate_gusset, s > 0 ? boom_tube_w/2 : -boom_tube_w/2 - plate_gusset);
    // накладка на зовнішній (верхній) кут стику — лежить на полицях МІЖ щоками
    t0 = boom_tube_h/2; t1 = t0 + plate_gusset;
    if (sel("cover")) color([0.74, 0.76, 0.78]) plate_xz([K_l - u1_l*cover_half + n1_l*t0, K_l + n1_l*t0 + u1_l*(t0*tan(boom_bend/2)), K_l + u2_l*cover_half + n2_l*t0,
                                       K_l + u2_l*cover_half + n2_l*t1, K_l + n1_l*t1 + u1_l*(t1*tan(boom_bend/2)), K_l - u1_l*cover_half + n1_l*t1],
                                      boom_tube_w, -boom_tube_w/2);
}

// Вилка кронштейна D під стрілою: сідло (між нижніми виступами щік перелому) + 2 пластини вилки ПІД сідлом
module boom_cyl_bracket_D() {
    gap = boom_cyl_pin == 30 ? clevis_gap_30 : clevis_gap_25;
    e = boom_cyl_eD; r = boom_cyl_pin/2 + 22;
    base_y = -boom_tube_h/2; sad_y = base_y - plate_boss;
    loc = [[-110, sad_y], [110, sad_y], [70, -e + r*0.3], [0, -e - r], [-70, -e + r*0.3]];
    pts = [for (p = loc) D_org + p[0]*D_u + p[1]*D_n];
    hole = D_l;
    if (sel("D_clevis")) color([0.26, 0.25, 0.24]) for (s = sides()) let(y0 = s > 0 ? gap/2 : -gap/2 - plate_clevis) difference() {
        hull() { plate_xz(pts, plate_clevis, y0); ring_plate_xz(hole, r, 1, plate_clevis, y0); }
        y_hole(hole, boom_cyl_pin);
    }
    sad = [[-130, sad_y], [130, sad_y], [130, base_y], [-130, base_y]];
    if (sel("D_saddle")) color([0.45, 0.49, 0.54]) plate_xz([for (p = sad) D_org + p[0]*D_u + p[1]*D_n], boom_tube_w, -boom_tube_w/2);
}

// Кронштейн F бази циліндра рукояті: "вежа" на верхній накладці перелому або (далеко від K) вилка на сідлі між щоками
module boom_cyl_bracket_F() {
    gap = clevis_gap_25; e = stick_cyl_eF; r = stick_cyl_pin/2 + 20;
    top_y = boom_tube_h/2;
    dK = abs(boom_L2 - stick_cyl_sF);                           // відстань від F до перелому K уздовж осі
    on_apex = dK < cover_half + 60;
    hole = F_l;
    if (on_apex) {
        t1 = top_y + plate_gusset;                              // стоїть НА верхній накладці
        // Основа йде ПО поверхні накладки двома відрізками (вершина перелому опукла, тому hull через хорду різав би трубу)
        // Передня лапа коротка (tower_fwd): далі вперед над накладкою проходить КОРПУС циліндра рукояті (Ø60 ширший за проміжок вилки)
        // tower_fwd < 0: уся основа вежі — на 1-му сегменті (передня кромка майже вертикальна під вушком)
        e1 = K_l - cover_half*u1_l + t1*n1_l; ap = K_l + (t1*tan(boom_bend/2))*u1_l + t1*n1_l;
        e2 = tower_fwd >= 0 ? K_l + tower_fwd*u2_l + t1*n2_l : K_l + tower_fwd*u1_l + t1*n1_l;
        if (sel("F_tower")) color([0.45, 0.49, 0.54]) for (s = sides()) let(y0 = s > 0 ? gap/2 : -gap/2 - plate_clevis) difference() {
            union() { if (tower_fwd >= 0) { plate_xz([e1, ap, hole], plate_clevis, y0); plate_xz([ap, e2, hole], plate_clevis, y0); }
                      else plate_xz([e1, e2, hole], plate_clevis, y0);
                      ring_plate_xz(hole, r, 1, plate_clevis, y0); }
            y_hole(hole, stick_cyl_pin);
        }
    } else {
        half = min(90, max(40, dK - cover_half - 25));
        sad_y = top_y + plate_boss;
        loc = [[-half, sad_y], [half, sad_y], [half*0.65, e - r*0.3], [0, e + r], [-half*0.65, e - r*0.3]];
        pts = [for (p = loc) F_org + p[0]*F_u + p[1]*F_n];
        if (sel("F_clevis")) color([0.26, 0.25, 0.24]) for (s = sides()) let(y0 = s > 0 ? gap/2 : -gap/2 - plate_clevis) difference() {
            hull() { plate_xz(pts, plate_clevis, y0); ring_plate_xz(hole, r, 1, plate_clevis, y0); }
            y_hole(hole, stick_cyl_pin);
        }
        sad = [[-half - 20, top_y], [half + 20, top_y], [half + 20, sad_y], [-half - 20, sad_y]];
        if (sel("F_saddle")) color([0.45, 0.49, 0.54]) plate_xz([for (p = sad) F_org + p[0]*F_u + p[1]*F_n], boom_tube_w, -boom_tube_w/2);
    }
}

// Вісь A: втулка крізь трубу (отвір у трубі) + круглі накладки з отвором під втулку
module boom_foot_boss() {
    if (sel("A_bushing")) color([0.55, 0.30, 0.12]) bushing([0, 0, 0], bush_od_main, pin_A, boom_foot_boss_len);
    if (sel("A_doubler")) color([0.74, 0.76, 0.78]) for (s = sides()) ring_plate_xz([0, 0], boom_tube_h/2 + 5, bush_od_main/2, plate_boss, s > 0 ? boom_tube_w/2 : -boom_tube_w/2 - plate_boss);
}

// Вилка на кінці стріли (вісь B): 2 пластини ВРІВЕНЬ зі стінками труби; проміжок = boom_tube_w = пакет рукояті + 2 шайби
module boom_fork_B() {
    r = pin_B/2 + 30;
    org = B_l; back = boom_fork_reach + boom_nose_cut + 100;
    loc = [[-back, -boom_tube_h/2], [-boom_fork_reach - 10, -boom_tube_h/2], [0, -r], [0, r], [-boom_fork_reach - 40, boom_tube_h/2], [-back, boom_tube_h/2]];
    pts = [for (p = loc) org + p[0]*u2_l + p[1]*n2_l];
    if (sel("B_fork")) color([0.26, 0.25, 0.24]) for (s = sides()) let(y0 = s > 0 ? boom_tube_w/2 : -boom_tube_w/2 - plate_clevis) difference() {
        hull() { plate_xz(pts, plate_clevis, y0); ring_plate_xz(org, r, 1, plate_clevis, y0); }
        y_hole(org, pin_B + 0.5);
    }
}

module boom_assembly() {
    if (show_boom) { boom_body(); boom_bend_gussets(); boom_cyl_bracket_D(); boom_cyl_bracket_F(); boom_foot_boss(); boom_fork_B(); }
}

// =============================================================================
//  РУКОЯТЬ (у власній системі: B = 0, вісь B→E вздовж +X, +Z = зовнішній бік)
// =============================================================================
// Фаски кутів торця біля осі E (зрізаються і труба, і накладки): торець описує довкола E менший радіус
module stick_tip_chamfer_cut() {
    c = stick_tip_chamfer; x1 = stick_L + stick_tip_ext; h2 = stick_tube_h/2;
    if (c > 0) for (s = [-1, 1]) halfspace([x1 - c, s*h2], [1, s]/sqrt(2));
}
module stick_body() {
    if (sel("tube")) color([0.92, 0.72, 0.12]) difference() {
        translate([-stick_rear_ext, 0, 0]) rect_tube(stick_L + stick_rear_ext + stick_tip_ext, stick_tube_h, stick_tube_w, stick_tube_t);
        y_hole([0, 0], bush_od_main);          // втулка осі B
        y_hole(E_s, bushE_od);                 // втулка осі E
        stick_tip_chamfer_cut();
    }
}
// Щоки п'яти: 2 пластини з боків труби; несуть втулку осі B і вушко G циліндра рукояті
module stick_cheeks() {
    r_g = stick_cyl_pin/2 + 24; r_b = min(bush_od_main/2 + 18, stick_rear_ext);   // кільце не виступає за задній торець щоки
    h2 = stick_tube_h/2;
    hb = h2 + 20;   // щоки виступають на 20 мм за полиці труби (вищий переріз у зоні бази H); шов — по стінці труби
    body = [[-stick_rear_ext, -hb], [380, -hb], [420, -h2], [420, h2], [380, hb], [-stick_rear_ext, hb]];
    if (sel("cheek")) color([0.74, 0.76, 0.78]) for (s = sides()) let(y0 = s > 0 ? stick_tube_w/2 : -stick_tube_w/2 - plate_cheek) difference() {
        union() {
            hull() { plate_xz(body, plate_cheek, y0); ring_plate_xz([0, 0], r_b, 1, plate_cheek, y0); }
            hull() { ring_plate_xz(G_s, r_g, 1, plate_cheek, y0);
                     ring_plate_xz([-stick_rear_ext + 25, h2 - 25], 25, 1, plate_cheek, y0);
                     ring_plate_xz([140, h2 - 25], 25, 1, plate_cheek, y0); }
        }
        y_hole(G_s, stick_cyl_pin + 0.5);
        y_hole([0, 0], bush_od_main);          // втулка проходить крізь щоки
    }
    // втулка осі B крізь трубу і щоки
    if (sel("B_bushing")) color([0.55, 0.30, 0.12]) bushing([0, 0, 0], bush_od_main, pin_B, stick_pack_w);
    // приварені розпірні втулки осі G між щоками: проміжок під вушко = clevis_gap_25
    if (sel("G_boss")) color([0.55, 0.30, 0.12]) for (s = sides()) translate(p3(G_s)) rotate([90, 0, 0])
        translate([0, 0, s*(clevis_gap_25/2 + (stick_tube_w - clevis_gap_25)/4)]) difference() {
            cylinder(d = stick_cyl_pin + 14, h = (stick_tube_w - clevis_gap_25)/2, center = true);
            cylinder(d = stick_cyl_pin + 0.5, h = 100, center = true);
        }
    // ребро жорсткості між щоками п'яти (стоїть на верхній полиці труби); НЕ доходить до вушка G
    // ребро: пластина plate_boss уздовж лінії rib0→rib1; підошва зрізана по полиці труби (не заходить у трубу)
    rib0 = [135, h2]; rib1 = [G_s[0] + 68, G_s[1] - 15]; rib_d = rib1 - rib0;
    rib_n = plate_boss/2 * [-rib_d[1], rib_d[0]] / norm(rib_d);          // нормаль (униз-назад)
    rib_w = (plate_boss/2) * norm(rib_d) / abs(rib_d[1]);                 // пів ширини підошви вздовж полиці
    if (sel("heel_rib")) color([0.45, 0.49, 0.54]) plate_xz([[rib0[0] - rib_w, h2], [rib0[0] + rib_w, h2], rib1 - rib_n, rib1 + rib_n], stick_tube_w, -stick_tube_w/2);
}
// Кронштейн H бази циліндра ковша: сідло на полиці МІЖ виступами щік + 2 пластини вилки НА сідлі
module stick_cyl_bracket_H() {
    gap = clevis_gap_25; e = bucket_cyl_eH; r = bucket_cyl_pin/2 + 20; top_y = stick_tube_h/2; sad_y = top_y + plate_boss;
    // Асиметрична: основа тягнеться НАЗАД (туди ж діє реакція циліндра при копанні); вперед плечей немає —
    // там при підкрученому ковші низько над рукояттю лежить корпус циліндра (Ø60 ширший за проміжок вилки)
    loc = [[-78, sad_y], [28, sad_y], [0, e + r], [-55, e - r*0.3]];
    pts = [for (p = loc) [bucket_cyl_sH + p[0], p[1]]];
    hole = H_s;
    if (sel("H_clevis")) color([0.26, 0.25, 0.24]) for (s = sides()) let(y0 = s > 0 ? gap/2 : -gap/2 - plate_clevis) difference() {
        hull() { plate_xz(pts, plate_clevis, y0); ring_plate_xz(hole, r, 1, plate_clevis, y0); }
        y_hole(hole, bucket_cyl_pin);
    }
    if (sel("H_saddle")) color([0.45, 0.49, 0.54]) plate_xz([[bucket_cyl_sH - 80, top_y], [bucket_cyl_sH + 40, top_y], [bucket_cyl_sH + 40, sad_y], [bucket_cyl_sH - 80, sad_y]], stick_tube_w, -stick_tube_w/2);
}
// Кінець рукояті: втулка осі E крізь трубу, втулка осі коромисла R над трубою, 2 накладки з отворами під втулки
module stick_tip_bosses() {
    len = stick_tube_w + 2*plate_boss;
    if (sel("E_bushing")) color([0.55, 0.30, 0.12]) bushing(p3(E_s), bushE_od, pin_E, len);
    if (sel("R_bushing")) color([0.55, 0.30, 0.12]) bushing(p3(R_s), bush_od_small, pin_R, len);
    h2 = stick_tube_h/2;
    c = stick_tip_chamfer; x0 = E_s[0] - rocker_rx - 120; x1 = E_s[0] + stick_tip_ext;
    loc = [[x0, -h2], [x1 - c, -h2], [x1, -h2 + c], [x1, h2 - c], [x1 - c, h2], [x0, h2]];
    if (sel("tip_plate")) color([0.74, 0.76, 0.78]) for (s = sides()) let(y0 = s > 0 ? stick_tube_w/2 : -stick_tube_w/2 - plate_boss) difference() {
        hull() { plate_xz(loc, plate_boss, y0); ring_plate_xz(E_s, bushE_od/2 + 15, 1, plate_boss, y0); ring_plate_xz(R_s, bush_od_small/2 + 12, 1, plate_boss, y0); }
        y_hole(E_s, bushE_od); y_hole(R_s, bush_od_small);
    }
}
// Упорні шайби осі B між щоками рукояті та вилкою стріли (у системі рукояті)
module washers_B() {
    t = (boom_tube_w - stick_pack_w)/2;
    if (t > 0.2) color([0.86, 0.88, 0.90]) for (s = sides()) translate([0, s*(stick_pack_w/2 + t/2), 0]) rotate([90, 0, 0])
        difference() { cylinder(d = bush_od_main + 10, h = t, center = true); cylinder(d = pin_B + 0.5, h = t + 2, center = true); }
}
module stick_assembly() {
    if (show_stick) { stick_body(); stick_cheeks(); stick_cyl_bracket_H(); stick_tip_bosses(); }
}

// =============================================================================
//  Коромисло і тяга
// =============================================================================
module rocker_and_link(th, psi, om, which = "both") { rocker_link_pts(pt_R(th, psi), pt_J(th, psi, om), pt_Q(th, psi, om), which); }
// те саме за готовими точками R, J, Q (для власних систем деталей: коромисло R = 0, J на +X; тяга J = 0, Q на +X)
module rocker_link_pts(R, J, Q, which = "both") {
    if (!is_undef(J)) {
        w_out = link_w_in;                         // коромисло охоплює рукоять зовні (зазор 1 мм на бік)
        w_l = link_w_out;                          // тяги — зовні коромисла (на осі J) і зовні вух ковша (на осі Q)
        if (which != "link") {
            if (sel("rocker_plate")) color([0.26, 0.25, 0.24]) for (s = sides()) let(y0 = s > 0 ? w_out/2 : -w_out/2 - plate_boss) difference() {
                hull() { ring_plate_xz(R, pin_R/2 + 22, 1, plate_boss, y0); ring_plate_xz(J, pin_JQ/2 + 20, 1, plate_boss, y0); }
                y_hole(R, pin_R + 0.5); y_hole(J, pin_JQ + 0.5);
            }
            // приварені до пластин коромисла бобишки на осі J: палець обпертий біля самого вушка циліндра
            boss_J = (w_out - clevis_gap_25)/2;
            if (sel("J_boss")) color([0.55, 0.30, 0.12]) for (s = sides()) translate(p3(J)) rotate([90, 0, 0]) translate([0, 0, s*(clevis_gap_25/2 + boss_J/2)])
                difference() { cylinder(d = pin_JQ + 16, h = boss_J, center = true); cylinder(d = pin_JQ + 0.5, h = boss_J + 2, center = true); }
        }
        if (which != "rocker")
            if (sel("link_plate")) color([0.26, 0.25, 0.24]) for (s = sides()) let(y0 = s > 0 ? w_l/2 : -w_l/2 - plate_boss) difference() {
                hull() { ring_plate_xz(J, pin_JQ/2 + 20, 1, plate_boss, y0); ring_plate_xz(Q, pin_JQ/2 + 20, 1, plate_boss, y0); }
                y_hole(J, pin_JQ + 0.5); y_hole(Q, pin_JQ + 0.5);
            }
        if (which != "rocker")
            if (sel("link_boss")) color([0.55, 0.30, 0.12]) for (s = sides()) for (P = [J, Q]) bushing([P[0], s*(w_l/2 + plate_boss + link_boss_len/2), P[1]], link_boss_od, pin_JQ + 0.5, link_boss_len);
        if (which == "both" && $sel == "") { pin(p3(J), pin_JQ, pin_JQ_len); pin(p3(Q), pin_JQ, pin_JQ_len); pin(p3(R), pin_R, w_out + 20); }
    }
}
// =============================================================================
//  КІВШ (у власній системі: E = 0, x — до вістря зуба, y (у 3D — Z) — зовнішній бік, де вушко тяги Q)
//  Зовнішній контур обичайки: губа S0 → пряма верхня полиця → дуга R(back_r) → спинка → дуга п'яти R(heel_r) → дно → ніж.
//  Довжина спинки обчислюється так, щоб дно лягло на лінію, що проходить через вістря зуба під кутом floor_angle.
//  Python-двійник: tools/bucket.py (місткість, зазори на всьому ході, міцність вух).
// =============================================================================
function bk_dir(h) = [cos(h), sin(h)];
function bk_nr(h) = [sin(h), -cos(h)];                      // права нормаль до напрямку h = УСЕРЕДИНУ ковша
bk_h1 = 90 - bucket_back_turn;                              // напрямок спинки
bk_h2 = -bucket_floor_angle;                                // напрямок дна (до зуба)
bk_turn2 = bk_h1 - bk_h2;                                   // кут дуги п'яти
bk_nin = bk_nr(bk_h2);                                      // нормаль дна всередину
bk_T = [bucket_tip, 0];                                     // вістря зуба — у серединній площині ножа
bk_Tu = bk_T - bucket_edge_t/2 * bk_nin;                    // точка на лінії НИЗУ дна під вістрям
bk_xsh = bucket_top_x + bucket_top_t;                       // зовнішня поверхня обичайки на верхній полиці
bk_S0 = [bk_xsh, bucket_lip_y];
bk_S1 = bk_S0 + [0, bucket_top_len];
bk_C1 = bk_S1 + bucket_back_r * bk_nr(90);
bk_A1 = bk_C1 - bucket_back_r * bk_nr(bk_h1);
_bk_end0 = bk_A1 + bucket_heel_r * (bk_nr(bk_h1) - bk_nr(bk_h2));
bk_back_len = -((_bk_end0 - bk_Tu) * bk_nin) / (bk_dir(bk_h1) * bk_nin);
bk_Pb = bk_A1 + bk_back_len * bk_dir(bk_h1);
bk_C2 = bk_Pb + bucket_heel_r * bk_nr(bk_h1);
bk_A2 = bk_C2 - bucket_heel_r * bk_nr(bk_h2);
bk_edge_front = bk_Tu - bucket_tooth_out * bk_dir(bk_h2);
bk_edge_back = bk_edge_front - bucket_edge_w * bk_dir(bk_h2);
bk_floor_len = (bk_edge_back - bk_A2) * bk_dir(bk_h2);
bk_bevel = 1.5 * bucket_edge_t;                             // фаска ножа зверху (≈ 34°)
bk_blade_top_front = bk_edge_front - bk_bevel * bk_dir(bk_h2) + bucket_edge_t * bk_nin;
bk_w_in = bucket_width - 2*bucket_side_t;                   // внутрішня ширина = ширина обичайки
function bk_arc(C, r, ha, hb, n = 24) = [for (i = [0 : n]) let(h = ha + (hb - ha) * i / n) C - r * bk_nr(h)];
// контур обичайки, зміщений усередину на off (0 = зовнішня поверхня)
function bk_path(off) = concat([bk_S0 + off * bk_nr(90)], bk_arc(bk_C1, bucket_back_r - off, 90, bk_h1),
                               bk_arc(bk_C2, bucket_heel_r - off, bk_h1, bk_h2), [bk_edge_back + off * bk_nin]);
function bk_rev(v) = [for (i = [len(v) - 1 : -1 : 0]) v[i]];
// довжина розгортки обичайки по нейтральній лінії (середина товщини)
bk_dev_len = bucket_top_len + (bucket_back_r - bucket_shell_t/2) * bucket_back_turn * PI/180 + bk_back_len
           + (bucket_heel_r - bucket_shell_t/2) * bk_turn2 * PI/180 + bk_floor_len;
bk_r_max = max([for (q = bk_path(0)) norm(q)]);
if (bk_back_len < 0) echo(str("!!! КІВШ: спинка від'ємної довжини (", round(bk_back_len), ") — зменште bucket_heel_r / bucket_back_r / bucket_top_len"));
if (bk_floor_len < 0) echo(str("!!! КІВШ: ніж заходить на дугу п'яти (", round(bk_floor_len), ") — зменште bucket_heel_r або bucket_edge_w"));
echo(str("=== КІВШ: спинка ", round(bk_back_len), " мм, дуга п'яти ", round(bk_turn2), "°, дно ", round(bk_floor_len), " мм + ніж ", bucket_edge_w,
         "; розгортка обичайки ", round(bk_dev_len), "×", bk_w_in, "; найдальша від E точка обичайки ", round(bk_r_max), " < радіус зуба ", bucket_tip));

module bucket_sides() {     // боковини: зовнішній контур обичайки; спереду стоять НА ножі, передня кромка — від ножа до губи
    pts = concat(bk_path(0), [bk_edge_back + bucket_edge_t * bk_nin, bk_blade_top_front]);
    if (sel("bk_side")) color([0.92, 0.72, 0.12]) for (s = sides()) plate_xz(pts, bucket_side_t, s > 0 ? bk_w_in/2 : -bk_w_in/2 - bucket_side_t);
}
module bucket_shell() {     // обичайка між боковинами: одна вальцьована/гнута смуга
    if (sel("bk_shell")) color([0.92, 0.72, 0.12]) plate_xz(concat(bk_path(0), bk_rev(bk_path(bucket_shell_t))), bk_w_in, -bk_w_in/2);
}
module bucket_top() {       // накладка під вуха (на обичайці та кромках боковин, на всю ширину) + ребро губи всередині
    y0 = bucket_lip_y; y1 = bucket_lip_y + bucket_top_len; xi = bk_xsh + bucket_shell_t;
    if (sel("bk_top")) color([0.92, 0.72, 0.12]) plate_xz([[bucket_top_x, y0], [bk_xsh, y0], [bk_xsh, y1], [bucket_top_x, y1]], bucket_width, -bucket_width/2);
    if (sel("bk_lip_rib")) color([0.92, 0.72, 0.12]) plate_xz([[xi, y0], [xi + bucket_lip_rib[0], y0], [xi + bucket_lip_rib[0], y0 + bucket_lip_rib[1]], [xi, y0 + bucket_lip_rib[1]]], bk_w_in, -bk_w_in/2);
}
module bucket_blade_2d_plate() {
    plate_xz([bk_edge_back, bk_edge_front, bk_blade_top_front, bk_edge_back + bucket_edge_t * bk_nin], bucket_width, -bucket_width/2);
}
module bucket_edge() {      // ніж на всю ширину + зуби (вилкою охоплюють ніж; вістря — у серединній площині ножа)
    if (sel("bk_edge")) color([0.13, 0.13, 0.14]) bucket_blade_2d_plate();
    function m(sb, v) = bk_T - sb * bk_dir(bk_h2) + v * bk_nin;
    leg = bucket_edge_t/2 + 10;
    tooth = [m(0, 2), m(0, -2), m(bucket_tooth_out, -leg), m(bucket_tooth_len, -leg + 6), m(bucket_tooth_len, leg - 6), m(bucket_tooth_out, leg)];
    span = bucket_width - bucket_tooth_w - 20;
    if (sel("bk_tooth")) color([0.13, 0.13, 0.14]) for (i = [0 : ($one ? 0 : bucket_tooth_n - 1)])
        let(yc = bucket_tooth_n < 2 ? 0 : -span/2 + span * i / (bucket_tooth_n - 1))
        difference() { plate_xz(tooth, bucket_tooth_w, yc - bucket_tooth_w/2); bucket_blade_2d_plate(); }
}
module bucket_ears() {      // вуха стоять на накладці; зовнішні бобишки на осі E; розпірна втулка осі Q між вухами
    gap = link_w_in; t = bucket_ear_t;
    base0 = [bucket_top_x, bucket_lip_y + 4]; base1 = [bucket_top_x, min(bucket_lip_y + bucket_top_len - 4, bucket_ear[1] + 75)];
    if (sel("bk_ear")) color([0.92, 0.72, 0.12]) for (s = sides()) let(y0 = s > 0 ? gap/2 : -gap/2 - t) difference() {
        hull() { ring_plate_xz([0, 0], bucket_ear_r_E, 1, t, y0); ring_plate_xz(bucket_ear, bucket_ear_r_Q, 1, t, y0);
                 plate_xz([base0, base1, base1 - [1, 0], base0 - [1, 0]], t, y0); }
        y_hole([0, 0], pin_E + 0.5); y_hole(bucket_ear, pin_JQ + 0.5);
        translate([bucket_top_x, -500, -2000]) cube([2000, 1000, 4000]);      // ніщо не заходить за поверхню накладки
    }
    if (sel("bk_boss_E")) color([0.55, 0.30, 0.12]) for (s = sides()) bushing([0, s*(gap/2 + t + bucket_boss_E_len/2), 0], bucket_boss_E_od, pin_E + 0.5, bucket_boss_E_len);
    if (sel("bk_spacer_Q")) color([0.55, 0.30, 0.12]) bushing(p3(bucket_ear), bush_od_small, pin_JQ + 0.5, gap);
}
module bucket_wear() {      // смуги зносу зовні на п'яті
    band = concat(bk_arc(bk_C2, bucket_heel_r + bucket_wear[1], bk_h1, bk_h2), bk_rev(bk_arc(bk_C2, bucket_heel_r, bk_h1, bk_h2)));
    span = bucket_width - 2*60 - bucket_wear[0];
    if (sel("bk_wear")) color([0.13, 0.13, 0.14]) for (i = [0 : ($one ? 0 : bucket_wear_n - 1)])
        let(yc = bucket_wear_n < 2 ? 0 : -span/2 + span * i / (bucket_wear_n - 1)) plate_xz(band, bucket_wear[0], yc - bucket_wear[0]/2);
}
module bucket_assembly() { bucket_sides(); bucket_shell(); bucket_top(); bucket_edge(); bucket_ears(); bucket_wear(); }
// ківш у світовій системі
module bucket_placed(th, psi, om) { translate(p3(pt_E(th, psi))) rotate([0, -bucket_dir(th, psi, om), 0]) bucket_assembly(); }

// Схематична поворотна колона: вісь A (вилка) і палець C бази циліндра стріли
module post_schematic() {
    w = boom_foot_boss_len + 2;
    color([0.26, 0.25, 0.24]) {
        for (s = sides()) translate([0, s*(w/2 + 6), 0]) rotate([90, 0, 0]) difference() {
            hull() { cylinder(d = 110, h = 12, center = true); translate([C_w[0], C_w[1], 0]) cylinder(d = 90, h = 12, center = true); translate([0, C_w[1] - 150, 0]) cylinder(d = 110, h = 12, center = true); }
            cylinder(d = pin_A, h = 20, center = true);
            translate([C_w[0], C_w[1], 0]) cylinder(d = boom_cyl_pin, h = 20, center = true);
        }
    }
    pin([0, 0, 0], pin_A, w + 40);
    pin(p3(C_w), boom_cyl_pin, w + 40);
}

// Земля — не ландшафт, а площина відліку: від неї рахуються глибина копання й висота
// вивантаження. Суцільна плита 5000×3000×20 показувала в кадрі свій ТОРЕЦЬ і читалася як
// коробка; сітка по 500 мм одразу дає і масштаб, і те, наскільки ківш пішов нижче землі.
// Розміри й крок — як у 3D-сторінці (buildGround: 9000×6000, GridHelper на 18 поділок),
// щоб рендер CLI і сторінка показували те саме.
module ground() {
    z = -ground_below_A;
    step = 500;                                             // клітинка, мм
    sx = ground_span; sy = ground_span * 2/3; ox = 1500 - sx/2; oy = -sy/2;   // центр зсунуто вперед, як на сторінці
    color([0.62, 0.56, 0.46]) translate([ox, oy, z - 3]) cube([sx, sy, 2]);
    color([0.44, 0.37, 0.27]) {                             // лінії сітки заходять у плиту: без спільних граней
        for (x = [0 : step : sx]) translate([ox + x - 2, oy, z - 1.5]) cube([4, sy, 1.5]);
        for (y = [0 : step : sy]) translate([ox, oy + y - 2, z - 1.5]) cube([sx, 4, 1.5]);
    }
}

module envelope_points() {
    if (!is_undef(boom_angle_min) && !is_undef(stick_angle_min) && !is_undef(bucket_angle_min) && !is_undef(bucket_angle_max))
        color([0.9, 0.3, 0.3]) for (t = [boom_angle_min : (boom_angle_max - boom_angle_min)/16 : boom_angle_max])
            for (p = [stick_angle_min : (stick_angle_max - stick_angle_min)/16 : stick_angle_max])
                for (o = [bucket_angle_min, bucket_angle_max])
                    translate(p3(pt_tip(t, p, o))) sphere(6, $fn = 8);
}

// =============================================================================
//  ЗБІРКА
// =============================================================================
module assembly() {
    th = th_eff; psi = psi_eff; om = om_eff;
    rotate([0, -th, 0]) boom_assembly();
    translate(p3(pt_B(th))) rotate([0, -stick_dir(th, psi), 0]) { stick_assembly(); if (show_stick) washers_B(); }
    if (show_cylinders) {
        hyd_cylinder(C_w, pt_D(th), boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
        hyd_cylinder(pt_F(th), pt_G(th, psi), stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
        if (show_bucket_linkage && !is_undef(pt_J(th, psi, om)))
            hyd_cylinder(pt_H(th, psi), pt_J(th, psi, om), bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);
        pin(p3(pt_D(th)), boom_cyl_pin, clevis_gap_30 + 2*plate_clevis + 20);
        pin(p3(pt_F(th)), stick_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20);
        pin(p3(pt_G(th, psi)), stick_cyl_pin, stick_pack_w + 20);
        pin(p3(pt_H(th, psi)), bucket_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20);
    }
    pin(p3(pt_B(th)), pin_B, boom_tube_w + 2*plate_clevis + 24);
    pin(p3(pt_E(th, psi)), pin_E, pin_E_len);
    if (show_bucket_linkage) rocker_and_link(th, psi, om);
    if (show_bucket) bucket_placed(th, psi, om);
    if (show_post) post_schematic();
    if (show_ground) ground();
    if (show_envelope) envelope_points();
}

// =============================================================================
//  ВИБІР ДЕТАЛІ (для експорту STL) і перевірка перетинів
//  Вузли стріли — у системі стріли (A = 0), вузли рукояті — у системі рукояті (B = 0).
// =============================================================================
module part_by_name(n) {
    if      (n == "boom")            boom_assembly();
    else if (n == "boom_tubes")      boom_body();
    else if (n == "boom_gussets")    boom_bend_gussets();
    else if (n == "boom_bracket_D")  boom_cyl_bracket_D();
    else if (n == "boom_bracket_F")  boom_cyl_bracket_F();
    else if (n == "boom_foot_boss")  boom_foot_boss();
    else if (n == "boom_fork_B")     boom_fork_B();
    else if (n == "stick")           stick_assembly();
    else if (n == "stick_tube")      stick_body();
    else if (n == "stick_cheeks")    stick_cheeks();
    else if (n == "stick_bracket_H") stick_cyl_bracket_H();
    else if (n == "stick_tip")       stick_tip_bosses();
    else if (n == "rocker")          rocker_and_link(th_eff, psi_eff, om_eff, "rocker");
    else if (n == "link")            rocker_and_link(th_eff, psi_eff, om_eff, "link");
    else if (n == "bucket")          bucket_assembly();
    else if (n == "bucket_sides")    bucket_sides();
    else if (n == "bucket_shell")    bucket_shell();
    else if (n == "bucket_top")      bucket_top();
    else if (n == "bucket_edge")     bucket_edge();
    else if (n == "bucket_ears")     bucket_ears();
    else if (n == "bucket_wear")     bucket_wear();
    // рухомі вузли у світовій системі при поточних кутах — для перевірки зіткнень (part="collide")
    // деталі у ВЛАСНИХ системах для інтерактивного перегляду (tools/viewer.py): поза складається у браузері
    else if (n == "v_stick")         { stick_assembly(); washers_B(); }
    else if (n == "v_rocker")        rocker_link_pts([0, 0], [rocker_L, 0], [0, 0], "rocker");
    else if (n == "v_link")          rocker_link_pts([0, 0], [0, 0], [link_L, 0], "link");
    else if (n == "v_cyl_boom_body")   hyd_cyl_part("body", boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
    else if (n == "v_cyl_boom_rod")    hyd_cyl_part("rod",  boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
    else if (n == "v_cyl_stick_body")  hyd_cyl_part("body", stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
    else if (n == "v_cyl_stick_rod")   hyd_cyl_part("rod",  stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
    else if (n == "v_cyl_bucket_body") hyd_cyl_part("body", bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);
    else if (n == "v_cyl_bucket_rod")  hyd_cyl_part("rod",  bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);
    else if (n == "m_boom")          rotate([0, -th_eff, 0]) boom_assembly();
    else if (n == "m_stick")         translate(p3(pt_B(th_eff))) rotate([0, -stick_dir(th_eff, psi_eff), 0]) stick_assembly();
    else if (n == "m_bucket")        bucket_placed(th_eff, psi_eff, om_eff);
    else if (n == "m_rocker")        rocker_and_link(th_eff, psi_eff, om_eff, "rocker");
    else if (n == "m_link")          rocker_and_link(th_eff, psi_eff, om_eff, "link");
    else if (n == "m_post")          post_schematic();
    else if (n == "m_bmcyl")         hyd_cylinder(C_w, pt_D(th_eff), boom_cyl_bore, boom_cyl_rod, boom_cyl_closed, boom_cyl_stroke, boom_cyl_pin, wall = 6.5);
    else if (n == "m_scyl")          hyd_cylinder(pt_F(th_eff), pt_G(th_eff, psi_eff), stick_cyl_bore, stick_cyl_rod, stick_cyl_closed, stick_cyl_stroke, stick_cyl_pin);
    else if (n == "m_bcyl")          hyd_cylinder(pt_H(th_eff, psi_eff), pt_J(th_eff, psi_eff, om_eff), bucket_cyl_bore, bucket_cyl_rod, bucket_cyl_closed, bucket_cyl_stroke, bucket_cyl_pin);
    else if (n == "post")            post_schematic();
    else echo(str("!!! невідома деталь: ", n));
}
// ---- Плоскі деталі (контур для DXF/ескізу): [ключ, вузол-власник, к-сть, товщина, кут вирівнювання, назва]
_F_on_apex = abs(boom_L2 - stick_cyl_sF) < cover_half + 60;
_Jw = pt_J(th_eff, psi_eff, om_eff); _Rw = pt_R(th_eff, psi_eff); _Qw = pt_Q(th_eff, psi_eff, om_eff);
flat_parts = concat([
    ["gusset",       "boom_gussets",    2, plate_gusset, boom_alpha1,               "Щока перелому стріли"],
    ["D_clevis",     "boom_bracket_D",  2, plate_clevis, ang2(D_u),                 "Вилка D (шток циліндра стріли)"]],
    _F_on_apex ? [["F_tower", "boom_bracket_F", 2, plate_clevis, boom_alpha1 - boom_bend/2, "Вежа F (база циліндра рукояті)"]]
               : [["F_clevis", "boom_bracket_F", 2, plate_clevis, ang2(F_u),        "Вилка F (база циліндра рукояті)"]], [
    ["A_doubler",    "boom_foot_boss",  2, plate_boss,   0,                         "Накладка осі A"],
    ["B_fork",       "boom_fork_B",     2, plate_clevis, ang2(u2_l),                "Пластина вилки B"],
    ["cheek",        "stick_cheeks",    2, plate_cheek,  0,                         "Щока п'яти рукояті"],
    ["H_clevis",     "stick_bracket_H", 2, plate_clevis, 0,                         "Вилка H (база циліндра ковша)"],
    ["tip_plate",    "stick_tip",       2, plate_boss,   0,                         "Накладка кінця рукояті (осі E, R)"],
    ["rocker_plate", "rocker",          2, plate_boss,   is_undef(_Jw) ? 0 : ang2(_Jw - _Rw), "Пластина коромисла"],
    ["link_plate",   "link",            2, plate_boss,   is_undef(_Jw) ? 0 : ang2(_Qw - _Jw), "Тяга ковша"],
    ["bk_side",      "bucket_sides",    2, bucket_side_t, ang2(bk_blade_top_front - bk_S0), "Боковина ковша"],
    ["bk_ear",       "bucket_ears",     2, bucket_ear_t,  90,                        "Вухо ковша (осі E і Q)"]]);
module flat(name) {
    i = search([name], flat_parts)[0];
    if (is_undef(i) || i == []) echo(str("!!! невідома плоска деталь: ", name));
    else { $sel = name; $one = true;
           projection() rotate([-90, 0, 0]) rotate([0, flat_parts[i][4], 0]) part_by_name(flat_parts[i][1]); }
}
// ---- Специфікація (читає tools/bom_drawings.py): смуги/прямокутні пластини, труби, втулки, пальці
_mitre = (boom_tube_h/2) * tan(boom_bend/2);
_rib_L = norm([G_s[0] + 68, G_s[1] - 15] - [135, stick_tube_h/2]) + 25;
echo(BOM_PARAMS = [["boom_h", boom_tube_h], ["boom_w", boom_tube_w], ["boom_t", boom_tube_t], ["stick_h", stick_tube_h], ["stick_w", stick_tube_w], ["stick_t", stick_tube_t],
    ["foot_ext", boom_foot_ext], ["L1", boom_L1], ["L2", boom_L2], ["bend", boom_bend], ["mitre", _mitre], ["fork_reach", boom_fork_reach], ["nose_cut", boom_nose_cut],
    ["bush_main", bush_od_main], ["bushE", bushE_od], ["stick_L", stick_L], ["rear_ext", stick_rear_ext], ["tip_ext", stick_tip_ext]]);
echo(BOM_FLAT = [for (f = flat_parts) [f[0], f[2], f[3], f[5]]]);
echo(BOM_STRIPS = concat([   // [ключ, к-сть, довжина, ширина, товщина, назва]
    ["cover",    1, 2*cover_half + 2*_mitre, boom_tube_w, plate_gusset, str("Верхня накладка перелому (гнути посередині на ", boom_bend, "° або з двох частин)")],
    ["D_saddle", 1, 260, boom_tube_w, plate_boss, "Сідло вилки D (між щоками перелому)"]],
    _F_on_apex ? [] : [["F_saddle", 1, 2*min(90, max(40, abs(boom_L2 - stick_cyl_sF) - cover_half - 25)) + 40, boom_tube_w, plate_boss, "Сідло вилки F"]], [
    ["H_saddle", 1, 120, stick_tube_w, plate_boss, "Сідло вилки H (між виступами щік)"],
    ["heel_rib", 1, round(_rib_L), stick_tube_w, plate_boss, "Ребро п'яти між щоками"],
    ["bk_shell",   1, round(bk_dev_len), bk_w_in, bucket_shell_t, str("Обичайка ковша — розгортка; гнути: полиця ", bucket_top_len, " → R", bucket_back_r - bucket_shell_t, " внутр. на ", bucket_back_turn,
                     "° → спинка ", round(bk_back_len), " → R", bucket_heel_r - bucket_shell_t, " внутр. на ", round(bk_turn2), "° → дно ", round(bk_floor_len))],
    ["bk_top",     1, bucket_top_len, bucket_width, bucket_top_t, "Накладка під вуха ковша (на обичайку і кромки боковин)"],
    ["bk_lip_rib", 1, bk_w_in, bucket_lip_rib[0], bucket_lip_rib[1], "Ребро губи ковша (на ребро під передньою кромкою верху)"]]));
echo(BOM_WEAR = [            // зносостійкі деталі ковша (НЕ Ст3): [ключ, к-сть, довжина, ширина, товщина, назва]
    ["bk_edge",    1, bucket_width, bucket_edge_w, bucket_edge_t, "Ніж ковша — ЗНОСОСТІЙКА сталь (Hardox 400/450, 65Г, ніж грейдера), фаска зверху ≈ 34°"],
    ["bk_tooth",   bucket_tooth_n, bucket_tooth_len, bucket_tooth_w, bucket_edge_t + 20, "Зуб ковша: покупний приварний під ніж 12 мм АБО з поковки/смуги 65Г, 30ХГСА"],
    ["bk_wear",    bucket_wear_n, round((bucket_heel_r + bucket_wear[1]/2) * bk_turn2 * PI/180), bucket_wear[0], bucket_wear[1], "Смуга зносу на п'яті ковша (гнути по R п'яти)"]]);
// розгортка обичайки для ескізу: ділянки по нейтральній лінії від губи [назва, довжина] + радіуси/кути гнуття
echo(BOM_SHELL = [bk_w_in, bucket_shell_t, [["полиця під вуха", bucket_top_len], [str("гнуття R", bucket_back_r - bucket_shell_t, " внутр. на ", bucket_back_turn, "°"), (bucket_back_r - bucket_shell_t/2) * bucket_back_turn * PI/180],
    ["спинка", bk_back_len], [str("гнуття R", bucket_heel_r - bucket_shell_t, " внутр. на ", round(bk_turn2*10)/10, "°"), (bucket_heel_r - bucket_shell_t/2) * bk_turn2 * PI/180], ["дно (до ножа)", bk_floor_len]]]);
echo(BOM_TUBES = [           // [ключ, h, w, t, довжина по довгій стороні, назва/різи]
    ["boom_seg1", boom_tube_h, boom_tube_w, boom_tube_t, round(boom_foot_ext + boom_L1 + _mitre), str("Стріла, сегмент 1: торець 90°, косий різ ", boom_bend/2, "°; отвір Ø", bush_od_main, " на ", boom_foot_ext, " мм від торця")],
    ["boom_seg2", boom_tube_h, boom_tube_w, boom_tube_t, round(boom_L2 - boom_fork_reach + _mitre), str("Стріла, сегмент 2: косий різ ", boom_bend/2, "°; скіс торця: верхня полиця коротша на ", boom_nose_cut, " мм")],
    ["stick",     stick_tube_h, stick_tube_w, stick_tube_t, stick_L + stick_rear_ext + stick_tip_ext, str("Рукоять: отвори Ø", bush_od_main, " на ", stick_rear_ext, " мм і Ø", bushE_od, " на ", stick_rear_ext + stick_L, " мм від заднього торця; фаски кутів переднього торця ", stick_tip_chamfer, "×", stick_tip_chamfer)]]);
echo(BOM_ROUND = [           // [ключ, к-сть, OD, ID, довжина, назва]
    ["A_bushing", 1, bush_od_main, pin_A, boom_foot_boss_len, "Втулка-бобишка осі A (труба 66×33, дві втулки ГАЗ-53 по краях)"],
    ["B_bushing", 1, bush_od_main, pin_B, stick_pack_w, "Втулка-бобишка осі B"],
    ["E_bushing", 1, bushE_od, pin_E, stick_tube_w + 2*plate_boss, "Втулка-бобишка осі E"],
    ["R_bushing", 1, bush_od_small, pin_R, stick_tube_w + 2*plate_boss, "Втулка осі коромисла R"],
    ["G_boss",    2, stick_cyl_pin + 14, stick_cyl_pin + 0.5, (stick_tube_w - clevis_gap_25)/2, "Розпірна втулка осі G (приварити до щоки)"],
    ["J_boss",    2, pin_JQ + 16, pin_JQ + 0.5, (stick_tube_w + 2*plate_boss + 2 - clevis_gap_25)/2, "Бобишка осі J (приварити до пластини коромисла)"],
    ["B_washer",  2, bush_od_main + 10, pin_B + 0.5, (boom_tube_w - stick_pack_w)/2, "Упорна шайба осі B"],
    ["link_boss", 4, link_boss_od, pin_JQ + 0.5, link_boss_len, "Бобишка тяги на осях J і Q (приварити зовні до пластини тяги)"],
    ["bk_boss_E", 2, bucket_boss_E_od, pin_E + 0.5, bucket_boss_E_len, "Зовнішня бобишка вуха ковша на осі E (приварити)"],
    ["bk_spacer_Q", 1, bush_od_small, pin_JQ + 0.5, link_w_in, "Розпірна втулка осі Q між вухами ковша (приварити до обох вух)"]]);
echo(BOM_PINS = [            // [ключ, к-сть, діаметр, довжина, назва]
    ["pin_A", 1, pin_A, boom_foot_boss_len + 42, "Палець осі A (шкворінь ГАЗ-53 / 40Х)"],
    ["pin_B", 1, pin_B, boom_tube_w + 2*plate_clevis + 24, "Палець осі B"],
    ["pin_E", 1, pin_E, pin_E_len, "Палець осі E (ківш): зафіксований у вухах ковша"],
    ["pin_R", 1, pin_R, stick_tube_w + 2*plate_boss + 22, "Палець осі коромисла R"],
    ["pin_CD", 2, boom_cyl_pin, clevis_gap_30 + 2*plate_clevis + 20, "Пальці циліндра стріли C, D (ШС30)"],
    ["pin_FH", 2, stick_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20, "Пальці баз циліндрів F, H (ШС25)"],
    ["pin_G", 1, stick_cyl_pin, stick_pack_w + 20, "Палець штока циліндра рукояті G"],
    ["pin_JQ", 2, pin_JQ, pin_JQ_len, "Пальці J (шток циліндра ковша) і Q (тяга–ківш)"]]);

// ---- Дані для інтерактивного перегляду (tools/viewer.py): локальні точки шарнірів, довжини ланок, межі кутів, пальці.
// Позу (світові точки) браузер складає за тими самими формулами, що й функції pt_*() вище.
// view_all — усі деталі перегляду ОДНИМ запуском (для OpenSCAD-WASM у браузері, tools/viewer-wasm): i-та деталь зсунута на i·view_spacing
// уздовж Y, сторінка розрізає сітку назад за координатою Y. Порядок = список view_parts.
view_parts = ["post", "boom", "v_stick", "bucket", "v_rocker", "v_link", "v_cyl_boom_body", "v_cyl_boom_rod",
              "v_cyl_stick_body", "v_cyl_stick_rod", "v_cyl_bucket_body", "v_cyl_bucket_rod"];
view_spacing = 5000;
module view_all() { for (i = [0 : len(view_parts) - 1]) translate([0, i * view_spacing, 0]) part_by_name(view_parts[i]); }
echo(VIEW = [["parts", view_parts], ["spacing", view_spacing], ["B_l", B_l], ["D_l", D_l], ["F_l", F_l], ["C_w", C_w], ["E_s", E_s], ["G_s", G_s], ["H_s", H_s], ["R_s", R_s],
    ["ear", bucket_ear], ["rocker_L", rocker_L], ["link_L", link_L], ["tip", bucket_tip], ["ground", ground_below_A],
    ["lim_boom", [boom_angle_min, boom_angle_max]], ["lim_stick", [stick_angle_min, stick_angle_max]], ["lim_bucket", [bucket_angle_min, bucket_angle_max]],
    ["cyl_boom", [boom_cyl_closed, boom_cyl_stroke]], ["cyl_stick", [stick_cyl_closed, stick_cyl_stroke]], ["cyl_bucket", [bucket_cyl_closed, bucket_cyl_stroke]],
    ["angles", [boom_angle, stick_angle, bucket_angle]],
    ["pins", [["A", pin_A, boom_foot_boss_len + 42], ["B", pin_B, boom_tube_w + 2*plate_clevis + 24], ["C", boom_cyl_pin, boom_foot_boss_len + 42],
              ["D", boom_cyl_pin, clevis_gap_30 + 2*plate_clevis + 20], ["F", stick_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20], ["G", stick_cyl_pin, stick_pack_w + 20],
              ["H", bucket_cyl_pin, clevis_gap_25 + 2*plate_clevis + 20], ["E", pin_E, pin_E_len], ["R", pin_R, link_w_in + 20], ["J", pin_JQ, pin_JQ_len], ["Q", pin_JQ, pin_JQ_len]]]]);

// ---- Стінки труб (розгортка для ескізів з 4 боків): труба вздовж +X у власній системі, стінка вирізається шаром і проєктується
module tube_local(name) {
    if (name == "boom_seg1") rotate([0, boom_alpha1, 0]) boom_seg1();
    else if (name == "boom_seg2") rotate([0, boom_alpha1 - boom_bend, 0]) translate(-p3(K_l)) boom_seg2();
    else if (name == "stick") stick_body();
    else echo(str("!!! невідома труба: ", name));
}
module tube_face_2d(name, face) {
    h = name == "stick" ? stick_tube_h : boom_tube_h; w = name == "stick" ? stick_tube_w : boom_tube_w; t = name == "stick" ? stick_tube_t : boom_tube_t;
    // Переріз стінки площиною біля зовнішньої поверхні (projection(cut = true)). Раніше проєктувалась «тінь» шару стінки:
    // об'ємна проєкція давала «ключові» контури (отвір зливався із зовнішнім контуром) і діагоналі в ескізі.
    m = 1;   // глибина площини перерізу від ЗОВНІШНЬОЇ поверхні: розмітку роблять зовні, тож довжини косих різів мають бути зовнішні (похибка ≤ 1·tg кута різу)
    if (face == "top")         projection(cut = true) translate([0, 0, -(h/2 - m)]) tube_local(name);
    else if (face == "bottom") projection(cut = true) translate([0, 0, h/2 - m]) tube_local(name);
    else if (face == "left")   projection(cut = true) translate([0, 0, w/2 - m]) rotate([-90, 0, 0]) tube_local(name);
    else if (face == "right")  projection(cut = true) translate([0, 0, -(w/2 - m)]) rotate([-90, 0, 0]) tube_local(name);
}

if (part == "assembly") assembly();
else if (part == "flat") flat(flat_name);
else if (part == "tubeface") tube_face_2d(tube_name, tube_face);
else if (part == "view_all") view_all();
else if (part == "overlap" || part == "collide") intersection() { part_by_name(ov_a); part_by_name(ov_b); }
else part_by_name(part);
