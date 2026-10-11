"""
Параметрическая 3D-модель (CadQuery / OpenCascade) регулируемого сварного каркаса
домашнего автосимулятора. Каждая деталь — отдельное твёрдое тело.

Запуск:  python cad/build.py     (экспорт STEP/STL, проверка столкновений)
"""
import math
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np
from scipy.spatial import ConvexHull

from params import *  # noqa: F401,F403

V = cq.Vector

# ===================================================================== примитивы


def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(axis, c, a0, a1, d):
    """Цилиндр вдоль оси axis ('X'|'Y'|'Z'); c — координаты центра в двух других осях."""
    a0, a1 = sorted((a0, a1))
    if axis == "X":
        return cq.Solid.makeCylinder(d / 2, a1 - a0, V(a0, c[0], c[1]), V(1, 0, 0))
    if axis == "Y":
        return cq.Solid.makeCylinder(d / 2, a1 - a0, V(c[0], a0, c[1]), V(0, 1, 0))
    return cq.Solid.makeCylinder(d / 2, a1 - a0, V(c[0], c[1], a0), V(0, 0, 1))


def tube(axis, a0, a1, c, w, h, t):
    """Прямоугольная труба w x h x t вдоль axis, c — центр сечения (в порядке осей)."""
    if axis == "X":
        (yc, zc) = c
        o = box(a0, a1, yc - w / 2, yc + w / 2, zc - h / 2, zc + h / 2)
        i = box(a0 - 1, a1 + 1, yc - w / 2 + t, yc + w / 2 - t, zc - h / 2 + t, zc + h / 2 - t)
    elif axis == "Y":
        (xc, zc) = c
        o = box(xc - w / 2, xc + w / 2, a0, a1, zc - h / 2, zc + h / 2)
        i = box(xc - w / 2 + t, xc + w / 2 - t, a0 - 1, a1 + 1, zc - h / 2 + t, zc + h / 2 - t)
    else:
        (xc, yc) = c
        o = box(xc - w / 2, xc + w / 2, yc - h / 2, yc + h / 2, a0, a1)
        i = box(xc - w / 2 + t, xc + w / 2 - t, yc - h / 2 + t, yc + h / 2 - t, a0 - 1, a1 + 1)
    return o.cut(i)


