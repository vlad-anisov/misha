"""
Предварительная оценка жёсткости рулевого узла: пространственная стержневая МКЭ-модель
(балки Эйлера–Бернулли, 6 степеней свободы в узле) + ручные проверки крепежа.

ОГРАНИЧЕНИЯ (важно): стыки считаются жёсткими (сварка полным контуром, болтовые
регулировочные узлы затянуты — без люфта); податливость сварных узлов, местные
деформации стенок труб и опор пола не учтены. Реальный прогиб будет больше в 1.5–3 раза.
Модель годится для сравнения вариантов и выявления слабых мест, а не для сертификации.

    python calc/frame_fem.py   ->  docs/generated/calc_results.md
"""
import math
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "cad"))
from params import *  # noqa: E402,F401,F403

E, G = 210000.0, 81000.0     # МПа
FY = 235.0                   # S235, МПа


def sec_rhs(b, h, t):
    """Прямоугольная труба: b — вдоль локальной y, h — вдоль локальной z."""
    A = b * h - (b - 2 * t) * (h - 2 * t)
    Iy = (b * h ** 3 - (b - 2 * t) * (h - 2 * t) ** 3) / 12    # изгиб в плоскости xz
    Iz = (h * b ** 3 - (h - 2 * t) * (b - 2 * t) ** 3) / 12
    Am = (b - t) * (h - t)
    J = 4 * Am ** 2 * t / (2 * ((b - t) + (h - t)))
    return dict(A=A, Iy=Iy, Iz=Iz, J=J, cy=b / 2, cz=h / 2)


def sec_flat(b, h):
    """Полоса: b — вдоль y (толщина), h — вдоль z (высота)."""
    t, w = min(b, h), max(b, h)
    J = w * t ** 3 / 3 * (1 - 0.63 * t / w)
    return dict(A=b * h, Iy=b * h ** 3 / 12, Iz=h * b ** 3 / 12, J=J, cy=b / 2, cz=h / 2)


RIGID = dict(A=1e5, Iy=1e9, Iz=1e9, J=1e9, cy=1, cz=1)
S40x3 = sec_rhs(40, 40, 3)
S40x2 = sec_rhs(40, 40, 2)
S50x3 = sec_rhs(50, 50, 3)
SQ40 = dict(A=1600.0, Iy=40 ** 4 / 12, Iz=40 ** 4 / 12, J=0.141 * 40 ** 4, cy=20, cz=20)   # сплошной квадрат 40
FIN = sec_flat(DECK_FIN_T, DECK_FIN_H)                    # 8 x 50 на ребро
DECK_X = dict(A=130 * 8, Iy=130 * 8 ** 3 / 12, Iz=8 * 130 ** 3 / 12, J=130 * 8 ** 3 / 3, cy=65, cz=4)  # полоса листа 8 мм


