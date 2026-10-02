// =============================================================================
//  Циліндри друкованої моделі 1:5 на шпильці M5×0.8 і моторедукторі N20
//
//  Шпилька — шток, вона НЕ крутиться: на її хвості поршень — сталева гайка M5 на клею, що ковзає
//  в шестигранному каналі гільзи. Ходова гайка M5 (латунна) — у шестерні в голові циліндра (біля
//  виходу штока), шестерня — на підшипнику 698ZZ. N20 стоїть паралельно, збоку,
//  корпусом уздовж гільзи; шестерня на його валу крутить шестерню гайки. Редуктор N20
//  утоплено в гніздо голови поруч із підшипником: інакше вал 10 мм не дістав би шестерні.
//
//  Датчики й магніти вставляються після друку: усі гнізда відкриті назовні (Холли кінцевиків —
//  радіально з боку приливів, латчі енкодера — з переднього торця, магніти — з торця шестерні
//  й грані гайки-поршня). Ходова гайка M5 — на паузі друку (gear) або після друку на клей (gear_glue).
//
//  Зворотний зв'язок:
//    енкодер  — 2 магніти Ø2×1 (N і S назустріч) у торці шестерні гайки, 2 латчі
//               Холла SS41F у передній стінці під 90° → квадратура,
//               4 фронти на оберт гайки = 0.2 мм ходу;
//    кінцевики — магніт Ø2×1 (той самий, що в енкодері) на грані гайки-поршня і 2 лінійні датчики
//               Холла SS49E: «розкритий» — у приливі гільзи одразу за головою, «зведений» —
//               у задній кришці. Упори механічні (поршень об голову / об дно кришки); точку
//               спрацювання задає прошивка (~1.5–2 мм до упору).
//
//  Довжини, хід, вушка й зовнішній Ø гільзи — з моделі (scad/excavator_boom.scad), 1:SC;
//  модель підключається як бібліотека й не змінюється. Мотор, шестерні й розміри гільзи —
//  сталі нижче; calc.py читає їх звідси ж і рахує, чи мотор тягне (CALC.md).
//
//  openscad -D 'cyl="stick"' -D 'pp="asm"' -D 'ext=40' m5_cyl.scad     — збірка, висунутий на 40 мм
//  pp: asm | cut | headcut (розрізи) | tube | head_rear | head_front | gear | gear_glue | pinion | cap | eye
//      pair, collide — перевірки make.sh
// =============================================================================
include <../../scad/excavator_boom.scad>
// Невдалий include — не помилка: модулі стають порожні, а STL валідними й порожніми
assert(!is_undef(boom_cyl_closed), "scad/excavator_boom.scad не підключився");
part = "none";

/* [Мотор і шестерні] */
SC = 5;                     // масштаб набору (print3d-parts/parts.scad; calc.py звіряє)
MOTOR = [298, 60];          // 12GAN20-298, 60 об/хв — вибір; що дали б інші N20 — у CALC.md
GEAR_M = 0.6; GEAR_ALPHA = 20;
Z_NUT = 27;                 // шестерня гайки: менша не вміщає гайку S8 і два магніти Ø2
Z_PIN = [27, 27, 27];       // шестерня мотора: стріла, рукоять, ківш; 27 = 1:1 (вибір)
// Поршень — сталева гайка M5 (виміряна): під ключ, по вершинах, висота. Не та, що в шестерні (там латунна, M5_NUT_*)
PISTON = [7.9, 8.97, 4.0];
PUCK = 4.0;                 // довжина поршня = висота гайки-поршня (calc.py читає звідси)
REAR_WALL = 1.2;            // дно кришки
EYE_LEN = 9.0;              // вісь вушка → корпус (як eye_len 45 у моделі), з обох кінців
FRONT_GAP = 0.5;            // шийка вушка штока ↔ ніс голови у зведеному

/* [Вибір] */
cyl = "stick";      // boom | stick | bucket
pp = "asm";
ext = 0;            // висування штока, друковані мм (0…хід)
// Кут мотора навколо осі циліндра, °: 0 = +Y (ліворуч, якщо дивитись від колони на ківш), 90 = +Z.
// Усі три ліворуч: мотори й джгути на одному боці, поза площиною механізму (make.sh collide: чисто)
MOTOR_PHI = [0, 0, 0];

/* [Що показати] */
// Лише для збірки й розрізів (pp = asm | cut | headcut): зняти зайве й зазирнути всередину.
// Перевірки make.sh беруть деталі напряму, галочки їх не зачіпають.
show_tube = true;       // гільза
show_head_rear = true;  // голова, задня частина
show_head_front = true; // передня стінка з носом
show_nut_gear = true;   // шестерня гайки
nut_glue = false;       // шестерня під гайку на клей (gear_glue) замість гайки на паузі друку
show_pinion = true;     // шестерня мотора
show_cap = true;        // задня кришка з вушком
show_piston = true;     // поршень — сталева гайка
show_eye = true;        // вушко штока
show_screw = true;      // шпилька й гайка M5
show_bearing = true;    // підшипник 698ZZ
show_motor = true;      // моторедуктор N20
show_magnets = true;    // магніти
show_halls = true;      // датчики Холла

