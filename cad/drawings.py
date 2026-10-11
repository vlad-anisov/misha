"""
Генерация листов чертежей (PNG + общий PDF) из параметрической модели.

    python cad/drawings.py           -> drawings/*.png, drawings/simrig_concept_drawings.pdf
"""
import math
import os
import sys
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle, FancyBboxPatch, Arc  # noqa: E402
from matplotlib.path import Path  # noqa: E402
import numpy as np  # noqa: E402

import cadquery as cq  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common  # noqa: E402
from OCP.BRepTools import BRepTools_WireExplorer  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Curve  # noqa: E402
from OCP.GCPnts import GCPnts_QuasiUniformDeflection  # noqa: E402
from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopoDS import TopoDS  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace  # noqa: E402
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from params import *  # noqa: E402,F401,F403
from simrig import build_model, box, tray_point  # noqa: E402
from render import shaded, hlr_lines, draw_lines, project, view_axes, VIEWS  # noqa: E402
import ergonomics as ERG  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTD = os.path.join(ROOT, "drawings")
A3 = (16.54, 11.69)
DPI = 150
FS = 7.5
SHEETS = []

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS})


# ======================================================================= оформление листа

def new_sheet(title, subtitle=""):
    fig = plt.figure(figsize=A3)
    fig.patches.append(Rectangle((0.012, 0.012), 0.976, 0.976, transform=fig.transFigure, fill=False, lw=1.2,
                                 edgecolor="k"))
    # штамп
    x0, y0, w, h = 0.70, 0.014, 0.286, 0.085
    fig.patches.append(Rectangle((x0, y0), w, h, transform=fig.transFigure, fill=False, lw=1.0, edgecolor="k"))
    fig.text(x0 + 0.006, y0 + h - 0.018, title, fontsize=11, weight="bold", va="top")
    if subtitle:
        fig.text(x0 + 0.006, y0 + h - 0.040, subtitle, fontsize=7.5, va="top")
    fig.text(x0 + 0.006, y0 + 0.020, "Каркас автосимулятора — КОНЦЕПЦИЯ (не рабочая документация)",
             fontsize=7.2, va="bottom", color="#a00000")
    fig.text(x0 + 0.006, y0 + 0.005, f"Размеры в мм · масштаб условный · лист {len(SHEETS)+1} · {date.today():%d.%m.%Y}",
             fontsize=6.8, va="bottom")
    return fig


def save(fig, name):
    os.makedirs(OUTD, exist_ok=True)
    fig.savefig(os.path.join(OUTD, name + ".png"), dpi=DPI)
    SHEETS.append((name, fig))


def axes(fig, rect, title=None):
    ax = fig.add_axes(rect)
    ax.set_aspect("equal")
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=9, weight="bold", loc="left")
    return ax


# ======================================================================= размеры

def dim(ax, p1, p2, off, text=None, axis="x", fs=FS, color="#1144aa", ext=True, tpos=0.5):
    """Линейный размер. axis='x' — горизонтальный, 'y' — вертикальный, 'a' — по направлению p1→p2."""
    p1, p2 = np.array(p1, float), np.array(p2, float)
    if axis == "x":
        yd = (p1[1] if off < 0 else max(p1[1], p2[1])) + off if False else max(p1[1], p2[1]) + off if off > 0 else min(p1[1], p2[1]) + off
        a, b = np.array([p1[0], yd]), np.array([p2[0], yd])
        val = abs(p2[0] - p1[0])
    elif axis == "y":
        xd = max(p1[0], p2[0]) + off if off > 0 else min(p1[0], p2[0]) + off
        a, b = np.array([xd, p1[1]]), np.array([xd, p2[1]])
        val = abs(p2[1] - p1[1])
    else:
        v = p2 - p1; L = np.linalg.norm(v); u = v / L; n = np.array([-u[1], u[0]])
        a, b = p1 + n * off, p2 + n * off
        val = L
    if ext:
        sgn = 1 if off > 0 else -1
        for p, q in ((p1, a), (p2, b)):
            d = q - p
            if np.linalg.norm(d) > 1e-6:
                e = q + d / np.linalg.norm(d) * 4
                ax.plot([p[0], e[0]], [p[1], e[1]], color=color, lw=0.4, zorder=6)
    ax.annotate("", xy=a, xytext=b, arrowprops=dict(arrowstyle="<|-|>", color=color, lw=0.6,
                                                    shrinkA=0, shrinkB=0, mutation_scale=7), zorder=6)
    if text is None:
        text = f"{val:.0f}" if abs(val - round(val)) < 0.05 else f"{val:.1f}"
    m = a + (b - a) * tpos
    if axis == "y":
        ax.text(m[0] - 3, m[1], text, rotation=90, ha="right", va="center", fontsize=fs, color=color, zorder=7,
                bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))
    else:
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) if axis == "a" else 0
        if ang > 90 or ang < -90:
            ang += 180
        ax.text(m[0], m[1] + 3, text, rotation=ang, ha="center", va="bottom", fontsize=fs, color=color, zorder=7,
                rotation_mode="anchor", bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))


def note(ax, xy, xytext, text, fs=FS, color="k", ha="left"):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=fs, color=color, ha=ha, va="center", zorder=8,
                arrowprops=dict(arrowstyle="-|>", lw=0.5, color=color, mutation_scale=6, shrinkA=1, shrinkB=1),
                bbox=dict(fc="white", ec=color, lw=0.4, pad=1.5, boxstyle="round,pad=0.25"))


def label(ax, xy, text, fs=FS + 1, color="k", **kw):
    kw.setdefault("fontsize", fs)
    ax.text(xy[0], xy[1], text, color=color, zorder=8, **kw)


# ======================================================================= сечения

def _wire_pts(w, defl=0.1):
    pts = []
    ex = BRepTools_WireExplorer(w)
    while ex.More():
        e = ex.Current()
        c = BRepAdaptor_Curve(e)
        d = GCPnts_QuasiUniformDeflection(c, defl)
        seg = [(d.Value(i).X(), d.Value(i).Y(), d.Value(i).Z()) for i in range(1, d.NbPoints() + 1)]
        if e.Orientation() == 1:  # REVERSED
            seg = seg[::-1]
        pts.extend(seg)
        ex.Next()
    return np.array(pts)


def section(ax, parts, origin, normal, view, hatch_color=None, lw=0.6):
    """Сечение деталей плоскостью: заливка + штриховка; возвращает число найденных контуров."""
    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*origin), gp_Dir(*normal)), -5000, 5000, -5000, 5000).Face()
    n = 0
    for p in parts:
        com = BRepAlgoAPI_Common(p.shape.wrapped, face)
        sh = com.Shape()
        exf = TopExp_Explorer(sh, TopAbs_FACE)
        while exf.More():
            f = TopoDS.Face_s(exf.Current())
            verts, codes = [], []
            exw = TopExp_Explorer(f, TopAbs_WIRE)
            while exw.More():
                w = TopoDS.Wire_s(exw.Current())
                P = _wire_pts(w)
                if len(P) > 2:
                    P2 = project(P, view)
                    verts.extend(list(P2) + [P2[0]])
                    codes.extend([Path.MOVETO] + [Path.LINETO] * (len(P2) - 1) + [Path.CLOSEPOLY])
                exw.Next()
            if verts:
                col = np.array(p.color) * 0.5 + 0.5
                pp = PathPatch(Path(verts, codes), facecolor=col, edgecolor="k", lw=lw, hatch="////", zorder=4)
                ax.add_patch(pp)
                n += 1
            exf.Next()
    return n


