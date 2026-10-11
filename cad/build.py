"""
Сборка конфигураций, экспорт STEP (AP214 и AP242) и STL, проверка столкновений.

    python cad/build.py            # все конфигурации из params.CONFIGS
    python cad/build.py nominal    # одна конфигурация
"""
import json
import os
import sys
import time

import cadquery as cq
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Writer

sys.path.insert(0, os.path.dirname(__file__))
from params import CONFIGS, Config  # noqa: E402
from simrig import build_model  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "out")


def volume(shape):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def to_assembly(m, include_refs=True):
    a = cq.Assembly(name=f"simrig_{m.cfg.name}")
    groups = {}
    for p in m.parts:
        if p.ref and not include_refs:
            continue
        g = groups.get(p.group)
        if g is None:
            g = cq.Assembly(name=p.group)
            groups[p.group] = g
        g.add(p.shape, name=p.name, color=cq.Color(*p.color))
    for g in groups.values():
        a.add(g)
    return a


def export_step(m, path, schema="AP214IS"):
    STEPControl_Writer()  # инициализирует статические параметры STEP
    Interface_Static.SetCVal_s("write.step.schema", schema)
    a = to_assembly(m)
    a.save(path, exportType="STEP")
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")


def export_stl(m, path, include_refs=False):
    shapes = [p.shape for p in m.parts if include_refs or not p.ref]
    comp = cq.Compound.makeCompound(shapes)
    cq.exporters.export(cq.Workplane().add(comp), path, tolerance=0.3, angularTolerance=0.3)


# пары деталей, которые по замыслу соприкасаются/входят друг в друга (сварка, резьба)
def bbox_overlap(a, b, tol=0.01):
    return not (a.xmax < b.xmin + tol or b.xmax < a.xmin + tol or a.ymax < b.ymin + tol or
                b.ymax < a.ymin + tol or a.zmax < b.zmin + tol or b.zmax < a.zmin + tol)


def interference(m, vol_tol=1.0, include_refs=True):
    parts = [p for p in m.parts if include_refs or not p.ref]
    bbs = [p.shape.BoundingBox() for p in parts]
    hits = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            if not bbox_overlap(bbs[i], bbs[j]):
                continue
            c = BRepAlgoAPI_Common(parts[i].shape.wrapped, parts[j].shape.wrapped)
            v = volume(c.Shape())
            if v > vol_tol:
                hits.append((parts[i].name, parts[j].name, round(v, 1)))
    return hits


def fastener_check(m):
    """Каждая гайка должна целиком сидеть на стержне болта (болт достаточной длины и стоит в отверстиях)."""
    import cadquery as cq
    bolts = [p for p in m.parts if "bolt" in p.name and p.kind == "fastener"]
    bad = []
    n_ok = 0
    for p in m.parts:
        if p.kind != "fastener" or "nut" not in p.name or "weldnut" in p.name or "foot" in p.name:
            continue
        bb = p.shape.BoundingBox()
        dims = [bb.xlen, bb.ylen, bb.zlen]
        ax = int(np.argmin(dims))
        c = [bb.center.x, bb.center.y, bb.center.z]
        L = dims[ax] - 3.0
        d = [0, 0, 0]; d[ax] = 1
        o = list(c); o[ax] -= L / 2
        probe = cq.Solid.makeCylinder(5.5, L, cq.Vector(*o), cq.Vector(*d))
        need = probe.Volume() * 0.97
        got = 0.0
        for b in bolts:
            if not bbox_overlap(bb, b.shape.BoundingBox()):
                continue
            got += volume(BRepAlgoAPI_Common(probe.wrapped, b.shape.wrapped).Shape())
        if got < need:
            bad.append(p.name)
        else:
            n_ok += 1
    return n_ok, bad


def bolt_extraction_check(m):
    """Каждый болт должен выниматься: вдоль оси со стороны головки свободно на длину болта + 5 мм
    (цилиндр Ø21 — по описанной окружности головки). Препятствия — стальные детали, вкладыши и другие болты."""
    import cadquery as cq
    obstacles = [p for p in m.parts if not p.ref and (p.kind in ("steel", "liner", "purchased") or "bolt" in p.name)]
    bad, n_ok = [], 0
    for p in m.parts:
        if p.kind != "fastener" or "bolt" not in p.name:
            continue
        bb = p.shape.BoundingBox()
        dims = [bb.xlen, bb.ylen, bb.zlen]
        ax = int(np.argmax(dims))
        c = p.shape.Center()
        cc = [c.x, c.y, c.z]
        mid = [bb.center.x, bb.center.y, bb.center.z]
        sgn = 1 if cc[ax] > mid[ax] else -1          # головка тяжелее — центр масс смещён к ней
        lo = [bb.xmin, bb.ymin, bb.zmin]; hi = [bb.xmax, bb.ymax, bb.zmax]
        start = list(mid); start[ax] = hi[ax] if sgn > 0 else lo[ax]
        L = dims[ax] + 5
        d = [0, 0, 0]; d[ax] = sgn
        probe = cq.Solid.makeCylinder(10.5, L, cq.Vector(*start), cq.Vector(*d))
        pb = probe.BoundingBox()
        hit = None
        for o in obstacles:
            if o is p or not bbox_overlap(pb, o.shape.BoundingBox()):
                continue
            if volume(BRepAlgoAPI_Common(probe.wrapped, o.shape.wrapped).Shape()) > 1.0:
                hit = o.name
                break
        if hit:
            bad.append((p.name, hit))
        else:
            n_ok += 1
    return n_ok, bad