/* [Допуски друку] */
FIT = 0.15;         // радіальний зазор посадок, мм
// 698ZZ: гніздо на BRG_CLR ширше за кільце, тримають його 8 ребер з вершинами на Ø19 + PRESS;
// надруковані ребра виходять трохи товщими й зминаються при запресовуванні (перша проба: не лізло без ребер)
PRESS = 0.0;
BRG_CLR = 0.4;      // гніздо й камера перед ним — Ø19.4: підшипник проходить крізь камеру вільно
HUB_FIT = 0.1;      // маточина шестерні на стільки тонша за отвір підшипника; сіла вільно — крапля клею
SHAFT_FIT = 0.35;   // отвір шестерні мотора під вал Ø3.05 з лиською (0.05 — не наліз)
PISTON_FIT = 0.25;  // зазор гайки-поршня до граней шестигранного каналу гільзи, на бік
MAG_GAP = 0.3;      // магніт на грані гайки ↔ дно каналу під нього в гільзі
HOLE_SHRINK = 0.3;  // надрукований отвір під шпильку виходить меншим на стільки (0.1 — замало)
MAG_CLR = [0.25, 0.3];    // гнізда магнітів: +Ø, +глибина (було 0.1 / 0.05–0.1 — затісно); магніт сідає на дно
NUT_CLR = 0.3;      // шестерня під гайку на клей: запас гнізда по розміру під ключ

/* [Hidden] */
$fn = 72;
eps = 0.01;
KEYS = ["boom", "stick", "bucket"];
ki = search([cyl], KEYS)[0];

// --- покупне
M5_D = 5.0; M5_NUT_S = 8.0;         // номінал: від нього — прохідні отвори
// висота гайки: DIN 934 — 4.0, ISO 4032 — до 4.7; шестерня (GEAR_B) розрахована на гайку до 4.8.
// Для гайки на паузі друку постав висоту своєї гайки — інакше в гнізді буде осьовий люфт
M5_NUT_H = 4.8;
STUD_D = 4.85;                      // виміряна шпилька (накатана різьба вужча за номінал)
// Отвір під нарізання різьби самою шпилькою: зовнішній Ø мінус ~60 % профілю M5×0.8 (2 × 0.6 × 0.541·P),
// плюс HOLE_SHRINK — надрукований отвір виходить меншим. Різьба нарізається від руки, без розсвердлювання.
TAP_D = STUD_D - 2 * 0.6 * 0.541 * 0.8 + HOLE_SHRINK;   // 4.63
BRG = [8, 19, 6];                   // 698ZZ: d, D, B
N20_W = 12; N20_T = 10; N20_GB = 9; N20_MOT = 15; N20_SHAFT = [3.05, 2.5, 10];  // Ø (виміряний), лиска, довжина
N20_HOLE = 9;                       // два M1.6 на торці редуктора, між осями
SHAFT_SHORT = 0.6;                  // кінець вала не доходить до переднього торця шестерні мотора
HALL = [4.1, 3.1, 1.6];             // плаский TO-92 (SS41F, SS49E: 4.1×3.0×1.6): ширина, висота, товщина
HALL_FIT = 0.2;                     // запас гнізда по ширині й висоті: датчик вставляється після друку
LEAD_W = 3.2;                       // проріз під виводи: 3 ніжки з кроком 1.27 займають 2.97
MAG_ENC = [2.0, 1.0];               // магніт енкодера Ø×h
MAG_LIM = MAG_ENC;                  // магніт поршня — той самий: один розмір на все

// --- голова (осьовий стек від заднього торця x_hr)
LIP = 1.8; TUBE_IN = 1.0;           // губа й глибина паза під торець гільзи
GAP_SH = 0.3; GEAR_B = 5.7; GAP_F = 0.4; FWALL = 2.0;   // шестерні: гайка до 4.8 + стінки по 0.4 + запас
HEAD_CORE = LIP + BRG[2] + GAP_SH + GEAR_B + GAP_F + FWALL;   // 16.2; calc.py складає з тих самих сталих
assert(GEAR_B - M5_NUT_H - 0.1 >= 0.8, "гайка не вміщається в шестерню зі стінками по 0.4");
R_MAG = 5.75;                       // радіус магнітів енкодера: навпроти граней гайки, посередині між гранню й западиною
WALL = 1.2;
NOSE_D = 8.0; NOSE_BORE = 5.3;
// Передня стінка стягується трьома саморізами M2 так, щоб вісь була всередині трикутника кріплення
// (з двома вушками на 150°/210° стінку підважувало з боку мотора): два — у перешийках між камерою шестерні
// гайки й камерою шестерні мотора, в обрисі голови, без вушок; третій — у вушку на 200° (на 180° —
// канавка ніжок латча B; на 120° вушко чіпляло вилку стріли).
EAR_R = 2.2; EAR_ANG = [200];       // вушка з приливом (кут від напрямку на мотор)
WAIST = [8.45, 7.75];               // саморізи в перешийках: уздовж напрямку на мотор і ± по дотичній, мм
FRONT_CHAMF = 1.4;                  // фаска 45° верхнього (+Z) переднього краю голови — під вилку D на стрілі

// --- дані циліндра з моделі
function mv(k, n) = let(t = [
    ["closed", boom_cyl_closed, stick_cyl_closed, bucket_cyl_closed],
    ["stroke", boom_cyl_stroke, stick_cyl_stroke, bucket_cyl_stroke],
    ["bore",   boom_cyl_bore,   stick_cyl_bore,   bucket_cyl_bore],
    ["pin",    boom_cyl_pin,    stick_cyl_pin,    bucket_cyl_pin],
    ["wall",   6.5, 5, 5]]) t[search([n], t)[0]][1 + search([k], KEYS)[0]];
