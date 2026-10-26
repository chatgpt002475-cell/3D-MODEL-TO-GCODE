"""3D-MODEL-TO-GCODE Automated CAM Engine."""

from .analyzer import inspect_model
from .config import ToolProfile, StockConfig, CAMSettings, MACHINE_PRESETS, TOOL_PRESETS
from .native_cam import NativeCAMEngine
from .pipeline import ModelToGCodePipeline
from .simulator import GCodeSimulator
from .freecad_bridge import find_freecad_cmd, convert_step_to_mesh
from .eureka_bridge import (
    is_eureka_installed,
    get_eureka_info,
    create_eureka_project,
    simulate_eureka_project,
    launch_eureka_gui
)

__version__ = "1.0.0"

__all__ = [
    "inspect_model",
    "ToolProfile",
    "StockConfig",
    "CAMSettings",
    "MACHINE_PRESETS",
    "TOOL_PRESETS",
    "NativeCAMEngine",
    "ModelToGCodePipeline",
    "GCodeSimulator",
    "find_freecad_cmd",
    "convert_step_to_mesh",
    "is_eureka_installed",
    "get_eureka_info",
    "create_eureka_project",
    "simulate_eureka_project",
    "launch_eureka_gui"
]
