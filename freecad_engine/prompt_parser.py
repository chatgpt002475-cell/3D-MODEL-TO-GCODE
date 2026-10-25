"""
Advanced Natural Language & Parametric Prompt Parser for FreeCAD.
Translates prompts into advanced B-Rep Wires, Lofts, Sweeps, Revolutions, Gear Profiles, and Multi-Loop Sketches.
"""

import re
import math
from typing import Dict, Any, Tuple
from .wire_builder import generate_wire_script_helpers

def parse_prompt_to_params(prompt: str) -> Dict[str, Any]:
    """Extracts geometric intent and parameters from natural language prompt."""
    p = prompt.lower().strip()

    # Determine advanced CAD operation category
    if any(w in p for w in ["loft", "transition", "nozzle", "duct", "square to round", "pyramid"]):
        category = "loft"
    elif any(w in p for w in ["sweep", "pipe", "elbow", "conduit", "tube", "bent"]):
        category = "sweep"
    elif any(w in p for w in ["revolve", "pulley", "turned", "lathe", "v-groove", "groove"]):
        category = "revolve"
    elif any(w in p for w in ["gear", "sprocket", "cog", "teeth"]):
        category = "gear"
    elif any(w in p for w in ["slot", "oblong"]):
        category = "slot_plate"
    elif any(w in p for w in ["flange", "disc", "ring", "pcd", "bolt circle"]):
        category = "flange"
    elif any(w in p for w in ["enclosure", "box", "housing", "casing"]):
        category = "enclosure"
    elif any(w in p for w in ["bushing", "spacer", "shaft", "cylinder", "boss"]):
        category = "cylinder"
    elif any(w in p for w in ["l-bracket", "angle", "l bracket"]):
        category = "l_bracket"
    else:
        # Default based on keywords
        if "circle" in p or "diameter" in p:
            category = "flange" if ("hole" in p or "bolt" in p) else "cylinder"
        else:
            category = "plate"

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

    dims_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|\*|\sby\s)\s*(\d+(?:\.\d+)?)(?:\s*(?:x|\*|\sby\s)\s*(\d+(?:\.\d+)?))?', p)

    params: Dict[str, Any] = {
        "category": category,
        "prompt": prompt,
        "name": re.sub(r'[^a-zA-Z0-9_]', '_', prompt[:30]).strip('_') or "Part"
    }

    # 1. LOFT (Transition between wires at different Z elevations)
    if category == "loft":
        base_w = find_val([r'square\s*(\d+(?:\.\d+)?)', r'base\s*(\d+(?:\.\d+)?)', r'width\s*(\d+(?:\.\d+)?)'], 80.0)
        top_dia = find_val([r'circle\s*(?:dia(?:meter)?)?\s*(\d+(?:\.\d+)?)', r'top\s*(?:dia(?:meter)?)?\s*(\d+(?:\.\d+)?)'], 40.0)
        height = find_val([r'height\s*(\d+(?:\.\d+)?)', r'length\s*(\d+(?:\.\d+)?)', r'at\s*(\d+(?:\.\d+)?)'], 60.0)
        bore = find_val([r'bore\s*(\d+(?:\.\d+)?)', r'hole\s*(\d+(?:\.\d+)?)'], 0.0)
        params.update({
            "base_width": base_w,
            "top_diameter": top_dia,
            "height": height,
            "bore_diameter": bore
        })

    # 2. SWEEP / PIPE (2D Wire Profile along 3D Spine Wire)
    elif category == "sweep":
        pipe_dia = find_val([r'pipe\s*(?:dia(?:meter)?)?\s*(\d+(?:\.\d+)?)', r'dia(?:meter)?\s*(\d+(?:\.\d+)?)'], 24.0)
        bend_r = find_val([r'(?:bend|arc|elbow)?\s*radius\s*(\d+(?:\.\d+)?)', r'bend\s*(\d+(?:\.\d+)?)'], 60.0)
        leg1 = find_val([r'leg\s*1\s*(\d+(?:\.\d+)?)', r'straight\s*(\d+(?:\.\d+)?)'], 40.0)
        leg2 = find_val([r'leg\s*2\s*(\d+(?:\.\d+)?)'], 40.0)
        bore = find_val([r'bore\s*(\d+(?:\.\d+)?)', r'inner\s*(\d+(?:\.\d+)?)'], pipe_dia * 0.7)
        params.update({
            "pipe_diameter": pipe_dia,
            "bend_radius": bend_r,
            "leg1": leg1,
            "leg2": leg2,
            "inner_bore": bore
        })

    # 3. REVOLVE (Rotational wire cross-section around Z axis)
    elif category == "revolve":
        od = find_val([r'dia(?:meter)?\s*(\d+(?:\.\d+)?)', r'outer\s*(\d+(?:\.\d+)?)'], 80.0)
        bore = find_val([r'bore\s*(\d+(?:\.\d+)?)', r'inner\s*(\d+(?:\.\d+)?)'], 20.0)
        width = find_val([r'width\s*(\d+(?:\.\d+)?)', r'thick(?:ness)?\s*(\d+(?:\.\d+)?)'], 30.0)
        groove_w = find_val([r'groove\s*(?:width)?\s*(\d+(?:\.\d+)?)'], 12.0)
        groove_d = find_val([r'depth\s*(\d+(?:\.\d+)?)'], 8.0)
        params.update({
            "outer_diameter": od,
            "bore_diameter": bore,
            "width": width,
            "groove_width": groove_w,
            "groove_depth": groove_d
        })

    # 4. GEAR (Involute Tooth Profile Wire)
    elif category == "gear":
        teeth = find_int([r'(\d+)\s*teeth', r'teeth\s*(\d+)'], 16)
        od = find_val([r'outer\s*dia(?:meter)?\s*(\d+(?:\.\d+)?)', r'dia(?:meter)?\s*(\d+(?:\.\d+)?)'], 60.0)
        bore = find_val([r'bore\s*(\d+(?:\.\d+)?)', r'hole\s*(\d+(?:\.\d+)?)'], 15.0)
        thick = find_val([r'thick(?:ness)?\s*(\d+(?:\.\d+)?)', r'face\s*width\s*(\d+(?:\.\d+)?)'], 18.0)
        keyway = find_val([r'keyway\s*(\d+(?:\.\d+)?)'], 5.0)
        params.update({
            "teeth": teeth,
            "outer_diameter": od,
            "root_diameter": od * 0.75,
            "bore_diameter": bore,
            "thickness": thick,
            "keyway_width": keyway
        })

    # 5. SLOT PLATE (Multi-Wire Compound with Oblong Slots)
    elif category == "slot_plate":
        w, l, h = 120.0, 80.0, 10.0
        if dims_match:
            w = float(dims_match.group(1))
            l = float(dims_match.group(2))
            if dims_match.group(3):
                h = float(dims_match.group(3))
        slot_l = find_val([r'slot\s*(?:length)?\s*(\d+(?:\.\d+)?)'], 30.0)
        slot_w = find_val([r'slot\s*(?:width)?\s*(\d+(?:\.\d+)?)'], 12.0)
        hole = find_val([r'hole\s*(\d+(?:\.\d+)?)'], 8.0)
        params.update({
            "width": w,
            "length": l,
            "thickness": h,
            "slot_length": slot_l,
            "slot_width": slot_w,
            "hole_diameter": hole
        })

    # 6. FLANGE (Multi-hole Bolt Circle Wire)
    elif category == "flange":
        od = find_val([r'outer\s*dia(?:meter)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                       r'od\s*[:=]?\s*(\d+(?:\.\d+)?)',
                       r'dia(?:meter)?\s*(?:of\s*)?(\d+(?:\.\d+)?)'], 100.0)
        bore = find_val([r'(?:inner|center|bore|hole)\s*(?:dia(?:meter)?)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], 30.0)
        thick = find_val([r'thick(?:ness)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                          r'height\s*[:=]?\s*(\d+(?:\.\d+)?)'], 15.0)
        bolt_count = find_int([r'(\d+)\s*(?:bolt|mounting)?\s*holes'], 6)
        bolt_dia = find_val([r'bolt\s*(?:hole)?\s*(?:dia(?:meter)?)?\s*[:=]?\s*(\d+(?:\.\d+)?)',
                             r'holes?\s*(?:of\s*)?dia(?:meter)?\s*(\d+(?:\.\d+)?)'], 8.0)
        pcd = find_val([r'pcd\s*[:=]?\s*(\d+(?:\.\d+)?)',
                        r'pitch\s*circle\s*[:=]?\s*(\d+(?:\.\d+)?)'], (od + bore) / 2.0)
        params.update({
            "outer_diameter": od,
            "bore_diameter": bore,
            "thickness": thick,
            "bolt_count": bolt_count,
            "bolt_diameter": bolt_dia,
            "pcd": pcd
        })

    # 7. PLATE
    elif category == "plate":
        w, l, h = 100.0, 60.0, 10.0
        if dims_match:
            w = float(dims_match.group(1))
            l = float(dims_match.group(2))
            if dims_match.group(3):
                h = float(dims_match.group(3))
        w = find_val([r'width\s*[:=]?\s*(\d+(?:\.\d+)?)'], w)
        l = find_val([r'length\s*[:=]?\s*(\d+(?:\.\d+)?)', r'height\s*[:=]?\s*(\d+(?:\.\d+)?)'], l)
        h = find_val([r'thick(?:ness)?\s*[:=]?\s*(\d+(?:\.\d+)?)'], h)
        hole_dia = find_val([r'holes?\s*dia(?:meter)?\s*(\d+(?:\.\d+)?)', r'holes?\s*(\d+(?:\.\d+)?)'], 6.0)
        center_hole = find_val([r'center\s*hole\s*(\d+(?:\.\d+)?)'], 0.0)
        params.update({
            "width": w,
            "length": l,
            "thickness": h,
            "corner_hole_diameter": hole_dia,
            "center_hole_diameter": center_hole
        })

    # 8. ENCLOSURE
    elif category == "enclosure":
        w, l, h = 120.0, 80.0, 40.0
        if dims_match:
            w = float(dims_match.group(1))
            l = float(dims_match.group(2))
            if dims_match.group(3):
                h = float(dims_match.group(3))
        wall = find_val([r'wall\s*(?:thick(?:ness)?)?\s*(\d+(?:\.\d+)?)'], 3.0)
        params.update({
            "width": w,
            "length": l,
            "height": h,
            "wall_thickness": wall
        })

    # 9. CYLINDER / STEPPED SHAFT
    elif category == "cylinder":
        od = find_val([r'outer\s*dia(?:meter)?\s*(\d+(?:\.\d+)?)', r'dia(?:meter)?\s*(\d+(?:\.\d+)?)'], 50.0)
        id_bore = find_val([r'(?:inner|bore|hole)\s*(\d+(?:\.\d+)?)'], 20.0)
        length = find_val([r'length\s*(\d+(?:\.\d+)?)', r'height\s*(\d+(?:\.\d+)?)'], 60.0)
        flange_dia = find_val([r'flange\s*dia(?:meter)?\s*(\d+(?:\.\d+)?)'], 0.0)
        flange_thick = find_val([r'flange\s*thick(?:ness)?\s*(\d+(?:\.\d+)?)'], 10.0)
        params.update({
            "outer_diameter": od,
            "bore_diameter": id_bore,
            "length": length,
            "flange_diameter": flange_dia,
            "flange_thickness": flange_thick
        })

    # 10. L-BRACKET
    elif category == "l_bracket":
        w = find_val([r'width\s*(\d+(?:\.\d+)?)'], 50.0)
        l1 = find_val([r'leg\s*1\s*(\d+(?:\.\d+)?)', r'height\s*(\d+(?:\.\d+)?)'], 70.0)
        l2 = find_val([r'leg\s*2\s*(\d+(?:\.\d+)?)', r'length\s*(\d+(?:\.\d+)?)'], 70.0)
        thick = find_val([r'thick(?:ness)?\s*(\d+(?:\.\d+)?)'], 8.0)
        hole = find_val([r'hole\s*(\d+(?:\.\d+)?)'], 6.0)
        params.update({
            "width": w,
            "leg1": l1,
            "leg2": l2,
            "thickness": thick,
            "hole_diameter": hole
        })

    return params


def generate_freecad_script(params: Dict[str, Any], output_fcstd: str, output_step: str, output_stl: str) -> str:
    """Generates complete, executable FreeCAD Python script using advanced OpenCASCADE Wiring."""
    cat = params.get("category", "flange")

    abs_fcstd = output_fcstd.replace("\\", "/")
    abs_step = output_step.replace("\\", "/")
    abs_stl = output_stl.replace("\\", "/")

    script_parts = [
        "import FreeCAD, Part, Sketcher, Mesh, MeshPart, json, math",
        "doc = FreeCAD.newDocument('Advanced_CAD_Model')",
        generate_wire_script_helpers(),
        ""
    ]

    # --- CATEGORY 1: LOFT (Square-to-Round or Multi-Wire Loft) ---
    if cat == "loft":
        bw = params["base_width"]
        td = params["top_diameter"]
        h = params["height"]
        bore = params.get("bore_diameter", 0.0)

        script_parts.append(f"""
# 1. Advanced Lofting between Square Wire and Circle Wire
hw = {bw / 2.0}
w1 = make_polygon_wire([
    [-hw, -hw, 0], [hw, -hw, 0], [hw, hw, 0], [-hw, hw, 0], [-hw, -hw, 0]
], closed=True)

w2 = make_circle_wire({td / 2.0}, center=(0,0,{h}), normal=(0,0,1))

solid = Part.makeLoft([w1, w2], True)

if {bore} > 0:
    bore_wire = make_circle_wire({bore / 2.0}, center=(0,0,-5), normal=(0,0,1))
    bore_face = Part.Face(bore_wire)
    bore_tool = bore_face.extrude(FreeCAD.Vector(0,0,{h + 10}))
    solid = solid.cut(bore_tool)

part_obj = doc.addObject('Part::Feature', 'LoftedTransition')
part_obj.Shape = solid
doc.recompute()
""")

    # --- CATEGORY 2: SWEEP (3D Pipe Along Trajectory Wire) ---
    elif cat == "sweep":
        pd = params["pipe_diameter"]
        br = params["bend_radius"]
        l1 = params["leg1"]
        l2 = params["leg2"]
        bore = params.get("inner_bore", 0.0)

        script_parts.append(f"""
# 2. Advanced 3D Wire Sweep (Elbow / Curved Conduit)
spine_wire = make_90deg_elbow_spine({l1}, {br}, {l2})
profile_wire = make_circle_wire({pd / 2.0}, center=(0,0,0), normal=(0,0,1))

solid = spine_wire.makePipe(profile_wire)

if {bore} > 0:
    inner_prof = make_circle_wire({bore / 2.0}, center=(0,0,0), normal=(0,0,1))
    inner_pipe = spine_wire.makePipe(inner_prof)
    solid = solid.cut(inner_pipe)

part_obj = doc.addObject('Part::Feature', 'SweptPipe')
part_obj.Shape = solid
doc.recompute()
""")

    # --- CATEGORY 3: REVOLVE (Pulley / Turned Wire Profile) ---
    elif cat == "revolve":
        od = params["outer_diameter"]
        bore = params["bore_diameter"]
        w = params["width"]
        gw = params["groove_width"]
        gd = params["groove_depth"]

        r_out = od / 2.0
        r_bore = bore / 2.0
        hw = w / 2.0
        hgw = gw / 2.0
        r_groove = max(r_bore + 5.0, r_out - gd)

        script_parts.append(f"""
# 3. Advanced Wire Revolution (V-Groove Pulley / Turned Solid)
pts = [
    ({r_bore}, 0, -{hw}),
    ({r_out}, 0, -{hw}),
    ({r_out}, 0, -{hgw}),
    ({r_groove}, 0, 0),
    ({r_out}, 0, {hgw}),
    ({r_out}, 0, {hw}),
    ({r_bore}, 0, {hw}),
    ({r_bore}, 0, -{hw})
]

cross_wire = make_polygon_wire(pts, closed=True)
cross_face = Part.Face(cross_wire)
solid = cross_face.revolve(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 360)

part_obj = doc.addObject('Part::Feature', 'RevolvedPulley')
part_obj.Shape = solid
doc.recompute()
""")

    # --- CATEGORY 4: GEAR (Involute Tooth Profile Wire) ---
    elif cat == "gear":
        teeth = params["teeth"]
        od = params["outer_diameter"]
        rd = params["root_diameter"]
        bore = params["bore_diameter"]
        thick = params["thickness"]
        kw = params.get("keyway_width", 5.0)

        script_parts.append(f"""
# 4. Advanced Gear Tooth Profile Wire
gear_wire = make_gear_profile_wire({teeth}, {od / 2.0}, {rd / 2.0}, center=(0,0,0))
gear_face = Part.Face(gear_wire)
solid = gear_face.extrude(FreeCAD.Vector(0,0,{thick}))

# Center bore & keyway cutout
if {bore} > 0:
    bore_wire = make_circle_wire({bore / 2.0}, center=(0,0,-1), normal=(0,0,1))
    bore_face = Part.Face(bore_wire)
    bore_tool = bore_face.extrude(FreeCAD.Vector(0,0,{thick + 2}))
    solid = solid.cut(bore_tool)
    
    if {kw} > 0:
        hkw = {kw / 2.0}
        kw_pts = [
            (-hkw, {bore/2.0 - 1}, -1), (hkw, {bore/2.0 - 1}, -1),
            (hkw, {bore/2.0 + kw*0.8}, -1), (-hkw, {bore/2.0 + kw*0.8}, -1),
            (-hkw, {bore/2.0 - 1}, -1)
        ]
        kw_face = Part.Face(make_polygon_wire(kw_pts, closed=True))
        kw_tool = kw_face.extrude(FreeCAD.Vector(0,0,{thick + 2}))
        solid = solid.cut(kw_tool)

part_obj = doc.addObject('Part::Feature', 'SpurGear')
part_obj.Shape = solid
doc.recompute()
""")

    # --- CATEGORY 5: SLOT PLATE (Oblong Slots & Multi-Wire Holes) ---
    elif cat == "slot_plate":
        w = params["width"]
        l = params["length"]
        thick = params["thickness"]
        sl = params["slot_length"]
        sw = params["slot_width"]
        hole = params.get("hole_diameter", 8.0)

        hw = w / 2.0
        hl = l / 2.0

        script_parts.append(f"""
# 5. Advanced Multi-Wire Plate with Oblong Slots
base_wire = make_polygon_wire([
    [-{hw}, -{hl}, 0], [{hw}, -{hl}, 0], [{hw}, {hl}, 0], [-{hw}, {hl}, 0], [-{hw}, -{hl}, 0]
], closed=True)
solid = Part.Face(base_wire).extrude(FreeCAD.Vector(0,0,{thick}))

# Cut dual oblong slots
slot1 = Part.Face(make_slot_wire({sl}, {sw}, center=(-{hw*0.4}, 0, -1))).extrude(FreeCAD.Vector(0,0,{thick + 2}))
slot2 = Part.Face(make_slot_wire({sl}, {sw}, center=({hw*0.4}, 0, -1))).extrude(FreeCAD.Vector(0,0,{thick + 2}))
solid = solid.cut(slot1).cut(slot2)

# Corner holes
if {hole} > 0:
    for cx in [-{hw * 0.8}, {hw * 0.8}]:
        for cy in [-{hl * 0.75}, {hl * 0.75}]:
            h_tool = Part.Face(make_circle_wire({hole / 2.0}, center=(cx, cy, -1))).extrude(FreeCAD.Vector(0,0,{thick + 2}))
            solid = solid.cut(h_tool)

part_obj = doc.addObject('Part::Feature', 'SlottedBracket')
part_obj.Shape = solid
doc.recompute()
""")

    # --- CATEGORY 6: FLANGE (PCD Bolt Circle Compound) ---
    elif cat == "flange":
        od = params["outer_diameter"]
        bore = params["bore_diameter"]
        thick = params["thickness"]
        bc = params["bolt_count"]
        bd = params["bolt_diameter"]
        pcd = params["pcd"]

        script_parts.append(f"""
# 6. Advanced Flange Multi-Wire Compound
outer_w = make_circle_wire({od / 2.0}, center=(0,0,0), normal=(0,0,1))
solid = Part.Face(outer_w).extrude(FreeCAD.Vector(0,0,{thick}))

if {bore} > 0:
    bore_w = make_circle_wire({bore / 2.0}, center=(0,0,-1), normal=(0,0,1))
    bore_tool = Part.Face(bore_w).extrude(FreeCAD.Vector(0,0,{thick + 2}))
    solid = solid.cut(bore_tool)

if {bc} > 0 and {pcd} > 0 and {bd} > 0:
    for i in range({bc}):
        ang = 2.0 * math.pi * i / {bc}
        bx = ({pcd} / 2.0) * math.cos(ang)
        by = ({pcd} / 2.0) * math.sin(ang)
        b_tool = Part.Face(make_circle_wire({bd / 2.0}, center=(bx, by, -1))).extrude(FreeCAD.Vector(0,0,{thick + 2}))
        solid = solid.cut(b_tool)

part_obj = doc.addObject('Part::Feature', 'Flange')
part_obj.Shape = solid
doc.recompute()
""")

    # --- DEFAULT / FALLBACK (PLATE, ENCLOSURE, CYLINDER, L-BRACKET) ---
    elif cat == "enclosure":
        w = params["width"]
        l = params["length"]
        h = params["height"]
        wall = params.get("wall_thickness", 3.0)
        hw = w / 2.0
        hl = l / 2.0
        iw = hw - wall
        il = hl - wall

        script_parts.append(f"""
# 7. Thin-Walled Enclosure Compound
outer_w = make_polygon_wire([[-{hw}, -{hl}, 0], [{hw}, -{hl}, 0], [{hw}, {hl}, 0], [-{hw}, {hl}, 0], [-{hw}, -{hl}, 0]])
solid = Part.Face(outer_w).extrude(FreeCAD.Vector(0,0,{h}))

inner_w = make_polygon_wire([[-{iw}, -{il}, {wall}], [{iw}, -{il}, {wall}], [{iw}, {il}, {wall}], [-{iw}, {il}, {wall}], [-{iw}, -{il}, {wall}]])
cavity = Part.Face(inner_w).extrude(FreeCAD.Vector(0,0,{h}))
solid = solid.cut(cavity)

part_obj = doc.addObject('Part::Feature', 'Enclosure')
part_obj.Shape = solid
doc.recompute()
""")

    elif cat == "l_bracket":
        w = params["width"]
        l1 = params["leg1"]
        l2 = params["leg2"]
        thick = params["thickness"]
        hole = params.get("hole_diameter", 6.0)

        script_parts.append(f"""
# 8. L-Profile Wire Extrusion
l_wire = make_polygon_wire([
    [0, 0, 0], [{l2}, 0, 0], [{l2}, {thick}, 0], [{thick}, {thick}, 0],
    [{thick}, {l1}, 0], [0, {l1}, 0], [0, 0, 0]
], closed=True)

solid = Part.Face(l_wire).extrude(FreeCAD.Vector(0,0,{w}))

if {hole} > 0:
    h1 = Part.Face(make_circle_wire({hole / 2.0}, center=({l2 * 0.6}, -1, {w / 2.0}), normal=(0,1,0))).extrude(FreeCAD.Vector(0,{thick + 2},0))
    h2 = Part.Face(make_circle_wire({hole / 2.0}, center=(-1, {l1 * 0.6}, {w / 2.0}), normal=(1,0,0))).extrude(FreeCAD.Vector({thick + 2},0,0))
    solid = solid.cut(h1).cut(h2)

part_obj = doc.addObject('Part::Feature', 'LBracket')
part_obj.Shape = solid
doc.recompute()
""")

    else:
        # Standard Plate
        w = params.get("width", 100.0)
        l = params.get("length", 60.0)
        thick = params.get("thickness", 10.0)
        hole = params.get("corner_hole_diameter", 6.0)
        center_hole = params.get("center_hole_diameter", 0.0)
        hw = w / 2.0
        hl = l / 2.0

        script_parts.append(f"""
# 9. Parametric Plate Wire
base_wire = make_polygon_wire([
    [-{hw}, -{hl}, 0], [{hw}, -{hl}, 0], [{hw}, {hl}, 0], [-{hw}, {hl}, 0], [-{hw}, -{hl}, 0]
], closed=True)
solid = Part.Face(base_wire).extrude(FreeCAD.Vector(0,0,{thick}))

if {center_hole} > 0:
    c_tool = Part.Face(make_circle_wire({center_hole / 2.0}, center=(0,0,-1))).extrude(FreeCAD.Vector(0,0,{thick + 2}))
    solid = solid.cut(c_tool)

if {hole} > 0:
    for sx in [-{hw*0.75}, {hw*0.75}]:
        for sy in [-{hl*0.75}, {hl*0.75}]:
            h_tool = Part.Face(make_circle_wire({hole / 2.0}, center=(sx, sy, -1))).extrude(FreeCAD.Vector(0,0,{thick + 2}))
            solid = solid.cut(h_tool)

part_obj = doc.addObject('Part::Feature', 'Plate')
part_obj.Shape = solid
doc.recompute()
""")

    # Extract 3D Wire Graph, Bounding Box, Volume, and Export
    script_parts.append(f"""
# Extract solid properties and B-Rep wire topology
shape = part_obj.Shape
bb = shape.BoundBox

wires_graph = extract_wire_graph(shape)

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
    "wires_count": len(shape.Wires),
    "wires_graph": wires_graph
}}

# Save native FreeCAD project file (.FCStd)
doc.saveAs('{abs_fcstd}')

# Export industrial CAD STEP (.step)
Part.export([part_obj], '{abs_step}')

# Export high-res 3D Mesh (.stl)
mesh = MeshPart.meshFromShape(
    Shape=shape,
    LinearDeflection=0.06,
    AngularDeflection=0.35,
    Relative=False
)
mesh.write('{abs_stl}')

print("---FREECAD_META_START---")
print(json.dumps(meta))
print("---FREECAD_META_END---")
print("CAD_BUILD_SUCCESS")
""")

    return "\n".join(script_parts)
