"""
Natural Language & Parametric Prompt Parser for FreeCAD.
Translates prompts into parametric FreeCAD Python scripts with 2D Sketching and 3D Modeling.
"""

import re
from typing import Dict, Any, Tuple

def parse_prompt_to_params(prompt: str) -> Dict[str, Any]:
    """Extracts geometric intent and parameters from natural language prompt."""
    p = prompt.lower().strip()

    # Determine general category
    category = "custom"
    if any(w in p for w in ["flange", "disc", "ring", "pcd", "bolt circle"]):
        category = "flange"
    elif any(w in p for w in ["bracket", "mount", "mounting plate", "plate"]):
        category = "plate"
    elif any(w in p for w in ["enclosure", "box", "housing", "casing"]):
        category = "enclosure"
    elif any(w in p for w in ["bushing", "spacer", "shaft", "cylinder", "boss"]):
        category = "cylinder"
    elif any(w in p for w in ["l-bracket", "angle", "l bracket"]):
        category = "l_bracket"
    elif any(w in p for w in ["pulley", "sheave"]):
        category = "pulley"
    else:
        # Default based on geometric keywords
        if "circle" in p or "diameter" in p or "radius" in p:
            category = "flange" if "hole" in p else "cylinder"
        else:
            category = "plate"

    # Regex patterns for extracting numbers with units (e.g. 100mm, 50, 12.5)
    def find_val(patterns, default=None):
        for pat in patterns:
            m = re.search(pat, p, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return default

    def find_int(patterns, default=None):
        for pat in patterns:
            m = re.search(pat, p, re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
        return default

    # Dimension pattern like 120x80x40 or 120 x 80 x 40 or 120*80*40
    dims_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|\*|\sby\s)\s*(\d+(?:\.\d+)?)(?:\s*(?:x|\*|\sby\s)\s*(\d+(?:\.\d+)?))?', p)

    params: Dict[str, Any] = {
        "category": category,
        "prompt": prompt,
        "name": re.sub(r'[^a-zA-Z0-9_]', '_', prompt[:30]).strip('_') or "Part"
    }

    if category == "flange":
        od = find_val([r'outer\s*dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                       r'od\s*[:=]?\s*(\d+(?:\.\d+)?)',
                       r'dia(?:meter)?\s*(?:of\s*)?(\d+(?:\.\d+)?)'], 100.0)
        bore = find_val([r'(?:inner|center|bore|hole)\s*(?:dia(?:meter)?)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                         r'id\s*[:=]?\s*(\d+(?:\.\d+)?)'], 30.0)
        thick = find_val([r'thick(?:ness)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                          r'height\s*[:=]?\s*(\d+(?:\.\d+)?)',
                          r'extrude\s*[:=]?\s*(\d+(?:\.\d+)?)',
                          r'length\s*[:=]?\s*(\d+(?:\.\d+)?)'], 15.0)
        bolt_count = find_int([r'(\d+)\s*(?:bolt|mounting)?\s*holes',
                               r'holes?\s*(?:count)?\s*[:=]?\s*(\d+)'], 6)
        bolt_dia = find_val([r'bolt\s*(?:hole)?\s*(?:dia(?:meter)?)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                             r'holes?\s*(?:of\s*)?dia(?:meter)?\s*(\d+(?:\.\d+)?)'], 8.0)
        pcd = find_val([r'pcd\s*[:=]?\s*(\d+(?:\.\d+)?)',
                        r'pitch\s*circle\s*[:=]?\s*(\d+(?:\.\d+)?)',
                        r'bolt\s*circle\s*[:=]?\s*(\d+(?:\.\d+)?)'], (od + bore) / 2.0)

        params.update({
            "outer_diameter": od,
            "bore_diameter": bore,
            "thickness": thick,
            "bolt_count": bolt_count,
            "bolt_diameter": bolt_dia,
            "pcd": pcd
        })

    elif category == "plate":
        w, l, h = 100.0, 60.0, 10.0
        if dims_match:
            w = float(dims_match.group(1))
            l = float(dims_match.group(2))
            if dims_match.group(3):
                h = float(dims_match.group(3))

        w = find_val([r'width\s*[:=]?\s*(\d+(?:\.\d+)?)'], w)
        l = find_val([r'length\s*[:=]?\s*(\d+(?:\.\d+)?)', r'height\s*[:=]?\s*(\d+(?:\.\d+)?)'], l)
        h = find_val([r'thick(?:ness)?\s*[:=]?\s*(\d+(?:\.\d+)?)', r'depth\s*[:=]?\s*(\d+(?:\.\d+)?)'], h)

        hole_dia = find_val([r'holes?\s*(?:dia(?:meter)?)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                             r'hole\s*[:=]?\s*(\d+(?:\.\d+)?)'], 6.0)
        center_hole = find_val([r'center\s*hole\s*[:=]?\s*(\d+(?:\.\d+)?)',
                                r'bore\s*[:=]?\s*(\d+(?:\.\d+)?)'], 0.0)
        fillet = find_val([r'fillet\s*[:=]?\s*(\d+(?:\.\d+)?)',
                           r'corner\s*radius\s*[:=]?\s*(\d+(?:\.\d+)?)'], 4.0)

        params.update({
            "width": w,
            "length": l,
            "thickness": h,
            "corner_hole_diameter": hole_dia,
            "center_hole_diameter": center_hole,
            "fillet_radius": fillet
        })

    elif category == "enclosure":
        w, l, h = 120.0, 80.0, 40.0
        if dims_match:
            w = float(dims_match.group(1))
            l = float(dims_match.group(2))
            if dims_match.group(3):
                h = float(dims_match.group(3))

        wall = find_val([r'wall\s*(?:thick(?:ness)?)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 3.0)
        fillet = find_val([r'fillet\s*[:=]?\s*(\d+(?:\.\d+)?)',
                           r'radius\s*[:=]?\s*(\d+(?:\.\d+)?)'], 4.0)

        params.update({
            "width": w,
            "length": l,
            "height": h,
            "wall_thickness": wall,
            "corner_fillet": fillet
        })

    elif category == "cylinder":
        od = find_val([r'outer\s*dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                       r'dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 50.0)
        id_bore = find_val([r'(?:inner|bore|hole)\s*dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 20.0)
        length = find_val([r'length\s*[:=]?\s*(\d+(?:\.\d+)?)',
                           r'height\s*[:=]?\s*(\d+(?:\.\d+)?)',
                           r'extrude\s*[:=]?\s*(\d+(?:\.\d+)?)'], 60.0)
        flange_dia = find_val([r'flange\s*dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 0.0)
        flange_thick = find_val([r'flange\s*thick(?:ness)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 10.0)

        params.update({
            "outer_diameter": od,
            "bore_diameter": id_bore,
            "length": length,
            "flange_diameter": flange_dia,
            "flange_thickness": flange_thick
        })

    elif category == "l_bracket":
        w = find_val([r'width\s*[:=]?\s*(\d+(?:\.\d+)?)'], 50.0)
        l1 = find_val([r'leg\s*1\s*[:=]?\s*(\d+(?:\.\d+)?)', r'height\s*[:=]?\s*(\d+(?:\.\d+)?)'], 70.0)
        l2 = find_val([r'leg\s*2\s*[:=]?\s*(\d+(?:\.\d+)?)', r'length\s*[:=]?\s*(\d+(?:\.\d+)?)'], 70.0)
        thick = find_val([r'thick(?:ness)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 8.0)
        hole = find_val([r'hole\s*dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 6.0)

        params.update({
            "width": w,
            "leg1": l1,
            "leg2": l2,
            "thickness": thick,
            "hole_diameter": hole
        })

    return params


def generate_freecad_script(params: Dict[str, Any], output_fcstd: str, output_step: str, output_stl: str) -> str:
    """Generates complete, executable FreeCAD Python script from parsed parameters."""
    cat = params.get("category", "flange")

    abs_fcstd = output_fcstd.replace("\\", "/")
    abs_step = output_step.replace("\\", "/")
    abs_stl = output_stl.replace("\\", "/")

    script_parts = [
        "import FreeCAD, Part, Sketcher, Mesh, MeshPart, json, math",
        "doc = FreeCAD.newDocument('FreeCAD_Model')",
        "body = doc.addObject('PartDesign::Body', 'Body')",
        ""
    ]

    if cat == "flange":
        od = params["outer_diameter"]
        id_bore = params["bore_diameter"]
        thick = params["thickness"]
        bolt_count = int(params["bolt_count"])
        bolt_dia = params["bolt_diameter"]
        pcd = params["pcd"]

        script_parts.append(f"""
# 1. Base Flange Sketch & Pad
sketch_base = doc.addObject('Sketcher::SketchObject', 'FlangeSketch')
body.addObject(sketch_base)
sketch_base.MapMode = 'FlatFace'

# Outer circle
sketch_base.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {od/2.0}))
# Center bore
if {id_bore} > 0:
    sketch_base.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {id_bore/2.0}))

doc.recompute()

pad = doc.addObject('PartDesign::Pad', 'Pad')
body.addObject(pad)
pad.Profile = sketch_base
pad.Length = {thick}
doc.recompute()

# 2. Bolt Holes
if {bolt_count} > 0 and {pcd} > 0 and {bolt_dia} > 0:
    sketch_holes = doc.addObject('Sketcher::SketchObject', 'HolesSketch')
    body.addObject(sketch_holes)
    sketch_holes.MapMode = 'FlatFace'
    
    # Calculate bolt coordinates along Pitch Circle Diameter
    for i in range({bolt_count}):
        angle = 2.0 * math.pi * i / {bolt_count}
        bx = ({pcd} / 2.0) * math.cos(angle)
        by = ({pcd} / 2.0) * math.sin(angle)
        sketch_holes.addGeometry(Part.Circle(FreeCAD.Vector(bx, by, 0), FreeCAD.Vector(0,0,1), {bolt_dia/2.0}))
    
    doc.recompute()
    pocket = doc.addObject('PartDesign::Pocket', 'BoltHoles')
    body.addObject(pocket)
    pocket.Profile = sketch_holes
    pocket.Length = {thick * 1.5}
    doc.recompute()
""")

    elif cat == "plate":
        w = params["width"]
        l = params["length"]
        thick = params["thickness"]
        hole_dia = params.get("corner_hole_diameter", 6.0)
        center_hole = params.get("center_hole_diameter", 0.0)
        fillet = params.get("fillet_radius", 4.0)

        script_parts.append(f"""
# 1. Base Plate Sketch & Pad
sketch_plate = doc.addObject('Sketcher::SketchObject', 'PlateSketch')
body.addObject(sketch_plate)
sketch_plate.MapMode = 'FlatFace'

# Rectangular perimeter centered at origin
hw = {w / 2.0}
hl = {l / 2.0}

sketch_plate.addGeometry(Part.LineSegment(FreeCAD.Vector(-hw, -hl, 0), FreeCAD.Vector(hw, -hl, 0)))
sketch_plate.addGeometry(Part.LineSegment(FreeCAD.Vector(hw, -hl, 0), FreeCAD.Vector(hw, hl, 0)))
sketch_plate.addGeometry(Part.LineSegment(FreeCAD.Vector(hw, hl, 0), FreeCAD.Vector(-hw, hl, 0)))
sketch_plate.addGeometry(Part.LineSegment(FreeCAD.Vector(-hw, hl, 0), FreeCAD.Vector(-hw, -hl, 0)))

# Center Hole if specified
if {center_hole} > 0:
    sketch_plate.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {center_hole/2.0}))

doc.recompute()

pad = doc.addObject('PartDesign::Pad', 'Pad')
body.addObject(pad)
pad.Profile = sketch_plate
pad.Length = {thick}
doc.recompute()

# 2. Corner Holes
if {hole_dia} > 0:
    sketch_corner_holes = doc.addObject('Sketcher::SketchObject', 'CornerHolesSketch')
    body.addObject(sketch_corner_holes)
    sketch_corner_holes.MapMode = 'FlatFace'
    
    # 4 Corner Hole positions with offset
    inset_x = min(hw * 0.75, hw - 10.0)
    inset_y = min(hl * 0.75, hl - 10.0)
    
    for sx in [-inset_x, inset_x]:
        for sy in [-inset_y, inset_y]:
            sketch_corner_holes.addGeometry(Part.Circle(FreeCAD.Vector(sx, sy, 0), FreeCAD.Vector(0,0,1), {hole_dia/2.0}))
            
    doc.recompute()
    pocket = doc.addObject('PartDesign::Pocket', 'CornerHoles')
    body.addObject(pocket)
    pocket.Profile = sketch_corner_holes
    pocket.Length = {thick * 1.5}
    doc.recompute()
""")

    elif cat == "enclosure":
        w = params["width"]
        l = params["length"]
        h = params["height"]
        wall = params.get("wall_thickness", 3.0)

        script_parts.append(f"""
# 1. Outer Enclosure Block
sketch_outer = doc.addObject('Sketcher::SketchObject', 'OuterBoxSketch')
body.addObject(sketch_outer)
sketch_outer.MapMode = 'FlatFace'

hw = {w / 2.0}
hl = {l / 2.0}
sketch_outer.addGeometry(Part.LineSegment(FreeCAD.Vector(-hw, -hl, 0), FreeCAD.Vector(hw, -hl, 0)))
sketch_outer.addGeometry(Part.LineSegment(FreeCAD.Vector(hw, -hl, 0), FreeCAD.Vector(hw, hl, 0)))
sketch_outer.addGeometry(Part.LineSegment(FreeCAD.Vector(hw, hl, 0), FreeCAD.Vector(-hw, hl, 0)))
sketch_outer.addGeometry(Part.LineSegment(FreeCAD.Vector(-hw, hl, 0), FreeCAD.Vector(-hw, -hl, 0)))

doc.recompute()

pad = doc.addObject('PartDesign::Pad', 'Pad')
body.addObject(pad)
pad.Profile = sketch_outer
pad.Length = {h}
doc.recompute()

# 2. Inner Hollow Pocket (Cavity)
sketch_inner = doc.addObject('Sketcher::SketchObject', 'CavitySketch')
body.addObject(sketch_inner)
sketch_inner.MapMode = 'FlatFace'

iw = hw - {wall}
il = hl - {wall}
sketch_inner.addGeometry(Part.LineSegment(FreeCAD.Vector(-iw, -il, 0), FreeCAD.Vector(iw, -il, 0)))
sketch_inner.addGeometry(Part.LineSegment(FreeCAD.Vector(iw, -il, 0), FreeCAD.Vector(iw, il, 0)))
sketch_inner.addGeometry(Part.LineSegment(FreeCAD.Vector(iw, il, 0), FreeCAD.Vector(-iw, il, 0)))
sketch_inner.addGeometry(Part.LineSegment(FreeCAD.Vector(-iw, il, 0), FreeCAD.Vector(-iw, -il, 0)))

doc.recompute()

pocket = doc.addObject('PartDesign::Pocket', 'Cavity')
body.addObject(pocket)
pocket.Profile = sketch_inner
pocket.Length = {h - wall}
doc.recompute()
""")

    elif cat == "cylinder":
        od = params["outer_diameter"]
        id_bore = params["bore_diameter"]
        length = params["length"]
        flange_dia = params.get("flange_diameter", 0.0)
        flange_thick = params.get("flange_thickness", 10.0)

        script_parts.append(f"""
# 1. Main Cylinder Sketch & Pad
sketch_cyl = doc.addObject('Sketcher::SketchObject', 'CylinderSketch')
body.addObject(sketch_cyl)
sketch_cyl.MapMode = 'FlatFace'

sketch_cyl.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {od/2.0}))
if {id_bore} > 0:
    sketch_cyl.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {id_bore/2.0}))

doc.recompute()

pad = doc.addObject('PartDesign::Pad', 'Pad')
body.addObject(pad)
pad.Profile = sketch_cyl
pad.Length = {length}
doc.recompute()

# 2. Flange if specified
if {flange_dia} > {od}:
    sketch_flg = doc.addObject('Sketcher::SketchObject', 'FlangeSketch')
    body.addObject(sketch_flg)
    sketch_flg.MapMode = 'FlatFace'
    sketch_flg.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {flange_dia/2.0}))
    if {id_bore} > 0:
        sketch_flg.addGeometry(Part.Circle(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {id_bore/2.0}))
    doc.recompute()
    
    pad_flg = doc.addObject('PartDesign::Pad', 'FlangePad')
    body.addObject(pad_flg)
    pad_flg.Profile = sketch_flg
    pad_flg.Length = {flange_thick}
    doc.recompute()
""")

    elif cat == "l_bracket":
        w = params["width"]
        l1 = params["leg1"]
        l2 = params["leg2"]
        thick = params["thickness"]
        hole = params.get("hole_diameter", 6.0)

        script_parts.append(f"""
# 1. L-Profile Sketch & Extrusion
sketch_l = doc.addObject('Sketcher::SketchObject', 'LProfileSketch')
body.addObject(sketch_l)
sketch_l.MapMode = 'FlatFace'

# Draw L-shaped wire profile
sketch_l.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector({l2}, 0, 0)))
sketch_l.addGeometry(Part.LineSegment(FreeCAD.Vector({l2}, 0, 0), FreeCAD.Vector({l2}, {thick}, 0)))
sketch_l.addGeometry(Part.LineSegment(FreeCAD.Vector({l2}, {thick}, 0), FreeCAD.Vector({thick}, {thick}, 0)))
sketch_l.addGeometry(Part.LineSegment(FreeCAD.Vector({thick}, {thick}, 0), FreeCAD.Vector({thick}, {l1}, 0)))
sketch_l.addGeometry(Part.LineSegment(FreeCAD.Vector({thick}, {l1}, 0), FreeCAD.Vector(0, {l1}, 0)))
sketch_l.addGeometry(Part.LineSegment(FreeCAD.Vector(0, {l1}, 0), FreeCAD.Vector(0, 0, 0)))

doc.recompute()

pad = doc.addObject('PartDesign::Pad', 'Pad')
body.addObject(pad)
pad.Profile = sketch_l
pad.Length = {w}
doc.recompute()
""")

    # Append solid measurement, 2D sketch extraction, and export
    script_parts.append(f"""
# Extract solid properties
shape = body.Shape
bb = shape.BoundBox

# Extract 2D sketch entities for visual blueprint
sketch_entities = []
for obj in doc.Objects:
    if obj.isDerivedFrom('Sketcher::SketchObject'):
        for g in obj.Geometry:
            if isinstance(g, Part.LineSegment):
                sketch_entities.append({{
                    "type": "line",
                    "x1": round(g.StartPoint.x, 2), "y1": round(g.StartPoint.y, 2),
                    "x2": round(g.EndPoint.x, 2), "y2": round(g.EndPoint.y, 2)
                }})
            elif isinstance(g, Part.Circle):
                sketch_entities.append({{
                    "type": "circle",
                    "cx": round(g.Center.x, 2), "cy": round(g.Center.y, 2),
                    "r": round(g.Radius, 2)
                }})

meta = {{
    "volume": float(shape.Volume),
    "area": float(shape.Area),
    "bounds": [
        [round(bb.XMin, 2), round(bb.YMin, 2), round(bb.ZMin, 2)],
        [round(bb.XMax, 2), round(bb.YMax, 2), round(bb.ZMax, 2)]
    ],
    "dimensions": [
        round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)
    ],
    "faces_count": len(shape.Faces),
    "edges_count": len(shape.Edges),
    "sketch_entities": sketch_entities
}}

# Save native FreeCAD project file (.FCStd)
doc.saveAs('{abs_fcstd}')

# Export industrial CAD STEP (.step)
Part.export([body], '{abs_step}')

# Export high-res 3D Mesh (.stl)
mesh = MeshPart.meshFromShape(
    Shape=shape,
    LinearDeflection=0.08,
    AngularDeflection=0.4,
    Relative=False
)
mesh.write('{abs_stl}')

print("---FREECAD_META_START---")
print(json.dumps(meta))
print("---FREECAD_META_END---")
print("CAD_BUILD_SUCCESS")
""")

    return "\n".join(script_parts)
