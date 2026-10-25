"""
FreeCAD Headless Executor: Runs CAD generation scripts, verifies output, and collects metadata.
"""

import os
import subprocess
import tempfile
import json
from typing import Dict, Any, Optional

FREECAD_BIN_PATHS = [
    r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe",
    r"C:\Program Files\FreeCAD\bin\freecadcmd.exe",
    r"C:\Program Files (x86)\FreeCAD 1.1\bin\freecadcmd.exe",
    r"C:\Program Files (x86)\FreeCAD\bin\freecadcmd.exe"
]

def find_freecad_cmd() -> str:
    """Finds path to freecadcmd.exe on the system."""
    for p in FREECAD_BIN_PATHS:
        if os.path.exists(p):
            return p
    import shutil
    which_fc = shutil.which("freecadcmd") or shutil.which("freecadcmd.exe")
    if which_fc:
        return which_fc
    raise RuntimeError("FreeCAD 1.1 command line executable (freecadcmd.exe) not found.")


def execute_freecad_cad_build(script_content: str, timeout_sec: int = 120) -> Dict[str, Any]:
    """Runs a FreeCAD CAD construction script and parses metadata."""
    fc_bin = find_freecad_cmd()

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script_content)
        temp_script = f.name

    try:
        cmd = [fc_bin, temp_script]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        out = proc.stdout
        err = proc.stderr

        if "CAD_BUILD_SUCCESS" not in out:
            raise RuntimeError(f"FreeCAD modeling failed.\nSTDOUT:\n{out}\nSTDERR:\n{err}")

        # Parse JSON Metadata
        metadata = {}
        if "---FREECAD_META_START---" in out and "---FREECAD_META_END---" in out:
            json_str = out.split("---FREECAD_META_START---")[1].split("---FREECAD_META_END---")[0].strip()
            metadata = json.loads(json_str)

        return {
            "status": "success",
            "metadata": metadata,
            "stdout": out,
            "script_executed": script_content
        }
    finally:
        if os.path.exists(temp_script):
            try:
                os.remove(temp_script)
            except OSError:
                pass
