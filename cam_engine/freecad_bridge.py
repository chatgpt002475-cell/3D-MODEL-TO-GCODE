"""FreeCAD 1.1 Headless Automation Bridge for CAD/CAM operations."""

import os
import subprocess
import tempfile
import json
from typing import Optional, Dict, Any, Tuple

DEFAULT_FREECAD_PATHS = [
    r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe",
    r"C:\Program Files\FreeCAD\bin\freecadcmd.exe",
    r"C:\Program Files (x86)\FreeCAD 1.1\bin\freecadcmd.exe",
    r"C:\Program Files (x86)\FreeCAD\bin\freecadcmd.exe"
]

def find_freecad_cmd() -> Optional[str]:
    """Finds the path to the freecadcmd binary."""
    # Check default installation paths
    for p in DEFAULT_FREECAD_PATHS:
        if os.path.exists(p):
            return p
    # Check PATH
    import shutil
    which_fc = shutil.which("freecadcmd") or shutil.which("freecadcmd.exe")
    if which_fc:
        return which_fc
    return None

def run_freecad_script(script_content: str, timeout_sec: int = 120) -> str:
    """Executes a Python script headlessly inside the FreeCAD environment."""
    fc_bin = find_freecad_cmd()
    if not fc_bin:
        raise RuntimeError("FreeCAD binary (freecadcmd.exe) not found on system.")

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script_content)
        temp_script = f.name

    try:
        cmd = [fc_bin, temp_script]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if proc.returncode != 0:
            err = proc.stderr or proc.stdout
            raise RuntimeError(f"FreeCAD execution failed (code {proc.returncode}):\n{err}")
        return proc.stdout
    finally:
        if os.path.exists(temp_script):
            try:
                os.remove(temp_script)
            except OSError:
                pass

def convert_step_to_mesh(step_file: str, output_stl: Optional[str] = None, linear_deflection: float = 0.1) -> str:
    """Converts a STEP/STP file to high-resolution STL mesh using FreeCAD."""
    if not output_stl:
        output_stl = os.path.splitext(step_file)[0] + "_mesh.stl"

    abs_step = os.path.abspath(step_file).replace("\\", "/")
    abs_stl = os.path.abspath(output_stl).replace("\\", "/")

    script = f"""
import Part, Mesh, MeshPart
shape = Part.read('{abs_step}')
mesh = MeshPart.meshFromShape(
    Shape=shape,
    LinearDeflection={linear_deflection},
    AngularDeflection=0.523599,
    Relative=False
)
mesh.write('{abs_stl}')
print("CONVERT_SUCCESS:" + '{abs_stl}')
"""
    output = run_freecad_script(script)
    if "CONVERT_SUCCESS:" not in output or not os.path.exists(output_stl):
        raise RuntimeError(f"STEP to STL conversion failed: {output}")
    return output_stl

def generate_freecad_cam_gcode(model_file: str, output_gcode: str, postprocessor: str = "grbl",
                               tool_diameter: float = 6.0, feed_rate: float = 1200.0,
                               spindle_speed: int = 12000) -> str:
    """Uses FreeCAD's native CAM module to create a Job, profile, and postprocess G-code."""
    abs_model = os.path.abspath(model_file).replace("\\", "/")
    abs_out = os.path.abspath(output_gcode).replace("\\", "/")

    script = f"""
import FreeCAD, Part
import CAM.Path.Main.Job as Job
import CAM.Path.Post.Processor as PostProcessor
import os

doc = FreeCAD.newDocument('AutomatedCAM')
ext = os.path.splitext('{abs_model}')[1].lower()

if ext in ['.step', '.stp', '.iges', '.igs', '.brep']:
    shape = Part.read('{abs_model}')
    feature = doc.addObject('Part::Feature', 'ModelPart')
    feature.Shape = shape
else:
    import Mesh
    mesh = Mesh.Mesh('{abs_model}')
    feature = doc.addObject('Mesh::Feature', 'ModelPart')
    feature.Mesh = mesh

doc.recompute()

# Create CAM Job
job = Job.Create('Job', [feature])
job.PostProcessor = '{postprocessor}'
job.PostProcessorOutputFile = '{abs_out}'

doc.recompute()

# Postprocess job to file
post = PostProcessor.PostProcessorFactory(job, '{postprocessor}')
gcode = post.export()
with open('{abs_out}', 'w') as f:
    f.write(gcode)

print("FREECAD_CAM_SUCCESS:" + '{abs_out}')
"""
    output = run_freecad_script(script)
    if "FREECAD_CAM_SUCCESS:" not in output or not os.path.exists(output_gcode):
        raise RuntimeError(f"FreeCAD CAM generation failed: {output}")
    return output_gcode
