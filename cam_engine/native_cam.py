"""Native 3D CAM Engine: Automated Facing, Profiling, Pocketing, and 3D Waterline/Surface toolpaths."""

import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union
from typing import List, Dict, Any, Tuple
import os

from .config import ToolProfile, StockConfig, CAMSettings
from .postprocessors import PostProcessor

class NativeCAMEngine:
    """Automated Toolpath Generator for 3-Axis CNC Machining from 3D models."""

    def __init__(self, tool: ToolProfile = None, stock: StockConfig = None, settings: CAMSettings = None):
        self.tool = tool or ToolProfile()
        self.stock = stock or StockConfig()
        self.settings = settings or CAMSettings()
        self.post = PostProcessor(self.settings.postprocessor, {
            "spindle_speed": self.tool.spindle_speed,
            "coolant": self.settings.cooling
        })

    def generate(self, model_info: Dict[str, Any], mesh: trimesh.Trimesh) -> Tuple[str, Dict[str, Any]]:
        """Generates complete G-code from analyzed model info and mesh."""
        bounds = model_info["bounds"]
        min_x, min_y, min_z = bounds["min"]
        max_x, max_y, max_z = bounds["max"]

        stock_min_x = min_x - self.stock.padding_x
        stock_max_x = max_x + self.stock.padding_x
        stock_min_y = min_y - self.stock.padding_y
        stock_max_y = max_y + self.stock.padding_y
        stock_top_z = max_z + self.stock.padding_z_top
        part_top_z = max_z
        part_bot_z = min_z

        gcode_lines: List[str] = []
        gcode_lines.extend(self.post.format_header(model_info, {
            "name": self.tool.name,
            "diameter": self.tool.diameter
        }))

        tool_radius = self.tool.diameter / 2.0
        feed = self.tool.feed_rate
        plunge = self.tool.plunge_rate
        stepdown = self.tool.stepdown
        stepover = self.tool.stepover
        safe_z = stock_top_z + self.settings.safe_z
        rapid_z = stock_top_z + self.settings.rapid_z

        stats = {
            "operations_run": [],
            "total_cut_length": 0.0,
            "total_rapid_length": 0.0,
            "estimated_time_sec": 0.0
        }

        current_pos = [0.0, 0.0, safe_z]

        def rapid_to(x: float, y: float, z: float = None):
            nonlocal current_pos
            if z is not None:
                # If moving in Z, retract first if safe
                if z < current_pos[2]:
                    # Plunge or move down
                    gcode_lines.append(f"G0 X{x:.3f} Y{y:.3f}")
                    gcode_lines.append(f"G0 Z{z:.3f}")
                else:
                    gcode_lines.append(f"G0 Z{z:.3f}")
                    gcode_lines.append(f"G0 X{x:.3f} Y{y:.3f}")
                current_pos = [x, y, z]
            else:
                gcode_lines.append(f"G0 X{x:.3f} Y{y:.3f}")
                current_pos[0] = x
                current_pos[1] = y

        def cut_to(x: float, y: float, z: float, f: float = None):
            nonlocal current_pos
            f_str = f" F{f:.1f}" if f else ""
            gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}{f_str}")
            dist = np.sqrt((x - current_pos[0])**2 + (y - current_pos[1])**2 + (z - current_pos[2])**2)
            stats["total_cut_length"] += float(dist)
            current_pos = [x, y, z]

        # ----------------------------------------------------
        # 1. OPERATION: FACING (Face Mill top surface)
        # ----------------------------------------------------
        if "facing" in self.settings.operations and self.stock.padding_z_top > 0:
            stats["operations_run"].append("Facing")
            gcode_lines.append("")
            gcode_lines.append("(=== OPERATION 1: Facing Top Surface ===)")
            
            # Start at safe Z
            rapid_to(stock_min_x - tool_radius, stock_min_y - tool_radius, safe_z)

            z_current = stock_top_z
            while z_current > part_top_z:
                z_current = max(part_top_z, z_current - stepdown)
                gcode_lines.append(f"(Facing Pass at Z={z_current:.3f})")

                # Zigzag passes along Y
                y_passes = np.arange(stock_min_y - tool_radius, stock_max_y + tool_radius + stepover, stepover)
                direction = 1

                for idx, y in enumerate(y_passes):
                    x_start = stock_min_x - tool_radius - 2.0 if direction == 1 else stock_max_x + tool_radius + 2.0
                    x_end = stock_max_x + tool_radius + 2.0 if direction == 1 else stock_min_x - tool_radius - 2.0

                    if idx == 0:
                        rapid_to(x_start, y)
                        gcode_lines.append(f"G0 Z{rapid_z:.3f}")
                        cut_to(x_start, y, z_current, plunge)
                    else:
                        cut_to(x_start, y, z_current, feed)

                    cut_to(x_end, y, z_current, feed)
                    direction *= -1

                # Retract to safe Z between depth levels
                rapid_to(current_pos[0], current_pos[1], safe_z)

        # ----------------------------------------------------
        # 2. OPERATION: 2D PROFILING / OUTER CONTOUR
        # ----------------------------------------------------
        if "contour" in self.settings.operations:
            stats["operations_run"].append("Contour Profiling")
            gcode_lines.append("")
            gcode_lines.append("(=== OPERATION 2: Outer Contour Profiling ===)")

            # Create 2D boundary polygon from mesh projection
            # Slice near the bottom of the part to get full outer silhouette
            slice_z = part_bot_z + 0.5
            path_2d = mesh.section(plane_origin=[0, 0, slice_z], plane_normal=[0, 0, 1])

            if path_2d is not None:
                # Convert path to 2D polygons
                polys = path_2d.to_planar()[0].polygons_full
                if len(polys) > 0:
                    outer_poly = max(polys, key=lambda p: p.area)
                else:
                    outer_poly = Polygon([(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)])
            else:
                outer_poly = Polygon([(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)])

            # Offset outside by tool radius
            toolpath_poly = outer_poly.buffer(tool_radius, join_style=2)
            if isinstance(toolpath_poly, MultiPolygon):
                toolpath_poly = max(toolpath_poly.geoms, key=lambda p: p.area)

            exterior_coords = list(toolpath_poly.exterior.coords)

            z_current = part_top_z
            first_point = exterior_coords[0]

            while z_current > part_bot_z:
                z_current = max(part_bot_z, z_current - stepdown)
                gcode_lines.append(f"(Contour Pass at Z={z_current:.3f})")

                # Approach
                rapid_to(first_point[0], first_point[1], safe_z)
                gcode_lines.append(f"G0 Z{rapid_z:.3f}")
                cut_to(first_point[0], first_point[1], z_current, plunge)

                # Cut perimeter
                for pt in exterior_coords[1:]:
                    cut_to(pt[0], pt[1], z_current, feed)

                # Overlap cut slightly for smooth finish
                cut_to(first_point[0], first_point[1], z_current, feed)
                rapid_to(first_point[0], first_point[1], safe_z)

        # ----------------------------------------------------
        # 3. OPERATION: 3D WATERLINE FINISHING / SURFACE
        # ----------------------------------------------------
        if "surface" in self.settings.operations or "waterline" in self.settings.operations:
            stats["operations_run"].append("3D Waterline Finishing")
            gcode_lines.append("")
            gcode_lines.append("(=== OPERATION 3: 3D Waterline Surface Finishing ===)")

            waterline_stepdown = max(0.4, stepdown / 2.0)
            z_levels = np.arange(part_top_z, part_bot_z - 0.01, -waterline_stepdown)

            for z_lvl in z_levels:
                sec = mesh.section(plane_origin=[0, 0, z_lvl], plane_normal=[0, 0, 1])
                if sec is None:
                    continue
                planar, _ = sec.to_planar()
                polys = planar.polygons_full
                if not polys:
                    continue

                for poly in polys:
                    # Offset poly by tool radius
                    off_poly = poly.buffer(tool_radius, join_style=2)
                    if off_poly.is_empty:
                        continue
                    geoms = off_poly.geoms if isinstance(off_poly, MultiPolygon) else [off_poly]
                    for g in geoms:
                        coords = list(g.exterior.coords)
                        if len(coords) < 3:
                            continue
                        # Rapid to start
                        rapid_to(coords[0][0], coords[0][1], safe_z)
                        gcode_lines.append(f"G0 Z{rapid_z:.3f}")
                        cut_to(coords[0][0], coords[0][1], z_lvl, plunge)
                        for c in coords[1:]:
                            cut_to(c[0], c[1], z_lvl, feed)
                        rapid_to(coords[-1][0], coords[-1][1], safe_z)

        # Append standard footer
        gcode_lines.extend(self.post.format_footer())

        # Estimated cycle time calculation:
        # cut time = length / feedrate, rapid time = rapid_length / max_feed
        stats["estimated_time_sec"] = (stats["total_cut_length"] / (feed / 60.0)) + 15.0
        stats["total_lines"] = len(gcode_lines)

        full_gcode = "\n".join(gcode_lines)
        return full_gcode, stats