// міжосьова пари з корекцією (inv αw = 2·tgα·(x1+x2)/(z1+z2) + inv α) — та сама формула, що в calc.py
function _inv(a) = tan(a) - a * PI / 180;
function _aw(t, lo = 0, hi = 60, n = 40) = n == 0 ? (lo + hi) / 2 :
    let(m = (lo + hi) / 2) _inv(m) < t ? _aw(t, m, hi, n - 1) : _aw(t, lo, m, n - 1);
function center_dist(z1, x1, z2, x2) = let(t = 2 * tan(GEAR_ALPHA) * (x1 + x2) / (z1 + z2) + _inv(GEAR_ALPHA))
    GEAR_M * (z1 + z2) / 2 * cos(GEAR_ALPHA) / cos(_aw(t));
function shift(z) = round(max(0, (17 - z) / 17) * 100) / 100;   // проти підрізання при z < 17

L0    = mv(cyl, "closed") / SC;
S     = mv(cyl, "stroke") / SC;
OD    = (mv(cyl, "bore") + 2 * mv(cyl, "wall")) / SC;
ID    = PISTON[0] + 2 * PISTON_FIT;     // канал гільзи — шестигранник, ID — під ключ (однаковий у всіх трьох)
PIN   = mv(cyl, "pin") / SC;
R_PUCK = PISTON[0] / 2;                // грань гайки-поршня: на ній магніт кінцевиків
assert(PUCK == PISTON[2], "PUCK має дорівнювати висоті гайки-поршня");
EYE_OD = (mv(cyl, "pin") + 28) / SC;
EYE_W  = (mv(cyl, "pin") >= 30 ? cyl_eye_w_30 : cyl_eye_w_25) / SC;
EYE_R  = EYE_OD / 2;
ZP = Z_PIN[ki]; XP = shift(ZP); A = center_dist(Z_NUT, 0, ZP, XP);
MOTOR_NAME = str("12GAN20-", MOTOR[0], ", ", MOTOR[1], " об/хв");
PHI = MOTOR_PHI[ki];

X_CI = EYE_LEN + REAR_WALL;           // дно кришки = упор поршня (зведений); стакан — з 9 мм, як корпус у моделі:
                                      // ближче до вушка — щоки вилки бази
X_HR = X_CI + S + PUCK;               // задній торець голови = упор поршня (розкритий)
X_BRG = X_HR + LIP;
X_GEAR = X_BRG + BRG[2] + GAP_SH;
X_FW = X_GEAR + GEAR_B + GAP_F;       // стик голова/передня стінка
X_HF = X_FW + FWALL;
X_NOSE = L0 - EYE_LEN - FRONT_GAP;
SCREW_L = L0 - PIN / 2 - 0.8 - X_CI;
// торець редуктора: утоплений у голову настільки, щоб вал 10 мм пройшов шестерню мотора
X_MF = X_GEAR + GEAR_B - SHAFT_SHORT - N20_SHAFT[2];
assert(X_NOSE >= X_HF, str(cyl, ": голова не влазить у зведену довжину"));
assert(X_MF >= X_HR, "вал мотора довший, ніж треба: редуктор вилазить за задній торець голови");

// шестерні
R_TIP_G = GEAR_M * (Z_NUT / 2 + 1);
R_CH = R_TIP_G + 0.5;                 // камера шестерні гайки
R_TIP_P = GEAR_M * (ZP / 2 + 1 + XP);
R_LOBE = R_TIP_P + 0.5 + WALL;        // прилив під шестерню мотора
R_IN = max(R_CH, (BRG[1] + BRG_CLR) / 2); // камера шестерні гайки: крізь неї вставляється підшипник
R_HEAD = R_IN + WALL;
assert(A >= OD / 2 + N20_T / 2 + 0.5, "мотор ближче до гільзи, ніж можна");
// редуктор стоїть поруч із підшипником в одному перерізі — між гніздами лишається стінка
// підшипник вставляється з переднього торця крізь камеру шестерні (з першою пробою камера була вужча за нього)
assert(R_IN >= BRG[1] / 2 + 0.1, "камера шестерні вужча за підшипник: 698ZZ не дійде до гнізда");
assert(A - N20_T / 2 - FIT - R_IN >= 1.0, "гніздо редуктора впирається в гніздо підшипника");
// саморізи в перешийку: отвір Ø2.3 передньої стінки — не ближче 0.8 до камер і гнізда редуктора
assert(OD / 2 - 0.6 - ID / 2 >= 1.0, "канавка дротів проти грані шестигранника: стінка тонша за 1 мм");
assert(norm(WAIST) - R_IN >= 1.15 + 0.6 && norm(WAIST - [A, 0]) - (R_TIP_P + 0.5) >= 1.15 + 0.6
       && A - N20_T / 2 - FIT - WAIST[0] >= 1.15 + 0.8, "саморіз у перешийку голови впирається в камеру");

// кути навколо осі X (0 = +Y, 90 = +Z)
function dirv(a) = [0, cos(a), sin(a)];
PHI_SENS = PHI + 180;                 // датчики кінцевиків, магніт поршня
ENC_ANG  = [PHI + 90, PHI + 180];     // латчі енкодера — 90° один від одного

// -----------------------------------------------------------------------------
//  Допоміжне: усе будується у площині YZ (профіль) і витягується вздовж X
// -----------------------------------------------------------------------------
module along(x0, x1) { translate([x0, 0, 0]) rotate([0, 90, 0]) rotate([0, 0, 90]) linear_extrude(x1 - x0) children(); }
// у профілі: вісь X профілю = Y світу, вісь Y профілю = Z світу... після rotate — перевірено на dirv()
module at_ang(a, r) { rotate([a, 0, 0]) translate([0, r, 0]) children(); }       // точка на радіусі r під кутом a (3D)
// те саме в профілі; вісь X дитини — уздовж радіуса, тож square([радіально, по дотичній]) однаковий за будь-якого кута
module p2_at(a, r) { translate([r * cos(a), r * sin(a)]) rotate(a) children(); }

