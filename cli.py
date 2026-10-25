#!/usr/bin/env python3
"""
3D-MODEL-TO-GCODE CLI: Automated CNC CAM conversion and control suite.
"""

import sys
import os
import json
import click

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from cam_engine import (
    ModelToGCodePipeline,
    inspect_model,
    GCodeSimulator,
    ToolProfile,
    StockConfig,
    CAMSettings,
    MACHINE_PRESETS,
    TOOL_PRESETS,
    find_freecad_cmd
)

@click.group()
@click.version_option(version="1.0.0", prog_name="3D-MODEL-TO-GCODE CLI")
def main():
    """Automate 3D Model (STEP, STL, OBJ) to CNC G-Code conversion and hosting."""
    pass


@main.command(name="inspect")
@click.argument("model_file", type=click.Path(exists=True, readable=True))
@click.option("--padding-x", default=5.0, help="Stock padding in X (mm)")
@click.option("--padding-y", default=5.0, help="Stock padding in Y (mm)")
@click.option("--padding-z-top", default=1.0, help="Top facing allowance (mm)")
@click.option("--padding-z-bot", default=2.0, help="Bottom holding allowance (mm)")
@click.option("--json-out", is_flag=True, help="Output results in JSON format")
def cmd_inspect(model_file, padding_x, padding_y, padding_z_top, padding_z_bot, json_out):
    """Analyze 3D model geometry, bounding box, volume, and stock requirements."""
    try:
        data = inspect_model(
            model_file,
            padding_x=padding_x,
            padding_y=padding_y,
            padding_z_top=padding_z_top,
            padding_z_bottom=padding_z_bot
        )
        if json_out:
            click.echo(json.dumps(data, indent=2))
            return

        click.secho(f"\n==================================================", fg="cyan", bold=True)
        click.secho(f" 3D MODEL GEOMETRIC INSPECTION REPORT", fg="cyan", bold=True)
        click.secho(f"==================================================", fg="cyan", bold=True)
        click.echo(f"File:           {data['file_name']} ({data['format']})")
        click.echo(f"Size:           {data['file_size_bytes'] / 1024:.1f} KB")
        dim = data["dimensions"]
        click.echo(f"Dimensions:     X: {dim['x']} mm | Y: {dim['y']} mm | Z: {dim['z']} mm")
        click.echo(f"Bounding Box:   Min: {data['bounds']['min']} mm")
        click.echo(f"                Max: {data['bounds']['max']} mm")
        click.echo(f"Volume:         {data.get('volume', 0):.2f} mm³")
        click.echo(f"Surface Area:   {data.get('surface_area', 0):.2f} mm²")

        stock = data["recommended_stock"]
        click.secho(f"\n[Recommended Stock Size]:", fg="yellow", bold=True)
        click.echo(f"Dimensions:     {stock['dimensions'][0]} x {stock['dimensions'][1]} x {stock['dimensions'][2]} mm")
        click.echo(f"Facing margin:  {stock['top_facing_allowance']} mm")
        click.echo(f"Base holding:   {stock['bottom_holding_allowance']} mm")

        click.secho(f"\n[Recommended Tooling]:", fg="green", bold=True)
        for t in data["recommended_tools"]:
            click.echo(f" - {t['role']:<24}: {t['tool']}")
        click.echo("")

    except Exception as e:
        click.secho(f"Error inspecting model: {e}", fg="red", err=True)
        sys.exit(1)


@main.command(name="convert")
@click.argument("model_file", type=click.Path(exists=True, readable=True))
@click.option("-o", "--output", default=None, help="Output G-code file path")
@click.option("-p", "--post", default="grbl", type=click.Choice(list(MACHINE_PRESETS.keys())),
              help="Machine controller post-processor")
