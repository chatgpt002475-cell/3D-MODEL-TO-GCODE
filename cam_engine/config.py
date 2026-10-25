"""Configuration and presets for 3D-MODEL-TO-GCODE CAM Engine."""

from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class ToolProfile:
    name: str = "6mm_Flat_Endmill"
    tool_type: str = "endmill"  # endmill, ballnose, bullnose, face_mill
    diameter: float = 6.0       # mm
    length: float = 50.0        # mm
    flutes: int = 2
    stepdown: float = 1.5       # mm per pass
    stepover: float = 2.4       # mm (40% of tool diameter)
    feed_rate: float = 1200.0   # mm/min
    plunge_rate: float = 400.0  # mm/min
    spindle_speed: int = 12000  # RPM

@dataclass
class StockConfig:
    padding_x: float = 5.0      # mm extra stock on X sides
    padding_y: float = 5.0      # mm extra stock on Y sides
    padding_z_top: float = 1.0  # mm facing allowance on top
    padding_z_bottom: float = 2.0 # mm holding stock at bottom

@dataclass
class CAMSettings:
    safe_z: float = 5.0         # mm clearance plane above stock
    rapid_z: float = 2.0        # mm rapid traverse plane
    operations: List[str] = field(default_factory=lambda: ["facing", "contour", "pocket", "surface"])
    postprocessor: str = "grbl" # grbl, linuxcnc, fanuc, haas, marlin, mach3, generic
    units: str = "mm"           # mm or inch
    coordinate_system: str = "G54"
    cooling: str = "flood"      # flood, mist, off
    climb_milling: bool = True  # True=Climb, False=Conventional

MACHINE_PRESETS: Dict[str, Dict[str, Any]] = {
    "grbl": {
        "name": "GRBL CNC / Router",
        "extension": ".nc",
        "description": "Standard GRBL / CNC Shield / Shapeoko / X-Carve",
        "supports_toolchange": False,
        "max_feed": 5000.0,
        "spindle_max": 24000
    },
    "linuxcnc": {
        "name": "LinuxCNC / EMC2",
        "extension": ".ngc",
        "description": "Industrial PC-based LinuxCNC controller",
        "supports_toolchange": True,
        "max_feed": 10000.0,
        "spindle_max": 30000
    },
    "fanuc": {
        "name": "Fanuc 0i / 31i",
        "extension": ".nc",
        "description": "Standard Fanuc industrial CNC milling center",
        "supports_toolchange": True,
        "max_feed": 15000.0,
        "spindle_max": 20000
    },
    "haas": {
        "name": "Haas VF / Mini Mill",
        "extension": ".nc",
        "description": "Haas Automation VMC series",
        "supports_toolchange": True,
        "max_feed": 15000.0,
        "spindle_max": 15000
    },
    "mach3": {
        "name": "Mach3 / Mach4",
        "extension": ".tap",
        "description": "Mach3/4 mill controller with G54 work offset",
        "supports_toolchange": True,
        "max_feed": 6000.0,
        "spindle_max": 24000
    },
    "marlin": {
        "name": "Marlin CNC / MP3DP",
        "extension": ".gcode",
        "description": "Marlin 2.x based CNC / 3D printer conversions",
        "supports_toolchange": False,
        "max_feed": 4000.0,
        "spindle_max": 10000
    },
    "generic": {
        "name": "Generic ISO G-Code",
        "extension": ".gcode",
        "description": "ISO 6983 standard RS-274D compatible G-code",
        "supports_toolchange": True,
        "max_feed": 8000.0,
        "spindle_max": 24000
    }
}

TOOL_PRESETS: Dict[str, Dict[str, Any]] = {
    "3mm_endmill": {
        "name": "3mm 2-Flute Flat Endmill",
        "tool_type": "endmill",
        "diameter": 3.175,
        "flutes": 2,
        "stepdown": 0.8,
        "stepover": 1.2,
        "feed_rate": 800.0,
        "plunge_rate": 300.0,
        "spindle_speed": 16000
    },
    "6mm_endmill": {
        "name": "6mm 4-Flute Flat Endmill",
        "tool_type": "endmill",
        "diameter": 6.0,
        "flutes": 4,
        "stepdown": 1.5,
        "stepover": 2.4,
        "feed_rate": 1400.0,
        "plunge_rate": 450.0,
        "spindle_speed": 12000
    },
    "10mm_rougher": {
        "name": "10mm Roughing Endmill",
        "tool_type": "endmill",
        "diameter": 10.0,
        "flutes": 3,
        "stepdown": 2.5,
        "stepover": 4.5,
        "feed_rate": 2000.0,
        "plunge_rate": 600.0,
        "spindle_speed": 9000
    },
    "6mm_ballnose": {
        "name": "6mm Ballnose Finishing Mill",
        "tool_type": "ballnose",
        "diameter": 6.0,
        "flutes": 2,
        "stepdown": 0.5,
        "stepover": 0.8,
        "feed_rate": 1600.0,
        "plunge_rate": 500.0,
        "spindle_speed": 14000
    },
    "25mm_facemill": {
        "name": "25mm Indexable Face Mill",
        "tool_type": "face_mill",
        "diameter": 25.0,
        "flutes": 3,
        "stepdown": 0.5,
        "stepover": 15.0,
        "feed_rate": 1800.0,
        "plunge_rate": 300.0,
        "spindle_speed": 6000
    }
}
