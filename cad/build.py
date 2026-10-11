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
        report[n] = dict(cfg=cfg.__dict__, n_parts=len(m.parts), interference=hits,
                         inner_hole_z=m.notes.get("inner_hole_z"))
        if n == "nominal":
            export_step(m, os.path.join(OUT, "step", "simrig_nominal_AP214.step"), "AP214IS")
            export_step(m, os.path.join(OUT, "step", "simrig_nominal_AP242.step"), "AP242DIS")
            export_stl(m, os.path.join(OUT, "stl", "simrig_nominal_frame.stl"))
            export_stl(m, os.path.join(OUT, "stl", "simrig_nominal_with_refs.stl"), include_refs=True)
        elif n.startswith("wheel_"):   # крайние положения руля; прочие конфигурации — только проверка
            export_step(m, os.path.join(OUT, "step", f"simrig_{n}_AP214.step"), "AP214IS")
            export_stl(m, os.path.join(OUT, "stl", f"simrig_{n}.stl"))
        print(f"{n:22s} parts={len(m.parts):4d}  interference={hits}  ({time.time()-t:.1f}s)", flush=True)
    with open(os.path.join(OUT, "interference_report.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIGS))