// Профіль каналу гільзи: шестигранник гранню на PHI_SENS + паз під магніт на грані гайки; c — стиснути на c
module bore_profile(c = 0) {
    rotate(PHI_SENS + 30) circle(d = (ID - 2 * c) / cos(30), $fn = 6);
    p2_at(PHI_SENS, 0) translate([0, -(MAG_SLOT[1] / 2 - c)]) square([MAG_SLOT[0] - c, MAG_SLOT[1] - 2 * c]);
}
MAG_SLOT = [R_PUCK + MAG_LIM[1] + MAG_GAP, MAG_LIM[0] + 0.4];   // паз магніту: радіус дна, ширина

// Гніздо датчика кінцевика на боці PHI_SENS: центр по осі x, дно на радіусі r, відкрите назовні —
// датчик вставляється після друку, чутливою стороною до гільзи. Проріз під ніжки йде від гнізда до x_lead
// (у будь-який бік: ніжки дивляться туди). У rotate([a, 0, 0]) радіус — локальна Y, дотична — Z.
module sens_pocket(x, r, x_lead) {
    hl = HALL[1] + HALL_FIT; hw = HALL[0] + HALL_FIT;
    translate([x - hl / 2, 0, 0]) rotate([PHI_SENS, 0, 0]) translate([0, r, -hw / 2]) cube([hl, 10, hw]);
    translate([min(x, x_lead), 0, 0]) rotate([PHI_SENS, 0, 0]) translate([0, r, -LEAD_W / 2]) cube([abs(x_lead - x), 10, LEAD_W]);
}
module sens_body(x, r) {             // сам датчик (для збірки й перевірки перетинів)
    translate([x - HALL[1] / 2 + 0.05, 0, 0]) rotate([PHI_SENS, 0, 0])
        translate([0, r + 0.05, -HALL[0] / 2 + 0.05]) cube([HALL[1] - 0.1, HALL[2] - 0.1, HALL[0] - 0.1]);
}
// канавка дротів «зведеного» — на 60° від осі датчиків, навпроти середини грані шестигранника (стінка під нею
// 1.2 мм у рукояті й ковша): на осі датчиків зсередини паз магніту, а на ±30° — вершини шестигранника
GROOVE_ANG = 60;
X_SENS_EXT = X_HR - PUCK / 2;          // датчик «розкритий»: навпроти магніту поршня на упорі
X_SENS_RET = X_CI + PUCK / 2;          // датчик «зведений»

// евольвентна шестерня (2D), корекція x, бічний зазор bl
function inv_(a) = tan(a) - a * PI / 180;
module gear2d(z, m, x = 0, alpha = 20, bl = 0.06) {
    r = m * z / 2; rb = r * cos(alpha); ra = r + m * (1 + x); rf = r - m * (1.25 - x);
    psi = (PI / 2 + 2 * x * tan(alpha)) / z - bl / (2 * r);
    r0 = max(rb, rf);
    half = function(rr) max(0.5, (psi + inv_(alpha) - inv_(acos(min(1, rb / rr)))) * 180 / PI);
    n = 8;
    rs = [for (i = [0:n]) r0 + (ra - r0) * i / n];
    union() {
        circle(r = rf, $fn = z * 3);
        for (k = [0:z - 1]) rotate(k * 360 / z) polygon(concat(
            [[rf * 0.95 * cos(-half(r0)), rf * 0.95 * sin(-half(r0)) ]],
            [for (rr = rs) [rr * cos(-half(rr)), rr * sin(-half(rr))]],
            [for (i = [n:-1:0]) let(rr = rs[i]) [rr * cos(half(rr)), rr * sin(half(rr))]],
            [[rf * 0.95 * cos(half(r0)), rf * 0.95 * sin(half(r0))]]));
    }
}

// контур голови в профілі (YZ): коло навколо осі + прилив навколо вала мотора
module head_outline(extra = 0) {
    hull() {
        circle(r = R_HEAD + extra);
        p2_at(PHI, A) circle(r = R_LOBE + extra);
    }
    for (a = EAR_ANG) p2_at(PHI + a, R_IN + EAR_R) circle(r = EAR_R + WALL * 0.6 + extra);
}
module ear_holes(d) {
    for (a = EAR_ANG) p2_at(PHI + a, R_IN + EAR_R) circle(d = d, $fn = 24);
    for (s = [-1, 1]) rotate(PHI) translate([WAIST[0], s * WAIST[1]]) circle(d = d, $fn = 24);
}
module motor_profile(c = 0) {        // переріз N20: 12 уздовж дотичної, 10 радіально
    p2_at(PHI, A) square([N20_T + 2 * c, N20_W + 2 * c], center = true);
}