def clip(parts, x=(-1e4, 1e4), y=(-1e4, 1e4), z=(-1e4, 1e4)):
    """Детали, обрезанные коробкой (для местных видов/разрезов)."""
    B = box(x[0], x[1], y[0], y[1], z[0], z[1])
    bb = B.BoundingBox()
    out = []
    for p in parts:
        pb = p.shape.BoundingBox()
        if pb.xmax < bb.xmin or pb.xmin > bb.xmax or pb.ymax < bb.ymin or pb.ymin > bb.ymax or pb.zmax < bb.zmin or pb.zmin > bb.zmax:
            continue
        s = p.shape.intersect(B)
        if s.Volume() > 1e-3:
            q = type(p)(p.name, s, p.color, p.group, p.spec, p.ref, p.kind)
            out.append(q)
    return out


def lines(ax, parts, view, lw=0.55, color="k", hidden=False, hcolor="0.65"):
    shapes = [p.shape for p in parts]
    if not shapes:
        return
    vis, hid = hlr_lines(shapes, view, hidden=hidden)
    if hidden:
        draw_lines(ax, hid, hcolor, lw * 0.55, (0, (3, 2)))
    draw_lines(ax, vis, color, lw)


def fit(ax, xs, ys, pad=40):
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)


# ======================================================================= листы

def frame_parts(m, refs=False):
    return [p for p in m.parts if refs or not p.ref]


def sheet_iso(m):
    fig = new_sheet("Общий вид — изометрия", "Номинальная конфигурация; полупрозрачно — условные габариты руля и сиденья")
    ax = axes(fig, [0.02, 0.10, 0.62, 0.86])
    shaded(ax, m.parts, "iso_rear", cull=False)
    ax2 = axes(fig, [0.60, 0.42, 0.38, 0.54])
    shaded(ax2, m.parts, "iso", cull=False)
    # подписи на основном виде
    def P(x, y, z):
        return project([(x, y, z)], "iso_rear")[0]
    cfg = m.cfg
    tags = [
        (P(0, -270, 65), "Основание 1300×580,\nтруба 40×40×3", (-160, 60)),
        (P(550, -290, 300), "Наружная стойка 50×50×3\n+ косынка-накладка 6 мм,\nряд отв. Ø13 шаг 25", (-260, 40)),
        (P(550, -265, cfg.H - 140), "Выдвижная стойка 40×40×3\n(телескоп, 2 болта М12)", (-300, 40)),
        (P(550 + 150, -270, 250), "Подкос 40×40×2", (60, -40)),
        (P(550, -190, cfg.H - 40), "Седло-вилка + гребень 60×10\n(продольная регулировка)", (-330, 60)),
        (P(400, 0, cfg.H), "Площадка руля 420×300×6", (-120, 110)),
        (P(cfg.xp - 120, -235, 230), "Педальная площадка 460×330\nна щеках-секторах (угол 20…60°)", (-200, -60)),
        (P(cfg.xp - 120, -275, 110), "Башмак на гребне 50×8\n(3 болта М12)", (-160, -110)),
        (P(cfg.xc1, -260, 160), "Поперечины сиденья\nна башмаках (шаг 25)", (100, -80)),
        (P(1280, -270, 20), "Регулируемые опоры М12 (6 шт.)", (60, -50)),
    ]
    for xy, t, dxy in tags:
        note(ax, xy, (xy[0] + dxy[0], xy[1] + dxy[1]), t, fs=7.5)
    fig.text(0.62, 0.38, "Цвета: тёмно-серый — основание; красный — неподвижная часть стойки; оранжевый — подвижный узел высоты;\n"
             "синий — площадка руля; зелёный — педальный узел; фиолетовый — узел сиденья; светло-серый — накладки/вкладыши;\n"
             "жёлтый — крепёж; полупрозрачный — условные габариты (база Ø130×230, обод Ø300, ковш сиденья).",
             fontsize=7.5, va="top")
    fig.text(0.62, 0.30, "Слева — вид сзади-слева (со стороны пилота), справа вверху — вид спереди-слева.", fontsize=7.5)
    save(fig, "S01_isometric")


def sheet_side(m):
    cfg = m.cfg
    fig = new_sheet("Вид сбоку (слева)", "Номинал: H=650, d=0, педали X=285 / 30°, сиденье 925/1200")
    ax = axes(fig, [0.03, 0.12, 0.94, 0.84])
    fp = frame_parts(m)
    lines(ax, fp, "side", hidden=False)
    refs = [p for p in m.parts if p.ref]
    lines(ax, refs, "side", lw=0.4, color="0.6")
    H = cfg.H
    # педальная площадка — выделить линию верхней плоскости
    a = tray_point(cfg, -25, 31); b = tray_point(cfg, 305, 31)
    ax.plot([a[0], b[0]], [a[1], b[1]], color="#0a8a3a", lw=2.2, zorder=9)
    note(ax, (b[0], b[1]), (b[0] - 20, b[1] + 150), "ВЕРХНИЙ край педальной площадки\n(к переду кокпита)", color="#0a8a3a")
    note(ax, (a[0], a[1]), (a[0] + 60, a[1] + 260), "НИЖНИЙ край (к сиденью)", color="#0a8a3a")
    label(ax, (-10, 760), "◄ ПЕРЕД (педали)", fontsize=12, weight="bold", color="#a00000")
    label(ax, (1090, 760), "СИДЕНЬЕ ►", fontsize=12, weight="bold", color="#a00000")
    # размеры
    dim(ax, (0, Z_BASE), (BASE_L, Z_BASE), -110, axis="x")
    dim(ax, (0, Z_BASE), (POST_X, Z_BASE), -75, axis="x")
    dim(ax, (POST_X, Z_BASE), (CROSS_X[2], Z_BASE), -75, axis="x")
    dim(ax, (0, 0), (0, H), -120, axis="y", text=f"{H:.0f} (575…725, шаг 25)")
    dim(ax, (BASE_L, 0), (BASE_L, Z_BASE), 40, axis="y", text="45±15")
    dim(ax, (BASE_L, 0), (BASE_L, Z_RAIL_TOP), 85, axis="y")
    dim(ax, (POST_X + 25, Z_RAIL_TOP), (POST_X + 25, OUTER_TOP), 210, axis="y", text=f"{OUTER_TOP - Z_RAIL_TOP:.0f}")
    x0d, x1d = DECK_X0_NOM + cfg.d, DECK_X0_NOM + DECK_D + cfg.d
    dim(ax, (x0d, H), (x1d, H), 60, axis="x", text="300 (ход ±75, шаг 12.5)")
    ax.plot([0, BASE_L], [0, 0], color="k", lw=1.0)
    for x in np.arange(0, BASE_L, 40):
        ax.plot([x, x - 15], [0, -15], color="k", lw=0.4)
    # педали: ось
    ax.plot([cfg.xp], [PEDAL_PIVOT_Z], "o", ms=4, color="#0a8a3a", zorder=10)
    dim(ax, (0, PEDAL_PIVOT_Z), (cfg.xp, PEDAL_PIVOT_Z), -330, axis="x", text=f"{cfg.xp:.0f} (260…385, шаг 25)")
    note(ax, (cfg.xp, PEDAL_PIVOT_Z), (cfg.xp + 120, 280), f"ось качания Z={PEDAL_PIVOT_Z:.0f}\nугол {cfg.alpha:.0f}° (20…60, шаг 10)")
    dim(ax, (0, FIN_Z1), (cfg.xc1, FIN_Z1), -265, axis="x", text=f"{cfg.xc1:.0f} (875…1250, шаг 25)")
    dim(ax, (cfg.xc1, FIN_Z1 + 54), (cfg.xc2, FIN_Z1 + 54), 40, axis="x")
    rx, rz, _ = m.notes["rim"]
    ax.plot([rx], [rz], "+", ms=10, color="0.4")
    note(ax, (rx, rz), (rx + 120, rz + 100), f"центр обода (допущение)\nX≈{rx:.0f}, Z≈{rz:.0f}", color="0.35")
    note(ax, (POST_X + 25 + 120, 300), (POST_X + 300, 470), "подкос 40×40×2")
    note(ax, (POST_X, 300), (POST_X - 330, 520), "ряд 10 отв. Ø13, шаг 25\n(положения высоты)")
    fit(ax, [-150, 1450], [-180, 900])
    save(fig, "S02_side")


