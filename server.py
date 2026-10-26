"""
3D-MODEL-TO-GCODE Local Hosting Server.
Provides interactive web dashboard, 3D CAD viewer, 3D G-code visualizer, and REST APIs.
"""

import os
import sys
import uuid
import json
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from cam_engine import (
    ModelToGCodePipeline,
    inspect_model,
    GCodeSimulator,
    ToolProfile,
    StockConfig,
    CAMSettings,
    MACHINE_PRESETS,
    TOOL_PRESETS,
    is_eureka_installed,
    get_eureka_info,
    create_eureka_project,
    simulate_eureka_project,
    launch_eureka_gui
)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "web", "templates"),
    static_folder=os.path.join(BASE_DIR, "web", "static")
)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route("/")
def index():
    """Serves the interactive web interface."""
    return render_template(
        "index.html",
        machine_presets=MACHINE_PRESETS,
        tool_presets=TOOL_PRESETS
    )


@app.route("/api/presets", methods=["GET"])
def get_presets():
    """Returns available machine controllers and tool presets."""
    return jsonify({
        "status": "success",
        "machines": MACHINE_PRESETS,
        "tools": TOOL_PRESETS
    })


@app.route("/api/inspect", methods=["POST"])
def api_inspect():
    """Analyzes an uploaded 3D model without generating G-code."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    job_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1].lower()
    temp_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    file.save(temp_path)

    try:
        pad_x = float(request.form.get("padding_x", 5.0))
        pad_y = float(request.form.get("padding_y", 5.0))
        pad_z_top = float(request.form.get("padding_z_top", 1.0))
        pad_z_bot = float(request.form.get("padding_z_bot", 2.0))

        info = inspect_model(
            temp_path,
            padding_x=pad_x,
            padding_y=pad_y,
            padding_z_top=pad_z_top,
            padding_z_bottom=pad_z_bot
        )
        return jsonify({"status": "success", "model_info": info})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/convert", methods=["POST"])
def api_convert():
    """Converts an uploaded 3D model into optimized CNC G-Code."""
    if "file" not in request.files:
        return jsonify({"error": "No 3D model file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    job_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1].lower()
    model_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    file.save(model_path)

    try:
        # Extract parameters
        post = request.form.get("postprocessor", "grbl").lower()
        tool_preset = request.form.get("tool_preset", "6mm_endmill")
        tool_dia = float(request.form.get("tool_diameter", 6.0))
        stepdown = float(request.form.get("stepdown", 1.5))
        stepover = float(request.form.get("stepover", 2.4))
        feed_rate = float(request.form.get("feed_rate", 1200.0))
        plunge_rate = float(request.form.get("plunge_rate", 400.0))
        spindle_speed = int(request.form.get("spindle_speed", 12000))
        stock_pad = float(request.form.get("stock_padding", 5.0))
        ops_str = request.form.get("operations", "facing,contour,surface")
        operations = [op.strip().lower() for op in ops_str.split(",") if op.strip()]

        tool = ToolProfile(
            name=f"Tool_{tool_dia}mm",
            diameter=tool_dia,
            stepdown=stepdown,
            stepover=stepover,
            feed_rate=feed_rate,
            plunge_rate=plunge_rate,
            spindle_speed=spindle_speed
        )
        stock = StockConfig(padding_x=stock_pad, padding_y=stock_pad, padding_z_top=1.0, padding_z_bottom=2.0)
        settings = CAMSettings(postprocessor=post, operations=operations)

        out_ext = MACHINE_PRESETS.get(post, {}).get("extension", ".nc")
        base_name = os.path.splitext(file.filename)[0]
        out_filename = f"{base_name}_{post}_{job_id}{out_ext}"
        out_path = os.path.join(OUTPUT_DIR, out_filename)

        pipeline = ModelToGCodePipeline(tool=tool, stock=stock, settings=settings)
        result = pipeline.process(model_path, out_path)

        return jsonify({
            "status": "success",
            "job_id": job_id,
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "model_info": result["model_info"],
            "simulation": result["simulation"],
            "gcode_preview": result["gcode_preview"],
            "gcode_content": result["gcode_content"]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/download/<filename>")
def download_file(filename):
    """Download generated G-code program."""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """Simulates G-code provided in the request body."""
    data = request.get_json(force=True)
    gcode = data.get("gcode", "")
    if not gcode:
        return jsonify({"error": "No G-code provided"}), 400

    sim = GCodeSimulator()
    res = sim.simulate(gcode)
    return jsonify({"status": "success", "simulation": res})


@app.route("/api/eureka/status", methods=["GET"])
def api_eureka_status():
    """Returns Eureka 3X installation and COM automation status."""
    return jsonify(get_eureka_info())


@app.route("/api/eureka/create-project", methods=["POST"])
def api_eureka_create():
    """Generates an official Eureka 3X (.epf) project file for a G-code job."""
    data = request.get_json(force=True)
    gcode_filename = data.get("filename")
    if not gcode_filename:
        return jsonify({"error": "G-code filename required"}), 400

    gcode_path = os.path.join(OUTPUT_DIR, gcode_filename)
    if not os.path.exists(gcode_path):
        return jsonify({"error": f"File not found: {gcode_filename}"}), 404

    try:
        stock_dims = data.get("stock_dims")
        if stock_dims and len(stock_dims) == 3:
            dims = (float(stock_dims[0]), float(stock_dims[1]), float(stock_dims[2]))
        else:
            dims = (100.0, 100.0, 30.0)

        epf_filename = f"{os.path.splitext(gcode_filename)[0]}_eureka.epf"
        out_epf = os.path.join(OUTPUT_DIR, epf_filename)

        model_file = data.get("model_file")
        if model_file and not os.path.isabs(model_file):
            model_file = os.path.join(UPLOAD_DIR, model_file)

        epf_path = create_eureka_project(
            gcode_path=gcode_path,
            stock_dims=dims,
            finished_model=model_file,
            output_epf=out_epf
        )

        return jsonify({
            "status": "success",
            "epf_filename": epf_filename,
            "epf_path": epf_path,
            "download_url": f"/api/download/{epf_filename}"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/eureka/simulate", methods=["POST"])
def api_eureka_simulate():
    """Runs automated virtual machining simulation and collision detection in Eureka 3X."""
    data = request.get_json(force=True)
    epf_filename = data.get("epf_filename")
    if not epf_filename:
        return jsonify({"error": "epf_filename required"}), 400

    epf_path = os.path.join(OUTPUT_DIR, epf_filename)
    if not os.path.exists(epf_path):
        return jsonify({"error": f"Project file not found: {epf_filename}"}), 404

    try:
        res = simulate_eureka_project(epf_path)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/eureka/launch", methods=["POST"])
def api_eureka_launch():
    """Launches the Eureka 3X GUI with the specified project loaded."""
    data = request.get_json(force=True)
    epf_filename = data.get("epf_filename")
    epf_path = os.path.join(OUTPUT_DIR, epf_filename) if epf_filename else None

    try:
        launch_eureka_gui(epf_path)
        return jsonify({"status": "success", "message": "Eureka 3X application launched"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

