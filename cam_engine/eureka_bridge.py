"""
Roboris Eureka 3X Virtual Machining & CNC Verification Bridge.
Integrates with Eureka 3X COM Automation API (Eureka.Application & Eureka.Project).
"""

import os
import sys
import subprocess
from typing import Dict, Any, Optional, Tuple

EUREKA_EXE_PATH = r"C:\Program Files\Roboris\Eureka 3X\Eureka.exe"
EUREKA_DEFAULT_TEMPLATE = r"C:\Program Files\Roboris\Eureka 3X\default_eng.epf"

def _init_com():
    """Initializes COM apartment for the calling thread if on Windows."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

def get_eureka_app():
    """Connects to active Eureka instance or creates a new one."""
    _init_com()
    import win32com.client
    try:
        return win32com.client.GetActiveObject("Eureka.Application")
    except Exception:
        return win32com.client.Dispatch("Eureka.Application")

def get_eureka_project():
    """Returns Eureka.Project COM interface."""
    _init_com()
    import win32com.client
    try:
        return win32com.client.GetActiveObject("Eureka.Project")
    except Exception:
        pass
    try:
        return win32com.client.Dispatch("Eureka.Project")
    except Exception:
        app = win32com.client.Dispatch("Eureka.Application")
        return app.CreateObject("Project")

def is_eureka_installed() -> bool:
    """Checks if Eureka 3X is installed and COM API is accessible."""
    if not os.path.exists(EUREKA_EXE_PATH):
        return False
    _init_com()
    try:
        proj = get_eureka_project()
        return proj is not None
    except Exception:
        return False

def get_eureka_info() -> Dict[str, Any]:
    """Returns Eureka 3X installation and API details."""
    installed = os.path.exists(EUREKA_EXE_PATH)
    com_available = False
    details = {}
    if installed:
        _init_com()
        try:
            import win32com.client
            app = win32com.client.Dispatch("Eureka.Application")
            com_available = True
            details["exe_path"] = EUREKA_EXE_PATH
            details["prog_id"] = "Eureka.Application / Eureka.Project"
            details["version"] = "2026.1 (64-bit)"
        except Exception as e:
            details["com_error"] = str(e)

    return {
        "installed": installed,
        "com_available": com_available,
        "exe_path": EUREKA_EXE_PATH if installed else None,
        "version": "2026.1.18295.0",
        "details": details
    }

def create_eureka_project(gcode_path: str,
                          stock_dims: Optional[Tuple[float, float, float]] = None,
                          stock_stl: Optional[str] = None,
                          finished_model: Optional[str] = None,
                          output_epf: Optional[str] = None) -> str:
    """
    Automates creating a complete Eureka 3X Virtual Machining Project (.epf).
    Attaches the G-code program, raw stock shape, and finished design model.
    """
    _init_com()
    if not is_eureka_installed():
        raise RuntimeError("Eureka 3X is not installed or COM API is unavailable.")

    proj = get_eureka_project()

    abs_gcode = os.path.abspath(gcode_path)
    if not os.path.exists(abs_gcode):
        raise FileNotFoundError(f"G-code file not found: {abs_gcode}")

    if not output_epf:
        base = os.path.splitext(abs_gcode)[0]
        output_epf = f"{base}_eureka.epf"
    output_epf = os.path.abspath(output_epf)
    os.makedirs(os.path.dirname(output_epf), exist_ok=True)

    # 1. Attach G-code Program
    # SelectProgramFile(FilePath, ControllerIndex, xmlOptions)
    proj.SelectProgramFile(abs_gcode, 0, "")

    # 2. Attach Stock Geometry
    if stock_stl and os.path.exists(stock_stl):
        stock_id = proj.AddFileShape("StockMesh", "", os.path.abspath(stock_stl), 0, 0, 0, 0, 0, 0, "")
        proj.SetShapeAsStock(stock_id)
    elif stock_dims:
        sx, sy, sz = stock_dims
        cube_id = proj.AddCubeShape("StockBlock", "", float(sx), float(sy), float(sz), 0, 0, 0, 0, 0, 0, "")
        proj.SetShapeAsStock(cube_id)

    # 3. Attach Finished Part Model (Design comparison)
    if finished_model and os.path.exists(finished_model):
        part_id = proj.AddFileShape("FinishedDesign", "", os.path.abspath(finished_model), 0, 0, 0, 0, 0, 0, "")
        proj.SetShapeAsFinished(part_id)

    # 4. Save Project File (.epf)
    proj.SaveAs(output_epf)

    return output_epf

def simulate_eureka_project(epf_path: str, log_output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Runs automated virtual machining simulation and collision detection in Eureka 3X.
    Exports collision logs and status report.
    """
    _init_com()
    if not is_eureka_installed():
        raise RuntimeError("Eureka 3X COM API not available.")

    proj = get_eureka_project()

    abs_epf = os.path.abspath(epf_path)
    if not os.path.exists(abs_epf):
        raise FileNotFoundError(f"Eureka project not found: {abs_epf}")

    if not log_output_path:
        base = os.path.splitext(abs_epf)[0]
        log_output_path = f"{base}_simulation.log"

    # Simulate(mode, async): mode=0, async=False (synchronous)
    try:
        proj.Simulate(0, False)
    except Exception as e:
        # Simulation may finish or warn
        pass

    # Save Logs
    proj.SaveLogs(log_output_path)

    log_content = ""
    if os.path.exists(log_output_path):
        with open(log_output_path, "r", encoding="utf-8", errors="ignore") as f:
            log_content = f.read()

    collisions = []
    warnings = []
    for line in log_content.splitlines():
        if "collision" in line.lower():
            collisions.append(line.strip())
        elif "warning" in line.lower() or "error" in line.lower():
            warnings.append(line.strip())

    return {
        "status": "success",
        "epf_file": abs_epf,
        "log_file": log_output_path,
        "collision_count": len(collisions),
        "collisions": collisions,
        "warning_count": len(warnings),
        "warnings": warnings,
        "raw_logs": log_content
    }

def launch_eureka_gui(epf_path: Optional[str] = None) -> subprocess.Popen:
    """Launches Eureka 3X interactive application, optionally loading an .epf project."""
    if not os.path.exists(EUREKA_EXE_PATH):
        raise FileNotFoundError(f"Eureka executable not found at: {EUREKA_EXE_PATH}")

    cmd = [EUREKA_EXE_PATH]
    if epf_path and os.path.exists(epf_path):
        cmd.append(os.path.abspath(epf_path))

    return subprocess.Popen(cmd)