@click.option("-t", "--tool-preset", default="6mm_endmill", help="Preconfigured tool preset")
@click.option("-d", "--tool-dia", default=None, type=float, help="Override tool diameter in mm")
@click.option("-s", "--stepdown", default=None, type=float, help="Override depth of cut per pass (mm)")
@click.option("--stepover", default=None, type=float, help="Override stepover distance (mm)")
@click.option("--feed", default=None, type=float, help="Override cutting feedrate (mm/min)")
@click.option("--plunge", default=None, type=float, help="Override plunge feedrate (mm/min)")
@click.option("--rpm", default=None, type=int, help="Override spindle speed (RPM)")
@click.option("--ops", default="facing,contour,surface", help="Comma-separated operations: facing,contour,surface")
@click.option("--pad", default=5.0, type=float, help="Stock padding on X/Y (mm)")
@click.option("--backend", default="auto", type=click.Choice(["auto", "native", "freecad"]), help="CAM engine backend")
@click.option("--json-out", is_flag=True, help="Print result summary as JSON")
def cmd_convert(model_file, output, post, tool_preset, tool_dia, stepdown, stepover, feed, plunge, rpm, ops, pad, backend, json_out):
    """Automatically convert a 3D model into production-ready CNC G-Code."""
    try:
        # Build Tool Profile
        preset_data = TOOL_PRESETS.get(tool_preset, TOOL_PRESETS["6mm_endmill"]).copy()
        if tool_dia:
            preset_data["diameter"] = tool_dia
        if stepdown:
            preset_data["stepdown"] = stepdown
        if stepover:
            preset_data["stepover"] = stepover
        if feed:
            preset_data["feed_rate"] = feed
        if plunge:
            preset_data["plunge_rate"] = plunge
        if rpm:
            preset_data["spindle_speed"] = rpm

        tool = ToolProfile(
            name=preset_data.get("name", "Custom_Tool"),
            tool_type=preset_data.get("tool_type", "endmill"),
            diameter=preset_data.get("diameter", 6.0),
            flutes=preset_data.get("flutes", 2),
            stepdown=preset_data.get("stepdown", 1.5),
            stepover=preset_data.get("stepover", 2.4),
            feed_rate=preset_data.get("feed_rate", 1200.0),
            plunge_rate=preset_data.get("plunge_rate", 400.0),
            spindle_speed=preset_data.get("spindle_speed", 12000)
        )

        stock = StockConfig(padding_x=pad, padding_y=pad, padding_z_top=1.0, padding_z_bottom=2.0)
        operations = [op.strip().lower() for op in ops.split(",") if op.strip()]
        settings = CAMSettings(postprocessor=post, operations=operations)

        if not json_out:
            click.secho(f"\n[Starting Automated 3D-to-GCode Conversion...]", fg="cyan", bold=True)
            click.echo(f"Model:          {model_file}")
            click.echo(f"Post-processor: {post.upper()} ({MACHINE_PRESETS[post]['description']})")
            click.echo(f"Tool:           {tool.name} (Ø {tool.diameter}mm, Stepdown: {tool.stepdown}mm)")
            click.echo(f"Operations:     {', '.join(operations)}")

        pipeline = ModelToGCodePipeline(tool=tool, stock=stock, settings=settings, backend=backend)
        result = pipeline.process(model_file, output)

        if json_out:
            # Drop raw content to avoid huge JSON terminal spam
            res_copy = result.copy()
            res_copy.pop("gcode_content", None)
            click.echo(json.dumps(res_copy, indent=2))
            return

        click.secho(f"\n[G-Code Generation Completed Successfully!]", fg="green", bold=True)
        click.echo(f"Output File:    {result['output_file']}")
        click.echo(f"G-Code Size:    {result['file_size_bytes'] / 1024:.1f} KB ({result['simulation']['total_lines']} lines)")
        click.echo(f"Cutting Length: {result['simulation']['feed_distance_mm']:.1f} mm")
        click.echo(f"Rapid Length:   {result['simulation']['rapid_distance_mm']:.1f} mm")
        click.echo(f"Estimated Time: {result['simulation']['estimated_time_formatted']}")
        click.echo(f"Machining Span: X={result['simulation']['bounds']['travel_span'][0]}mm, "
                   f"Y={result['simulation']['bounds']['travel_span'][1]}mm, "
                   f"Z={result['simulation']['bounds']['travel_span'][2]}mm\n")

    except Exception as e:
        click.secho(f"Error converting model: {e}", fg="red", err=True)
        sys.exit(1)