class Frame:
    def __init__(self):
        self.nodes, self.el, self.fix, self.loads = [], [], {}, {}

    def node(self, p):
        p = np.array(p, float)
        for i, q in enumerate(self.nodes):
            if np.linalg.norm(q - p) < 1e-6:
                return i
        self.nodes.append(p)
        return len(self.nodes) - 1

    def beam(self, p1, p2, sec, name, ref=(0, 0, 1)):
        self.el.append((self.node(p1), self.node(p2), sec, name, np.array(ref, float)))

    def chain(self, pts, sec, name, ref=(0, 0, 1)):
        for a, b in zip(pts[:-1], pts[1:]):
            self.beam(a, b, sec, name, ref)

    @staticmethod
    def k_local(L, s):
        A, Iy, Iz, J = s["A"], s["Iy"], s["Iz"], s["J"]
        k = np.zeros((12, 12))
        def put(i, j, v):
            k[i, j] += v
            if i != j:
                k[j, i] += v
        put(0, 0, E * A / L); put(0, 6, -E * A / L); put(6, 6, E * A / L)
        put(3, 3, G * J / L); put(3, 9, -G * J / L); put(9, 9, G * J / L)
        a, b, c = 12 * E * Iz / L ** 3, 6 * E * Iz / L ** 2, E * Iz / L
        put(1, 1, a); put(1, 5, b); put(1, 7, -a); put(1, 11, b)
        put(5, 5, 4 * c); put(5, 7, -b); put(5, 11, 2 * c); put(7, 7, a); put(7, 11, -b); put(11, 11, 4 * c)
        a, b, c = 12 * E * Iy / L ** 3, 6 * E * Iy / L ** 2, E * Iy / L
        put(2, 2, a); put(2, 4, -b); put(2, 8, -a); put(2, 10, -b)
        put(4, 4, 4 * c); put(4, 8, b); put(4, 10, 2 * c); put(8, 8, a); put(8, 10, b); put(10, 10, 4 * c)
        return k

    def T(self, i, j, ref):
        x = self.nodes[j] - self.nodes[i]
        L = np.linalg.norm(x); x = x / L
        if abs(x @ ref) > 0.99:
            ref = np.array([1.0, 0, 0])
        y = np.cross(ref, x); y /= np.linalg.norm(y)
        z = np.cross(x, y)
        R = np.vstack([x, y, z])
        T = np.zeros((12, 12))
        for k in range(4):
            T[3 * k:3 * k + 3, 3 * k:3 * k + 3] = R
        return T, L

    def solve(self):
        n = len(self.nodes) * 6
        K = np.zeros((n, n))
        cache = []
        for (i, j, s, name, ref) in self.el:
            T, L = self.T(i, j, ref)
            kl = self.k_local(L, s)
            kg = T.T @ kl @ T
            dofs = np.r_[6 * i:6 * i + 6, 6 * j:6 * j + 6]
            K[np.ix_(dofs, dofs)] += kg
            cache.append((T, kl, dofs))
        F = np.zeros(n)
        for nd, f in self.loads.items():
            F[6 * nd:6 * nd + 6] += f
        fixed = []
        for nd, dofs in self.fix.items():
            fixed += [6 * nd + d for d in dofs]
        free = np.setdiff1d(np.arange(n), fixed)
        u = np.zeros(n)
        u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
        stresses = []
        for (T, kl, dofs), (i, j, s, name, ref) in zip(cache, self.el):
            f = kl @ (T @ u[dofs])
            N = abs(f[0])
            My = max(abs(f[4]), abs(f[10])); Mz = max(abs(f[5]), abs(f[11]))
            if s is RIGID:
                continue
            sig = N / s["A"] + My * s["cz"] / s["Iy"] + Mz * s["cy"] / s["Iz"]
            stresses.append((sig, name))
        return u, stresses