def plate_xz(pts, y0, y1):
    """Плоская пластина с контуром pts=[(x,z)...] между y0 и y1."""
    y0, y1 = sorted((y0, y1))
    pl = cq.Plane(origin=(0, y1, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    return cq.Workplane(pl).polyline(pts).close().extrude(y1 - y0).val()


def hexprism_y(xc, zc, y0, y1, af):
    y0, y1 = sorted((y0, y1))
    pl = cq.Plane(origin=(xc, y0, zc), xDir=(1, 0, 0), normal=(0, 1, 0))
    return cq.Workplane(pl).polygon(6, af / math.cos(math.pi / 6)).extrude(y1 - y0).val()


def hexprism_x(yc, zc, x0, x1, af):
    x0, x1 = sorted((x0, x1))
    pl = cq.Plane(origin=(x0, yc, zc), xDir=(0, 1, 0), normal=(1, 0, 0))
    return cq.Workplane(pl).polygon(6, af / math.cos(math.pi / 6)).extrude(x1 - x0).val()


def hexprism_z(xc, yc, z0, z1, af):
    z0, z1 = sorted((z0, z1))
    pl = cq.Plane(origin=(xc, yc, z0), xDir=(1, 0, 0), normal=(0, 0, 1))
    return cq.Workplane(pl).polygon(6, af / math.cos(math.pi / 6)).extrude(z1 - z0).val()


def cut_all(s, tools):
    for t in tools:
        s = s.cut(t)
    return s


def fuse_all(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s.clean()


def mirror_y(s):
    return s.mirror("XZ")


def hull_outline(circles, extra_pts=()):
    """Контур выпуклой оболочки набора окружностей (x,z,r) и точек."""
    pts = list(extra_pts)
    for (x, z, r) in circles:
        for k in range(48):
            a = 2 * math.pi * k / 48
            pts.append((x + r * math.cos(a), z + r * math.sin(a)))
    pts = np.array(pts)
    h = ConvexHull(pts)
    return [tuple(map(float, pts[i])) for i in h.vertices]


# ===================================================================== крепёж (упрощённо)
M12 = dict(d=11.8, af=18.0, k=7.5, washer_d=24.0, washer_t=2.5, nut_h=10.0)


def bolt_y(xc, zc, y_head_face, y_end, head_side, d=11.8, af=18.0, k=7.5,
           washer=(24.0, 2.5)):
    """Болт вдоль Y. y_head_face — опорная поверхность под шайбой;
    head_side=+1 — головка со стороны +Y."""
    wd, wt = washer
    s = head_side
    yw1 = y_head_face + s * wt
    yh1 = yw1 + s * k
    parts = [cyl("Y", (xc, zc), y_end, yw1, d),
             cyl("Y", (xc, zc), y_head_face, yw1, wd).cut(cyl("Y", (xc, zc), y_head_face - 1, yw1 + 1, d + 1.2)),
             hexprism_y(xc, zc, yw1, yh1, af)]
    return fuse_all(parts)


def weld_nut_y(xc, zc, y_face, side, h=10.0, af=18.0, d_hole=12.0):
    y1 = y_face + side * h
    return hexprism_y(xc, zc, y_face, y1, af).cut(cyl("Y", (xc, zc), y_face - 20, y_face + 20, d_hole))


def nut_y(xc, zc, y_face, side, h=12.0, af=18.0):
    """Самоконтрящаяся гайка ISO 7042 М12 с шайбой (side — направление от опорной поверхности)."""
    yw = y_face + side * 2.5
    w = cyl("Y", (xc, zc), y_face, yw, 24.0).cut(cyl("Y", (xc, zc), y_face - 5, y_face + 5, 13.0))
    n = hexprism_y(xc, zc, yw, yw + side * h, af).cut(cyl("Y", (xc, zc), y_face - 30, y_face + 30, 12.0))
    return w.fuse(n)


def shoe_parts(prefix, sx0, sx1, holes_x, top_y0, col):
    """Башмак на гребне основания: верхняя пластина + приварная щека (внутри) + съёмная прижимная
    пластина (снаружи). Болты — головкой внутрь, гайки ISO 7042 снаружи. Все пластины 8 мм."""
    out = []
    holes = [cyl("Y", (x, FIN_HOLE_Z), 150, 340, HOLE) for x in holes_x]
    cy1 = RAIL_YC - FIN_T / 2 - GAP              # 265.8 — внутренняя (приварная) щека
    cl0 = RAIL_YC + FIN_T / 2 + GAP              # 274.2 — прижимная пластина
    L = sx1 - sx0
    out.append((f"{prefix}_top", box(sx0, sx1, top_y0, RAIL_YC + 15, FIN_Z1, FIN_Z1 + PLATE), col,
                f"Лист 8 мм {L:.0f}x{RAIL_YC + 15 - top_y0:.0f}", "steel"))
    # щёки начинаются на 8 мм выше лонжерона — не упираются в обварку гребня (катет ≤ 5 мм)
    out.append((f"{prefix}_cheek", cut_all(box(sx0, sx1, cy1 - PLATE, cy1, Z_RAIL_TOP + 8, FIN_Z1), holes), col,
                f"Лист 8 мм {L:.0f}x42, {len(holes_x)} отв. Ø13 (приварная щека = та же деталь, что прижимная)", "steel"))
    out.append((f"{prefix}_clamp", cut_all(box(sx0, sx1, cl0, cl0 + PLATE, Z_RAIL_TOP + 8, FIN_Z1), holes),
                C_PLATE, f"Лист 8 мм {L:.0f}x42, {len(holes_x)} отв. Ø13 (съёмная прижимная = та же деталь, что щека)", "steel"))
    for i, x in enumerate(holes_x):
        # головка снаружи (вынимается наружу), гайка внутри
        out.append((f"{prefix}_bolt_{i+1}", bolt_y(x, FIN_HOLE_Z, cl0 + PLATE, cy1 - PLATE - 16.5, +1), C_BOLT,
                    "Болт М12x45 8.8 + шайба", "fastener"))
        out.append((f"{prefix}_nut_{i+1}", nut_y(x, FIN_HOLE_Z, cy1 - PLATE, -1), C_BOLT,
                    "Гайка ISO 7042 М12 + шайба", "fastener"))
    return out


def plate_yz(pts, x0, x1):
    """Пластина с контуром pts=[(y,z)...] между x0 и x1."""
    x0, x1 = sorted((x0, x1))
    pl = cq.Plane(origin=(x0, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
    return cq.Workplane(pl).polyline(pts).close().extrude(x1 - x0).val()


def along_z_bolt(x, y, z_head_face, z_end):
    """Болт вдоль Z головкой вверх: опорная поверхность z_head_face, конец z_end (ниже)."""
    b = bolt_y(0, 0, 0, z_head_face - z_end, -1)          # вдоль Y: головка в −Y, стержень в +Y
    return b.rotate(V(0, 0, 0), V(1, 0, 0), -90).translate(V(x, y, z_head_face))


def along_z_nut(x, y, z_face):
    n = nut_y(0, 0, 0, +1)
    return n.rotate(V(0, 0, 0), V(1, 0, 0), -90).translate(V(x, y, z_face))


def along_x(shape_y, xc_y_z):
    """Перевести деталь, построенную вдоль Y в начале координат (ось Y через (0,0)), на ось X через точку."""
    x, y, z = xc_y_z
    return shape_y.rotate(V(0, 0, 0), V(0, 0, 1), -90).translate(V(x, y, z))


# ===================================================================== реестр деталей


@dataclass
class Part:
    name: str
    shape: object
    color: tuple
    group: str
    spec: str = ""
    ref: bool = False          # условный габарит покупного изделия (не входит в ВМ)
    kind: str = "steel"        # steel | fastener | liner | ref


@dataclass
class Model:
    cfg: Config
    parts: list = field(default_factory=list)
    notes: dict = field(default_factory=dict)

    def add(self, name, shape, color, group, spec="", ref=False, kind="steel"):
        self.parts.append(Part(name, shape, color, group, spec, ref, kind))

    def add_lr(self, name, shape_r, color, group, spec="", kind="steel"):
        """Деталь справа (+Y) и её зеркальная копия слева."""
        self.add(name + "_R", shape_r, color, group, spec, kind=kind)
        self.add(name + "_L", mirror_y(shape_r), color, group, spec, kind=kind)


# цвета (RGB 0..1)
C_BASE = (0.25, 0.27, 0.30)
C_TOWER = (0.80, 0.30, 0.15)
C_INNER = (0.95, 0.60, 0.15)
C_DECK = (0.20, 0.45, 0.75)
C_PEDAL = (0.20, 0.60, 0.35)
C_SEAT = (0.45, 0.35, 0.65)
C_PLATE = (0.55, 0.57, 0.60)
C_BOLT = (0.85, 0.80, 0.20)
C_LINER = (0.95, 0.95, 0.90)
C_REF = (0.70, 0.70, 0.75)
C_PLASTIC = (0.10, 0.10, 0.10)

# ===================================================================== основание


def build_base(m: Model):
    zc = Z_BASE + TUBE / 2
    for side, sgn in (("R", 1), ("L", -1)):
        m.add(f"base_rail_{side}", tube("X", 0, BASE_L, (sgn * RAIL_YC, zc), TUBE, TUBE, T_RAIL),
              C_BASE, "base", "Труба 40x40x3, L=1300")
    for side, sgn in (("R", 1), ("L", -1)):
        for k, xe in enumerate((-3.0, BASE_L)):
            m.add(f"base_cap_{side}{k+1}", box(xe, xe + 3, sgn * (RAIL_YC - 20), sgn * (RAIL_YC + 20), Z_BASE, Z_BASE + TUBE),
                  C_PLASTIC, "base", "Заглушка пластиковая 40x40 (вставная)", kind="purchased")
    yi = RAIL_YC - TUBE / 2   # 250
    for i, xc in enumerate(CROSS_X):
        t = 3.0          # все поперечины одинаковые — мастер не перепутает 2 и 3 мм
        m.add(f"base_cross_{i+1}", tube("Y", -yi, yi, (xc, zc), TUBE, TUBE, t),
              C_BASE, "base", f"Труба 40x40x{t:g}, L={2*yi:.0f}")
    # гребни-гребёнки (полоса 50x8 на ребро) с отверстиями шагом 25
    pedal_holes = PEDAL_FIN_HOLES
    seat_holes = SEAT_FIN_HOLES
    m.notes["pedal_fin_holes"] = pedal_holes
    m.notes["seat_fin_holes"] = seat_holes
    for zone, (x0, x1), holes in (("pedal", PEDAL_FIN_X, pedal_holes), ("seat", SEAT_FIN_X, seat_holes)):
        fin = box(x0, x1, RAIL_YC - FIN_T / 2, RAIL_YC + FIN_T / 2, FIN_Z0, FIN_Z1)
        fin = cut_all(fin, [cyl("Y", (x, FIN_HOLE_Z), 200, 340, HOLE) for x in holes])
        m.add_lr(f"fin_{zone}", fin, C_BASE, "base",
                 f"Лист 8 мм (лазер), гребень 50x{x1-x0:.0f}, {len(holes)} отв. Ø13 шаг 25")
    # площадки и регулируемые опоры
    for i, xf in enumerate(FOOT_X):
        x0 = min(max(xf - 30, 0.0), BASE_L - 60)
        # пластина выходит наружу за лонжерон: над гайкой свободно — шпилька опоры проходит вверх на весь ход
        yf = RAIL_YC + 48                      # ось опоры, 318
        pad = box(x0, x0 + 60, RAIL_YC - 20, RAIL_YC + 70, Z_BASE - 8, Z_BASE)
        pad = pad.cut(cyl("Z", (x0 + 30, yf), Z_BASE - 9, Z_BASE + 1, 13))
        m.add_lr(f"foot_plate_{i+1}", pad, C_BASE, "base", "Лист 8 мм 60x90, отв. Ø13 (выступает наружу)")
        nut = hexprism_z(x0 + 30, yf, Z_BASE - 18, Z_BASE - 8, 18).cut(cyl("Z", (x0 + 30, yf), 0, 60, 12))
        m.add_lr(f"foot_weldnut_{i+1}", nut, C_BOLT, "base", "Гайка М12 (приварная, под пластиной)", kind="fastener")
        foot = fuse_all([cyl("Z", (x0 + 30, yf), 0, 12, 50),
                         cyl("Z", (x0 + 30, yf), 12, Z_BASE + 25, 11.8),
                         hexprism_z(x0 + 30, yf, Z_BASE, Z_BASE + 10, 18)])
        m.add_lr(f"foot_{i+1}", foot, C_BOLT, "base", "Опора регулируемая М12x80, шарнирная, Ø50 + контргайка сверху",
                 kind="fastener")


# ===================================================================== рулевая стойка


def outer_post_parts():
    """Наружная стойка (правая) с рядом отверстий, накладками и вкладышами."""
    out = []
    x0, x1 = POST_X - OUTER / 2, POST_X + OUTER / 2         # 425..475
    y0, y1 = POST_YC - OUTER / 2, POST_YC + OUTER / 2       # 240..290
    post = tube("Z", Z_RAIL_TOP, OUTER_TOP, (POST_X, POST_YC), OUTER, OUTER, T_OUTER)
    holes = [cyl("Y", (POST_X, z), y0 - 30, y1 + 30, HOLE) for z in OUTER_ROW_Z]
    post = cut_all(post, holes)
    out.append(("tower_outer_post", post, C_TOWER, "Труба 50x50x3, L=%.0f, 10 отв. Ø13 шаг 25" % (OUTER_TOP - Z_RAIL_TOP)))
    # наружная косынка-накладка 8 мм (работает и как усиление стенки под болты, и как косынка к лонжерону)
    gx0, gx1, gz = POST_X - 90, POST_X + 120, OUTER_TOP - 14
    g = plate_xz([(gx0, Z_BASE + 5), (gx1, Z_BASE + 5), (gx1, Z_RAIL_TOP), (x1, Z_RAIL_TOP + 105),
                  (x1, gz), (x0, gz), (x0, Z_RAIL_TOP + 75), (gx0, Z_RAIL_TOP)], y1, y1 + PLATE)
    g = cut_all(g, holes)
    out.append(("tower_gusset_outer", g, C_PLATE, "Лист 8 мм, косынка-накладка, 10 отв. Ø13"))
    # прижимной винт М10 на передней грани: поджимает X-вкладыш, выбирает качку без перетяжки болтов
    jz = OUTER_TOP - 30
    post = post.cut(cyl("X", (POST_YC, jz), x0 - 1, x0 + 5, 10.5))
    out[0] = ("tower_outer_post", post, C_TOWER, out[0][3] + ", отв. Ø10.5 под прижим")
    out.append(("tower_press_weldnut", hexprism_x(POST_YC, jz, x0 - 8, x0, 17).cut(
        cyl("X", (POST_YC, jz), x0 - 20, x0 + 5, 10)), C_BOLT, "Гайка приварная М10 (прижим)"))
    out.append(("tower_press_screw", fuse_all([cyl("X", (POST_YC, jz), x0 - 22, x0 + T_OUTER, 9.8),
                                                hexprism_x(POST_YC, jz, x0 - 14, x0 - 8, 17),
                                                hexprism_x(POST_YC, jz, x0 - 28.5, x0 - 22, 16)]), C_BOLT,
                "Винт М10x30 + контргайка (прижим вкладыша)"))
    # внутренняя накладка не нужна: внутренняя стойка сплошная — пакет под болтом не сминается
    # стальные калиброванные вкладыши по граням Y (в пакете под болтом)
    for nm, (ya, yb) in (("in", (y0 + T_OUTER, y0 + T_OUTER + LINER)),
                         ("out", (y1 - T_OUTER - LINER, y1 - T_OUTER))):
        ln = box(POST_X - 18, POST_X + 18, ya, yb, Z_RAIL_TOP + 50, OUTER_TOP)
        # Т-образная головка (лазер, без гибки) лежит на торцах граней X — вкладыш не проваливается
        ln = ln.fuse(box(POST_X - 30, POST_X + 30, ya, yb, OUTER_TOP, OUTER_TOP + 5))
        ln = cut_all(ln, holes)
        out.append((f"tower_liner_steel_{nm}", ln, C_LINER,
                    "Лист 2 мм нерж. (лазер), вкладыш Т-образный 36/60x%.0f, 10 отв. Ø13; подбор 1.5/2.0/2.5"
                    % (OUTER_TOP + 5 - Z_RAIL_TOP - 50)))
    # вкладыши по граням X (без отверстий) — выбирают зазор поперёк оси болтов; головка лежит на головках Y-вкладышей
    for nm, (xa, xb) in (("front", (x0 + T_OUTER, x0 + T_OUTER + LINER)), ("rear", (x1 - T_OUTER - LINER, x1 - T_OUTER))):
        ln = box(xa, xb, POST_YC - 18, POST_YC + 18, Z_RAIL_TOP + 50, OUTER_TOP + 5)
        ln = ln.fuse(box(xa, xb, POST_YC - 28, POST_YC + 28, OUTER_TOP + 5, OUTER_TOP + 10))
        out.append((f"tower_liner_x_{nm}", ln, C_LINER,
                    "Лист 2 мм нерж. (лазер), вкладыш Т-образный 36/56x%.0f, без отв.; подбор 1.5/2.0/2.5"
                    % (OUTER_TOP + 10 - Z_RAIL_TOP - 50)))
    return out


def build_tower(m: Model):
    for name, s, col, spec in outer_post_parts():
        kind = "fastener" if "nut" in name or "screw" in name else ("liner" if "liner" in name else "steel")
        m.add_lr(name, s, col, "tower_fixed", spec, kind=kind)
    # подкосы назад (40x40x3): от задней грани стойки к лонжерону
    xa, za = POST_X + OUTER / 2, OUTER_TOP - 50
    xb, zb = CROSS_X[2], Z_RAIL_TOP
    L = math.hypot(xb - xa, za - zb) + 200
    ang = math.degrees(math.atan2(za - zb, xb - xa))
    raw = box(-100, L - 100, -20, 20, -20, 20)
    raw = raw.cut(box(-101, L, -17, 17, -17, 17))   # 40x40x3
    raw = raw.rotate(V(0, 0, 0), V(0, 1, 0), ang).translate(V(xa, RAIL_YC, za))
    br = raw.intersect(box(xa, 2000, 0, 400, zb, 2000))
    m.add_lr("tower_brace", br, C_TOWER, "tower_fixed",
             "Труба 40x40x3, подкос, L≈%.0f по оси" % math.hypot(xb - xa, za - zb))
    # приварная гайка М16 на поперечине основания под стойками — для съёмного домкратного винта
    # (перестановка высоты руля одним человеком: винт упирается в верхнюю поперечину)
    zc0 = Z_RAIL_TOP
    m.add("tower_jack_weldnut_M16", hexprism_z(POST_X, 0, zc0, zc0 + 13, 24).cut(cyl("Z", (POST_X, 0), zc0 - 1, zc0 + 20, 16)),
          C_BOLT, "tower_fixed", "Гайка М16 приварная (под съёмный домкратный винт М16)", kind="fastener")
    # внутренняя косынка стойки на поперечину основания (поперечная жёсткость узла стойка–основание)
    gi = plate_yz([(POST_YC - OUTER / 2, Z_RAIL_TOP), (POST_YC - OUTER / 2, Z_RAIL_TOP + 50),
                   (POST_YC - OUTER / 2 - 100, Z_RAIL_TOP)], POST_X - PLATE / 2, POST_X + PLATE / 2)
    m.add_lr("tower_gusset_inner", gi, C_PLATE, "tower_fixed",
             "Лист 8 мм (лазер), косынка 100x50 (ниже гаек нижнего положения)")
    m.notes["brace"] = (xa, za, xb, zb)


def build_height_unit(m: Model):
    """Подвижный П-образный узел: две внутренние стойки + верхняя поперечина + сёдла."""
    H = m.cfg.H
    top = H - STACK
    bot = top - INNER_L
    m.notes["inner_bot"] = bot
    zh = [bot + h for h in INNER_HOLE_FROM_BOTTOM]
    m.notes["inner_hole_z"] = zh
    for z in zh:
        assert any(abs(z - r) < 1e-6 for r in OUTER_ROW_Z), (z, "нет совпадения с рядом наружной стойки")
    y0, y1 = POST_YC - INNER / 2, POST_YC + INNER / 2   # 245..285
    ip = box(POST_X - INNER / 2, POST_X + INNER / 2, y0, y1, bot, top)
    ip = cut_all(ip, [cyl("Y", (POST_X, z), y0 - 1, y1 + 1, HOLE) for z in zh])
    m.add_lr("height_inner_post", ip, C_INNER, "height",
             "Квадрат сплошной 40x40 (калиброванный), L=%.0f, 2 отв. Ø13 (разнос 75) — станок + кондуктор" % INNER_L)
    # фиксирующие болты М12 (2 на стойку), головка снаружи, гайка ISO 7042 внутри
    for i, z in enumerate(zh):
        b = bolt_y(POST_X, z, POST_YC + OUTER / 2 + PLATE, POST_YC - OUTER / 2 - 17.5, +1)
        m.add_lr(f"height_bolt_{i+1}", b, C_BOLT, "height", "Болт М12x90 8.8 + шайба", kind="fastener")
        m.add_lr(f"height_nut_{i+1}", nut_y(POST_X, z, POST_YC - OUTER / 2, -1), C_BOLT, "height",
                 "Гайка ISO 7042 М12 + шайба DIN 9021", kind="fastener")
    # верхняя поперечина 40x40x3 на торцах внутренних стоек
    m.add("height_head_cross", tube("Y", -(POST_YC + 20), POST_YC + 20, (POST_X, top + 20), TUBE, TUBE, 3.0),
          C_INNER, "height", "Труба 40x40x3, L=570")
    for k, ye in enumerate((-(POST_YC + 23), POST_YC + 20)):
        m.add(f"height_head_cap_{k+1}", box(POST_X - 20, POST_X + 20, ye, ye + 3, top, top + 40), C_PLASTIC, "height",
              "Заглушка пластиковая 40x40", kind="purchased")
    # сёдла-вилки продольной регулировки
    zc_hole = H - DECK_T - DECK_FIN_H / 2      # H-33
    ycf = DECK_FIN_Y
    fy0, fy1 = ycf - DECK_FIN_T / 2, ycf + DECK_FIN_T / 2       # 175..185
    sx0, sx1 = POST_X - SADDLE_L / 2, POST_X + SADDLE_L / 2      # 375..525
    hx = [POST_X + h for h in SADDLE_HOLES]
    holes = [cyl("Y", (x, zc_hole), 100, 260, HOLE) for x in hx]
    cy0, cy1 = fy1 + GAP, fy1 + GAP + PLATE                         # наружная (приварная) щека
    cheek = plate_xz([(sx0, top), (POST_X - 20, top), (POST_X - 20, top + 40), (POST_X + 20, top + 40),
                      (POST_X + 20, top), (sx1, top), (sx1, H - DECK_T - 1), (sx0, H - DECK_T - 1)], cy0, cy1)
    cheek = cut_all(cheek, holes)
    m.add_lr("saddle_cheek_welded", cheek, C_INNER, "height",
             "Лист 8 мм %.0fx%.0f, вырез под поперечину, 2 отв. Ø13" % (SADDLE_L, H - DECK_T - 1 - top))
    ly0, ly1 = fy0 - GAP - PLATE, fy0 - GAP
    lp = cut_all(box(sx0, sx1, ly0, ly1, top + 40, H - DECK_T - 1), holes)
    m.add_lr("saddle_clamp_plate", lp, C_PLATE, "height",
             "Лист 8 мм %.0fx%.0f, 2 отв. Ø13, съёмная прижимная" % (SADDLE_L, H - DECK_T - 41 - top))
    m.notes["saddle_holes_x"] = hx
    m.notes["saddle_ly0"] = ly0
    m.notes["saddle_cy1"] = cy1


def build_deck(m: Model):
    H, d = m.cfg.H, m.cfg.d
    zc_hole = H - DECK_T - DECK_FIN_H / 2
    active = SADDLE_HOLES
    # отверстия гребня (в координатах площадки при d = 0) — объединение всех рабочих положений
    fin_holes = set()
    for dd in np.arange(D_MIN, D_MAX + 0.01, D_STEP):
        for h in SADDLE_HOLES:
            fin_holes.add(round(POST_X + h - dd, 3))
    fin_holes = sorted(fin_holes)
    m.notes["deck_fin_holes_nom"] = fin_holes
    x0, x1 = DECK_X0_NOM + d, DECK_X0_NOM + DECK_D + d
    fy0, fy1 = DECK_FIN_Y - DECK_FIN_T / 2, DECK_FIN_Y + DECK_FIN_T / 2
    fin = box(x0, x1, fy0, fy1, H - DECK_T - DECK_FIN_H, H - DECK_T)
    fin = cut_all(fin, [cyl("Y", (x + d, zc_hole), 100, 260, HOLE) for x in fin_holes])
    # проверка: активные отверстия седла совпадают с отверстиями гребня
    for h in active:
        xs = POST_X + h
        assert any(abs(xs - (x + d)) < 1e-6 for x in fin_holes), ("нет совпадения", xs, d)
    m.add_lr("deck_fin", fin, C_DECK, "deck", "Лист 8 мм (лазер), гребень 50x%.0f, %d отв. Ø13 шаг 25" % (DECK_D, len(fin_holes)))
    # 2 ряда болтов (разнос 100) — вне пути болтов сёдел при любом положении площадки
    fm_holes = [(x0 + dx, y) for dx in (45.0, 145.0) for y in (-90.0, 90.0)]
    plate = box(x0, x1, -DECK_W / 2, DECK_W / 2, H - DECK_T, H)
    plate = cut_all(plate, [cyl("Z", (x, y), H - 20, H + 20, HOLE) for (x, y) in fm_holes])
    m.add("deck_plate", plate, C_DECK, "deck",
          "Лист 8 мм %.0fx%.0f, 4 отв. Ø13 под фронтальный кронштейн (отверстия под базу — после выбора базы)"
          % (DECK_W, DECK_D))
    if m.cfg.front_mount:
        fl = cut_all(box(x0 + 20, x0 + 190, -165, 165, H, H + PLATE),
                     [cyl("Z", (x, y), H - 5, H + 20, HOLE) for (x, y) in fm_holes])
        m.add("deck_fm_flange", fl, C_DECK, "deck", "Лист 8 мм (лазер) 170x330, 4 отв. Ø13 — основание фронтального кронштейна")
        m.add("deck_fm_plate", box(x0 + 20, x0 + 28, -150, 150, H + PLATE, H + 230), C_DECK, "deck",
              "Лист 8 мм (лазер) 300x222 — фронтальная плита (отверстия под базу — после выбора базы)")
        for y in (-118.0, 110.0):
            g = plate_xz([(x0 + 28, H + PLATE), (x0 + 190, H + PLATE), (x0 + 28, H + 200)], y, y + PLATE)
            m.add(f"deck_fm_gusset_{'L' if y < 0 else 'R'}", g, C_DECK, "deck", "Лист 8 мм (лазер), косынка 162x192")
        for i, (x, y) in enumerate(fm_holes):
            b = along_z_bolt(x, y, H + PLATE, H - DECK_T - 16.5)
            m.add(f"deck_fm_bolt_{i+1}", b, C_BOLT, "deck", "Болт М12x40 8.8 + шайба", kind="fastener")
            m.add(f"deck_fm_nut_{i+1}", along_z_nut(x, y, H - DECK_T), C_BOLT, "deck", "Гайка ISO 7042 М12 + шайба",
                  kind="fastener")
    for i, h in enumerate(active):
        xs = POST_X + h
        b = bolt_y(xs, zc_hole, m.notes["saddle_ly0"], m.notes["saddle_cy1"] + 17.5, -1)
        m.add_lr(f"deck_bolt_{i+1}", b, C_BOLT, "deck", "Болт М12x45 8.8 + шайба", kind="fastener")
        m.add_lr(f"deck_nut_{i+1}", nut_y(xs, zc_hole, m.notes["saddle_cy1"], +1), C_BOLT, "deck",
                 "Гайка ISO 7042 М12 + шайба", kind="fastener")


# ===================================================================== педальный узел


def pedal_carriage_parts(xp, alpha, pz=PEDAL_PIVOT_Z):
    out = []
    sx0, sx1 = xp - 225, xp - 25
    shoe_holes = [xp - 200, xp - 125, xp - 50]
    out += shoe_parts("pedal_shoe", sx0, sx1, shoe_holes, UPRIGHT_Y0 + 8, C_PEDAL)
    # щека-сектор: ось качания + дуга отверстий R250, углы 20..60°
    P = (xp, pz)
    pts = []
    for z0 in PEDAL_PZ:                      # два ряда оси — регулировка высоты педалей
        pts.append((xp, z0))
        for R in PEDAL_R:
            for a in PEDAL_ANGLES:
                ar = math.radians(a)
                pts.append((xp - R * math.cos(ar), z0 + R * math.sin(ar)))
    circles = [(x, z, 22) for (x, z) in pts]
    outline = hull_outline(circles, [(sx0, FIN_Z1 + 8), (sx1, FIN_Z1 + 8), (sx0, Z_RAIL_TOP + 10),
                                     (xp + 22, Z_RAIL_TOP + 10)])
    up = plate_xz(outline, UPRIGHT_Y0, UPRIGHT_Y0 + 8)
    up = cut_all(up, [cyl("Y", (x, z), 200, 260, HOLE) for (x, z) in pts])
    out.append(("pedal_sector_plate", up, C_PEDAL, "Лист 8 мм, щека-сектор, %d отв. Ø13" % len(pts), "steel"))
    # болты: ось + один на дуге для выбранного угла
    ar = math.radians(alpha)
    act = [P] + [(P[0] - R * math.cos(ar), P[1] + R * math.sin(ar)) for R in PEDAL_R]
    for i, (x, z) in enumerate(act):
        # головка изнутри площадки (вынимается внутрь — снаружи мешает гребень), гайка снаружи сектора
        b = bolt_y(x, z, UPRIGHT_Y0 - 1 - 8, UPRIGHT_Y0 + 8 + 16.5, -1)
        out.append((f"pedal_pivot_bolt_{i+1}", b, C_BOLT, "Болт М12x40 8.8 + шайба", "fastener"))
        out.append((f"pedal_pivot_nut_{i+1}", nut_y(x, z, UPRIGHT_Y0 + 8, +1), C_BOLT, "Гайка ISO 7042 М12 + шайба",
                    "fastener"))
    return out


def build_pedals(m: Model):
    xp, alpha = m.cfg.xp, m.cfg.alpha
    for name, s, col, spec, kind in pedal_carriage_parts(xp, alpha, m.cfg.pz):
        m.add_lr(name, s, col, "pedals", spec, kind=kind)
    # площадка педалей — строится в локальной СК (u — вдоль наклона, ось качания в начале)
    fl_y1 = UPRIGHT_Y0 - 1            # 230
    fl_y0 = fl_y1 - 8                 # 222
    parts = []
    plate = box(-25, -25 + TRAY_L, -TRAY_W / 2, TRAY_W / 2, -25 - TRAY_T, -25)
    parts.append(("pedal_tray_plate", plate, "Лист 8 мм %.0fx%.0f (отв. под педали — по месту)" % (TRAY_W, TRAY_L)))
    for sgn, side in ((1, "R"), (-1, "L")):
        fl = box(-25, -25 + TRAY_L, sgn * fl_y0, sgn * fl_y1, -25, 25)
        fl = cut_all(fl, [cyl("Y", (u, 0), -300, 300, HOLE) for u in (0.0,) + PEDAL_R])
        parts.append((f"pedal_tray_flange_{side}", fl, "Лист 8 мм (лазер), фланец 50x330, %d отв. Ø13" % (1 + len(PEDAL_R))))

    for j, u in enumerate((80.0, 180.0)):
        st = tube("Y", -fl_y0, fl_y0, (u + 20, -5.0), 40, 40, 3.0)   # под листом (та же труба 40x40x3)
        parts.append((f"pedal_tray_stiffener_{j+1}", st, "Труба 40x40x3, L=%.0f" % (2 * fl_y0)))
    rot = alpha - 180.0
    for name, s, spec in parts:
        # локальная −Z (низ листа) после поворота смотрит вверх-назад, к пилоту
        s2 = s.rotate(V(0, 0, 0), V(0, 1, 0), rot).translate(V(xp, 0, m.cfg.pz))
        kind = "fastener" if "nut" in name else "steel"
        m.add(name, s2, C_BOLT if kind == "fastener" else C_PEDAL, "pedals", spec, kind=kind)
    m.notes["tray_rot"] = rot


def tray_point(cfg, u, w):
    """Глобальные X,Z точки площадки: u — вдоль наклона от оси, w — по нормали (вверх-назад)."""
    a = math.radians(cfg.alpha)
    return (cfg.xp - u * math.cos(a) + w * math.sin(a), cfg.pz + u * math.sin(a) + w * math.cos(a))


# ===================================================================== сиденье


def build_seat(m: Model):
    for k, xc in enumerate((m.cfg.xc1, m.cfg.xc2)):
        parts = shoe_parts(f"seat_shoe{k+1}", xc - 75, xc + 75, (xc - 50, xc, xc + 50), 245, C_SEAT)
        for name, s, col, spec, kind in parts:
            m.add_lr(name, s, col, "seat", spec, kind=kind)
        zt = FIN_Z1 + 8
        m.add(f"seat_crossbar_{k+1}", tube("Y", -285, 285, (xc, zt + 25), 50, 50, 3.0), C_SEAT, "seat",
              "Труба 50x50x3, L=570 (жёсткая на кручение — держит кронштейн ручника)")
        m.add(f"seat_crossbar_flange_{k+1}", box(xc - 40, xc + 40, -262, 262, zt + 50, zt + 58), C_SEAT, "seat",
              "Лист 8 мм (лазер) 80x524 — полка поперечины (сверловка под салазки по месту)")
    zt = FIN_Z1 + 8 + 58       # 201
    x0, x1 = m.cfg.xc1 - 60, m.cfg.xc2 + 60
    for sgn, side in ((1, "R"), (-1, "L")):
        m.add(f"seat_adapter_bar_{side}", box(x0, x1, sgn * 165, sgn * 215, zt, zt + 8), C_PLATE, "seat",
              "Лист 8 мм (лазер) 50x%.0f — адаптер под салазки (отверстия по месту)" % (x1 - x0))
    m.notes["seat_mount_z"] = zt + 8


# ===================================================================== кронштейн шифтера / ручника


def build_side_mount(m: Model):
    """Съёмный боковой кронштейн на торце передней поперечины сиденья (едет вместе с сиденьем).
    Фланцы под него приварены на ОБОИХ торцах поперечины — ставится справа или слева."""
    xc = m.cfg.xc1
    zt = FIN_Z1 + PLATE                       # низ поперечины, 143
    fz0, fz1 = zt, zt + 72                    # фланец по высоте 143…215
    fl_holes_xz = [(xc + dx, z) for dx in (-44, 44) for z in (158.0, 200.0)]   # торцевая головка 18 мм проходит
    # фланцы на торцах поперечины (оба торца — часть узла сиденья)
    for k, xcb in enumerate((m.cfg.xc1, m.cfg.xc2)):      # обе поперечины одинаковые — с фланцами
        hb = [(xcb + dx, z) for dx in (-44, 44) for z in (158.0, 200.0)]
        for sgn, nm in ((1, "R"), (-1, "L")):
            f = box(xcb - 58, xcb + 58, 285, 293, fz0, fz1)
            f = cut_all(f, [cyl("Y", (x, z), 270, 310, HOLE) for (x, z) in hb])
            m.add(f"seat_end_flange_{nm}{k+1}", f if sgn > 0 else mirror_y(f), C_SEAT, "seat",
                  "Лист 8 мм (лазер) 116x72, 4 отв. Ø13 — фланец под боковой кронштейн")
    if m.cfg.side == 0:
        return
    parts = []
    # ответный фланец + консоль 40x40x3 + стакан 50x50x3 + косынка
    f2 = cut_all(box(xc - 58, xc + 58, 293, 301, fz0, fz1),
                 [cyl("Y", (x, z), 270, 320, HOLE) for (x, z) in fl_holes_xz])
    parts.append(("side_flange", f2, C_SEAT, "Лист 8 мм (лазер) 116x72, 4 отв. Ø13", "steel"))
    za = 170.0
    parts.append(("side_arm", tube("Y", SIDE_ARM_Y[0], SIDE_ARM_Y[1], (xc, za), 40, 40, 3.0), C_SEAT,
                  "Труба 40x40x3, L=%.0f" % (SIDE_ARM_Y[1] - SIDE_ARM_Y[0]), "steel"))
    cy0, cy1 = SIDE_CUP_YC - 25, SIDE_CUP_YC + 25
    cup = tube("Z", SIDE_CUP_Z[0], SIDE_CUP_Z[1], (xc, SIDE_CUP_YC), 50, 50, 3.0)
    holes = [cyl("X", (SIDE_CUP_YC, z), xc - 40, xc + 40, HOLE) for z in SIDE_CUP_ROW]
    cup = cut_all(cup, holes)
    parts.append(("side_cup", cup, C_SEAT, "Труба 50x50x3, L=%.0f, 8 отв. Ø13 шаг 25 (труборез)"
                  % (SIDE_CUP_Z[1] - SIDE_CUP_Z[0]), "steel"))
    g = plate_yz([(SIDE_ARM_Y[0] + 20, za - 20), (cy0, za - 20), (cy0, za - 95)], xc + 12, xc + 20)   # под задней стенкой консоли — не мешает болту башмака
    parts.append(("side_gusset", g, C_SEAT, "Лист 8 мм (лазер), косынка", "steel"))
    # калиброванные вкладыши по граням X (в пакете под болтом), Т-головка на торце стакана
    for nm, (xa, xb) in (("front", (xc - 22, xc - 20)), ("rear", (xc + 20, xc + 22))):
        ln = box(xa, xb, SIDE_CUP_YC - 18, SIDE_CUP_YC + 18, SIDE_CUP_ROW[0] - 30, SIDE_CUP_Z[1])
        ln = ln.fuse(box(xa, xb, SIDE_CUP_YC - 30, SIDE_CUP_YC + 30, SIDE_CUP_Z[1], SIDE_CUP_Z[1] + 5))
        parts.append((f"side_liner_{nm}", cut_all(ln, holes), C_LINER,
                      "Лист 2 мм нерж. (лазер), вкладыш Т-образный, 8 отв. Ø13", "liner"))
    for nm, (ya, yb) in (("in", (SIDE_CUP_YC - 22, SIDE_CUP_YC - 20)), ("out", (SIDE_CUP_YC + 20, SIDE_CUP_YC + 22))):
        ln = box(xc - 18, xc + 18, ya, yb, SIDE_CUP_ROW[0] - 30, SIDE_CUP_Z[1] + 5)
        ln = ln.fuse(box(xc - 28, xc + 28, ya, yb, SIDE_CUP_Z[1] + 5, SIDE_CUP_Z[1] + 10))
        parts.append((f"side_liner_y_{nm}", ln, C_LINER, "Лист 2 мм нерж. (лазер), вкладыш Т-образный, без отв.", "liner"))
    zp = m.cfg.zp
    zh = [zp - h for h in SIDE_BAR_HOLES]
    for z in zh:
        assert any(abs(z - r) < 1e-6 for r in SIDE_CUP_ROW), ("кронштейн: нет совпадения отверстий", z)
    bar = box(xc - 20, xc + 20, SIDE_CUP_YC - 20, SIDE_CUP_YC + 20, zp - SIDE_BAR_L, zp)
    bar = cut_all(bar, [cyl("X", (SIDE_CUP_YC, z), xc - 30, xc + 30, HOLE) for z in zh])
    parts.append(("side_bar", bar, C_INNER, "Квадрат сплошной 40x40 (калиброванный), L=%.0f, 2 отв. Ø13 (разнос 75) — станок + кондуктор" % SIDE_BAR_L,
                  "steel"))
    px, py = SIDE_PLATE
    plat = box(xc - px / 2 - 70, xc + px / 2 - 70, SIDE_CUP_YC - py / 2, SIDE_CUP_YC + py / 2, zp, zp + PLATE)
    parts.append(("side_platform", plat, C_SEAT,
                  "Лист 8 мм %.0fx%.0f — платформа шифтера/ручника (отверстия под устройства — по месту)" % (px, py),
                  "steel"))
    for i, z in enumerate(zh):
        b = along_x(bolt_y(0, 0, 0, 25 + 17.5 + 50, -1), (xc - 25, SIDE_CUP_YC, z))
        parts.append((f"side_bolt_{i+1}", b, C_BOLT, "Болт М12x90 8.8 + шайба", "fastener"))
        n = along_x(nut_y(0, 0, 0, +1), (xc + 25, SIDE_CUP_YC, z))
        parts.append((f"side_nut_{i+1}", n, C_BOLT, "Гайка ISO 7042 М12 + шайба DIN 9021", "fastener"))
    for i, (x, z) in enumerate(fl_holes_xz):
        parts.append((f"side_flange_bolt_{i+1}", bolt_y(x, z, 301, 285 - 16.5, +1), C_BOLT,
                      "Болт М12x40 8.8 + шайба", "fastener"))
        parts.append((f"side_flange_nut_{i+1}", nut_y(x, z, 285, -1), C_BOLT, "Гайка ISO 7042 М12 + шайба",
                      "fastener"))
    cap = box(xc - 25, xc + 25, cy0, cy1, SIDE_CUP_Z[0] - 3, SIDE_CUP_Z[0])
    parts.append(("side_cup_cap", cap, C_PLASTIC, "Заглушка пластиковая 50x50", "purchased"))
    for name, s_, col, spec, kind in parts:
        if m.cfg.side < 0:
            s_ = mirror_y(s_)
        m.add(name, s_, col, "side", spec, kind=kind)


# ===================================================================== условные габариты (не изготавливаются)


def build_refs(m: Model):
    cfg = m.cfg
    H, d = cfg.H, cfg.d
    zax = H + (110 if cfg.front_mount else 70)
    xb0 = DECK_X0_NOM + d + RIM_FROM_DECK_FRONT - 320 + (18 if cfg.front_mount else 0)
    base = cyl("X", (0, zax), xb0, xb0 + 230, 130)
    if not cfg.front_mount:
        base = fuse_all([base, box(xb0, xb0 + 230, -70, 70, H, zax)])
    m.add("REF_wheelbase", base, C_REF, "ref", "Условный габарит DD-базы Ø130x230", ref=True, kind="ref")
    hub = cyl("X", (0, zax), xb0 + 230, xb0 + 310, 60)
    m.add("REF_wheel_hub", hub, C_REF, "ref", "Условный быстросъём + ступица", ref=True, kind="ref")
    xr = xb0 + 320
    rim = cq.Solid.makeTorus(150, 14, V(xr, 0, zax), V(1, 0, 0))
    spokes = fuse_all([box(xr - 6, xr + 6, -150, 150, zax - 15, zax + 15), box(xr - 6, xr + 6, -15, 15, zax - 150, zax)])
    m.add("REF_wheel_rim", fuse_all([rim, spokes]), C_REF, "ref", "Условный обод Ø300 (центр обода)", ref=True, kind="ref")
    m.notes["rim"] = (xr, zax, 150)
    # сиденье (условный ковш) на салазках
    zs = m.notes["seat_mount_z"]
    xs0 = cfg.xc1 - 40 + cfg.slide
    sl = [box(xs0, xs0 + 420, s * 170, s * 205, zs, zs + 35) for s in (1, -1)]
    m.add("REF_seat_sliders", fuse_all(sl), C_REF, "ref", "Условные салазки", ref=True, kind="ref")
    zc = zs + 35
    cushion = box(xs0, xs0 + 400, -255, 255, zc, zc + 90)
    bols = [box(xs0 + 40, xs0 + 400, s * 200, s * 255, zc + 90, zc + 170) for s in (1, -1)]
    back = box(-40, 40, -255, 255, 0, 720)
    back = back.rotate(V(0, 0, 0), V(0, 1, 0), SEAT_RECLINE).translate(V(xs0 + 400, 0, zc + 40))
    m.add("REF_seat_shell", fuse_all([cushion] + bols + [back]), C_REF, "ref",
          "Условный ковш сиденья (габарит)", ref=True, kind="ref")
    m.notes["seat_xs0"] = xs0
    m.notes["seat_zc"] = zc


def build_model(cfg: Config, refs=None):
    cfg.validate()
    m = Model(cfg)
    build_base(m)
    build_tower(m)
    build_height_unit(m)
    build_deck(m)
    build_pedals(m)
    build_seat(m)
    build_side_mount(m)
    if cfg.show_refs if refs is None else refs:
        build_refs(m)
    return m
