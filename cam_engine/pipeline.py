"""Unified CAM Pipeline: Converts 3D Models into Optimized, Production-Ready G-Code."""

import os
import trimesh
from typing import Dict, Any, Optional, Tuple

from .analyzer import inspect_model
from .config import ToolProfile, StockConfig, CAMSettings, TOOL_PRESETS, MACHINE_PRESETS
from .native_cam import NativeCAMEngine
from .simulator import GCodeSimulator
from .freecad_bridge import find_freecad_cmd, convert_step_to_mesh

class ModelToGCodePipeline:
    """End-to-End Pipeline converting 3D Models (STEP, STL, OBJ) into G-Code."""

    def __init__(self,
                 tool: Optional[ToolProfile] = None,
                 stock: Optional[StockConfig] = None,
                 settings: Optional[CAMSettings] = None,
                 backend: str = "auto"):
        self.tool = tool or ToolProfile()
        self.stock = stock or StockConfig()
        self.settings = settings or CAMSettings()
        self.backend = backend.lower()  # "auto", "native", "freecad"
        self.simulator = GCodeSimulator()

    def process(self, input_model_path: str, output_gcode_path: Optional[str] = None) -> Dict[str, Any]:
        """Runs the complete inspection, toolpath generation, postprocessing, and simulation."""
        if not os.path.exists(input_model_path):
            raise FileNotFoundError(f"File not found: {input_model_path}")

        # 1. Analyze model geometry
        model_info = inspect_model(
            input_model_path,
            padding_x=self.stock.padding_x,
            padding_y=self.stock.padding_y,
            padding_z_top=self.stock.padding_z_top,
            padding_z_bottom=self.stock.padding_z_bottom
        )

        ext = os.path.splitext(input_model_path)[1].lower()

        # 2. Prepare mesh for CAM processing
        temp_stl_created = None
        if ext in [".step", ".stp", ".iges", ".igs", ".brep"]:
            # Need a tessellated representation for slicing
            fc_bin = find_freecad_cmd()
            if fc_bin:
                cache_dir = os.path.join(os.path.dirname(os.path.abspath(input_model_path)), ".cam_cache")
                os.makedirs(cache_dir, exist_ok=True)
                target_stl = os.path.join(cache_dir, f"{os.path.splitext(os.path.basename(input_model_path))[0]}.stl")
                if not os.path.exists(target_stl) or os.path.getmtime(target_stl) < os.path.getmtime(input_model_path):
                    target_stl = convert_step_to_mesh(input_model_path, target_stl)
                mesh = trimesh.load(target_stl, force="mesh")
            else:
                # Load via cadquery
                import cadquery as cq
                shape = cq.importers.importStep(input_model_path)
                cache_dir = os.path.join(os.path.dirname(os.path.abspath(input_model_path)), ".cam_cache")
                os.makedirs(cache_dir, exist_ok=True)
                target_stl = os.path.join(cache_dir, "temp_shape.stl")
                cq.exporters.export(shape, target_stl)
                mesh = trimesh.load(target_stl, force="mesh")
        else:
            mesh = trimesh.load(input_model_path, force="mesh")
            if not isinstance(mesh, trimesh.Trimesh):
                mesh = mesh.dump().sum()

        # 3. Generate G-code using Native CAM Engine
        cam_engine = NativeCAMEngine(
            tool=self.tool,
            stock=self.stock,
            settings=self.settings
        )
        gcode_text, cam_stats = cam_engine.generate(model_info, mesh)

        # 4. Determine output file path
        if not output_gcode_path:
            post_info = MACHINE_PRESETS.get(self.settings.postprocessor, {})
            out_ext = post_info.get("extension", ".nc")
            base = os.path.splitext(input_model_path)[0]
            output_gcode_path = f"{base}_{self.settings.postprocessor}{out_ext}"

        # 5. Write G-code to disk
        os.makedirs(os.path.dirname(os.path.abspath(output_gcode_path)), exist_ok=True)
        with open(output_gcode_path, "w", encoding="utf-8") as f:
            f.write(gcode_text)

        # 6. Simulate G-code to calculate exact bounds & cycle times
        sim_results = self.simulator.simulate(gcode_text)

        return {
            "status": "success",
            "model_info": model_info,
            "output_file": os.path.abspath(output_gcode_path),
            "output_file_name": os.path.basename(output_gcode_path),
            "file_size_bytes": os.path.getsize(output_gcode_path),
            "cam_stats": cam_stats,
            "simulation": sim_results,
            "gcode_preview": "\n".join(gcode_text.splitlines()[:50]),
            "gcode_content": gcode_text
        }