def build_frame(H, d):
    f = Frame()
    zc = Z_BASE + TUBE / 2
    xs = sorted(set([0.0, BASE_L] + list(CROSS_X) + list(FOOT_X)))
    for s in (1, -1):
        f.chain([(x, s * RAIL_YC, zc) for x in xs], S40x3, "лонжерон основания")
    for x in CROSS_X:
        f.beam((x, -RAIL_YC, zc), (x, RAIL_YC, zc), S40x3, "поперечина основания")
    top_in = H - STACK
    zhead = top_in + 20
    zbrace = OUTER_TOP - 39
    for s in (1, -1):
        y = s * RAIL_YC
        f.beam((POST_X, y, zc), (POST_X, y, Z_RAIL_TOP), RIGID, "узел стойка-лонжерон (косынка)")
        f.chain([(POST_X, y, Z_RAIL_TOP), (POST_X, y, zbrace), (POST_X, y, OUTER_TOP)], S50x3, "наружная стойка 50x50x3",
                ref=(1, 0, 0))
        f.beam((POST_X, y, OUTER_TOP), (POST_X, y, zhead), SQ40, "внутренняя стойка — квадрат 40 (над направляющей)",
               ref=(1, 0, 0))
        f.beam((POST_X, y, zbrace), (CROSS_X[2], y, zc), S40x3, "подкос 40x40x3")
    ys = [-RAIL_YC, -DECK_FIN_Y, DECK_FIN_Y, RAIL_YC]
    f.chain([(POST_X, y, zhead) for y in ys], S40x3, "верхняя поперечина 40x40x3")
    zf = H - DECK_T - DECK_FIN_H / 2
    xa = [POST_X + h for h in SADDLE_HOLES]
    x0, x1 = DECK_X0_NOM + d, DECK_X0_NOM + DECK_D + d
    xmount = (x0 + 30, x0 + 230)            # условные точки крепления базы руля
    xr = DECK_X0_NOM + d + RIM_FROM_DECK_FRONT
    for s in (1, -1):
        y = s * DECK_FIN_Y
        for xb in xa:
            f.beam((POST_X, y, zhead), (xb, y, zf), RIGID, "седло (жёстко, затянутые болты)")
        pts = sorted(set([x0, x1] + xa + list(xmount)))
        f.chain([(x, y, zf) for x in pts], FIN, "гребень площадки 50x8", ref=(0, 0, 1))
    for xm in xmount:   # лист + рёбра связывают гребни поперёк (в точках крепления базы)
        f.chain([(xm, -DECK_FIN_Y, zf), (xm, 0, zf), (xm, DECK_FIN_Y, zf)], DECK_X, "лист площадки 8 мм")
    rim = (xr, 0.0, H + 70)
    for xm in xmount:
        for s in (1, -1):
            f.beam((xm, s * DECK_FIN_Y, zf), rim, RIGID, "база руля (жёсткое тело)")
    # опоры пола: Z во всех шести, X и Y — минимально для исключения смещения как жёсткого тела
    for x in FOOT_X:
        for s in (1, -1):
            nd = f.node((x, s * RAIL_YC, zc))
            f.fix[nd] = [2]
    f.fix[f.node((FOOT_X[0], RAIL_YC, zc))] = [0, 1, 2]
    f.fix[f.node((FOOT_X[0], -RAIL_YC, zc))] = [0, 1, 2]
    f.fix[f.node((FOOT_X[2], RAIL_YC, zc))] = [1, 2]
    return f, f.node(rim)


LOADS = {
    "LC1 вертикально вниз 1000 Н на ободе (опора рукой при посадке)": np.array([0, 0, -1000, 0, 0, 0]),
    "LC2 к пилоту 500 Н (тянет руль на себя)": np.array([500, 0, 0, 0, 0, 0]),
    "LC3 от пилота 500 Н (упор в руль при торможении)": np.array([-500, 0, 0, 0, 0, 0]),
    "LC4 момент базы 25 Н·м + поперечно 300 Н": np.array([0, 300, 0, 25000, 0, 0]),
    "LC5 вверх 600 Н": np.array([0, 0, 600, 0, 0, 0]),
}


def run_fem():
    rows = []
    for (H, d) in ((H_NOM, 0.0), (H_MAX, D_MAX), (H_MIN, D_MIN), (H_MAX, D_MIN)):
        for lc, F in LOADS.items():
            f, nr = build_frame(H, d)
            f.loads = {nr: F}
            u, st = f.solve()
            dv = u[6 * nr:6 * nr + 3]
            rot = u[6 * nr + 3:6 * nr + 6]
            smax = max(st)
            rows.append(dict(H=H, d=d, lc=lc, dx=dv[0], dy=dv[1], dz=dv[2], rx=math.degrees(rot[0]),
                             ry=math.degrees(rot[1]), smax=smax[0], selem=smax[1]))
    return rows


