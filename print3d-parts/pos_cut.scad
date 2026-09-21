// Контури деталей у перерізі — для креслення «де саме стають накладні деталі».
// Модель підключається як бібліотека і НЕ змінюється.
//
//   openscad -o out.svg -D 'part="none"' -D 'own="boom"' -D 'k="F_tower"' -D 'ycut=19.5' pos_cut.scad
//   openscad -o geo.echo -D 'part="none"' -D 'k=""' pos_cut.scad      // тільки числа
//
// projection(cut=true) ріже площиною z=0, а пластини вузлів лежать у площині XZ
// (товщина — уздовж Y). Тому спершу translate підсуває потрібний зріз у y=0, і лише
// потім rotate([90,0,0]) кладе його на z=0. Зворотний порядок дає порожній файл:
// поворот уже переніс Y у Z, і зсув по Y нічого не ріже. На деталях на всю ширину
// (ycut = 0) помилка непомітна — саме тому її легко не побачити.

include <../scad/excavator_boom.scad>
assert(!is_undef(boom_tube_h) && !is_undef(cover_half), "scad/excavator_boom.scad не підключився");

k = "";        // ключ $sel деталі
own = "boom";  // вузол, у якому вона живе
ycut = 0;      // на якій відстані вздовж Y брати переріз

if (k == "") {
    echo(GEO = [
        // системи координат вузлів
        ["alpha1", boom_alpha1],                 // нахил 1-го сегмента до хорди
        ["u2_ang", boom_alpha1 - boom_bend],     // нахил 2-го сегмента
        ["K", K_l], ["D_org", D_org],
        ["F_hole", F_l], ["D_hole", D_l],
        ["H_hole", H_s], ["sH", bucket_cyl_sH],
        ["E_hole", [0, 0]], ["Q_hole", bucket_ear],
        ["bk_top_x", bucket_top_x], ["bk_lip_y", bucket_lip_y],
        // поверхні, на які стають накладні деталі (у системі свого вузла)
        ["surf_F", boom_tube_h/2 + plate_gusset],
        ["surf_D", -boom_tube_h/2 - plate_boss],
        ["surf_H", stick_tube_h/2 + plate_boss],
        // проміжки між пластинами пар, товщина пластини
        ["gap_F", clevis_gap_25], ["gap_D", clevis_gap_30],
        ["gap_H", clevis_gap_25], ["gap_E", link_w_in],
        ["plate", plate_clevis], ["ear_t", bucket_ear_t],
        // ширина й товщина пластини-бази
        ["base_F", [boom_tube_w, plate_gusset]],
        ["base_D", [boom_tube_w, plate_boss]],
        ["base_H", [stick_tube_w, plate_boss]],
        ["base_E", [bucket_width, bucket_top_t]]]);
} else {
    projection(cut = true) rotate([90, 0, 0]) translate([0, -ycut, 0]) {
        $sel = k; $one = true;
        part_by_name(own);
    }
}