@main.command(name="simulate")
@click.argument("gcode_file", type=click.Path(exists=True, readable=True))
def cmd_simulate(gcode_file):
    """Simulate and verify existing CNC G-Code, calculating time and travel bounds."""
    try:
        with open(gcode_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        sim = GCodeSimulator()
        data = sim.simulate(content)

        click.secho(f"\n==================================================", fg="cyan", bold=True)
        click.secho(f" CNC G-CODE SIMULATION & VERIFICATION", fg="cyan", bold=True)
        click.secho(f"==================================================", fg="cyan", bold=True)
        click.echo(f"File:           {os.path.basename(gcode_file)}")
        click.echo(f"Total Lines:    {data['total_lines']}")
        click.echo(f"Cut Distance:   {data['feed_distance_mm']} mm")
        click.echo(f"Rapid Distance: {data['rapid_distance_mm']} mm")
        click.echo(f"Est. Machining: {data['estimated_time_formatted']}")
        click.echo(f"Coordinate Min: {data['bounds']['min']}")
        click.echo(f"Coordinate Max: {data['bounds']['max']}")
        click.echo(f"Work Envelope:  X: {data['bounds']['travel_span'][0]}mm | "
                   f"Y: {data['bounds']['travel_span'][1]}mm | Z: {data['bounds']['travel_span'][2]}mm\n")

    except Exception as e:
        click.secho(f"Error simulating G-code: {e}", fg="red", err=True)
        sys.exit(1)


@main.command(name="batch")
@click.argument("input_folder", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output-folder", default=None, help="Destination folder for G-code files")
@click.option("-p", "--post", default="grbl", help="Postprocessor dialect")
@click.option("-t", "--tool-preset", default="6mm_endmill", help="Tool preset")
def cmd_batch(input_folder, output_folder, post, tool_preset):
    """Batch convert all 3D CAD/mesh files in a folder into G-Code."""
    if not output_folder:
        output_folder = os.path.join(input_folder, "gcode_output")
    os.makedirs(output_folder, exist_ok=True)

    supported_exts = {".step", ".stp", ".stl", ".obj", ".iges", ".igs"}
    files = [os.path.join(input_folder, f) for f in os.listdir(input_folder)
             if os.path.splitext(f)[1].lower() in supported_exts]

    if not files:
        click.secho(f"No supported 3D models found in {input_folder}", fg="yellow")
        return

    click.secho(f"Found {len(files)} 3D models. Starting batch processing...\n", fg="cyan")
    successes = 0
    for f in files:
        try:
            base_name = os.path.splitext(os.path.basename(f))[0]
            ext = MACHINE_PRESETS.get(post, {}).get("extension", ".nc")
            out_file = os.path.join(output_folder, f"{base_name}_{post}{ext}")
            pipeline = ModelToGCodePipeline(
                tool=ToolProfile(name=tool_preset),
                settings=CAMSettings(postprocessor=post)
            )
            pipeline.process(f, out_file)
            click.secho(f"✓ Converted: {os.path.basename(f)} -> {os.path.basename(out_file)}", fg="green")
            successes += 1
        except Exception as e:
            click.secho(f"✗ Failed {os.path.basename(f)}: {e}", fg="red")

    click.secho(f"\nBatch complete: {successes}/{len(files)} files successfully converted.", fg="cyan", bold=True)


@main.command(name="list-posts")
def cmd_list_posts():
    """List all supported CNC machine post-processors."""
    click.secho(f"\nSupported CNC Post-Processors:", fg="cyan", bold=True)
    for key, p in MACHINE_PRESETS.items():
        click.echo(f" • {key:<12} [{p['extension']}]: {p['name']} - {p['description']}")
    click.echo("")


@main.command(name="list-tools")
def cmd_list_tools():
    """List available cutting tool presets."""
    click.secho(f"\nAvailable Cutting Tool Presets:", fg="cyan", bold=True)
    for key, t in TOOL_PRESETS.items():
        click.echo(f" • {key:<16} Ø{t['diameter']}mm {t['tool_type']} ({t['flutes']} flutes) | "
                   f"Feed: {t['feed_rate']}mm/min | RPM: {t['spindle_speed']}")
    click.echo("")


@main.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Host interface to bind to")
@click.option("--port", default=5000, type=int, help="Port to host the web app")
@click.option("--open-browser", is_flag=True, help="Automatically open browser on launch")
def cmd_serve(host, port, open_browser):
    """Launch the local hosting web application for automated 3D model to G-Code."""
    from server import app
    click.secho(f"\n=======================================================", fg="green", bold=True)
    click.secho(f" 3D-MODEL-TO-GCODE LOCAL HOSTING SERVER IS STARTING", fg="green", bold=True)
    click.secho(f"=======================================================", fg="green", bold=True)
    click.echo(f"URL:            http://{host}:{port}/")
    click.echo(f"Interactive UI: 3D CAD viewer, G-code toolpath visualizer, and CAM controls")
    click.echo(f"REST API:       http://{host}:{port}/api/convert")
    click.echo(f"Press CTRL+C to stop the server.\n")

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}/")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