# --------------------------------------------------------------------- ручные проверки
def bolt_checks():
    out = []
    d, As = 12.0, 84.3
    fub, fyb = 800.0, 640.0
    gm2 = 1.25
    Fv_Rd = 0.6 * fub * As / gm2 / 1000          # кН на плоскость среза (резьба в плоскости — запас)
    out.append(("Срез М12 8.8, одна плоскость (EN 1993-1-8, по резьбе)", f"{Fv_Rd:.1f} кН"))
    T, K = 80.0, 0.20
    Fp = T / (K * d / 1000) / 1000
    out.append(("Усилие затяжки М12 при 80 Н·м, K≈0.20 (оцинк. болт, гайка ISO 7042)", f"≈{Fp:.0f} кН (~{Fp/48.5*100:.0f}% пробной нагрузки 48.5 кН)"))
    mu = 0.20
    out.append(("Сдвиг трением на болт, 2 плоскости трения, μ=0.20", f"≈{2*mu*Fp:.0f} кН"))
    # седло: момент от LC1 в крайнем заднем положении
    lever = (DECK_X0_NOM + D_MAX + RIM_FROM_DECK_FRONT) - POST_X
    M = 1000 * lever / 1000                        # Н·м
    pair = 75.0
    Fb = M / 2 / (pair / 1000) / 1000              # кН на болт, 2 седла
    out.append((f"Седло: LC1 1000 Н на плече {lever:.0f} мм → момент {M:.0f} Н·м, пара болтов 75 мм на каждом седле",
                f"≈{Fb:.2f} кН на болт (запас по срезу > {Fv_Rd/Fb:.0f}, по трению > {2*mu*Fp/Fb:.0f})"))
    t_fin = DECK_FIN_T
    sb = Fb * 1000 / (d * t_fin)
    out.append((f"Смятие гребня {t_fin:.0f} мм под болтом М12", f"{sb:.0f} МПа (допускаемое для S235 ≈ 2.5·360/1.25 = 720 МПа)"))
    # телескоп
    Mpost = 1000 * lever / 1000 / 2
    overlap_min = OUTER_TOP - (H_MAX - STACK - INNER_L)
    Rg = Mpost / (overlap_min / 1000) / 1000
    out.append((f"Телескоп: момент на стойку {Mpost:.0f} Н·м, мин. перекрытие {overlap_min:.0f} мм (при H={H_MAX:.0f})",
                f"реакция пары направляющих ≈{Rg:.2f} кН — воспринимается затянутым пакетом и вкладышами"))
    out.append(("Телескоп: вертикальная нагрузка 1000 Н + вес узла ~150 Н на 4 болта, двойной срез", "≈0.3 кН на плоскость — запас > 60"))
    # педали
    Fped, arm = 2000.0, 200.0
    Mp = Fped * arm / 1000
    Fs = Mp / 2 / (PEDAL_R[0] / 1000) / 1000
    out.append((f"Педали: тормоз {Fped:.0f} Н по нормали на расстоянии {arm:.0f} мм от оси → {Mp:.0f} Н·м; ось + 1 болт на дуге R{PEDAL_R[0]:.0f} на каждой щеке",
                f"болт дуги ≈{Fs:.2f} кН, оси ≈{(Fped/2/1000 + Fs):.1f} кН (одна плоскость; запас > {Fv_Rd/(Fped/2/1000 + Fs):.0f})"))
    st_I = (40 ** 4 - 34 ** 4) / 12
    Ls = 444.0
    Pm = Fped / 2
    sig = Pm * Ls / 4 / (st_I / 20)
    dl = Pm * Ls ** 3 / (48 * E * st_I)
    out.append(("Ребро педальной площадки 40x40x3, пролёт 444, 1000 Н в середине (без учёта листа 8 мм)",
                f"σ ≈ {sig:.0f} МПа, прогиб ≈ {dl:.2f} мм"))
    # щеки башмаков: проверка на отрыв
    out.append(("Башмак педалей: 3 болта М12 на сторону (сквозные, гайка ISO 7042), сдвиг 2 кН/2 стороны", "≈0.33 кН на болт — трение и опора болта с запасом > 30"))
    # боковой кронштейн: ручник 500 Н вдоль X на 150 мм выше платформы, платформа в верхнем положении
    Fh, zr = 500.0, SIDE_ZP[-1] + 150
    zc_cross = FIN_Z1 + PLATE + 25
    M_cup = Fh * (zr - SIDE_CUP_Z[1]) / 1000
    over = SIDE_CUP_Z[1] - (SIDE_ZP[-1] - SIDE_BAR_L)
    out.append((f"Кронштейн шифтера: ручник {Fh:.0f} Н на высоте {zr:.0f} мм, плечо до верха стакана → {M_cup:.0f} Н·м; перекрытие {over:.0f} мм",
                f"реакция направляющих ≈{M_cup/(over/1000)/1000:.2f} кН; болты М12 — срез ≈{Fh/2/1000:.2f} кН"))
    T = Fh * (zr - zc_cross) / 1000
    J40 = sec_rhs(50, 50, 3)["J"]
    L = 270.0
    th = T * 1000 * L / (G * J40)
    out.append((f"Кручение передней поперечины сиденья от ручника: {T:.0f} Н·м на половине пролёта {L:.0f} мм",
                f"угол ≈{math.degrees(th):.2f}° → смещение рукояти ≈{th*(zr - zc_cross):.1f} мм (+ податливость башмаков) [!] проверить замером"))
    Mx = Fh * (zr - zc_cross) / 1000
    out.append(("Фланец кронштейна (4 болта М12, разнос по высоте 42 мм) — боковая сила 500 Н на рукояти",
                f"момент ≈{Mx:.0f} Н·м → растяжение ≈{Mx/0.042/2/1000:.1f} кН на болт (несущая способность М12 8.8 ≈ 48 кН)"))
    return out


