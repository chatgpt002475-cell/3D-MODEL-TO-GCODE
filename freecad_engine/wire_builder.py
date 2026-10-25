"""
Advanced OpenCASCADE / FreeCAD 2D & 3D Wire Geometry Generators.
Creates parametric wire profiles: Slots, Involute Gears, Lofts, Sweeps, Revolves, and Multi-loop Compounds.
"""

import math
from typing import List, Dict, Any, Tuple

def generate_wire_script_helpers() -> str:
    """Returns Python helper functions to be included in FreeCAD headless execution script."""
    return """
def make_polygon_wire(pts, closed=True):
    vecs = [FreeCAD.Vector(p[0], p[1], p[2]) for p in pts]
    if closed and (vecs[0] - vecs[-1]).Length > 1e-4:
        vecs.append(vecs[0])
    return Part.makePolygon(vecs)

def make_circle_wire(radius, center=(0,0,0), normal=(0,0,1)):
    c = Part.makeCircle(radius, FreeCAD.Vector(*center), FreeCAD.Vector(*normal))
    return Part.Wire([c])

def make_slot_wire(length, width, center=(0,0,0)):
    r = width / 2.0
    half_l = max(0.1, (length - width) / 2.0)
    cx, cy, cz = center
    
    l1 = Part.makeLine(FreeCAD.Vector(cx - half_l, cy - r, cz), FreeCAD.Vector(cx + half_l, cy - r, cz))
    arc1 = Part.Arc(
        FreeCAD.Vector(cx + half_l, cy - r, cz),
        FreeCAD.Vector(cx + half_l + r, cy, cz),
        FreeCAD.Vector(cx + half_l, cy + r, cz)
    )
    l2 = Part.makeLine(FreeCAD.Vector(cx + half_l, cy + r, cz), FreeCAD.Vector(cx - half_l, cy + r, cz))
    arc2 = Part.Arc(
        FreeCAD.Vector(cx - half_l, cy + r, cz),
        FreeCAD.Vector(cx - half_l - r, cy, cz),
        FreeCAD.Vector(cx - half_l, cy - r, cz)
    )
    return Part.Wire([l1, arc1.toShape(), l2, arc2.toShape()])

def make_gear_profile_wire(teeth, r_outer, r_root, center=(0,0,0)):
    cx, cy, cz = center
    pts = []
    for i in range(teeth * 2):
        angle = i * math.pi / teeth
        r = r_outer if (i % 2 == 0) else r_root
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle), cz))
    pts.append(pts[0])
    return make_polygon_wire(pts, closed=True)

def make_90deg_elbow_spine(leg1, arc_r, leg2):
    # Trajectory in XZ plane: start at (0,0,0) along Z, curve 90 deg into X, continue along X
    p1 = Part.makeLine(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0, 0, leg1))
    arc = Part.Arc(
        FreeCAD.Vector(0, 0, leg1),
        FreeCAD.Vector(arc_r * 0.2929, 0, leg1 + arc_r * 0.7071),
        FreeCAD.Vector(arc_r, 0, leg1 + arc_r)
    )
    p2 = Part.makeLine(
        FreeCAD.Vector(arc_r, 0, leg1 + arc_r),
        FreeCAD.Vector(arc_r + leg2, 0, leg1 + arc_r)
    )
    return Part.Wire([p1, arc.toShape(), p2])

def extract_wire_graph(shape):
    wires_data = []
    for widx, w in enumerate(shape.Wires):
        edges_data = []
        for e in w.Edges:
            pts = e.discretize(Number=12)
            edges_data.append({
                "type": e.Curve.__class__.__name__ if hasattr(e, 'Curve') and e.Curve else "Edge",
                "length": round(e.Length, 2),
                "points": [[round(p.x, 2), round(p.y, 2), round(p.z, 2)] for p in pts]
            })
        wires_data.append({
            "wire_index": widx,
            "is_closed": bool(w.isClosed()),
            "length": round(w.Length, 2),
            "edges_count": len(w.Edges),
            "edges": edges_data
        })
    return wires_data
"""