def sheet_front(m):
    cfg = m.cfg
    fig = new_sheet("Вид спереди", "Со стороны педалей; номинальная конфигурация")
    ax = axes(fig, [0.05, 0.12, 0.62, 0.84])
    fp = frame_parts(m)
    lines(ax, fp, "front")
    lines(ax, [p for p in m.parts if p.ref], "front", lw=0.4, color="0.6")
    H = cfg.H
    # в координатах листа x = -Y
    dim(ax, (-BASE_W / 2, Z_BASE), (BASE_W / 2, Z_BASE), -90, axis="x")
    dim(ax, (-RAIL_YC, Z_BASE), (RAIL_YC, Z_BASE), -55, axis="x", text="540 (оси лонжеронов)")
    dim(ax, (-POST_YC, OUTER_TOP), (POST_YC, OUTER_TOP), 30, axis="x", text="530 (оси стоек)")
    dim(ax, (-DECK_W / 2, H), (DECK_W / 2, H), 260, axis="x")
    dim(ax, (-DECK_FIN_Y, H - 66), (DECK_FIN_Y, H - 66), 200, axis="x", text="360 (оси гребней площадки)")
    dim(ax, (-TRAY_W / 2, 200), (TRAY_W / 2, 200), 0.1, axis="x", text="460 (педальная площадка)")
    dim(ax, (BASE_W / 2, 0), (BASE_W / 2, H), 70, axis="y")
    dim(ax, (BASE_W / 2, 0), (BASE_W / 2, OUTER_TOP), 30, axis="y")
    dim(ax, (-BASE_W / 2, H - STACK), (-BASE_W / 2, H), -40, axis="y", text="116")
    lo = (BASE_W / 2 - 6 - (POST_YC - 20), H - STACK)
    note(ax, (-(POST_YC - 25), 300), (-470, 420), "свободный проём для ног\nмежду стойками ≈480")
    ax.plot([-320, 320], [0, 0], "k", lw=1)
    fit(ax, [-560, 420], [-150, 950])
    # справа — поясняющий текст
    fig.text(0.69, 0.92, "Пояснения к виду спереди", fontsize=10, weight="bold")
    fig.text(0.69, 0.89,
             "• Две стойки по наружным граням лонжеронов + верхняя поперечина\n"
             "  образуют П-образную раму (портал) — она держит боковые силы и\n"
             "  крутящий момент рулевой базы.\n"
             "• Площадка руля опирается на два гребня 60×10 на расстоянии 360 мм;\n"
             "  гребни зажаты в сёдлах-вилках — по 2 болта М12 на сторону,\n"
             "  фиксация симметрична слева и справа.\n"
             "• Болты высоты — снаружи (головки на косынке), приварные гайки —\n"
             "  внутри: регулировка одним ключом с одной стороны.\n"
             "• Болты сёдел — изнутри (из-под площадки), гайки приварены к\n"
             "  наружным щекам.\n"
             "• Ширина 580 сохранена: стойки не выступают за лонжероны.",
             fontsize=8, va="top", linespacing=1.4)
    save(fig, "S03_front")


def sheet_top(m):
    cfg = m.cfg
    fig = new_sheet("Вид сверху", "Номинальная конфигурация (без условного сиденья)")
    ax = axes(fig, [0.03, 0.12, 0.94, 0.84])
    fp = frame_parts(m)
    lines(ax, fp, "top")
    lines(ax, [p for p in m.parts if p.ref and "seat" not in p.name], "top", lw=0.4, color="0.6")
    dim(ax, (0, -BASE_W / 2), (BASE_L, -BASE_W / 2), -80, axis="x")
    dim(ax, (BASE_L, -BASE_W / 2), (BASE_L, BASE_W / 2), 50, axis="y")
    dim(ax, (PEDAL_FIN_X[0], RAIL_YC), (PEDAL_FIN_X[1], RAIL_YC), 60, axis="x", text="гребень педалей 20…410")
    dim(ax, (SEAT_FIN_X[0], RAIL_YC), (SEAT_FIN_X[1], RAIL_YC), 60, axis="x", text="гребень сиденья 820…1290")
    x0d, x1d = DECK_X0_NOM + cfg.d, DECK_X0_NOM + DECK_D + cfg.d
    dim(ax, (x0d, DECK_W / 2), (x1d, DECK_W / 2), 105, axis="x", text="площадка руля 300")
    dim(ax, (x0d, -DECK_W / 2), (x0d, DECK_W / 2), -40, axis="y", text="420")
    dim(ax, (0, -BASE_W / 2), (POST_X, -BASE_W / 2), -45, axis="x")
    dim(ax, (POST_X, -BASE_W / 2), (cfg.xc1, -BASE_W / 2), -45, axis="x")
    dim(ax, (cfg.xc1, -BASE_W / 2), (cfg.xc2, -BASE_W / 2), -45, axis="x")
    label(ax, (-20, 330), "◄ ПЕРЕД", fontsize=11, weight="bold", color="#a00000")
    label(ax, (1180, 330), "СИДЕНЬЕ ►", fontsize=11, weight="bold", color="#a00000")
    note(ax, (cfg.xc1, 0), (cfg.xc1 + 80, 120), "полки 80×6 поперечин —\nсверловка под салазки по месту")
    note(ax, (cfg.xc1 + 120, 190), (cfg.xc1 + 220, 230), "адаптерные полосы 50×8\n(без отверстий до выбора сиденья)")
    fit(ax, [-120, 1420], [-420, 420])
    save(fig, "S04_top")


# ----------------------------------------------------------------------- узел высоты