// -----------------------------------------------------------------------------
//  Деталі (у системі циліндра, вісь +X від пальця бази)
// -----------------------------------------------------------------------------
// Гільза: друкується стоячи на задньому торці. Канал усередині — шестигранник під гайку-поршень
// (гранню до датчиків), вона ж не дає шпильці провертатися; уздовж грані — паз під магніт на гайці.
// Прилив датчика «розкритий» біля переднього торця (той «горбик» на гільзі), канавка під дроти.
module tube() {
    x0 = X_CI; x1 = X_HR + TUBE_IN;
    difference() {
        union() {
            along(x0, x1) circle(d = OD);
            // прилив датчика (з фасками 45° знизу для друку)
            hull() {
                along(X_HR - 7, X_HR) p2_at(PHI_SENS, OD / 2 + 0.6) square([2.6, HALL[0] + 2 + HALL_FIT], center = true);
                along(X_HR - 9.6, X_HR - 9.5) p2_at(PHI_SENS, OD / 2 - 0.5) square([0.2, HALL[0] + 2 + HALL_FIT], center = true);
            }
            // мотор тримають два M1.6 на торці редуктора; хвіст — крапля клею до гільзи (хомут з фаскою під
            // друк виходив плавником більшим за сам мотор)
        }
        // шестигранник гранню на PHI_SENS і паз під магніт на цій грані — наскрізь: гайка з магнітом проходить
        // ще не вклеєну гільзу, а голова ловить паз як шпонку
        along(x0 - 1, x1 + 1) bore_profile();
        // гніздо датчика «розкритий», дно — на зовнішній поверхні гільзи. Ніжки — до кришки, прорізом крізь
        // увесь прилив: з боку голови від корпусу датчика до її торця лише 0.35 мм, ніжки не загнути
        sens_pocket(X_SENS_EXT, OD / 2, X_HR - 10);
        // канавка під дроти датчика «зведений»: від заднього торця до голови, збоку від приливу
        along(x0 - 1, X_HR) p2_at(PHI_SENS + GROOVE_ANG, OD / 2) square([1.4, 1.2], center = true);
        // мітка орієнтації на передньому торці (проти мотора — там і датчики)
        along(x1 - 1.5, x1 + 1) p2_at(PHI_SENS, OD / 2) circle(d = 0.8, $fn = 12);
    }
}

// Голова, задня частина: губа (упор поршня), гніздо 698ZZ, камера шестерень, гніздо редуктора N20.
// Друкується заднім торцем на стіл: кишені догори, крім гнізда редуктора — у нього стеля-міст 10 мм.
module head_rear() {
    difference() {
        along(X_HR, X_FW) head_outline();
        // паз під торець гільзи
        // острівець усередині паза — профіль каналу гільзи з зазором FIT: шестигранник із виступом у паз магніту,
        // тож гільза стає лише одним боком (паз — до датчиків); торець острівця — упор гайки-поршня
        along(X_HR - 1, X_HR + TUBE_IN) difference() { circle(d = OD + 2 * FIT); bore_profile(FIT); }
        // отвір шпильки
        along(X_HR - 1, X_BRG + 1) circle(d = M5_D + 0.6);
        // виїмка під внутрішнє кільце (губа тримає лише зовнішнє)
        along(X_BRG - 0.25, X_BRG + 0.1) circle(d = (BRG[0] + BRG[1]) / 2);
        // гніздо підшипника й камера шестерні гайки — одним діаметром 2·R_IN: підшипник заходить з переднього торця
        along(X_BRG, X_FW + 1) circle(r = R_IN);
        hull() { along(X_FW - 0.5, X_FW - 0.5 + eps) circle(r = R_IN); along(X_FW, X_FW + 1) circle(r = R_IN + 0.5); }   // заходка
        // камера шестерні мотора — лише перед підшипником
        along(X_BRG + BRG[2], X_FW + 1) p2_at(PHI, A) circle(r = R_TIP_P + 0.5);
        // гніздо редуктора: торець утоплено до X_MF, поруч із гніздом підшипника (міжосьова та сама)
        along(X_HR - 1, X_MF) motor_profile(FIT);
        // вал мотора, бобишка редуктора, гвинти M1.6 (голівки — у зенківках з боку камери)
        along(X_MF - 1, X_GEAR) p2_at(PHI, A) circle(d = N20_SHAFT[0] + 0.6, $fn = 24);
        along(X_MF - 1, X_MF + 0.6) p2_at(PHI, A) circle(d = 4.4, $fn = 24);
        for (s = [-1, 1]) {
            along(X_MF - 1, X_GEAR) p2_at(PHI, A) translate([0, s * N20_HOLE / 2]) circle(d = 1.8, $fn = 16);
            along(X_GEAR - 1.4, X_GEAR + 1) p2_at(PHI, A) translate([0, s * N20_HOLE / 2]) circle(d = 3.3, $fn = 16);
        }
        // вушка M2: отвір під саморіз
        along(X_HR - 1, X_FW + 1) ear_holes(1.6);
        // вихід дротів датчиків на боці датчиків
        along(X_HR - 1, X_FW + 1) p2_at(PHI_SENS, R_HEAD) square([3.0, 2.0], center = true);
    }
    brg_ribs();
}
// Ребра, що тримають 698ZZ у гнізді: вершини на Ø(BRG[1] + PRESS), угорі — заходка до стінки гнізда,
// щоб кільце не зрізало ребро, а м'яло
module brg_ribs() {
    rc = (BRG[1] + PRESS) / 2 + 0.5;          // вісь ребра Ø1: вершина — на rc − 0.5
    for (k = [0:7]) let(a = PHI + 22.5 + k * 45) hull() {
        along(X_BRG, X_BRG + BRG[2] - 0.8) p2_at(a, rc) circle(d = 1.0, $fn = 12);
        along(X_BRG + BRG[2] - eps, X_BRG + BRG[2]) p2_at(a, R_IN + 0.3) circle(d = 0.6, $fn = 12);
    }
}

