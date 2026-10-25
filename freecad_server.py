"""
Dedicated FreeCAD Local Hosting Web Server & CAD Modeling Studio.
Provides interactive 3D WebGL preview, 2D Sketch Blueprint viewer, and Prompt-to-CAD compiler.
"""

import os
import sys
import uuid
import json
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from freecad_engine import (
    parse_prompt_to_params,
    generate_freecad_script,
    execute_freecad_cad_build
)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "freecad_web", "templates"),
    static_folder=os.path.join(BASE_DIR, "freecad_web", "static")
)

CAD_OUTPUT_DIR = os.path.join(BASE_DIR, "cad_output")
os.makedirs(CAD_OUTPUT_DIR, exist_ok=True)


@app.route("/")
def index():
    """Serves the FreeCAD Studio web interface."""
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Generates FreeCAD 2D sketch and 3D solid from command prompt or parameters."""
    data = request.get_json(silent=True) or request.form.to_dict()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt cannot be empty"}), 400

    try:
        # 1. Parse prompt
        params = parse_prompt_to_params(prompt)
        file_id = str(uuid.uuid4())[:8]
        safe_name = "".join(c if c.isalnum() or c == '_' else '_' for c in params.get("name", "part"))
        base_name = f"{safe_name}_{file_id}"

        out_fcstd = os.path.join(CAD_OUTPUT_DIR, f"{base_name}.FCStd")
        out_step = os.path.join(CAD_OUTPUT_DIR, f"{base_name}.step")
        out_stl = os.path.join(CAD_OUTPUT_DIR, f"{base_name}.stl")

        # 2. Build FreeCAD script
        script = generate_freecad_script(params, out_fcstd, out_step, out_stl)

        # 3. Execute FreeCAD
        res = execute_freecad_cad_build(script)
        meta = res.get("metadata", {})

        return jsonify({
            "status": "success",
            "prompt": prompt,
            "params": params,
            "metadata": meta,
            "script_code": script,
            "files": {
                "stl": f"/api/download/{base_name}.stl",
                "step": f"/api/download/{base_name}.step",
                "fcstd": f"/api/download/{base_name}.FCStd"
            },
            "filenames": {
                "stl": f"{base_name}.stl",
                "step": f"{base_name}.step",
                "fcstd": f"{base_name}.FCStd"
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/run-code", methods=["POST"])
def api_run_code():
    """Executes custom FreeCAD Python code directly and generates 3D preview."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "No Python code provided"}), 400

    try:
        file_id = str(uuid.uuid4())[:8]
        out_fcstd = os.path.join(CAD_OUTPUT_DIR, f"custom_{file_id}.FCStd")
        out_step = os.path.join(CAD_OUTPUT_DIR, f"custom_{file_id}.step")
        out_stl = os.path.join(CAD_OUTPUT_DIR, f"custom_{file_id}.stl")

        # Inject export statements if not present
        if "Part.export" not in code:
            code += f"\nPart.export(doc.Objects, r'{out_step}')\n"
        if "mesh.write" not in code:
            code += f"""
import MeshPart
shape = doc.Objects[-1].Shape
mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.08, AngularDeflection=0.4, Relative=False)
mesh.write(r'{out_stl}')
doc.saveAs(r'{out_fcstd}')
print('CAD_BUILD_SUCCESS')
"""
        res = execute_freecad_cad_build(code)
        return jsonify({
            "status": "success",
            "files": {
                "stl": f"/api/download/custom_{file_id}.stl",
                "step": f"/api/download/custom_{file_id}.step",
                "fcstd": f"/api/download/custom_{file_id}.FCStd"
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/download/<filename>")
def download_cad_file(filename):
    """Downloads a generated CAD file (FCStd, STEP, STL)."""
    file_path = os.path.join(CAD_OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