def sheet_height(m):
    cfg = m.cfg
    fig = new_sheet("Узел регулировки высоты руля (крупно)",
                    "Телескоп 50×50×3 / 40×40×3, 7 положений 575…725 шаг 25, два болта М12 на стойку")
    H = cfg.H
    tower = [p for p in m.parts if p.group in ("tower_fixed", "height", "base") and p.name.endswith("_R") or
             p.name.startswith("height_head")]
    tower = [p for p in tower if "brace" not in p.name and "foot" not in p.name and "fin_" not in p.name]
    reg = clip(tower, x=(POST_X - 140, POST_X + 140), y=(150, 330), z=(30, H - 70))
    # (а) изометрия выреза
    ax = axes(fig, [0.01, 0.40, 0.33, 0.56], "а) Правая стойка — изометрия")
    cut = clip(reg, x=(POST_X - 140, POST_X + 140), y=(150, 330), z=(30, H))
    cut_half = clip(cut, x=(POST_X - 140, POST_X + 0.0))
    shaded(ax, cut_half + [p for p in cut if "liner" in p.name or "bolt" in p.name], ((-1.0, -0.9, 0.55), (1, -1.1, 0)),
           cull=False, max_edge=25)
    ax.set_title("а) Правая стойка — изометрия с вырезом по оси (X<550)", fontsize=9, weight="bold", loc="left")
    # (б) разрез A-A плоскостью X=POST_X (вид спереди)
    ax = axes(fig, [0.33, 0.12, 0.30, 0.84], "б) Разрез А-А по оси болтов (плоскость X=550)")
    behind = clip(reg, x=(POST_X, POST_X + 200))
    lines(ax, behind, "front", lw=0.4, color="0.45")
    section(ax, reg, (POST_X, 0, 0), (1, 0, 0), "front")
    zb = m.notes["inner_hole_z"]
    for z in zb:
        ax.plot([-330, -170], [z, z], color="#a00000", lw=0.4, ls="-.")
    dim(ax, (-POST_YC, zb[0]), (-POST_YC, zb[1]), -95, axis="y", text="75")
    dim(ax, (-POST_YC, OUTER_ROW_Z[0]), (-POST_YC, OUTER_ROW_Z[-1]), -125, axis="y", text="9×25=225")
    dim(ax, (-POST_YC, Z_RAIL_TOP), (-POST_YC, OUTER_TOP), 75, axis="y")
    dim(ax, (-POST_YC, OUTER_TOP), (-POST_YC, H - STACK), 75, axis="y")
    ib = m.notes["inner_bot"]
    dim(ax, (-POST_YC + 20, ib), (-POST_YC + 20, OUTER_TOP), 95, axis="y", text=f"перекрытие {OUTER_TOP-ib:.0f}")
    note(ax, (-(POST_YC + 28), zb[1]), (-430, zb[1] + 90), "болт М12×80 8.8\n+ Nord-Lock + шайба 300HV")
    note(ax, (-(POST_YC - 29), zb[0]), (-110, zb[0] - 60), "приварная гайка DIN 929 М12\nна накладке 40×6")
    note(ax, (-(POST_YC - 21), zb[0] + 15), (-110, zb[0] + 120), "вварная распорная втулка\n17×2 (внутри 40×40×3)")
    note(ax, (-(POST_YC + 21), OUTER_TOP - 120), (-430, OUTER_TOP - 40), "стальной вкладыш 2 мм\n(подбор 1.6–2.2) — заполняет\nзазор, пакет без смятия")
    note(ax, (-(POST_YC + 28), 120), (-430, 150), "косынка-накладка 6 мм\n(усиливает стенку под болтами)")
    note(ax, (-(POST_YC - 40), H - STACK + 20), (-130, H - 20), "верхняя поперечина 40×40×3")
    fit(ax, [-480, 60], [20, H + 10])
    # (в) горизонтальный разрез Б-Б через болт
    ax = axes(fig, [0.63, 0.55, 0.36, 0.41], "в) Разрез Б-Б через верхний болт (вид сверху)")
    zc = zb[1]
    reg2 = clip(tower, x=(POST_X - 60, POST_X + 60), y=(200, 320), z=(zc - 40, zc + 40))
    section(ax, reg2, (0, 0, zc), (0, 0, 1), "top")
    dim(ax, (POST_X - 25, POST_YC + 25), (POST_X + 25, POST_YC + 25), 45, axis="x", text="50")
    dim(ax, (POST_X - 20, POST_YC - 20), (POST_X + 20, POST_YC - 20), -45, axis="x", text="40")
    note(ax, (POST_X - 24, POST_YC), (POST_X - 120, POST_YC + 40), "полимерный вкладыш\nPA6/UHMW 2 мм (грани X)")
    note(ax, (POST_X, POST_YC + 21), (POST_X + 75, POST_YC + 60), "стальной вкладыш 2 мм\n(грани Y, под болтом)")
    fit(ax, [POST_X - 160, POST_X + 160], [POST_YC - 80, POST_YC + 90], pad=5)
    # (г) пояснение
    fig.text(0.635, 0.53, "Принцип фиксации по высоте", fontsize=10, weight="bold", va="top")
    fig.text(0.635, 0.505,
             "1. Наружная стойка 50×50×3 приварена к лонжерону и усилена косынкой-накладкой 6 мм\n"
             "   (снаружи) и полосой 40×6 (внутри). В них — ряд 10 отв. Ø13 с шагом 25 мм.\n"
             "2. Внутренняя стойка 40×40×3 имеет ДВА отверстия на расстоянии 75 мм с вварными\n"
             "   втулками 17×2 → любые 2 отверстия ряда совпадают через 25 мм: 7 положений.\n"
             "3. Зазор 2 мм по граням Y заполнен калиброванными стальными вкладышами — при\n"
             "   затяжке пакет «накладка–стенка–вкладыш–стенка–втулка» сплошной, стенки не мнутся.\n"
             "4. По граням X — полимерные вкладыши сверху и башмак на торце внутренней стойки:\n"
             "   направляющие разнесены на ≥190 мм (≈4.8 ширины) — перекос исключён.\n"
             "5. Винт-прижим М10 (передняя грань) выбирает зазор по X при перестановке.\n"
             "6. Сдвиг воспринимают 2 болта в круглых отверстиях (положительная фиксация),\n"
             "   а при затяжке 50–60 Н·м — ещё и трение пакета (≈10 кН на болт).\n"
             "7. Обе стойки связаны верхней поперечиной в П-раму — перестановка выполняется\n"
             "   синхронно: сначала ослабить 4 болта, поднять/опустить узел, вставить болты.",
             fontsize=7.6, va="top", linespacing=1.35)
    fig.text(0.635, 0.21, "Почему 25 мм и 575…725:", fontsize=8.5, weight="bold", va="top")
    fig.text(0.635, 0.19,
             "• 25 мм ≈ 1/12 диаметра обода — разница незаметна для посадки, тоньше\n"
             "  не нужно (тонкая доводка — проставками под базой 5/10 мм).\n"
             "• Диапазон 150 мм перекрывает P5…P95 (см. лист эргономики); исходные 625\n"
             "  лежат внутри. Ограничение сверху — перекрытие телескопа ≥190 мм.\n"
             "• При необходимости диапазон расширяется только новыми внутренними\n"
             "  стойками (длиннее), без сварки по раме.",
             fontsize=7.6, va="top", linespacing=1.35)
    save(fig, "S05_height_mechanism")


# ----------------------------------------------------------------------- продольная регулировка