def socket_access(m, r=13.0, depth=40.0):
    """Справочно: где проходит торцевая головка 18 мм (Ø26, глубина 40) на гайку/головку болта.
    Где не проходит — нужен рожковый/накидной ключ сбоку."""
    import cadquery as cq
    obstacles = [p for p in m.parts if not p.ref and p.kind in ("steel", "liner", "purchased")]
    only_open = []
    for p in m.parts:
        if p.kind != "fastener" or ("nut" not in p.name and "bolt" not in p.name) or "foot" in p.name:
            continue
        bb = p.shape.BoundingBox()
        dims = [bb.xlen, bb.ylen, bb.zlen]
        c = p.shape.Center(); cc = [c.x, c.y, c.z]; mid = [bb.center.x, bb.center.y, bb.center.z]
        lo = [bb.xmin, bb.ymin, bb.zmin]; hi = [bb.xmax, bb.ymax, bb.zmax]
        if "bolt" in p.name:
            ax = int(np.argmax(dims)); sgn = 1 if cc[ax] > mid[ax] else -1
            face = hi[ax] - 9 if sgn > 0 else lo[ax] + 9          # торец головки (высота головки ~7.5)
        else:
            ax = int(np.argmin(dims))
            # гайка: наружу — в сторону от болта (болт ближе к шайбе); берём сторону, где меньше металла
            sgn = None
        if sgn is None:
            res = []
            for sg in (1, -1):
                start = list(mid); start[ax] = (hi[ax] if sg > 0 else lo[ax]) - sg * 12
                d = [0, 0, 0]; d[ax] = sg
                pr = cq.Solid.makeCylinder(r, depth, cq.Vector(*start), cq.Vector(*d))
                res.append(any(volume(BRepAlgoAPI_Common(pr.wrapped, o.shape.wrapped).Shape()) > 1
                               for o in obstacles if bbox_overlap(pr.BoundingBox(), o.shape.BoundingBox())))
            if all(res):
                only_open.append(p.name)
            continue
        start = list(mid); start[ax] = face
        d = [0, 0, 0]; d[ax] = sgn
        pr = cq.Solid.makeCylinder(r, depth, cq.Vector(*start), cq.Vector(*d))
        if any(volume(BRepAlgoAPI_Common(pr.wrapped, o.shape.wrapped).Shape()) > 1
               for o in obstacles if bbox_overlap(pr.BoundingBox(), o.shape.BoundingBox())):
            only_open.append(p.name)
    return only_open


def min_distance(s1, s2):
    d = BRepExtrema_DistShapeShape(s1.wrapped, s2.wrapped)
    d.Perform()
    return d.Value()


def main(names):
    os.makedirs(os.path.join(OUT, "step"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)
    report = {}
    for n in names:
        cfg = CONFIGS[n]
        t = time.time()
        m = build_model(cfg)
        hits = interference(m)
        n_ok, bad_nuts = fastener_check(m)
        n_bo, bad_bolts = bolt_extraction_check(m)
        report[n] = dict(cfg=cfg.__dict__, n_parts=len(m.parts), interference=hits,
                         nuts_on_bolts_ok=n_ok, nuts_not_on_bolt=bad_nuts,
                         bolts_removable_ok=n_bo, bolts_blocked=bad_bolts,
                         inner_hole_z=m.notes.get("inner_hole_z"))
        if n == "nominal":
            export_step(m, os.path.join(OUT, "step", "simrig_nominal_AP214.step"), "AP214IS")
            export_step(m, os.path.join(OUT, "step", "simrig_nominal_AP242.step"), "AP242DIS")
            export_stl(m, os.path.join(OUT, "stl", "simrig_nominal_frame.stl"))
            export_stl(m, os.path.join(OUT, "stl", "simrig_nominal_with_refs.stl"), include_refs=True)
        elif n.startswith("wheel_"):   # крайние положения руля; прочие конфигурации — только проверка
            export_step(m, os.path.join(OUT, "step", f"simrig_{n}_AP214.step"), "AP214IS")
            export_stl(m, os.path.join(OUT, "stl", f"simrig_{n}.stl"))
        print(f"{n:26s} parts={len(m.parts):4d}  interference={hits}  nuts ok={n_ok} bad={bad_nuts}  bolts removable={n_bo} blocked={bad_bolts}  "
              f"({time.time()-t:.1f}s)", flush=True)
    with open(os.path.join(OUT, "interference_report.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIGS))
