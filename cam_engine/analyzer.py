"""3D Model Analyzer for geometry inspection, bounding box, volume, and stock sizing."""

import os
import json
import numpy as np
from typing import Dict, Any, Optional
import trimesh

try:
    import FreeCAD
    import Part
    HAS_FREECAD_DIRECT = True
except ImportError:
    HAS_FREECAD_DIRECT = False


def inspect_model(file_path: str, padding_x: float = 5.0, padding_y: float = 5.0,
                  padding_z_top: float = 1.0, padding_z_bottom: float = 2.0) -> Dict[str, Any]:
    """Inspects a 3D model file (STEP, STL, OBJ, IGES, etc.) and returns geometric parameters."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Model file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    stats: Dict[str, Any] = {
        "file_name": os.path.basename(file_path),
        "file_path": os.path.abspath(file_path),
        "format": ext.replace(".", "").upper(),
        "file_size_bytes": os.path.getsize(file_path)
    }

    mesh = None
    solid = None

    # For mesh files (STL, OBJ, PLY)
    if ext in [".stl", ".obj", ".ply", ".off", ".3mf"]:
        mesh = trimesh.load(file_path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            # Combined scene
            mesh = mesh.dump().sum()

        bounds = mesh.bounds
        stats["vertex_count"] = len(mesh.vertices)
        stats["face_count"] = len(mesh.faces)
        stats["is_watertight"] = bool(mesh.is_watertight)
        stats["surface_area"] = float(mesh.area)
        stats["volume"] = float(mesh.volume) if mesh.is_watertight else float(mesh.convex_hull.volume)
        stats["center_of_mass"] = [float(c) for c in mesh.center_mass]

    # For CAD files (STEP, STP, IGES, BREP)
    elif ext in [".step", ".stp", ".iges", ".igs", ".brep"]:
        loaded = False
        if HAS_FREECAD_DIRECT:
            try:
                solid = Part.read(file_path)
                bb = solid.BoundBox
                bounds = np.array([
                    [bb.XMin, bb.YMin, bb.ZMin],
                    [bb.XMax, bb.YMax, bb.ZMax]
                ])
                stats["volume"] = float(solid.Volume)
                stats["surface_area"] = float(solid.Area)
                stats["is_solid"] = solid.isValid()
                stats["faces_count"] = len(solid.Faces)
                stats["edges_count"] = len(solid.Edges)
                loaded = True
            except Exception as e:
                pass

        if not loaded:
            # Try via trimesh or FreeCAD headless subprocess
            try:
                import cadquery as cq
                cq_obj = cq.importers.importStep(file_path)
                bb = cq_obj.val().BoundingBox()
                bounds = np.array([
                    [bb.xmin, bb.ymin, bb.zmin],
                    [bb.xmax, bb.ymax, bb.zmax]
                ])
                stats["volume"] = float(cq_obj.val().Volume())
                stats["surface_area"] = float(cq_obj.val().Area())
                stats["is_solid"] = True
                loaded = True
            except Exception:
                pass

        if not loaded:
            # Fallback to FreeCAD 1.1 binary inspection
            from .freecad_bridge import run_freecad_script
            script = f"""
import json, Part
s = Part.read(r'{os.path.abspath(file_path)}')
bb = s.BoundBox
out = {{
    "bounds": [[bb.XMin, bb.YMin, bb.ZMin], [bb.XMax, bb.YMax, bb.ZMax]],
    "volume": float(s.Volume),
    "surface_area": float(s.Area),
    "faces": len(s.Faces),
    "edges": len(s.Edges),
    "is_solid": s.isValid()
}}
print("---FREECAD_JSON_START---")
print(json.dumps(out))
print("---FREECAD_JSON_END---")
"""
            out_str = run_freecad_script(script)
            if "---FREECAD_JSON_START---" in out_str:
                j_str = out_str.split("---FREECAD_JSON_START---")[1].split("---FREECAD_JSON_END---")[0].strip()
                data = json.loads(j_str)
                bounds = np.array(data["bounds"])
                stats["volume"] = data["volume"]
                stats["surface_area"] = data["surface_area"]
                stats["faces_count"] = data.get("faces", 0)
                stats["edges_count"] = data.get("edges", 0)
                stats["is_solid"] = data.get("is_solid", True)
                loaded = True

        if not loaded:
            raise RuntimeError(f"Unable to parse STEP/CAD geometry from {file_path}")
    else:
        raise ValueError(f"Unsupported 3D file format: {ext}")

    # Calculate bounding box & dimensions
    min_x, min_y, min_z = [float(v) for v in bounds[0]]
    max_x, max_y, max_z = [float(v) for v in bounds[1]]
    dim_x = max_x - min_x
    dim_y = max_y - min_y
    dim_z = max_z - min_z

    stats["bounds"] = {
        "min": [round(min_x, 3), round(min_y, 3), round(min_z, 3)],
        "max": [round(max_x, 3), round(max_y, 3), round(max_z, 3)]
    }
    stats["dimensions"] = {
        "x": round(dim_x, 3),
        "y": round(dim_y, 3),
        "z": round(dim_z, 3)
    }

    # Recommended Stock Size
    stock_x = dim_x + (padding_x * 2)
    stock_y = dim_y + (padding_y * 2)
    stock_z = dim_z + padding_z_top + padding_z_bottom

    stats["recommended_stock"] = {
        "dimensions": [round(stock_x, 2), round(stock_y, 2), round(stock_z, 2)],
        "origin_offset": [round(min_x - padding_x, 2), round(min_y - padding_y, 2), round(min_z - padding_z_bottom, 2)],
        "top_facing_allowance": round(padding_z_top, 2),
        "bottom_holding_allowance": round(padding_z_bottom, 2),
        "stock_volume": round(stock_x * stock_y * stock_z, 2)
    }

    # Recommend Tools
    min_feature = min(dim_x, dim_y, dim_z)
    stats["recommended_tools"] = [
        {"role": "Facing", "tool": "25mm_facemill" if dim_x > 40 and dim_y > 40 else "10mm_rougher"},
        {"role": "Roughing", "tool": "10mm_rougher" if min_feature > 15 else "6mm_endmill"},
        {"role": "Finishing / Contour", "tool": "6mm_endmill" if min_feature > 10 else "3mm_endmill"},
        {"role": "3D Surface Finishing", "tool": "6mm_ballnose"}
    ]

    return stats