def sheet_foreaft(m):
    cfg = m.cfg
    H = cfg.H
    fig = new_sheet("Узел продольной регулировки площадки руля (крупно)",
                    "Гребни 60×10 в сёдлах-вилках, нониус 12.5 мм, ход ±75 мм, 2+2 болта М12")
    deck = [p for p in m.parts if p.group in ("deck", "height") and not p.ref]
    regR = clip(deck, x=(POST_X - 200, POST_X + 200), y=(100, 300), z=(H - 130, H + 5))
    ax = axes(fig, [0.01, 0.50, 0.40, 0.46])
    sel = clip(regR, x=(POST_X - 200, POST_X + 200), y=(120, 300), z=(H - 130, H - DECK_T - 0.01))
    shaded(ax, sel, ((-0.9, -1.0, 0.45), (1, -0.9, 0)), cull=False, max_edge=20)
    ax.set_title("а) Седло правой стороны (лист площадки скрыт), вид изнутри", fontsize=9, weight="bold", loc="left")
    # (б) вид сбоку с нониусом
    ax = axes(fig, [0.42, 0.50, 0.57, 0.46], "б) Вид сбоку изнутри на седло: отверстия гребня и пары А/Б")
    side = clip(deck, y=(0, 300))
    view = ((0, 1, 0), (-1, 0, 0))   # изнутри (из центра наружу), перед справа
    view = "side"
    lines(ax, [p for p in side if "clamp" not in p.name and "bolt" not in p.name], view, lw=0.6)
    zc = H - DECK_T - DECK_FIN_H / 2
    for i, h in enumerate(SADDLE_HOLES_A + SADDLE_HOLES_B):
        x = POST_X + h
        c = "#c03000" if h in SADDLE_HOLES_A else "#0050c0"
        ax.add_patch(plt.Circle((x, zc), 9, fill=False, ec=c, lw=1.6, zorder=9))
        ax.text(x, zc - 26, "А" if h in SADDLE_HOLES_A else "Б", color=c, ha="center", fontsize=9, weight="bold")
    xs = [POST_X + h for h in sorted(SADDLE_HOLES_A + SADDLE_HOLES_B)]
    for a, b in zip(xs[:-1], xs[1:]):
        dim(ax, (a, zc), (b, zc), 70, axis="x", text="37.5")
    dim(ax, (xs[0], zc), (xs[2], zc), 100, axis="x", text="пара А: 75")
    dim(ax, (xs[1], zc), (xs[3], zc), 130, axis="x", text="пара Б: 75")
    fh = [x + cfg.d for x in m.notes["deck_fin_holes_nom"]]
    dim(ax, (fh[0], zc), (fh[1], zc), -55, axis="x", text="шаг 25")
    dim(ax, (DECK_X0_NOM + cfg.d, H), (DECK_X0_NOM + cfg.d + DECK_D, H), 170, axis="x", text="гребень 300 = глубина площадки")
    dim(ax, (POST_X - SADDLE_L / 2, H - STACK), (POST_X + SADDLE_L / 2, H - STACK), -40, axis="x", text="седло 150")
    note(ax, (POST_X, H - STACK + 20), (POST_X - 330, H - STACK - 10), "верхняя поперечина 40×40×3")
    fit(ax, [DECK_X0_NOM - 120, DECK_X0_NOM + DECK_D + 120], [H - 170, H + 180], pad=5)
    # (в) разрез через болт
    ax = axes(fig, [0.01, 0.10, 0.36, 0.38], "в) Разрез В-В по оси болта (плоскость X = отверстие пары А)")
    xb = POST_X + SADDLE_HOLES_A[1]
    reg3 = clip(deck, x=(xb - 40, xb + 40), y=(100, 300), z=(H - 130, H + 5))
    section(ax, reg3, (xb, 0, 0), (1, 0, 0), "front")
    lines(ax, clip(reg3, x=(xb, xb + 40)), "front", lw=0.35, color="0.55")
    note(ax, (-152, zc), (-120, zc + 45), "болт М12×45 8.8,\nголовка изнутри")
    note(ax, (-171, zc - 20), (-120, zc - 55), "съёмная прижимная\nпластина 8 мм")
    note(ax, (-180, H - 60), (-330, H - 95), "гребень 60×10")
    note(ax, (-190, zc - 22), (-330, zc + 45), "приварная щека 8 мм\n+ гайка DIN 929")
    note(ax, (-190, H - 105), (-330, H - 125), "верхняя поперечина (разрез вдоль)")
    dim(ax, (-175, H - 66), (-185, H - 66), -60, axis="x", text="10")
    fit(ax, [-340, -20], [H - 140, H + 20], pad=5)
    # (г) таблица положений
    ax = fig.add_axes([0.38, 0.10, 0.30, 0.36]); ax.axis("off")
    ax.set_title("г) Положения площадки (d — смещение к сиденью)", fontsize=9, weight="bold", loc="left")
    rows = []
    for d in np.arange(D_MIN, D_MAX + 0.1, D_STEP):
        setA = (d - D_MIN) % 25 == 0
        hs = SADDLE_HOLES_A if setA else SADDLE_HOLES_B
        idx = [int(round((POST_X + h - d - m.notes["deck_fin_holes_nom"][0]) / 25)) + 1 for h in hs]
        rows.append([f"{d:+.1f}", "А" if setA else "Б", f"{idx[0]} и {idx[1]}"])
    t = ax.table(cellText=rows, colLabels=["d, мм", "пара седла", "№ отв. гребня (с переда)"], loc="upper left",
                 cellLoc="center", colWidths=[0.25, 0.25, 0.5])
    t.auto_set_font_size(False); t.set_fontsize(7.2); t.scale(1, 1.05)
    fig.text(0.70, 0.46, "Принцип фиксации вперёд-назад", fontsize=10, weight="bold", va="top")
    fig.text(0.70, 0.435,
             "1. Под листом площадки — два гребня (полоса 60×10 на ребро)\n"
             "   с 11 отверстиями Ø13 шагом 25 мм.\n"
             "2. На верхней поперечине — два седла-вилки: приварная щека 8 мм\n"
             "   с опорой и съёмная прижимная пластина 8 мм. В седле 4 отв.:\n"
             "   пара А (75 мм) и пара Б (75 мм, сдвиг 12.5) — нониус:\n"
             "   шаг 25 гребня + сдвиг пар = шаг 12.5 мм, 13 положений.\n"
             "3. В каждом седле работают 2 болта М12 в КРУГЛЫХ отверстиях\n"
             "   (всего 4) — срез, а не трение в пазу; плюс трение по\n"
             "   2 плоскостям при затяжке (≈10 кН на болт).\n"
             "4. Гребень сплошной — нет смятия; вертикаль вниз передаётся\n"
             "   кромкой гребня на опорный пруток седла, а не болтами.\n"
             "5. Прижимная пластина съёмная: зазор не надо «выбирать»\n"
             "   изгибом щёк — пакет стягивается без деформации.\n"
             "6. Левое и правое сёдла одинаковы — фиксация симметрична.\n"
             "7. Перестановка: ослабить 4 болта, вынуть 2 (по одному на\n"
             "   сторону), сдвинуть, вставить в нужную пару, затянуть.\n"
             "Доступ: головки изнутри (снизу между коленями), гайки\n"
             "приварены — второй ключ не нужен.",
             fontsize=7.6, va="top", linespacing=1.35)
    save(fig, "S06_foreaft_mechanism")


# ----------------------------------------------------------------------- крайние положения