// Голова, передня стінка з носом-напрямною. Латчі енкодера — у кишенях на передньому торці
// (чутливою стороною до шестерні, дно 0.4 мм), виводи — канавками назовні.
module head_front() {
    difference() {
        union() {
            along(X_FW, X_HF) head_outline();
            along(X_HF - eps, X_NOSE) circle(d = NOSE_D);
        }
        along(X_FW - 1, X_NOSE + 1) circle(d = NOSE_BORE);
        along(X_FW - 1, X_HF - 0.4) circle(d = M5_D + 1.2);     // не труться об торець гайки
        // гнізда латчів відкриті на передній торець: вставляються після друку, ніжками назовні
        for (a = ENC_ANG) {
            translate([X_HF - HALL[2], 0, 0]) rotate([a, 0, 0])
                translate([0, R_MAG - (HALL[1] + HALL_FIT) / 2, -(HALL[0] + HALL_FIT) / 2])
                cube([HALL[2] + 1, HALL[1] + HALL_FIT, HALL[0] + HALL_FIT]);
            translate([X_HF - 1.0, 0, 0]) rotate([a, 0, 0]) translate([0, R_MAG, -LEAD_W / 2]) cube([2, R_HEAD + 5, LEAD_W]);
        }
        along(X_FW - 1, X_HF + 1) ear_holes(2.3);
        // фаска у площині механізму, згори: стріла на −90° підходить вилкою D до переднього торця голови
        translate([X_HF, 0, R_HEAD - FRONT_CHAMF]) rotate([0, 45, 0]) translate([-30, -50, 0]) cube([60, 100, 30]);
    }
}

// Шестерня гайки, маточина — у підшипник, магніти — на передньому торці навпроти граней гайки.
// glue = false: гайка закладається на паузі друку (замкнена з обох боків);
// glue = true:  гніздо відкрите на передній торець, гайка вставляється після друку й садиться на клей.
//               Дно гнізда — з боку маточини; назад гайку тримає клей, а зірвану — передня стінка голови.
module nut_gear(glue = false) {
    nut_h = glue ? M5_NUT_H + NUT_CLR / 2 : M5_NUT_H + 0.1;
    nut_s = M5_NUT_S + (glue ? NUT_CLR : 0.1);
    nut_x0 = glue ? X_GEAR + GEAR_B - nut_h : X_GEAR + (GEAR_B - nut_h) / 2;
    difference() {
        union() {
            along(X_GEAR, X_GEAR + GEAR_B) rotate(PHI) gear2d(Z_NUT, GEAR_M, 0, GEAR_ALPHA);   // зуб — на мотор
            along(X_GEAR - GAP_SH, X_GEAR + eps) circle(d = BRG[0] + 1.4);   // заплечик: лише внутрішнє кільце
            along(X_BRG, X_GEAR) circle(d = BRG[0] - HUB_FIT);               // маточина
        }
        along(X_BRG - 1, X_GEAR + GEAR_B + 1) circle(d = M5_D + 0.4);
        along(nut_x0, nut_x0 + nut_h + (glue ? 1 : 0))
            rotate(30 + PHI) circle(d = nut_s / cos(30), $fn = 6);           // грані — до магнітів
        for (a = [0, 180]) translate([X_GEAR + GEAR_B - MAG_ENC[1] - MAG_CLR[1], 0, 0]) rotate([PHI + a, 0, 0])
            translate([0, R_MAG, 0]) rotate([0, 90, 0]) cylinder(d = MAG_ENC[0] + MAG_CLR[0], h = MAG_ENC[1] + 1, $fn = 24);
    }
}

module pinion() {
    translate([0, 0, 0]) rotate([PHI, 0, 0]) translate([0, A, 0]) rotate([-PHI, 0, 0])
    difference() {
        along(X_GEAR, X_GEAR + GEAR_B) rotate(PHI + 180 + 180 / ZP) gear2d(ZP, GEAR_M, XP, GEAR_ALPHA);   // западина — на гайку
        along(X_GEAR - 1, X_GEAR + GEAR_B + 1) rotate(PHI) d_shaft(SHAFT_FIT);   // лиска — так само, як на валу мотора
    }
}

// Поршень — сталева гайка M5 на хвості шпильки, на клею (покупна, не друкується). Магніт кінцевиків
// приклеюється на її грань з боку датчиків і сам тримається на сталі.
module piston(e = 0) {
    translate([e, 0, 0]) along(X_CI, X_CI + PUCK) difference() {
        intersection() { rotate(PHI_SENS + 30) circle(d = PISTON[0] / cos(30), $fn = 6); circle(d = PISTON[1]); }
        circle(d = STUD_D);
    }
}

