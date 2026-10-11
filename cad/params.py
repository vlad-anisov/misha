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
BASE_L = 1300.0            # длина основания
BASE_W = 580.0             # габаритная ширина основания
TUBE = 40.0                # основная труба 40x40
T_RAIL = 3.0               # стенка лонжеронов основания
RAIL_YC = (BASE_W - TUBE) / 2      # ось лонжерона, 270
Z_BASE = 45.0              # низ основания над полом при номинальной опоре
Z_RAIL_TOP = Z_BASE + TUBE         # 85
CROSS_X = (20.0, 550.0, 790.0, 1280.0)   # оси поперечин основания
FOOT_X = (20.0, 550.0, 1280.0)           # регулируемые опоры (6 шт.)

# --------------------------------------------- направляющие «гребни» на лонжеронах
FIN_H, FIN_T = 50.0, 8.0                 # полоса 50x8 на ребро
FIN_Z0, FIN_Z1 = Z_RAIL_TOP, Z_RAIL_TOP + FIN_H   # 85..135
FIN_HOLE_Z = Z_RAIL_TOP + 25.0           # 110
PITCH = 25.0                              # шаг отверстий всех гребёнок
PEDAL_FIN_X = (20.0, 410.0)
SEAT_FIN_X = (820.0, 1290.0)
HOLE = 13.0                               # отверстие под М12 (рекоменд. 12.5–13.0)
GAP = 0.2                                 # зазор «щека–гребень» после подгонки

# ------------------------------------------------------------- рулевая стойка
POST_X = 550.0             # ось стоек (вдоль X); исходно 450 — сдвинуто по эргономике
POST_YC = 265.0            # ось стоек поперёк (наружная грань заподлицо с лонжероном)
OUTER = 50.0; T_OUTER = 3.0          # наружная стойка 50x50x3
INNER = 40.0; T_INNER = 3.0          # внутренняя (выдвижная) 40x40x3
OUTER_TOP = 439.0          # верх наружной стойки
INNER_L = 360.0            # длина внутренней стойки
STACK = 116.0              # от верха площадки до верха внутренней стойки
H_MIN, H_MAX, H_STEP = 575.0, 725.0, 25.0   # высота верха площадки руля от пола
H_NOM = 650.0             # исходные 625 — в диапазоне
INNER_HOLE_FROM_BOTTOM = (60.0, 135.0)      # два фиксатора на внутренней стойке (разнос 75)
OUTER_ROW_Z = [159.0 + PITCH * i for i in range(10)]   # 159..384 — ряд отверстий наружной стойки
LINER = 2.0                # толщина антилюфтовых вкладышей (подбирается 1.6–2.2)

# ----------------------------------------------- площадка руля и продольная регулировка
DECK_W, DECK_D, DECK_T = 420.0, 300.0, 6.0     # предложено 420x300 (было 420x260)
DECK_FIN_H, DECK_FIN_T = 60.0, 10.0            # полоса 60x10 под площадкой
DECK_FIN_Y = 180.0                              # оси гребней площадки
SADDLE_L = 150.0                                # длина сёдел-вилок
# Нониус: отверстия седла относительно оси стойки. Пара A и пара B (смещение 12.5 мм)
SADDLE_HOLES_A = (-56.25, 18.75)
SADDLE_HOLES_B = (-18.75, 56.25)
D_MIN, D_MAX, D_STEP = -75.0, 75.0, 12.5       # продольное смещение площадки (+ к сиденью)
DECK_X0_NOM = POST_X - DECK_D / 2               # 300

# ------------------------------------------------------------------ педали
PEDAL_PIVOT_Z = 120.0
PEDAL_XP = [260.0 + PITCH * i for i in range(6)]   # 260..385 — положение оси качания
PEDAL_ANGLES = [20.0, 30.0, 40.0, 50.0, 60.0]     # угол площадки к горизонту, град
PEDAL_R = (150.0, 250.0)                           # радиусы двух дуг фиксации
TRAY_W, TRAY_L, TRAY_T = 460.0, 330.0, 6.0
TRAY_FLANGE_H = 50.0
UPRIGHT_Y0 = 231.0                                 # внутренняя грань щёк-секторов

# ------------------------------------------------------------------ сиденье
SEAT_XC = [875.0 + PITCH * i for i in range(16)]    # 875..1250 — оси поперечин сиденья
SLIDE_TRAVEL = 200.0     # типовой ход салазок сиденья (допущение); slide<0 — сиденье ближе к рулю
SEAT_RECLINE = 22.0      # наклон спинки от вертикали (условный ковш), град


@dataclass
class Config:
    name: str = "nominal"
    H: float = H_NOM          # высота площадки руля
    d: float = 0.0            # смещение площадки руля вдоль X (+ к сиденью)
    xp: float = 285.0         # ось качания педальной площадки
    alpha: float = 30.0       # угол педальной площадки
    xc1: float = 925.0        # передняя поперечина сиденья
    xc2: float = 1200.0       # задняя поперечина сиденья
    slide: float = 0.0        # положение сиденья на салазках, −100…+100 (минус — ближе к рулю)
    show_refs: bool = True    # показывать условные габариты руля/сиденья

    def validate(self):
        assert H_MIN <= self.H <= H_MAX and (self.H - H_MIN) % H_STEP == 0, self.H
        assert D_MIN <= self.d <= D_MAX and (self.d - D_MIN) % D_STEP == 0, self.d
        assert self.xp in PEDAL_XP, self.xp
        assert self.alpha in PEDAL_ANGLES, self.alpha
        assert self.xc1 in SEAT_XC and self.xc2 in SEAT_XC and self.xc2 - self.xc1 >= 150
        assert -SLIDE_TRAVEL / 2 <= self.slide <= SLIDE_TRAVEL / 2


CONFIGS = {
    "nominal": Config(),
    "wheel_low_fwd": Config("wheel_low_fwd", H=575, d=-75),
    "wheel_low_back": Config("wheel_low_back", H=575, d=75),
    "wheel_high_fwd": Config("wheel_high_fwd", H=725, d=-75),
    "wheel_high_back": Config("wheel_high_back", H=725, d=75),
    "pedals_front_flat": Config("pedals_front_flat", xp=260, alpha=20),
    "pedals_front_steep": Config("pedals_front_steep", xp=260, alpha=60),
    "pedals_rear_flat": Config("pedals_rear_flat", xp=385, alpha=20),
    "pedals_rear_steep": Config("pedals_rear_steep", xp=385, alpha=60),
    "seat_front": Config("seat_front", xc1=875, xc2=1150),
    "seat_rear": Config("seat_rear", xc1=975, xc2=1250),
}