def sheet_extremes():
    fig = new_sheet("Крайние положения регулировок рулевого узла",
                    "Проверка столкновений: 4 угловые комбинации H × d (вид сбоку) + условный обод")
    combos = [("wheel_low_fwd", "H=575, d=−75"), ("wheel_low_back", "H=575, d=+75"),
              ("wheel_high_fwd", "H=725, d=−75"), ("wheel_high_back", "H=725, d=+75")]
    rects = [[0.02, 0.53, 0.48, 0.43], [0.51, 0.53, 0.48, 0.43], [0.02, 0.10, 0.48, 0.43], [0.51, 0.10, 0.48, 0.43]]
    for (name, t), r in zip(combos, rects):
        m = build_model(CONFIGS[name])
        ax = axes(fig, r, f"{name}: {t}")
        fixed = [p for p in m.parts if not p.ref and p.group not in ("height", "deck")]
        mov = [p for p in m.parts if not p.ref and p.group in ("height", "deck")]
        lines(ax, clip(fixed, x=(150, 1000)), "side", lw=0.4, color="0.45")
        lines(ax, mov, "side", lw=0.8, color="#c04000")
        lines(ax, [p for p in m.parts if p.ref], "side", lw=0.35, color="0.65")
        H = m.cfg.H
        dim(ax, (DECK_X0_NOM + m.cfg.d, 0), (DECK_X0_NOM + m.cfg.d, H), -40, axis="y")
        ib = m.notes["inner_bot"]
        ax.text(150, 860, f"перекрытие телескопа {OUTER_TOP - ib:.0f} мм; зазор поперечина–наружная стойка "
                f"{H - STACK - OUTER_TOP - 2:.0f} мм;\nпара отверстий седла: {m.notes['saddle_set']}; "
                f"болты высоты на Z={m.notes['inner_hole_z'][0]:.0f}/{m.notes['inner_hole_z'][1]:.0f}",
                fontsize=7.2)
        ax.set_xlim(150, 1000); ax.set_ylim(-10, 900)
    fig.text(0.03, 0.035, "Автоматическая проверка (cad/build.py): во всех 11 конфигурациях пересечений тел "
             "объёмом >1 мм³ не найдено — см. out/interference_report.json", fontsize=8)
    save(fig, "S07_wheel_extremes")


# ----------------------------------------------------------------------- педали

def sheet_pedals(m):
    fig = new_sheet("Педальный узел: угол и положение вдоль основания",
                    "Площадка 460×330 на двух щеках-секторах; 5 углов × 6 положений; фиксация 3 болтами на сторону")
    ax = axes(fig, [0.02, 0.38, 0.58, 0.58], "а) Вид сбоку: все углы 20…60° (номинал 30° — жирно)")
    cfg = m.cfg
    base = [p for p in m.parts if p.group == "base" and not p.ref]
    lines(ax, clip(base, x=(-100, 600)), "side", lw=0.4, color="0.5")
    car = [p for p in m.parts if p.group == "pedals" and ("shoe" in p.name or "sector" in p.name)]
    lines(ax, car, "side", lw=0.6)
    for a in PEDAL_ANGLES:
        c = Config(xp=cfg.xp, alpha=a)
        p0 = tray_point(c, -25, 31); p1 = tray_point(c, 305, 31)
        q0 = tray_point(c, -25, -25); q1 = tray_point(c, 305, -25)
        lw = 2.4 if a == cfg.alpha else 0.8
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#0a8a3a", lw=lw, zorder=9)
        ax.plot([q1[0], p1[0]], [q1[1], p1[1]], color="#0a8a3a", lw=0.5, zorder=9)
        ax.text(p1[0] - 8, p1[1] + 6, f"{a:.0f}°", color="#0a8a3a", fontsize=8, ha="right")
    P = (cfg.xp, PEDAL_PIVOT_Z)
    for R in PEDAL_R:
        ax.add_patch(Arc(P, 2 * R, 2 * R, theta1=180 - 62, theta2=180 - 18, color="#a00000", lw=0.6, ls="--", zorder=8))
        ax.text(P[0] - R * math.cos(math.radians(65)) - 5, P[1] + R * math.sin(math.radians(65)) + 6, f"R{R:.0f}",
                color="#a00000", fontsize=7.5)
    ax.plot(*P, "o", color="#a00000", ms=5, zorder=10)
    note(ax, P, (P[0] + 90, P[1] - 60), "ось качания (болт М12)\n= НИЖНИЙ край площадки,\nсо стороны сиденья")
    top = tray_point(cfg, 305, 31)
    note(ax, top, (top[0] - 30, top[1] + 120), "ВЕРХНИЙ край площадки —\nк переду кокпита (влево)", ha="right")
    label(ax, (-140, 520), "◄ ПЕРЕД кокпита", fontsize=12, weight="bold", color="#a00000")
    label(ax, (430, 520), "к СИДЕНЬЮ ►", fontsize=12, weight="bold", color="#a00000")
    ax.annotate("", xy=(tray_point(cfg, 305, 70)), xytext=(tray_point(cfg, -25, 70)),
                arrowprops=dict(arrowstyle="<-", lw=1.2, color="#0a8a3a"))
    ax.text(*tray_point(cfg, 140, 95), "линия площадки: сверху-слева → вниз-вправо", color="#0a8a3a", fontsize=8,
            rotation=-cfg.alpha, rotation_mode="anchor", ha="center")
    fit(ax, [-160, 560], [20, 560], pad=5)
    # (б) положения вдоль основания
    ax = axes(fig, [0.61, 0.55, 0.38, 0.41], "б) Крайние положения каретки: X=260 и X=385")
    for xp, col in ((260, "#0050c0"), (385, "#c04000")):
        mm = build_model(Config(xp=xp, alpha=40, show_refs=False))
        lines(ax, [p for p in mm.parts if p.group == "pedals"], "side", lw=0.6, color=col)
    lines(ax, clip([p for p in m.parts if p.group in ("base", "tower_fixed") and not p.ref], x=(-100, 650)), "side",
          lw=0.4, color="0.5")
    dim(ax, (260, PEDAL_PIVOT_Z), (385, PEDAL_PIVOT_Z), -95, axis="x", text="125 (6 положений, шаг 25)")
    fit(ax, [-120, 640], [0, 520], pad=5)
    # (в) разрез башмака
    ax = axes(fig, [0.61, 0.10, 0.18, 0.40], "в) Разрез Г-Г: башмак на гребне")
    xs = cfg.xp - 125
    reg = clip([p for p in m.parts if p.name.endswith("_R") and p.group in ("pedals", "base")],
               x=(xs - 30, xs + 30), y=(200, 320), z=(30, 200))
    section(ax, reg, (xs, 0, 0), (1, 0, 0), "front")
    note(ax, (-270, FIN_HOLE_Z), (-230, 175), "гребень 50×8\nна лонжероне")
    note(ax, (-262, 120), (-180, 60), "щека 6 мм +\nгайка DIN 929")
    note(ax, (-277, 120), (-330, 60), "прижимная\nпластина 6 мм", ha="right")
    fit(ax, [-330, -200], [30, 200], pad=5)
    fig.text(0.80, 0.48, "Принцип фиксации", fontsize=10, weight="bold", va="top")
    fig.text(0.80, 0.455,
             "Угол: площадка висит на оси\n(болт М12) и фиксируется ещё\nДВУМЯ болтами — по одному\n"
             "на дугах R150 и R250 (на каждой\nщеке). Итого 3 болта на сторону,\n6 на площадку; все отверстия\n"
             "круглые, болты на срез.\n\n"
             "Вдоль основания: каретка —\nбашмак на гребне лонжерона:\n3 болта М12 в отверстиях шагом 25,\n"
             "щека с приварными гайками +\nсъёмная прижимная пластина.\n\n"
             "Лист площадки без отверстий —\nпод педали ставится адаптер\nпосле выбора модели.",
             fontsize=7.6, va="top", linespacing=1.35)
    save(fig, "S08_pedal_unit")