// Задня кришка з вушком бази: гільза вклеюється в стакан; датчик «зведений» — у приливі стакана.
// Друкується стаканом донизу: дно — міст над Ø стакана, далі шийка й вушко.
module cap() {
    cup = 5.5; cod = OD + 2 * FIT + 2.0;
    // ключ: ребро на стінці стакана заходить у канавку дротів гільзи (вона йде від заднього торця),
    // тож кришка стає лише одним боком — прилив датчика над пазом магніту. Біля краю стакана ребра немає:
    // там у канавку лягають дроти «зведеного». Ребро вертикальне — друкується без підпор.
    along(X_CI, X_CI + cup - 1.5) p2_at(PHI_SENS + GROOVE_ANG, OD / 2 - 0.6 + FIT) translate([0, -(1.4 - 2 * FIT) / 2])
        square([0.6 + 0.3, 1.4 - 2 * FIT]);
    difference() {
        union() {
            along(X_CI - REAR_WALL, X_CI + cup) circle(d = cod);
            hull() {
                along(X_CI + 0.8, X_CI + cup) p2_at(PHI_SENS, cod / 2 + 0.6) square([2.6, HALL[0] + 2 + HALL_FIT], center = true);
                along(X_CI - REAR_WALL, X_CI - REAR_WALL + 0.1) p2_at(PHI_SENS, cod / 2 - 1) square([0.2, HALL[0] + 2 + HALL_FIT], center = true);
            }
            rotate([90, 0, 0]) cylinder(d = EYE_OD, h = EYE_W, center = true);
            translate([0, -EYE_W / 2, -EYE_OD * 0.35]) cube([X_CI - REAR_WALL + eps, EYE_W, EYE_OD * 0.7]);
        }
        along(X_CI, X_CI + cup + 1) circle(d = OD + 2 * FIT);
        // гніздо датчика «зведений» у приливі стакана (0.3 мм стінки до гільзи), відкрите назовні;
        // ніжки — прорізом до краю стакана, звідти дроти лягають у канавку гільзи
        sens_pocket(X_SENS_RET, OD / 2 + FIT + 0.3, X_CI + cup + 1);
        rotate([90, 0, 0]) cylinder(d = PIN, h = 20, center = true);
    }
}

// Вушко штока: M5 вкручується в шийку (нарізає PLA сама) і садиться на клей
module rod_eye(e = 0) {
    translate([L0 + e, 0, 0]) difference() {
        union() {
            rotate([90, 0, 0]) cylinder(d = EYE_OD, h = EYE_W, center = true);
            translate([-EYE_LEN, -EYE_W / 2, -EYE_OD * 0.35]) cube([EYE_LEN - PIN / 2, EYE_W, EYE_OD * 0.7]);
            translate([-EYE_LEN, 0, 0]) rotate([0, 90, 0]) cylinder(d = min(NOSE_D, EYE_OD * 0.7), h = EYE_LEN - EYE_R + 1);
        }
        rotate([90, 0, 0]) cylinder(d = PIN, h = 20, center = true);
        translate([-EYE_LEN - 1, 0, 0]) rotate([0, 90, 0]) cylinder(d = TAP_D, h = EYE_LEN - PIN / 2 - 0.8 + 1);
    }
}

// -----------------------------------------------------------------------------
//  Покупне (для збірки й розрізу)
// -----------------------------------------------------------------------------
module screw(e = 0) { translate([X_CI + e, 0, 0]) rotate([0, 90, 0]) cylinder(d = STUD_D, h = SCREW_L, $fn = 24); }
module nut(glue = false) { let(x0 = glue ? X_GEAR + GEAR_B - M5_NUT_H - NUT_CLR / 2 : X_GEAR + (GEAR_B - M5_NUT_H) / 2)
    along(x0, x0 + M5_NUT_H) difference() { rotate(30 + PHI) circle(d = M5_NUT_S / cos(30), $fn = 6); circle(d = M5_D); } }
module bearing() { along(X_BRG, X_BRG + BRG[2]) difference() { circle(d = BRG[1]); circle(d = BRG[0]); } }
module motor() {
    along(X_MF - N20_GB, X_MF) motor_profile();
    along(X_MF - N20_GB - N20_MOT, X_MF - N20_GB) intersection() { motor_profile(); p2_at(PHI, A) circle(d = N20_W); }
    along(X_MF, X_MF + N20_SHAFT[2]) p2_at(PHI, A) d_shaft(0);
}
module d_shaft(c) {                  // вал N20 з лиською (у профілі, центр — у початку)
    intersection() { circle(d = N20_SHAFT[0] + c, $fn = 24);
                     translate([N20_SHAFT[1] - N20_SHAFT[0] / 2 + c / 2 - 4, -2]) square(4); }
}
module magnets(e = 0) {
    for (a = [0, 180]) translate([X_GEAR + GEAR_B - MAG_ENC[1] - MAG_CLR[1], 0, 0]) rotate([PHI + a, 0, 0])
        translate([0, R_MAG, 0]) rotate([0, 90, 0]) cylinder(d = MAG_ENC[0], h = MAG_ENC[1], $fn = 24);
    translate([X_CI + PUCK / 2 + e, 0, 0]) rotate([PHI_SENS, 0, 0])
        translate([0, R_PUCK, 0]) rotate([-90, 0, 0]) cylinder(d = MAG_LIM[0], h = MAG_LIM[1], $fn = 24);
}
module halls() {
    for (a = ENC_ANG) translate([X_HF - HALL[2] + 0.05, 0, 0]) rotate([a, 0, 0])
        translate([0, R_MAG - HALL[1] / 2 + 0.05, -HALL[0] / 2 + 0.05]) cube([HALL[2] - 0.1, HALL[1] - 0.1, HALL[0] - 0.1]);
    sens_body(X_SENS_EXT, OD / 2);
    sens_body(X_SENS_RET, OD / 2 + FIT + 0.3);
}
// колір деталі; у розрізі ріжеться кожна окремо — тоді площина розрізу має колір своєї деталі
$CUT = false;
module cutter() { rotate([PHI + 90, 0, 0]) translate([-10, 0, -50]) cube([400, 60, 100]); }
module cc(c) { color(c) if ($CUT) difference() { children(); cutter(); } else children(); }
module buy(e = 0) {
    cc([0.75, 0.76, 0.78]) screw(e);
    cc([0.7, 0.7, 0.72]) nut();
    cc([0.55, 0.57, 0.6]) bearing();
    cc([0.85, 0.7, 0.3]) motor();
    cc([0.8, 0.1, 0.1]) magnets(e);
    cc([0.15, 0.15, 0.15]) halls();
    cc([0.6, 0.62, 0.66]) piston(e);
}
// окрема деталь за назвою — для перевірки перетинів (make.sh)
module piece(n, e) {
    if (n == "tube") tube(); else if (n == "head_rear") head_rear(); else if (n == "head_front") head_front();
    else if (n == "gear") nut_gear(); else if (n == "gear_glue") nut_gear(true);
    else if (n == "pinion") pinion(); else if (n == "cap") cap();
    else if (n == "piston") piston(e); else if (n == "eye") rod_eye(e); else if (n == "screw") screw(e);
    else if (n == "nut") nut(); else if (n == "nut_glue") nut(true); else if (n == "bearing") bearing(); else if (n == "motor") motor();
    else if (n == "magnets") magnets(e); else if (n == "halls") halls();
    else echo(str("!!! невідома деталь: ", n));
}

