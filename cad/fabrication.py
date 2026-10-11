"""
Комплект для изготовления (из той же модели):
  * fabrication/dxf/*.dxf          — контуры всех лазерных деталей (1:1, мм), с отверстиями
  * fabrication/laser_parts.csv    — перечень лазерных деталей: толщина, габарит, кол-во
  * fabrication/cut_list.csv       — раскрой труб, квадратов и полос: длина, углы, кол-во
  * docs/generated/fabrication_tables.md — те же таблицы для чтения
  * drawings/S12_laser_parts.png   — раскладка лазерных деталей с номерами позиций

    python cad/fabrication.py
"""
import csv
import math
import os
import re
import sys
from collections import OrderedDict

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from params import *  # noqa: E402,F401,F403
from simrig import build_model  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAB = os.path.join(ROOT, "fabrication")


def base_name(name):
    n = re.sub(r"_(R|L)$", "", name)
    n = re.sub(r"_(R|L)(\d)$", r"_\2", n)
    return n


def is_laser(p):
    return p.kind in ("steel", "liner") and p.spec.startswith("Лист")


def plate_outline(shape):
    """Контур пластины в её плоскости: (outer, [holes]) в 2D, толщина."""
    shape = shape.clean()
    faces = [f for f in shape.Faces() if f.geomType() == "PLANE"]
    f = max(faces, key=lambda x: x.Area())
    n = f.normalAt(f.Center())
    n = np.array([n.x, n.y, n.z])
    bb = shape.BoundingBox()
    # толщина = размах вершин вдоль нормали
    pts = np.array([[v.X, v.Y, v.Z] for v in shape.Vertices()])
    t = float(np.ptp(pts @ n))
    # ось x листа — вдоль самого длинного прямого ребра внешнего контура
    ow = f.outerWire()
    best = None
    for e in ow.Edges():
        if e.geomType() == "LINE":
            a, b = e.startPoint(), e.endPoint()
            v = np.array([b.x - a.x, b.y - a.y, b.z - a.z])
            if best is None or np.linalg.norm(v) > np.linalg.norm(best):
                best = v
    ex = best / np.linalg.norm(best)
    ey = np.cross(n, ex)

    def wire2d(w):
        P = []
        for e in w.Edges():
            m = 2 if e.geomType() == "LINE" else 24
            seg = [e.positionAt(i / m) for i in range(m + 1)]
            seg = [np.array([q.x, q.y, q.z]) for q in seg]
            if P and np.linalg.norm(P[-1] - seg[0]) > 1e-3 and np.linalg.norm(P[-1] - seg[-1]) < 1e-3:
                seg = seg[::-1]
            P.extend(seg if not P else seg[1:])
        A = np.array(P)
        return np.stack([A @ ex, A @ ey], axis=1)

    outer = wire2d(ow)
    holes = []
    for w in f.innerWires():
        h = wire2d(w)
        c = h.mean(axis=0)
        r = np.linalg.norm(h - c, axis=1).mean()
        holes.append((c, r, h))
    o = outer.min(axis=0)
    outer = outer - o
    holes = [(c - o, r, h - o) for (c, r, h) in holes]
    plate_outline.axes = (ex, ey)
    return outer, holes, t