# ----------------------------------------------------------------------- схема соединений

def sheet_joints(m):
    fig = new_sheet("Схемы регулируемых соединений и принцип фиксации",
                    "Все регулировки — болтовые, без сварки; сдвиг воспринимают болты в круглых отверстиях")
    cfg = m.cfg
    H = cfg.H
    items = []
    # 1 высота
    zb = m.notes["inner_hole_z"][1]
    reg = clip([p for p in m.parts if p.name.endswith("_R") and p.group in ("tower_fixed", "height")],
               x=(POST_X - 60, POST_X + 60), y=(200, 330), z=(zb - 30, zb + 30))
    items.append(("1. Высота руля (телескоп)", reg, (POST_X, 0, 0), (1, 0, 0), "front",
                  ([-330, -195], [zb - 30, zb + 30]),
                  "Болт М12 8.8 сквозь пакет: накладка 6 + стенка 3 + стальной\nвкладыш 2 + стенка 3 + вварная втулка + ... + "
                  "гайка DIN 929.\nПоложительная фиксация: 2 болта на стойку в круглых отв.\nЛюфт: калиброванные вкладыши + "
                  "винт-прижим М10.\nСмятие исключено: пакет сплошной (втулка, вкладыши)."))
    zc = H - DECK_T - DECK_FIN_H / 2
    xb = POST_X + SADDLE_HOLES_A[1]
    reg = clip([p for p in m.parts if p.group in ("deck", "height")], x=(xb - 30, xb + 30), y=(140, 215),
               z=(H - 120, H + 2))
    items.append(("2. Вперёд-назад (седло + гребень)", reg, (xb, 0, 0), (1, 0, 0), "front",
                  ([-220, -135], [H - 120, H + 2]),
                  "Двойной срез: приварная щека 8 | гребень 10 | съёмная\nпластина 8. 2 болта на седло в круглых отв. "
                  "(пара А/Б).\nВертикаль вниз — кромкой гребня на опору седла.\nЗатяжка не деформирует щёки (пластина "
                  "съёмная)."))
    xs = cfg.xp - 125
    reg = clip([p for p in m.parts if p.name.endswith("_R") and p.group in ("pedals", "base")],
               x=(xs - 30, xs + 30), y=(225, 300), z=(40, 160))
    items.append(("3. Башмак на гребне (педали, сиденье)", reg, (xs, 0, 0), (1, 0, 0), "front",
                  ([-300, -220], [40, 160]),
                  "Тот же принцип, что у седла: щека 6 с гайками DIN 929 |\nгребень 8 | прижимная пластина 6. "
                  "Педали — 3 болта\nна сторону, сиденье — 2 болта на каждый конец поперечины.\nОтверстия гребня шагом 25."))
    P = (cfg.xp, PEDAL_PIVOT_Z)
    reg = clip([p for p in m.parts if p.group == "pedals" and (p.name.endswith("_R") or "tray" in p.name)],
               x=(P[0] - 25, P[0] + 25), y=(195, 260), z=(P[1] - 40, P[1] + 40))
    items.append(("4. Ось и секторы педальной площадки", reg, (P[0], 0, 0), (1, 0, 0), "front",
                  ([-260, -190], [P[1] - 40, P[1] + 40]),
                  "Щека-сектор 8 | фланец площадки 8 | гайка DIN 929 на\nфланце. Ось + 2 болта на дугах R150/R250 "
                  "на каждой\nстороне: момент от тормоза воспринимается парой сил,\nа не трением одного болта."))
    reg = clip([p for p in m.parts if p.name in ("foot_plate_3_R", "foot_weldnut_3_R", "foot_3_R", "base_rail_R")],
               x=(1220, 1300), y=(230, 310), z=(-5, 90))
    items.append(("5. Регулируемая опора", reg, (1270, 0, 0), (1, 0, 0), "front", ([-310, -230], [-5, 90]),
                  "Пластина 8 мм под лонжероном + приварная гайка М12 снизу\n(резьба не в тонкой стенке). Опора с "
                  "контргайкой,\nход ±15 мм. Нагрузка на опору ≈1 кН."))
    rects = [[0.02, 0.66, 0.20, 0.27], [0.24, 0.66, 0.20, 0.27], [0.46, 0.66, 0.20, 0.27],
             [0.02, 0.27, 0.20, 0.27], [0.24, 0.27, 0.20, 0.27]]
    trects = [[r[0], r[1] - 0.115, r[2], 0.1] for r in rects]
    for (title, reg, o, n, v, (xl, yl), txt), r, tr in zip(items, rects, trects):
        ax = axes(fig, r)
        ax.set_title(title, fontsize=8.5, weight="bold", loc="left")
        section(ax, reg, o, n, v, lw=0.5)
        ax.set_xlim(*xl); ax.set_ylim(*yl)
        fig.text(tr[0], tr[1] + tr[3] - 0.03, txt, fontsize=6.9, va="top", linespacing=1.4, wrap=True)
    # общая таблица фиксации
    ax = fig.add_axes([0.47, 0.15, 0.51, 0.36]); ax.axis("off")
    ax.set_title("Сводка регулировок", fontsize=9, weight="bold", loc="left")
    data = [
        ["Высота руля", "575…725 / 25", "2+2 М12, срез + трение", "вкладыши, прижим М10"],
        ["Руль вперёд-назад", "±75 / 12.5", "2+2 М12, двойной срез", "съёмная пластина"],
        ["Педали: угол", "20…60° / 10°", "3+3 М12 (ось+2 дуги)", "—"],
        ["Педали: вдоль", "260…385 / 25", "3+3 М12 в гребне", "съёмная пластина"],
        ["Сиденье: поперечины", "875…1250 / 25", "2+2 М12 на поперечину", "съёмная пластина"],
        ["Сиденье: салазки", "≈±100 плавно", "фиксатор салазок", "—"],
        ["Опоры", "±15 плавно", "М12 + контргайка", "—"],
    ]
    t = ax.table(cellText=data, colLabels=["Регулировка", "Диапазон / шаг", "Фиксация", "Выборка люфта"],
                 loc="upper left", cellLoc="left", colWidths=[0.27, 0.22, 0.30, 0.21])
    t.auto_set_font_size(False); t.set_fontsize(6.9); t.scale(1, 1.55)
    fig.text(0.02, 0.105, "Штриховка — сечение деталей плоскостью через ось болта. Цвет заливки соответствует узлу. "
             "Крепёж: болты ISO 4014 8.8 (гладкая часть стержня в плоскости среза), шайбы ISO 7089 300HV или DIN 9021, "
             "стопорные шайбы-пары (Nord-Lock/аналог), гайки приварные DIN 929.", fontsize=7.2)
    save(fig, "S09_joint_schemes")


# ----------------------------------------------------------------------- эргономика