module cyl_asm(e) {   // збірка з галочками «Що показати»
    if (show_tube)       cc([0.2, 0.2, 0.22]) tube();
    if (show_head_rear)  cc([0.25, 0.45, 0.75]) head_rear();
    if (show_head_front) cc([0.3, 0.55, 0.85]) head_front();
    if (show_nut_gear)   cc([0.9, 0.55, 0.15]) nut_gear(nut_glue);
    if (show_pinion)     cc([0.95, 0.75, 0.2]) pinion();
    if (show_cap)        cc([0.2, 0.2, 0.22]) cap();
    if (show_piston)     cc([0.6, 0.62, 0.66]) piston(e);
    if (show_eye)        cc([0.2, 0.2, 0.22]) rod_eye(e);
    if (show_screw)      { cc([0.75, 0.76, 0.78]) screw(e); cc([0.7, 0.7, 0.72]) nut(nut_glue); }
    if (show_bearing)    cc([0.55, 0.57, 0.6]) bearing();
    if (show_motor)      cc([0.85, 0.7, 0.3]) motor();
    if (show_magnets)    cc([0.8, 0.1, 0.1]) magnets(e);
    if (show_halls)      cc([0.15, 0.15, 0.15]) halls();
}

// Нова геометрія без вушок (вушка — ті самі, що в моделі) — для перевірки зіткнень
cn_only = "";   // діагностика: лише одна деталь
module cyl_new(e) {
    difference() {
        if (cn_only != "") piece(cn_only, e);
        else union() { tube(); head_rear(); head_front(); cap(); buy(e); }
        translate([-50, -50, -50]) cube([X_CI - REAR_WALL + 50, 100, 100]);   // вушко бази й шийка
    }
}

// -----------------------------------------------------------------------------
//  Вибір
// -----------------------------------------------------------------------------
// Укладання на стіл: вісь X деталі — догори (деталі, що друкуються «стоячи»)
module up(x0) { rotate([0, -90, 0]) translate([-x0, 0, 0]) children(); }
module down(x0) { rotate([0, 90, 0]) translate([-x0, 0, 0]) children(); }

if (pp == "asm") cyl_asm(ext);
// розріз площиною через вісь шпильки й вал мотора; повернуто розрізом до −Y (камера 90,0,0)
else if (pp == "cut" || pp == "headcut") translate([pp == "headcut" ? -(X_HR + 6) : 0, 0, 0]) rotate([90 - PHI, 0, 0])
    let($CUT = true) cyl_asm(ext);
else if (pp == "tube")       up(X_CI) tube();
else if (pp == "head_rear")  up(X_HR) head_rear();
else if (pp == "head_front") up(X_FW) head_front();
else if (pp == "gear")       down(X_GEAR + GEAR_B) nut_gear();
else if (pp == "gear_glue")  down(X_GEAR + GEAR_B) nut_gear(true);   // гніздом гайки на стіл
else if (pp == "pinion")     up(X_GEAR) rotate([-PHI, 0, 0]) translate([0, 0, 0]) pinion_centered();
else if (pp == "cap")        down(X_CI + 5.5) cap();
else if (pp == "eye")        up(L0 - EYE_LEN) rod_eye();
else if (pp == "pair") intersection() { piece(pa, ext); piece(pb, ext); }
else if (pp == "collide") {
    // машина в позі (boom_angle, stick_angle, bucket_angle з -D), новий циліндр × деталь `with`
    P1 = cyl == "boom" ? C_w : cyl == "stick" ? pt_F(th_eff) : pt_H(th_eff, psi_eff);
    P2 = cyl == "boom" ? pt_D(th_eff) : cyl == "stick" ? pt_G(th_eff, psi_eff) : pt_J(th_eff, psi_eff, om_eff);
    Lm = norm(P2 - P1);
    intersection() {
        translate(p3(P1)) rotate([0, -ang2(P2 - P1), 0]) scale(SC) cyl_new((Lm - mv(cyl, "closed")) / SC);
        part_by_name(with);
    }
}
else if (pp != "none") echo(str("!!! невідома деталь: ", pp));

with = "m_stick";
pa = "tube"; pb = "motor";
module pinion_centered() { translate([0, -A * cos(PHI), -A * sin(PHI)]) pinion(); }

echo(str("=== M5 ", cyl, ": зведений ", L0, ", хід ", S, ", голова ", X_HR, "…", X_NOSE, ", шпилька ", SCREW_L,
         ", шестерні ", Z_NUT, "/", ZP, " a=", A, ", мотор ", MOTOR_NAME));
