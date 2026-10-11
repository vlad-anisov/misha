"""
Параметры концепции регулируемого каркаса автосимулятора.

Система координат (мм):
  X — вдоль основания; X = 0 — ПЕРЕДНИЙ торец (педали), +X — к сиденью (назад).
  Y — поперёк; 0 — ось симметрии; +Y — правая сторона пилота.
  Z — вверх; Z = 0 — пол.

Это КОНЦЕПТУАЛЬНЫЕ значения. Всё, что зависит от выбранного руля,
педалей и сиденья, помечено в docs/04_open_parameters.md.
"""
from dataclasses import dataclass

# ---------------------------------------------------------------- основание
BASE_L = 1400.0            # длина основания (исходно ~1300; +100 спереди — ход педалей для P95, см. docs/01)
BASE_W = 580.0             # габаритная ширина основания
TUBE = 40.0                # основная труба 40x40
T_RAIL = 3.0               # стенка лонжеронов основания
RAIL_YC = (BASE_W - TUBE) / 2      # ось лонжерона, 270
Z_BASE = 45.0              # низ основания над полом при номинальной опоре
Z_RAIL_TOP = Z_BASE + TUBE         # 85
CROSS_X = (20.0, 650.0, 890.0, 1380.0)   # оси поперечин основания
FOOT_X = (20.0, 650.0, 1380.0)           # регулируемые опоры (6 шт.)

# --------------------------------------------- направляющие «гребни» на лонжеронах
FIN_H, FIN_T = 50.0, 8.0                 # полоса 50x8 на ребро
FIN_Z0, FIN_Z1 = Z_RAIL_TOP, Z_RAIL_TOP + FIN_H   # 85..135
FIN_HOLE_Z = Z_RAIL_TOP + 25.0           # 110
PITCH = 25.0                              # шаг отверстий всех гребёнок
PEDAL_FIN_X = (20.0, 510.0)
SEAT_FIN_X = (920.0, 1390.0)
PEDAL_FIN_HOLES = [60.0 + 25.0 * i for i in range(16)]   # 60..435
SEAT_FIN_HOLES = [950.0 + 25.0 * i for i in range(18)]    # 950..1375
HOLE = 13.0                               # отверстие под М12 (рекоменд. 12.5–13.0)
GAP = 1.0                                 # зазор «приварная щека – гребень»: допуск ширины рамы, выбирается прижимной пластиной

# ------------------------------------------------------------- рулевая стойка
POST_X = 650.0             # ось стоек (вдоль X) от переднего торца основания
POST_YC = 265.0            # ось стоек поперёк (наружная грань заподлицо с лонжероном)
OUTER = 50.0; T_OUTER = 3.0          # наружная стойка 50x50x3
INNER = 40.0                         # внутренняя (выдвижная) стойка — сплошной квадрат 40x40 (без втулок, без смятия)
OUTER_TOP = 503.0          # верх наружной стойки
INNER_L = 380.0            # длина внутренней стойки
STACK = 102.0              # от верха площадки до верха внутренней стойки (лист 12 + гребень 50 + поперечина 40)
H_MIN, H_MAX, H_STEP = 625.0, 775.0, 25.0   # высота верха площадки руля от пола (исходные 625 — нижнее положение)
H_NOM = 700.0
INNER_HOLE_FROM_BOTTOM = (60.0, 135.0)      # два фиксатора на внутренней стойке (разнос 75)
OUTER_ROW_Z = [H_MIN - STACK - INNER_L + INNER_HOLE_FROM_BOTTOM[0] + PITCH * i for i in range(10)]   # 203..428
LINER = 2.0                # толщина вкладышей (подбор из комплекта 1.5/2.0/2.5 — обычная сталь, холоднокатаный лист)
PLATE = 8.0                # единая толщина мелких пластин (щёки, прижимные пластины, башмаки, косынки)

# ----------------------------------------------- площадка руля и продольная регулировка
DECK_W, DECK_D, DECK_T = 420.0, 260.0, 12.0    # исходный размер 420x260, лист 12 мм (жёсткость под базу)
DECK_FIN_H, DECK_FIN_T = 50.0, 8.0             # полоса 50x8 (единая для всех гребней)
DECK_FIN_Y = 180.0                              # оси гребней площадки
SADDLE_L = 120.0                                # длина сёдел-вилок
SADDLE_HOLES = (-37.5, 37.5)                    # одна пара отверстий седла (разнос 75) относительно оси стоек
D_MIN, D_MAX, D_STEP = -75.0, 75.0, 25.0       # продольное смещение площадки (+ к сиденью), 7 положений
DECK_X0_NOM = POST_X - DECK_D / 2               # 420
RIM_FROM_DECK_FRONT = 330.0                     # ДОПУЩЕНИЕ: центр обода от переднего края площадки

# ------------------------------------------------------------------ педали
PEDAL_PIVOT_Z = 120.0
PEDAL_PZ = (120.0, 170.0)                          # два ряда оси качания — высота педалей
PEDAL_XP = [260.0 + PITCH * i for i in range(10)]  # 260..485 — положение оси качания
PEDAL_ANGLES = [20.0, 30.0, 40.0, 50.0, 60.0]     # угол площадки к горизонту, град
PEDAL_R = (250.0,)                                 # одна дуга фиксации (+ ось = 2 болта на щеку)
TRAY_W, TRAY_L, TRAY_T = 450.0, 330.0, 8.0
TRAY_FLANGE_H = 50.0
UPRIGHT_Y0 = 226.0                                 # внутренняя грань щёк-секторов

