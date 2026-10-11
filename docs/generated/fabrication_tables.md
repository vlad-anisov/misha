# Комплект для изготовления — таблицы (генерируется cad/fabrication.py)

> Концепция: перед запуском в резку сверить размеры с моделью и фактическим сортаментом. DXF — в масштабе 1:1, мм, слой CUT; все отверстия Ø13 под болты М12.

## Лазерная резка листа

| Поз. | Деталь | t, мм | Габарит, мм | Отв. | Кол-во | Файл |
|---|---|---|---|---|---|---|
| Л01 | fin_pedal | 8 | 390x50 | 12 | 2 | `fabrication/dxf/Л01_fin_pedal_t8.dxf` |
| Л02 | fin_seat | 8 | 470x50 | 18 | 2 | `fabrication/dxf/Л02_fin_seat_t8.dxf` |
| Л03 | foot_plate | 8 | 60x60 | 1 | 6 | `fabrication/dxf/Л03_foot_plate_t8.dxf` |
| Л04 | tower_gusset_outer | 8 | 393x210 | 10 | 2 | `fabrication/dxf/Л04_tower_gusset_outer_t8.dxf` |
| Л05 | tower_liner_steel | 2 | 330x60 | 10 | 4 | `fabrication/dxf/Л05_tower_liner_steel_t2.dxf` |
| Л06 | tower_gusset_inner | 8 | 112x45 | 0 | 2 | `fabrication/dxf/Л06_tower_gusset_inner_t8.dxf` |
| Л07 | saddle_cheek_welded | 8 | 120x87 | 2 | 2 | `fabrication/dxf/Л07_saddle_cheek_welded_t8.dxf` |
| Л08 | saddle_clamp_plate | 8 | 120x47 | 2 | 2 | `fabrication/dxf/Л08_saddle_clamp_plate_t8.dxf` |
| Л09 | deck_fin | 8 | 260x50 | 10 | 2 | `fabrication/dxf/Л09_deck_fin_t8.dxf` |
| Л10 | deck_plate | 8 | 420x260 | 4 | 1 | `fabrication/dxf/Л10_deck_plate_t8.dxf` |
| Л11 | deck_fm_flange | 8 | 300x96 | 4 | 1 | `fabrication/dxf/Л11_deck_fm_flange_t8.dxf` |
| Л12 | deck_fm_plate | 8 | 300x222 | 0 | 1 | `fabrication/dxf/Л12_deck_fm_plate_t8.dxf` |
| Л13 | deck_fm_gusset | 8 | 176x76 | 0 | 2 | `fabrication/dxf/Л13_deck_fm_gusset_t8.dxf` |
| Л14 | pedal_shoe_top | 8 | 200x46 | 0 | 2 | `fabrication/dxf/Л14_pedal_shoe_top_t8.dxf` |
| Л15 | pedal_shoe_cheek | 8 | 200x45 | 3 | 4 | `fabrication/dxf/Л15_pedal_shoe_cheek_t8.dxf` |
| Л16 | pedal_sector_plate | 8 | 305x229 | 6 | 2 | `fabrication/dxf/Л16_pedal_sector_plate_t8.dxf` |
| Л17 | pedal_tray_plate | 8 | 460x330 | 0 | 1 | `fabrication/dxf/Л17_pedal_tray_plate_t8.dxf` |
| Л18 | pedal_tray_flange | 8 | 330x50 | 2 | 2 | `fabrication/dxf/Л18_pedal_tray_flange_t8.dxf` |
| Л19 | seat_shoe_top | 8 | 100x40 | 0 | 4 | `fabrication/dxf/Л19_seat_shoe_top_t8.dxf` |
| Л20 | seat_shoe_cheek | 8 | 100x45 | 2 | 8 | `fabrication/dxf/Л20_seat_shoe_cheek_t8.dxf` |
| Л21 | seat_crossbar_flange | 8 | 524x80 | 0 | 2 | `fabrication/dxf/Л21_seat_crossbar_flange_t8.dxf` |
| Л22 | seat_adapter_bar | 8 | 395x50 | 0 | 2 | `fabrication/dxf/Л22_seat_adapter_bar_t8.dxf` |
| Л23 | seat_end_flange | 8 | 100x72 | 4 | 3 | `fabrication/dxf/Л23_seat_end_flange_t8.dxf` |
| Л24 | side_gusset | 8 | 95x46 | 0 | 1 | `fabrication/dxf/Л24_side_gusset_t8.dxf` |
| Л25 | side_liner | 2 | 248x60 | 8 | 2 | `fabrication/dxf/Л25_side_liner_t2.dxf` |
| Л26 | side_platform | 8 | 300x170 | 0 | 1 | `fabrication/dxf/Л26_side_platform_t8.dxf` |

## Раскрой труб, квадратов, полос

| Деталь | Сортамент | Длина, мм | Кол-во | Примечание |
|---|---|---|---|---|
| base_rail | Труба 40x40x3 | 1300 | 2 |  |
| base_cross | Труба 40x40x3 | 500 | 4 |  |
| tower_outer_post | Труба 50x50x3 | 372 | 2 | ТРУБОРЕЗ: 10 сквозных отв. Ø13 (оси на 72, 97, 122, 147, 172, 197, 222, 247, 272, 297 мм от низа) |
| tower_brace | Труба 40x40x3 | 440 | 2 | подкос под 57° к горизонту; торцы: к стойке — плоскость реза под 33° к оси трубы, к лонжерону — под 57° (длина по длинной стороне) |
| height_inner_post | Квадрат сплошной 40x40 | 380 | 2 | 2 отв. Ø13 — сверлить ПО МЕСТУ через отверстия наружной трубы (см. порядок сборки) |
| height_head_cross | Труба 40x40x3 | 570 | 1 |  |
| pedal_tray_stiffener | Труба 40x40x3 | 444 | 2 |  |
| seat_crossbar | Труба 50x50x3 | 570 | 2 |  |
| side_arm | Труба 40x40x3 | 79 | 1 |  |
| side_cup | Труба 50x50x3 | 305 | 1 | ТРУБОРЕЗ: 8 сквозных отв. Ø13 (оси на 95, 120, 145, 170, 195, 220, 245, 270 мм от низа) |
| side_bar | Квадрат сплошной 40x40 | 250 | 1 | 2 отв. Ø13 — сверлить ПО МЕСТУ через отверстия наружной трубы (см. порядок сборки) |

## Сколько покупать (без учёта реза и брака, +10 %)

| Сортамент | Итого, м |
|---|---|
| Труба 40x40x3 | 7.02 |
| Труба 50x50x3 | 2.19 |
| Квадрат сплошной 40x40 | 1.01 |