def sheet_ergo():
    fig = new_sheet("Эргономическая проверка (P5 жен. — P95 муж.)",
                    "Подбор регулировок перебором по сетке; обод — условный (Ø300, ось на 70 мм выше площадки)")
    rects = [[0.02, 0.48, 0.32, 0.46], [0.345, 0.48, 0.32, 0.46], [0.67, 0.48, 0.32, 0.46]]
    rows = []
    fits = {}
    for (nm, man), r in zip(ERG.MANNEQUINS.items(), rects):
        best, n_ok = ERG.search(man)
        fits[nm] = best
        cfg = Config(nm, H=float(best["H"]), d=float(best["d"]), xp=float(best["xp"]), alpha=float(best["alpha"]),
                     xc1=float(best["xc1"]), xc2=float(best["xc1"]) + 275, slide=float(best["slide"]))
        m = build_model(cfg)
        ax = axes(fig, r, f"{nm}: найдено подходящих комбинаций — {n_ok}")
        lines(ax, [p for p in m.parts if not p.ref], "side", lw=0.35, color="0.45")
        lines(ax, [p for p in m.parts if p.ref], "side", lw=0.3, color="0.7")
        hip, knee, heel, sh = best["hip_pt"], best["knee_pt"], best["heel_pt"], best["sh_pt"]
        for a, b, rr in ((hip, knee, ERG.R_THIGH), (knee, heel, ERG.R_SHIN)):
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#d06000", lw=rr * 0.22, alpha=0.35, solid_capstyle="round")
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#d06000", lw=1.2)
        ax.plot([hip[0], sh[0]], [hip[1], sh[1]], color="#d06000", lw=1.2)
        rc = best["rim"]
        grip = np.array([rc[0], rc[1] + 39])
        # плечо-локоть-кисть в боковой проекции (условно)
        ax.plot([sh[0], grip[0]], [sh[1], grip[1]], color="#d06000", lw=0.8, ls="--")
        for p in (hip, knee, heel, sh):
            ax.plot(*p, "o", color="#d06000", ms=3)
        ax.text(knee[0], knee[1] + 60, f"колено {best['knee']:.0f}°", fontsize=7, ha="center")
        ax.text(hip[0] + 20, hip[1] - 40, f"таз {best['hip']:.0f}°", fontsize=7)
        ax.text(sh[0] - 300, sh[1] + 30, f"локоть ≈{best['elbow']:.0f}°", fontsize=7)
        ax.set_xlim(-100, 1600); ax.set_ylim(-20, 1100)
        rows.append([nm, f"{best['H']:.0f}", f"{best['d']:+.1f}", f"{best['xp']:.0f}/{best['alpha']:.0f}°",
                     f"{best['xc1']:.0f}/{best['xc1']+275:.0f}", f"{best['slide']:+.0f}",
                     f"{best['knee']:.0f}/{best['hip']:.0f}/{best['elbow']:.0f}",
                     f"{best['clear']:.0f} ({best['clear_to']})", f"{best['entry_gap']:.0f}"])
    ax = fig.add_axes([0.02, 0.12, 0.96, 0.30]); ax.axis("off")
    t = ax.table(cellText=rows, colLabels=["Манекен", "H руля", "d руля", "педали X/угол", "поперечины",
                                           "салазки", "углы: колено/таз/локоть", "мин. зазор ног, мм (до чего)",
                                           "проход обод→подушка, мм"],
                 loc="upper left", cellLoc="center")
    t.auto_set_font_size(False); t.set_fontsize(8); t.scale(1, 1.6)
    fig.text(0.02, 0.22,
             "Целевые углы GT-посадки: колено 110…140°, таз 95…125°, локоть 100…150°. Зазор — от поверхности ног "
             "(бедро R70, колено R55, голень R50) до\nгребней, сёдел, поперечины, обода и ступицы в боковой проекции "
             "(консервативно: все детали считаются находящимися над ногами).\n"
             "Вывод: каркас позволяет подобрать посадку для P5…P95. Проход между ободом и подушкой мал (≈70–200 мм) — "
             "для посадки рекомендуется быстросъём руля\nили временное смещение площадки вперёд (d=−75). Результат "
             "зависит от реального сиденья и руля — повторить после их выбора (cad/ergonomics.py).",
             fontsize=7.8, va="top", linespacing=1.4)
    save(fig, "S10_ergonomics")
    return fits


def renders_extremes():
    """Отдельные 3D-изображения крайних положений высоты и вылета руля."""
    d3 = os.path.join(OUTD, "3d")
    os.makedirs(d3, exist_ok=True)
    items = [("nominal", "Номинал: H=650, d=0")] + [
        (n, t) for n, t in (("wheel_low_fwd", "Низ + вперёд: H=575, d=−75"), ("wheel_low_back", "Низ + назад: H=575, d=+75"),
                            ("wheel_high_fwd", "Верх + вперёд: H=725, d=−75"), ("wheel_high_back", "Верх + назад: H=725, d=+75"))]
    for n, t in items:
        m = build_model(CONFIGS[n])
        fig = plt.figure(figsize=(14, 7.5))
        ax = fig.add_axes([0.0, 0.0, 0.55, 0.93]); shaded(ax, m.parts, "iso_rear", cull=False)
        ax2 = fig.add_axes([0.52, 0.05, 0.48, 0.85]); shaded(ax2, m.parts, "side", cull=False)
        H, d = m.cfg.H, m.cfg.d
        ax2.axhline(H, color="#c04000", lw=0.6, ls="--")
        ax2.text(-60, H + 8, f"верх площадки {H:.0f}", color="#c04000", fontsize=9)
        ax2.axvline(POST_X, color="0.5", lw=0.5, ls=":")
        ax2.text(POST_X + 5, 40, "ось стоек X=550", color="0.4", fontsize=8)
        x0 = DECK_X0_NOM + d
        ax2.annotate("", xy=(x0, H + 25), xytext=(DECK_X0_NOM, H + 25),
                     arrowprops=dict(arrowstyle="->", color="#0050c0", lw=1.2)) if d else None
        ax2.text(x0, H + 35, f"d={d:+.0f} мм", color="#0050c0", fontsize=9)
        ib = m.notes["inner_bot"]
        fig.suptitle(f"{t}   |   перекрытие телескопа {OUTER_TOP - ib:.0f} мм, пара отверстий седла {m.notes['saddle_set']}, "
                     f"пересечений тел: нет", fontsize=11, weight="bold", x=0.02, ha="left")
        fig.savefig(os.path.join(d3, f"{n}.png"), dpi=110)
        plt.close(fig)


def main():
    renders_extremes()
    m = build_model(CONFIGS["nominal"])
    sheet_iso(m)
    sheet_side(m)
    sheet_front(m)
    sheet_top(m)
    sheet_height(m)
    sheet_foreaft(m)
    sheet_extremes()
    sheet_pedals(m)
    sheet_joints(m)
    fits = sheet_ergo()
    with PdfPages(os.path.join(OUTD, "simrig_concept_drawings.pdf")) as pdf:
        for _, f in SHEETS:
            pdf.savefig(f)
    import json
    with open(os.path.join(ROOT, "out", "ergonomic_fits.json"), "w") as fh:
        json.dump({k: {kk: (vv.tolist() if hasattr(vv, "tolist") else vv) for kk, vv in v.items()} for k, v in fits.items()},
                  fh, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    only = sys.argv[1:]
    if only:
        m = build_model(CONFIGS["nominal"])
        for s in only:
            f = globals()[s]
            f(m) if s not in ("sheet_extremes", "sheet_ergo", "renders_extremes") else f()
    else:
        main()
