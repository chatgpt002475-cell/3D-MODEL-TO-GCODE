#!/usr/bin/env python3
"""
FreeCAD CLI: Command-Line Interface for automated FreeCAD sketching and 3D modeling.
Translates command prompts into parametric 2D sketches, 3D solids, and local hosting visualizer.
"""

import sys
import os
import json
import click
import uuid

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from freecad_engine import (
    parse_prompt_to_params,
    generate_freecad_script,
    execute_freecad_cad_build,
    find_freecad_cmd
)

DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "cad_output"))
os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)


@click.group()
@click.version_option(version="1.1.0", prog_name="FreeCAD Automated Modeling CLI")
def main():
    """Build FreeCAD parametric 2D sketches and 3D models from command prompts."""
    pass


@main.command(name="prompt")
@click.argument("prompt_text")
@click.option("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for generated files")
@click.option("-n", "--name", default=None, help="Custom project model name")
@click.option("--json-out", is_flag=True, help="Output generation results in JSON format")
@click.option("--print-script", is_flag=True, help="Print generated FreeCAD Python script to console")
def cmd_prompt(prompt_text, output_dir, name, json_out, print_script):
    """Build a 2D sketch & 3D solid in FreeCAD directly from a command prompt."""
    try:
        if not json_out:
            click.secho(f"\n=======================================================", fg="cyan", bold=True)
            click.secho(f" FREECAD AUTOMATED SKETCHING & 3D MODELING", fg="cyan", bold=True)
            click.secho(f"=======================================================", fg="cyan", bold=True)
            click.echo(f"Input Prompt:   \"{prompt_text}\"")

        # 1. Parse prompt
        params = parse_prompt_to_params(prompt_text)
        model_name = name or params.get("name", "FreeCAD_Part")
        safe_name = "".join(c if c.isalnum() or c == '_' else '_' for c in model_name)
        file_id = str(uuid.uuid4())[:6]
        base_path = os.path.join(output_dir, f"{safe_name}_{file_id}")

        out_fcstd = f"{base_path}.FCStd"
        out_step = f"{base_path}.step"
        out_stl = f"{base_path}.stl"

        # 2. Generate Python Script
        script = generate_freecad_script(params, out_fcstd, out_step, out_stl)

        if print_script:
            click.secho(f"\n[Generated FreeCAD Python Script]:", fg="yellow")
            click.echo(script)

        if not json_out:
            click.echo(f"Target Part:    {params['category'].upper()} model")
            click.echo(f"Executing FreeCAD 1.1 headless engine...")

        # 3. Execute in FreeCAD
        res = execute_freecad_cad_build(script)
        meta = res.get("metadata", {})

        if json_out:
            meta["files"] = {
                "fcstd": out_fcstd,
                "step": out_step,
                "stl": out_stl
            }
            meta["params"] = params
            click.echo(json.dumps(meta, indent=2))
            return

        click.secho(f"\n[FreeCAD 3D Modeling Completed Successfully!]", fg="green", bold=True)
        dims = meta.get("dimensions", [0, 0, 0])
        click.echo(f"Bounding Size:  X: {dims[0]} mm | Y: {dims[1]} mm | Z: {dims[2]} mm")
        click.echo(f"Solid Volume:   {meta.get('volume', 0):.2f} mm³")
        click.echo(f"Surface Area:   {meta.get('area', 0):.2f} mm²")
        click.echo(f"Solid Topology: {meta.get('faces_count', 0)} Faces, {meta.get('edges_count', 0)} Edges")
        click.echo(f"Sketch Profile: {len(meta.get('sketch_entities', []))} 2D geometry elements")

        click.secho(f"\n[Generated Output Files]:", fg="cyan", bold=True)
        click.echo(f" • FreeCAD Native : {out_fcstd}")
        click.echo(f" • Industrial STEP: {out_step}")
        click.echo(f" • 3D Mesh (STL)  : {out_stl}\n")

    except Exception as e:
        click.secho(f"Error building FreeCAD model: {e}", fg="red", err=True)
        sys.exit(1)


@main.command(name="sketch-extrude")
@click.option("--shape", type=click.Choice(["rect", "circle"]), required=True, help="Base 2D sketch profile")
@click.option("--width", type=float, default=100.0, help="Rectangle width (mm)")
@click.option("--length", type=float, default=60.0, help="Rectangle length (mm)")
@click.option("--diameter", type=float, default=80.0, help="Circle diameter (mm)")
@click.option("--extrude", type=float, required=True, help="Extrusion height / pad length (mm)")
@click.option("--hole", type=float, default=0.0, help="Center hole diameter (mm)")
@click.option("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, help="Destination folder")
def cmd_sketch_extrude(shape, width, length, diameter, extrude, hole, output_dir):
    """Direct parametric sketch and 3D pad extrusion in FreeCAD."""
    if shape == "rect":
        prompt = f"mounting plate width {width} length {length} thickness {extrude}"
        if hole > 0:
            prompt += f" with center hole {hole}"
    else:
        prompt = f"cylinder with diameter {diameter} length {extrude}"
        if hole > 0:
            prompt += f" and inner bore {hole}"

    # Delegate to prompt parser
    ctx = click.get_current_context()
    ctx.invoke(cmd_prompt, prompt_text=prompt, output_dir=output_dir, name=None, json_out=False, print_script=False)


@main.command(name="run-script")
@click.argument("script_file", type=click.Path(exists=True, readable=True))
def cmd_run_script(script_file):
    """Execute any custom FreeCAD Python script headlessly."""
    try:
        with open(script_file, "r", encoding="utf-8") as f:
            code = f.read()
        click.secho(f"Executing FreeCAD script: {script_file}...", fg="cyan")
        res = execute_freecad_cad_build(code)
        click.secho(f"Execution succeeded!\n", fg="green")
        click.echo(res.get("stdout", ""))
    except Exception as e:
        click.secho(f"Script execution error: {e}", fg="red", err=True)
        sys.exit(1)


@main.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Host interface to bind to")
@click.option("--port", default=5050, type=int, help="Port to host the FreeCAD web app")
@click.option("--open-browser", is_flag=True, help="Automatically open browser")
def cmd_serve(host, port, open_browser):
    """Launch the FreeCAD Local Hosting Web Studio for interactive sketching and modeling."""
    from freecad_server import app
    click.secho(f"\n=======================================================", fg="green", bold=True)
    click.secho(f" FREECAD SKETCHING & MODELING LOCAL HOSTING SERVER", fg="green", bold=True)
    click.secho(f"=======================================================", fg="green", bold=True)
    click.echo(f"Web Studio URL: http://{host}:{port}/")
    click.echo(f"Features:       Command Prompt input, 2D Sketch Blueprint viewer,")
    click.echo(f"                Interactive 3D WebGL Model Viewer, and .FCStd/.STEP export")
    click.echo(f"Press CTRL+C to stop the server.\n")

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}/")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