# ------------------------------------------------------------------ сиденье
SEAT_XC = [1000.0 + PITCH * i for i in range(14)]   # 1000..1325 — оси поперечин сиденья (башмак 150, 3 болта)
# ------------------------------------------------- боковой кронштейн шифтера / ручника
SIDE_ARM_Y = (301.0, 380.0)  # консоль 40x40x3 от фланца поперечины до стакана
SIDE_CUP_YC = 405.0          # ось стакана 50x50x3 (снаружи основания)
SIDE_CUP_Z = (60.0, 365.0)   # стакан по высоте
SIDE_CUP_ROW = [155.0 + PITCH * i for i in range(8)]   # 155…330 — ряд отверстий стакана
SIDE_BAR_L = 250.0           # сплошной квадрат 40x40 под платформой
SIDE_BAR_HOLES = (150.0, 225.0)  # от низа платформы вниз (разнос 75)
SIDE_ZP = [380.0 + PITCH * i for i in range(5)]   # низ платформы 380…480 — 5 положений
SIDE_PLATE = (300.0, 170.0)  # платформа X x Y, лист 8 мм, отверстия под устройства — по месту
SLIDE_TRAVEL = 200.0     # типовой ход салазок сиденья (допущение); slide<0 — сиденье ближе к рулю
SEAT_RECLINE = 22.0      # наклон спинки от вертикали (условный ковш), град


@dataclass
class Config:
    name: str = "nominal"
    H: float = H_NOM          # высота площадки руля
    d: float = 0.0            # смещение площадки руля вдоль X (+ к сиденью)
    xp: float = 385.0         # ось качания педальной площадки
    pz: float = 120.0         # высота оси качания (ряд 120 или 170)
    alpha: float = 30.0       # угол педальной площадки
    xc1: float = 1025.0       # передняя поперечина сиденья
    xc2: float = 1300.0       # задняя поперечина сиденья
    slide: float = 0.0        # положение сиденья на салазках, −100…+100 (минус — ближе к рулю)
    show_refs: bool = True    # показывать условные габариты руля/сиденья
    side: int = 1             # сторона кронштейна шифтера: +1 справа, −1 слева, 0 — не ставить
    zp: float = 430.0         # высота низа платформы шифтера
    front_mount: bool = False # фронтальный кронштейн базы руля (вместо нижнего крепления)

    def validate(self):
        assert H_MIN <= self.H <= H_MAX and (self.H - H_MIN) % H_STEP == 0, self.H
        assert D_MIN <= self.d <= D_MAX and (self.d - D_MIN) % D_STEP == 0, self.d
        assert self.xp in PEDAL_XP, self.xp
        assert self.alpha in PEDAL_ANGLES, self.alpha
        assert self.pz in PEDAL_PZ, self.pz
        assert self.xc1 in SEAT_XC and self.xc2 in SEAT_XC and self.xc2 - self.xc1 >= 150
        assert -SLIDE_TRAVEL / 2 <= self.slide <= SLIDE_TRAVEL / 2
        assert self.side in (-1, 0, 1) and self.zp in SIDE_ZP


CONFIGS = {
    "nominal": Config(),
    "wheel_low_fwd": Config("wheel_low_fwd", H=H_MIN, d=D_MIN),
    "wheel_low_back": Config("wheel_low_back", H=H_MIN, d=D_MAX),
    "wheel_high_fwd": Config("wheel_high_fwd", H=H_MAX, d=D_MIN),
    "wheel_high_back": Config("wheel_high_back", H=H_MAX, d=D_MAX),
    "pedals_front_flat": Config("pedals_front_flat", xp=PEDAL_XP[0], alpha=20),
    "pedals_front_steep_high": Config("pedals_front_steep_high", xp=PEDAL_XP[0], alpha=60, pz=PEDAL_PZ[1]),
    "pedals_rear_flat_high": Config("pedals_rear_flat_high", xp=PEDAL_XP[-1], alpha=20, pz=PEDAL_PZ[1]),
    "pedals_rear_steep": Config("pedals_rear_steep", xp=PEDAL_XP[-1], alpha=60),
    "seat_front": Config("seat_front", xc1=SEAT_XC[0], xc2=SEAT_XC[0] + 275),
    "seat_rear": Config("seat_rear", xc1=SEAT_XC[-1] - 275, xc2=SEAT_XC[-1]),
    "shifter_low_front": Config("shifter_low_front", xc1=SEAT_XC[0], xc2=SEAT_XC[0] + 275, zp=SIDE_ZP[0], slide=-100),
    "shifter_high_rear": Config("shifter_high_rear", xc1=SEAT_XC[-1] - 275, xc2=SEAT_XC[-1], zp=SIDE_ZP[-1], slide=100),
    "shifter_left": Config("shifter_left", side=-1),
    "deck_front_mount_low_back": Config("deck_front_mount_low_back", H=H_MIN, d=D_MAX, front_mount=True),
    "deck_front_mount_high_fwd": Config("deck_front_mount_high_fwd", H=H_MAX, d=D_MIN, front_mount=True),
}
