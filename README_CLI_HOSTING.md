# 3D-MODEL-TO-GCODE — Automated CAM & Local Hosting Suite

Automates the manual workflow of importing 3D models into CAD/CAM software, configuring tools, setting depth passes, and postprocessing G-code. Converts **STEP, STL, OBJ, IGES** models directly into production-ready CNC G-code with a feature-rich CLI, a headless automation engine, and a local web hosting interface.

---

## ⚡ Quick Start

### 1. Launch Local Hosting Web Application
```bash
python cli.py serve --port 5000
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser:
- **3D CAD & Mesh Viewer:** Inspect 3D models with rotation, pan, zoom, and wireframe views.
- **3D Toolpath Visualizer:** View cutting moves (Neon Green G1/G2/G3), rapid retracts (Red G0), and stock boundaries in WebGL.
- **Dynamic CAM Parameter Controls:** Select machines, tool diameters, feeds & speeds, and operations.
- **G-Code Inspector & Editor:** Syntax-highlighted code with cycle time estimation and travel bounds.
- **1-Click Download:** Download `.nc`, `.gcode`, or `.tap` files tailored for your controller.

---

## 🛠️ CLI Commands & Usage

### 1. Convert 3D Model to G-Code
```bash
# Convert STL/STEP using GRBL dialect
python cli.py convert model.step --post grbl -o output.nc

# Convert with customized tool and cutting feeds
python cli.py convert part.stl --post linuxcnc --tool-dia 6.0 --stepdown 1.5 --feed 1400 --rpm 12000

# Select specific operations (Facing, Contour Profiling, 3D Waterline Finishing)
python cli.py convert part.step --ops facing,contour,surface --post fanuc
```

**Options:**
- `-o, --output PATH`: Custom output file path.
- `-p, --post [grbl|linuxcnc|fanuc|haas|mach3|marlin|generic]`: Machine controller dialect.
- `-t, --tool-preset [6mm_endmill|3mm_endmill|10mm_rougher|6mm_ballnose|25mm_facemill]`: Tool preset.
- `-d, --tool-dia FLOAT`: Override tool diameter (mm).
- `-s, --stepdown FLOAT`: Depth of cut per pass (mm).
- `--stepover FLOAT`: Stepover distance (mm).
- `--feed FLOAT`: Cutting feedrate (mm/min).
- `--plunge FLOAT`: Plunge feedrate (mm/min).
- `--rpm INT`: Spindle speed (RPM).
- `--ops TEXT`: Comma-separated operations (`facing,contour,surface`).
- `--pad FLOAT`: Stock padding margin on X/Y (mm).
- `--json-out`: Print output metadata and simulation summary as JSON.

---

### 2. Inspect 3D Model Geometry
Extracts dimensions, bounding box, volume, surface area, and recommended stock/tooling:
```bash
python cli.py inspect model.step
```

---

### 3. Simulate and Verify G-Code
Parses G-code lines, calculates total cut travel, rapid travel, estimated machining time, and bounding work envelope:
```bash
python cli.py simulate output.nc
```

---

### 4. Batch Convert All Models in a Folder
```bash
python cli.py batch path/to/cad_models/ --post grbl --output-folder path/to/gcode_output/
```

---

### 5. List Supported Post-Processors & Tools
```bash
python cli.py list-posts
python cli.py list-tools
```

---

## 🌐 REST API Endpoints

The local hosting server exposes REST endpoints for automated integration:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web Dashboard & 3D Visualizer |
| `GET` | `/api/presets` | Get supported machine controllers & tools |
| `POST` | `/api/inspect` | Inspect uploaded model geometry and stock |
| `POST` | `/api/convert` | Convert multipart 3D model to G-code |
| `GET` | `/api/download/<filename>` | Download generated G-code file |
| `POST` | `/api/simulate` | Simulate raw G-code text and extract 3D toolpaths |

### Example cURL Conversion:
```bash
curl -X POST http://127.0.0.1:5000/api/convert \
  -F "file=@sample_model.stl" \
  -F "postprocessor=grbl" \
  -F "tool_diameter=6.0" \
  -F "operations=facing,contour"
```

---

## 🏭 Supported CNC Post-Processors

- **GRBL:** Shapeoko, X-Carve, CNC 3018, Genmitsu routers (`.nc`)
- **LinuxCNC / EMC2:** PC-based industrial machine controllers (`.ngc`)
- **Fanuc:** 0i, 31i, and compatible CNC milling centers (`.nc`)
- **Haas Automation:** VF / Mini Mill series (`.nc`)
- **Mach3 / Mach4:** PC CNC mill controllers (`.tap`)
- **Marlin:** 3D printer CNC conversion / MP3DP (`.gcode`)
- **Generic ISO:** Standard ISO 6983 RS-274D G-code (`.gcode`)