def mass_and_stability():
    import cadquery as cq  # noqa
    from simrig import build_model
    m = build_model(Config(), refs=False)
    vol = sum(p.shape.Volume() for p in m.parts if p.kind in ("steel", "fastener"))
    mass = vol * 7.85e-6
    # центр масс по X
    cx = sum(p.shape.Volume() * p.shape.Center().x for p in m.parts if p.kind in ("steel", "fastener")) / vol
    return mass, cx


def main():
    os.makedirs(os.path.join(ROOT, "docs", "generated"), exist_ok=True)
    rows = run_fem()
    checks = bolt_checks()
    mass, cx = mass_and_stability()
    L = []
    L.append("# Результаты предварительного расчёта (генерируется calc/frame_fem.py)\n")
    L.append("> Оценочный расчёт концепции. Стыки приняты жёсткими, податливость сварных узлов, стенок труб и пола "
             "не учтена — реальные перемещения ожидаются в 1.5–3 раза больше. После выбора руля пересчитать с его "
             "массой, моментом и положением обода.\n")
    L.append("## Перемещение центра обода (стержневая МКЭ-модель)\n")
    L.append("| H, мм | d, мм | Нагрузка | dX, мм | dY, мм | dZ, мм | поворот X, ° | поворот Y, ° | σmax, МПа | где |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f"| {r['H']:.0f} | {r['d']:+.0f} | {r['lc']} | {r['dx']:+.2f} | {r['dy']:+.2f} | {r['dz']:+.2f} | "
                 f"{r['rx']:+.3f} | {r['ry']:+.3f} | {r['smax']:.0f} | {r['selem']} |")
    L.append("\n## Крепёж и соединения\n")
    L.append("| Проверка | Результат |")
    L.append("|---|---|")
    for a, b in checks:
        L.append(f"| {a} | {b} |")
    L.append("\n## Масса и устойчивость\n")
    W = mass * 9.81
    L.append(f"* Масса стальной части (без руля, педалей, сиденья), по модели: **≈{mass:.0f} кг**, центр масс X≈{cx:.0f} мм.")
    arm_y = RAIL_YC
    zr = H_MAX + 70
    Fy_tip = W * arm_y / zr
    L.append(f"* Опрокидывание ПУСТОЙ рамы вбок от горизонтальной силы на ободе (H={H_MAX:.0f}, высота обода ≈{zr:.0f} мм): "
             f"≈{Fy_tip:.0f} Н. С пилотом 80 кг на сиденье — ≈{(W + 785) * arm_y / zr:.0f} Н. "
             "Вывод: в работе устойчиво, но пустую раму не следует тянуть за руль вбок.")
    L.append("* Продольно: точка приложения нагрузок на руль (X≈700–825) и педали лежат внутри опорного контура "
             f"(опоры X={FOOT_X[0]:.0f}…{FOOT_X[2]:.0f}); усилия педалей замыкаются через пилота на сиденье (внутренние силы).")
    with open(os.path.join(ROOT, "docs", "generated", "calc_results.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
