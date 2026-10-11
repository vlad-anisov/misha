"""
Упрощённая эргономическая проверка (боковая проекция, консервативно).

Манекены P5 (женщина), P50 и P95 (мужчины) — приближённые длины сегментов
по типовым антропометрическим таблицам (ГОСТ Р ИСО 7250 / DIN 33402), с учётом обуви.
Для каждого манекена перебором по сетке реальных регулировок каркаса ищется
положение с целевыми углами GT-посадки и максимальным зазором ног до рулевого узла.

Положение обода — ДОПУЩЕНИЕ (база условно длиной 230 мм, обод Ø300 на 320 мм
позади переднего края базы, ось на 70 мм выше площадки). После выбора базы
и руля расчёт нужно повторить (см. docs/04_open_parameters.md).
"""
import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from params import *  # noqa: F401,F403

MANNEQUINS = {
    #          бедро  голень+обувь  таз→плечо  плечо  предпл.→хват  полуширина плеч
    "P5_жен":  dict(thigh=390, shin=465, torso=480, upper=275, fore=330, sh_y=170),
    "P50_муж": dict(thigh=435, shin=535, torso=540, upper=315, fore=360, sh_y=195),
    "P95_муж": dict(thigh=470, shin=580, torso=580, upper=340, fore=390, sh_y=210),
}
R_THIGH, R_KNEE, R_SHIN = 70.0, 55.0, 50.0
TARGET = dict(knee=(110, 140), hip=(95, 125), elbow=(100, 150))

SEAT_MOUNT_Z = FIN_Z1 + 8 + 46 + 8          # 197 — как в simrig.build_seat
SEAT_ZC = SEAT_MOUNT_Z + 35                  # низ подушки (условно)
RIM_R, RIM_TUBE = 150.0, 14.0


def h_point(xc1, slide):
    xs0 = xc1 - 40 + slide
    return np.array([xs0 + 265.0, SEAT_ZC + 95.0])


def heel_point(xp, alpha):
    a = math.radians(alpha)
    u, w = 45.0, 31.0 + 15.0       # пятка на листе + условная высота основания педалей
    return np.array([xp - u * math.cos(a) + w * math.sin(a), PEDAL_PIVOT_Z + u * math.sin(a) + w * math.cos(a)])


def rim_center(H, d):
    return np.array([DECK_X0_NOM + d + 30 + 320, H + 70.0])


def knee_point(hip, heel, thigh, shin):
    v = heel - hip
    L = np.linalg.norm(v)
    if L >= thigh + shin - 1:
        return None
    a = (thigh ** 2 - shin ** 2 + L ** 2) / (2 * L)
    h = math.sqrt(max(thigh ** 2 - a ** 2, 0))
    u = v / L
    nrm = np.array([-u[1], u[0]])
    if nrm[1] < 0:
        nrm = -nrm
    return hip + a * u + h * nrm


def angle(a, b, c):
    """Угол в точке b между ba и bc, град."""
    v1, v2 = a - b, c - b
    return math.degrees(math.acos(np.clip(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1)))


def obstacles(H, d):
    """Прямоугольники рулевого узла в боковой проекции (только то, что над ногами по Y)."""
    rc = rim_center(H, d)
    return {
        "гребни/площадка": (300 + d, 600 + d, H - DECK_T - DECK_FIN_H, H),
        "сёдла/поперечина": (POST_X - SADDLE_L / 2, POST_X + SADDLE_L / 2, H - STACK, H - 11),
        "обод": (rc[0] - RIM_TUBE, rc[0] + RIM_TUBE, rc[1] - RIM_R - RIM_TUBE, rc[1] + RIM_R + RIM_TUBE),
        "ступица": (DECK_X0_NOM + d + 260, DECK_X0_NOM + d + 340, rc[1] - 30, rc[1] + 30),
    }


