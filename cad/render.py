"""
Простые инструменты визуализации без внешнего CAD:
  * shaded()  — тонированная аксонометрия/проекция (алгоритм художника, matplotlib)
  * hlr_lines() — точные видимые/невидимые рёбра (OpenCascade HLR) для чертежей
"""
import math

import numpy as np
from matplotlib.collections import PolyCollection, LineCollection
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

import cadquery as cq


def view_axes(eye, xdir):
    """eye — направление от объекта к наблюдателю; xdir — направление «вправо» на листе."""
    n = np.array(eye, float); n /= np.linalg.norm(n)
    x = np.array(xdir, float); x -= n * x.dot(n); x /= np.linalg.norm(x)
    y = np.cross(n, x)
    return n, x, y


VIEWS = {
    # боковой вид слева: перёд (X=0) слева на листе, сиденье справа
    "side": ((0, -1, 0), (1, 0, 0)),
    # вид спереди (со стороны педалей)
    "front": ((-1, 0, 0), (0, -1, 0)),
    # вид сверху: X вправо, +Y вверх листа
    "top": ((0, 0, 1), (1, 0, 0)),
    # изометрия спереди-слева-сверху
    "iso": ((-1.0, -1.25, 0.9), (1, -0.8, 0)),
    "iso_rear": ((1.1, -1.0, 0.8), (1, 1.1, 0)),
}


def tessellate(shape, tol=0.4):
    vs, ts = shape.tessellate(tol, 0.35)
    v = np.array([(p.x, p.y, p.z) for p in vs])
    t = np.array(ts, int)
    return v, t


def subdivide(tri, max_edge=35.0):
    """Делит крупные треугольники, чтобы сортировка по глубине работала корректно."""
    out = []
    stack = list(tri)
    while stack:
        t = stack.pop()
        e = max(np.linalg.norm(t[0] - t[1]), np.linalg.norm(t[1] - t[2]), np.linalg.norm(t[2] - t[0]))
        if e <= max_edge or len(out) + len(stack) > 400000:
            out.append(t)
            continue
        a, b, c = t
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        stack.extend([np.array([a, ab, ca]), np.array([ab, b, bc]), np.array([ca, bc, c]), np.array([ab, bc, ca])])
    return np.array(out)


def shaded(ax, parts, view, light=(-0.4, -0.6, 0.7), alpha_ref=0.35, tol=0.5, edge=False, max_edge=35.0,
           cull=True):
    n, x, y = view_axes(*VIEWS[view]) if isinstance(view, str) else view_axes(*view)
    L = np.array(light, float); L /= np.linalg.norm(L)
    polys, cols, depth = [], [], []
    for p in parts:
        v, t = tessellate(p.shape, tol)
        if len(t) == 0:
            continue
        tri = subdivide(v[t], max_edge)             # (k,3,3)
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nl = np.linalg.norm(nrm, axis=1); nl[nl == 0] = 1
        nrm /= nl[:, None]
        facing = nrm @ n
        keep = facing > -1e-6 if (cull and not p.ref) else np.ones(len(tri), bool)
        tri, nrm = tri[keep], nrm[keep]
        if len(tri) == 0:
            continue
        sh = 0.45 + 0.55 * np.abs(nrm @ L)
        base = np.array(p.color)
        c = np.clip(base[None, :] * sh[:, None] + 0.08, 0, 1)
        a = alpha_ref if p.ref else 1.0
        c = np.concatenate([c, np.full((len(c), 1), a)], axis=1)
        P2 = np.stack([tri @ x, tri @ y], axis=2)
        polys.extend(list(P2)); cols.extend(list(c)); depth.extend(list((tri @ n).mean(axis=1)))
    order = np.argsort(depth)
    polys = [polys[i] for i in order]; cols = np.array(cols)[order]
    pc = PolyCollection(polys, facecolors=cols, edgecolors=cols, linewidths=0.15 if not edge else 0.3)
    ax.add_collection(pc)
    allp = np.concatenate(polys)
    ax.set_xlim(allp[:, 0].min() - 20, allp[:, 0].max() + 20)
    ax.set_ylim(allp[:, 1].min() - 20, allp[:, 1].max() + 20)
    ax.set_aspect("equal")
    ax.axis("off")
    return (n, x, y)


def project(pts, view):
    n, x, y = view_axes(*VIEWS[view]) if isinstance(view, str) else view_axes(*view)
    pts = np.atleast_2d(np.array(pts, float))
    return np.stack([pts @ x, pts @ y], axis=1)


def _edges_to_polylines(shape, defl=0.2):
    out = []
    if shape is None or shape.IsNull():
        return out
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge_s(exp.Current())
        try:
            c = BRepAdaptor_Curve(e)
            d = GCPnts_QuasiUniformDeflection(c, defl)
            if d.IsDone() and d.NbPoints() > 1:
                out.append(np.array([(d.Value(i).X(), d.Value(i).Y()) for i in range(1, d.NbPoints() + 1)]))
        except Exception:
            pass
        exp.Next()
    return out


def hlr_lines(shapes, view, hidden=False):
    """Возвращает (visible, hidden) — списки 2D-полилиний в координатах листа (мм)."""
    n, x, _ = view_axes(*VIEWS[view]) if isinstance(view, str) else view_axes(*view)
    comp = cq.Compound.makeCompound(shapes)
    algo = HLRBRep_Algo()
    algo.Add(comp.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*n), gp_Dir(*x))))
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    vis = _edges_to_polylines(h.VCompound()) + _edges_to_polylines(h.OutLineVCompound())
    hid = []
    if hidden:
        hid = _edges_to_polylines(h.HCompound()) + _edges_to_polylines(h.OutLineHCompound())
    return vis, hid


def draw_lines(ax, lines, color="k", lw=0.5, ls="-", z=3):
    if lines:
        ax.add_collection(LineCollection(lines, colors=color, linewidths=lw, linestyles=ls, zorder=z))