def write_dxf(path, outer, holes, label, mark=None, arrows=()):
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline([tuple(p) for p in outer], close=True, dxfattribs={"layer": "CUT"})
    for (c, r, h) in holes:
        if np.std(np.linalg.norm(h - c, axis=1)) < 0.05:
            msp.add_circle(tuple(c), r, dxfattribs={"layer": "CUT"})
        else:
            msp.add_lwpolyline([tuple(p) for p in h], close=True, dxfattribs={"layer": "CUT"})
    msp.add_text(label, height=6, dxfattribs={"layer": "TEXT"}).set_placement((0, -12))
    if mark:   # гравировка номера позиции на детали (лазер, слой MARK, без прорезки)
        w, h = outer.max(axis=0)
        hh = max(4.0, min(8.0, h / 6))
        msp.add_text(mark, height=hh, dxfattribs={"layer": "MARK"}).set_placement(
            (w * 0.5, min(h * 0.5, h - hh - 3)), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    w, h = outer.max(axis=0)
    for k, (txt, ang) in enumerate(arrows):   # гравировка направления установки
        msp.add_text(txt, height=5, rotation=ang, dxfattribs={"layer": "MARK"}).set_placement(
            (w * 0.25, h * (0.3 + 0.25 * k)), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    doc.saveas(path)


def main():
    os.makedirs(os.path.join(FAB, "dxf"), exist_ok=True)
    m = build_model(Config(front_mount=True), refs=False)   # с фронтальным кронштейном — чтобы попал в DXF
    # ----------------------------------------------------------------- лазер
    laser = OrderedDict()
    for p in m.parts:
        if not is_laser(p):
            continue
        outer, holes, t = plate_outline(p.shape)
        w, h = outer.max(axis=0)
        x, y = outer[:, 0], outer[:, 1]
        area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        sig = (round(t), round(w), round(h), len(holes), round(area / 50))
        k = re.sub(r"_?\d+$", "", base_name(p.name)).replace("seat_shoe_", "seat_shoe_")
        k = re.sub(r"seat_shoe\d", "seat_shoe", k)
        k = re.sub(r"_(in|out|front|rear)$", "", k)
        if sig not in laser:
            laser[sig] = dict(part=p, n=0, name=k)
        laser[sig]["n"] += 1
    # фланцы кронштейна на поперечине: только на передней поперечине (по 2 шт.)
    rows = []
    fig = plt.figure(figsize=(16.54, 11.69))
    cols = 6
    for i, (sig, d) in enumerate(laser.items()):
        p = d["part"]
        k = d["name"]
        outer, holes, t = plate_outline(p.shape)
        pos = f"Л{i+1:02d}"
        fn = f"{pos}_{k}_t{t:.0f}.dxf"
        ex, ey = plate_outline.axes
        arrows = []
        for txt, v in (("ПЕРЕД →", np.array([-1.0, 0, 0])), ("ВВЕРХ →", np.array([0, 0, 1.0]))):
            fx, fy = v @ ex, v @ ey
            if math.hypot(fx, fy) > 0.6:
                arrows.append((txt, math.degrees(math.atan2(fy, fx))))
        write_dxf(os.path.join(FAB, "dxf", fn), outer, holes, f"{pos} {k} t={t:.0f} x{d['n']}", mark=pos, arrows=arrows)
        w, h = outer.max(axis=0)
        rows.append(dict(pos=pos, part=k, thickness_mm=round(t, 1), size_mm=f"{w:.0f}x{h:.0f}", holes=len(holes),
                         qty=d["n"], spec=p.spec, dxf=fn))
        ax = fig.add_axes([0.01 + (i % cols) * 0.165, 0.80 - (i // cols) * 0.19, 0.15, 0.15])
        ax.fill(outer[:, 0], outer[:, 1], color=np.array(p.color) * 0.5 + 0.5, ec="k", lw=0.6)
        for (c, r, hh) in holes:
            ax.fill(hh[:, 0], hh[:, 1], color="white", ec="k", lw=0.4)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"{pos}  t={t:.0f}  ×{d['n']}\n{k}\n{w:.0f}×{h:.0f}, отв. {len(holes)}", fontsize=7, loc="left")
    # кондуктор для сверловки сплошных квадратов 40x40 (не входит в раму)
    jig_outer = np.array([[0, 0], [170, 0], [170, 40], [0, 40], [0, 0]], float)
    jig_holes = []
    for u in (25.0, 60.0, 100.0, 135.0):
        ang = np.linspace(0, 2 * np.pi, 49)
        jig_holes.append((np.array([u, 20.0]), 6.5, np.stack([u + 6.5 * np.cos(ang), 20 + 6.5 * np.sin(ang)], 1)))
    pos = f"Л{len(rows)+1:02d}"
    fn = f"{pos}_jig_drill_square40_t8.dxf"
    write_dxf(os.path.join(FAB, "dxf", fn), jig_outer, jig_holes,
              f"{pos} кондуктор: торец квадрата к краю X=0; стойки руля — отв. 60 и 135, шифтер — 25 и 100", mark=pos)
    rows.append(dict(pos=pos, part="jig_drill_square40 (кондуктор, не в раму)", thickness_mm=8.0, size_mm="170x40",
                     holes=4, qty=1, spec="Лист 8 мм (лазер) — кондуктор сверловки квадратов 40x40", dxf=fn))
    fig.text(0.70, 0.04, "Лазерные детали — раскладка (масштаб у каждой свой)\nDXF 1:1: fabrication/dxf/  ·  "
             "все отверстия Ø13 под М12\nКаркас автосимулятора — КОНЦЕПЦИЯ, до запуска сверить с моделью",
             fontsize=9)
    fig.savefig(os.path.join(ROOT, "drawings", "S12_laser_parts.png"), dpi=150)
    with open(os.path.join(FAB, "laser_parts.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    # ----------------------------------------------------------------- раскрой профиля
    cuts = OrderedDict()
    for p in m.parts:
        if p.kind != "steel" or is_laser(p):
            continue
        k = base_name(p.name)
        bb = p.shape.BoundingBox()
        L = max(bb.xlen, bb.ylen, bb.zlen)
        note = ""
        if "brace" in k:
            xa, za, xb, zb = m.notes["brace"]
            ang = math.degrees(math.atan2(za - zb, xb - xa))
            L = math.hypot(xb - xa, za - zb) + 20 / math.tan(math.radians(ang)) + 20 * math.tan(math.radians(ang))
            note = (f"подкос под {ang:.0f}° к горизонту; торцы: к стойке — плоскость реза под {90-ang:.0f}° к оси трубы, "
                    f"к лонжерону — под {ang:.0f}° (длина по длинной стороне)")
        if "outer_post" in k:
            note = "ТРУБОРЕЗ: 10 сквозных отв. Ø13 (оси на %s мм от низа)" % ", ".join(
                f"{z - Z_RAIL_TOP:.0f}" for z in OUTER_ROW_Z)
        if "side_cup" in k:
            note = "ТРУБОРЕЗ: 8 сквозных отв. Ø13 (оси на %s мм от низа)" % ", ".join(
                f"{z - SIDE_CUP_Z[0]:.0f}" for z in SIDE_CUP_ROW)
        if "inner_post" in k or "side_bar" in k:
            note = "КАЛИБРОВАННЫЙ квадрат (ГОСТ 8559, h11); 2 отв. Ø13 — сверлильный станок по лазерному кондуктору (см. docs/05)"
        k = re.sub(r"_\d+$", "", k)
        key = (k, p.spec.split(",")[0], round(L))
        if key not in cuts:
            cuts[key] = dict(part=k, stock=p.spec.split(",")[0], length_mm=round(L), qty=0, note=note)
        cuts[key]["qty"] += 1
    crows = list(cuts.values())
    with open(os.path.join(FAB, "cut_list.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(crows[0].keys()))
        w.writeheader(); w.writerows(crows)
    # сводка по сортаменту
    stock = OrderedDict()
    for r in crows:
        s = re.sub(r"\s*\(.*", "", r["stock"])
        stock.setdefault(s, 0.0)
        stock[s] += r["length_mm"] * r["qty"] / 1000
    # ----------------------------------------------------------------- markdown
    L = ["# Комплект для изготовления — таблицы (генерируется cad/fabrication.py)", "",
         "> Концепция: перед запуском в резку сверить размеры с моделью и фактическим сортаментом. "
         "DXF — в масштабе 1:1, мм, слой CUT; все отверстия Ø13 под болты М12.", "",
         "## Лазерная резка листа", "", "| Поз. | Деталь | t, мм | Габарит, мм | Отв. | Кол-во | Файл |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['pos']} | {r['part']} | {r['thickness_mm']:.0f} | {r['size_mm']} | {r['holes']} | {r['qty']} | "
                 f"`fabrication/dxf/{r['dxf']}` |")
    L += ["", "## Раскрой труб, квадратов, полос", "", "| Деталь | Сортамент | Длина, мм | Кол-во | Примечание |",
          "|---|---|---|---|---|"]
    for r in crows:
        L.append(f"| {r['part']} | {r['stock']} | {r['length_mm']} | {r['qty']} | {r['note']} |")
    L += ["", "## Сколько покупать (без учёта реза и брака, +10 %)", "", "| Сортамент | Итого, м |", "|---|---|"]
    for s, v in stock.items():
        L.append(f"| {s} | {v:.2f} |")
    with open(os.path.join(ROOT, "docs", "generated", "fabrication_tables.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