def rect_dist(p, r):
    x0, x1, z0, z1 = r
    dx = max(x0 - p[0], 0, p[0] - x1)
    dz = max(z0 - p[1], 0, p[1] - z1)
    return math.hypot(dx, dz)


def leg_clearance(hip, knee, heel, obst):
    best = (1e9, None)
    for (p0, p1, r0, r1) in ((hip, knee, R_THIGH, R_KNEE), (knee, heel, R_KNEE, R_SHIN)):
        for t in np.linspace(0, 1, 40):
            p = p0 + t * (p1 - p0)
            r = r0 + t * (r1 - r0)
            for name, rc in obst.items():
                dd = rect_dist(p, rc) - r
                if dd < best[0]:
                    best = (dd, name)
    return best


def evaluate(man, H, d, xp, alpha, xc1, slide):
    hip = h_point(xc1, slide)
    heel = heel_point(xp, alpha)
    knee = knee_point(hip, heel, man["thigh"], man["shin"])
    if knee is None:
        return None
    rc = rim_center(H, d)
    rec = math.radians(SEAT_RECLINE)
    sh2 = hip + man["torso"] * np.array([math.sin(rec), math.cos(rec)])
    sh = np.array([sh2[0], man["sh_y"], sh2[1]])
    grip = np.array([rc[0], RIM_R * math.cos(math.radians(15)), rc[1] + RIM_R * math.sin(math.radians(15))])
    reach = np.linalg.norm(grip - sh)
    if reach >= man["upper"] + man["fore"] - 5:
        return None
    elbow = math.degrees(math.acos((man["upper"] ** 2 + man["fore"] ** 2 - reach ** 2) / (2 * man["upper"] * man["fore"])))
    torso_pt = hip + np.array([math.sin(rec), math.cos(rec)]) * 100
    res = dict(H=H, d=d, xp=xp, alpha=alpha, xc1=xc1, slide=slide,
               knee=angle(hip, knee, heel), hip=angle(torso_pt, hip, knee), elbow=elbow,
               hip_pt=hip, knee_pt=knee, heel_pt=heel, sh_pt=sh2, rim=rc)
    cl, what = leg_clearance(hip, knee, heel, obstacles(H, d))
    res["clear"], res["clear_to"] = cl, what
    res["entry_gap"] = (xc1 - 40 + slide) - (rc[0] + RIM_TUBE)   # обод → передний край подушки
    return res


def grid():
    Hs = np.arange(H_MIN, H_MAX + 1, H_STEP)
    ds = np.arange(D_MIN, D_MAX + 0.1, D_STEP)
    xc1s = [x for x in SEAT_XC if x + 275 <= SEAT_XC[-1]][:5]
    slides = np.arange(-100, 100.1, 25)
    return itertools.product(Hs, ds, PEDAL_XP, PEDAL_ANGLES, xc1s, slides)


def in_range(v, rng):
    return rng[0] <= v <= rng[1]


def score(r):
    pen = 0.0
    for k, rng in TARGET.items():
        mid = (rng[0] + rng[1]) / 2
        pen += abs(r[k] - mid) / (rng[1] - rng[0])
    return min(r["clear"], 80) - 25 * pen


def search(man):
    best = None
    n_ok = 0
    for g in grid():
        r = evaluate(man, *g)
        if r is None or not all(in_range(r[k], TARGET[k]) for k in TARGET):
            continue
        n_ok += 1
        if best is None or score(r) > score(best):
            best = r
    return best, n_ok


if __name__ == "__main__":
    for nm, man in MANNEQUINS.items():
        b, n = search(man)
        print(nm, n, {k: (round(v, 1) if isinstance(v, float) else v) for k, v in b.items() if not k.endswith("_pt")})
    r = evaluate(MANNEQUINS["P50_муж"], H_NOM, 0, 335, 40, 925, 0)
    print("nominal P50", {k: v for k, v in r.items() if not k.endswith("_pt")})
