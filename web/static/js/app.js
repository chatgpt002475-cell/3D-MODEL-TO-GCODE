// 3D-MODEL-TO-GCODE Web UI & Three.js 3D Visualizer

let scene, camera, renderer, controls;
let modelMesh = null;
let toolpathLinesGroup = null;
let stockBoundingBox = null;
let selectedFile = null;
let currentGCodeData = null;

document.addEventListener("DOMContentLoaded", () => {
    init3DViewer();
    initEventListeners();
    initPresets();
});

// ----------------------------------------------------
// 1. Initialize Three.js 3D Scene
// ----------------------------------------------------
function init3DViewer() {
    const container = document.getElementById("viewer3d");
    if (!container) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f141c);

    // Camera
    camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 5000);
    camera.position.set(150, -200, 180);
    camera.up.set(0, 0, 1); // Z is UP in CNC Machining

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // Orbit Controls
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(200, 200, 400);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x00d2ff, 0.4);
    dirLight2.position.set(-200, -200, -100);
    scene.add(dirLight2);

    // CNC Bed Grid
    const gridHelper = new THREE.GridHelper(400, 40, 0x0088ff, 0x223348);
    gridHelper.rotation.x = Math.PI / 2; // XY Plane
    scene.add(gridHelper);

    // Coordinate Axes (X=Red, Y=Green, Z=Blue)
    const axesHelper = new THREE.AxesHelper(50);
    scene.add(axesHelper);

    // Group for toolpaths
    toolpathLinesGroup = new THREE.Group();
    scene.add(toolpathLinesGroup);

    // Responsive resize
    window.addEventListener("resize", onWindowResize);
    animate();
}

function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) renderer.render(scene, camera);
}

function onWindowResize() {
    const container = document.getElementById("viewer3d");
    if (!container || !camera || !renderer) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

// ----------------------------------------------------
// 2. Event Listeners & UI Controls
// ----------------------------------------------------
function initEventListeners() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");

    // Click dropzone to open file dialog
    dropzone.addEventListener("click", () => fileInput.click());

    // Drag & drop
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Tab buttons
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            document.getElementById(targetId).classList.add("active");
            if (targetId === "tab-3d") onWindowResize();
        });
    });

    // Generate Button
    document.getElementById("btnGenerate").addEventListener("click", runConversion);

    // Copy Button
    document.getElementById("btnCopyGCode").addEventListener("click", () => {
        const text = document.getElementById("gcodeEditor").value;
        if (!text) return;
        navigator.clipboard.writeText(text);
        showToast("G-Code copied to clipboard!", "success");
    });

    // Eureka 3X Buttons
    const btnEurekaSim = document.getElementById("btnEurekaSim");
    if (btnEurekaSim) {
        btnEurekaSim.addEventListener("click", runEurekaVerification);
    }
    const btnEurekaLaunch = document.getElementById("btnEurekaLaunch");
    if (btnEurekaLaunch) {
        btnEurekaLaunch.addEventListener("click", launchEurekaApp);
    }

    // Tool Preset Dropdown
    document.getElementById("toolPresetSelect").addEventListener("change", (e) => {
        const key = e.target.value;
        if (window.PRESETS && window.PRESETS.tools[key]) {
            const t = window.PRESETS.tools[key];
            document.getElementById("toolDia").value = t.diameter;
            document.getElementById("stepdown").value = t.stepdown;
            document.getElementById("stepover").value = t.stepover;
            document.getElementById("feedRate").value = t.feed_rate;
            document.getElementById("plungeRate").value = t.plunge_rate;
            document.getElementById("spindleSpeed").value = t.spindle_speed;
        }
    });
}

function initPresets() {
    fetch("/api/presets")
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                window.PRESETS = data;
            }
        })
        .catch(err => console.error("Could not load presets", err));
}

// ----------------------------------------------------
// 3. Handle File Selection & 3D Preview
// ----------------------------------------------------
function handleFileSelect(file) {
    selectedFile = file;
    const filePill = document.getElementById("filePill");
    const fileNameSpan = document.getElementById("fileName");
    const fileSizeSpan = document.getElementById("fileSize");

    fileNameSpan.textContent = file.name;
    fileSizeSpan.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    filePill.style.display = "flex";

    // Inspect file automatically via API
    const formData = new FormData();
    formData.append("file", file);

    updateStatus("Inspecting model geometry...", "cyan");

    fetch("/api/inspect", {
        method: "POST",
        body: formData
    })
    .then(r => r.json())
    .then(res => {
        if (res.status === "success") {
            const info = res.model_info;
            document.getElementById("statDim").textContent = 
                `${info.dimensions.x} x ${info.dimensions.y} x ${info.dimensions.z} mm`;
            document.getElementById("statVol").textContent = 
                `${(info.volume / 1000).toFixed(1)} cm³`;
            updateStatus("Model ready for CAM toolpath generation.", "green");
            showToast("Model geometry analyzed successfully", "success");
        } else {
            updateStatus("Model inspection warning: " + res.message, "yellow");
        }
    })
    .catch(err => {
        console.error(err);
        updateStatus("Ready (direct conversion available)", "green");
    });

    // If STL, render directly in Three.js
    if (file.name.toLowerCase().endsWith(".stl")) {
        const reader = new FileReader();
        reader.onload = function(e) {
            loadSTLIntoViewer(e.target.result);
        };
        reader.readAsArrayBuffer(file);
    }
}

function loadSTLIntoViewer(buffer) {
    if (modelMesh) scene.remove(modelMesh);

    const loader = new THREE.STLLoader();
    const geometry = loader.parse(buffer);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
        color: 0x3b82f6,
        metalness: 0.2,
        roughness: 0.5,
        wireframe: false
    });

    modelMesh = new THREE.Mesh(geometry, material);
    scene.add(modelMesh);

    // Center camera on model
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const center = new THREE.Vector3();
    bb.getCenter(center);
    controls.target.copy(center);

    const size = new THREE.Vector3();
    bb.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    camera.position.set(center.x + maxDim * 1.5, center.y - maxDim * 1.8, center.z + maxDim * 1.5);
    controls.update();
}

// ----------------------------------------------------
// 4. Run Automated CAM Conversion
// ----------------------------------------------------
function runConversion() {
    if (!selectedFile) {
        showToast("Please upload a 3D model first!", "warning");
        return;
    }

    const btn = document.getElementById("btnGenerate");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Generating G-Code...`;
    updateStatus("Generating automated CNC toolpaths...", "cyan");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("postprocessor", document.getElementById("postSelect").value);
    formData.append("tool_diameter", document.getElementById("toolDia").value);
    formData.append("stepdown", document.getElementById("stepdown").value);
    formData.append("stepover", document.getElementById("stepover").value);
    formData.append("feed_rate", document.getElementById("feedRate").value);
    formData.append("plunge_rate", document.getElementById("plungeRate").value);
    formData.append("spindle_speed", document.getElementById("spindleSpeed").value);
    formData.append("stock_padding", document.getElementById("stockPad").value);

    // Active operations
    const ops = [];
    if (document.getElementById("opFacing").checked) ops.push("facing");
    if (document.getElementById("opContour").checked) ops.push("contour");
    if (document.getElementById("opSurface").checked) ops.push("surface");
    formData.append("operations", ops.join(","));

    fetch("/api/convert", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = `⚡ Generate CNC G-Code`;

        if (data.status === "success") {
            currentGCodeData = data;
            onConversionSuccess(data);
        } else {
            showToast("Conversion failed: " + data.message, "danger");
            updateStatus("Error: " + data.message, "red");
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.innerHTML = `⚡ Generate CNC G-Code`;
        showToast("Request error: " + err.message, "danger");
        updateStatus("Request failed", "red");
    });
}

function onConversionSuccess(data) {
    showToast("G-Code generated successfully!", "success");
    updateStatus("G-Code Ready: " + data.filename, "green");

    // Populate Stats
    const sim = data.simulation;
    document.getElementById("statLines").textContent = sim.total_lines.toLocaleString();
    document.getElementById("statCutDist").textContent = `${sim.feed_distance_mm.toFixed(1)} mm`;
    document.getElementById("statRapidDist").textContent = `${sim.rapid_distance_mm.toFixed(1)} mm`;
    document.getElementById("statTime").textContent = sim.estimated_time_formatted;

    // Populate G-code text editor
    document.getElementById("gcodeEditor").value = data.gcode_content;

    // Enable Download Button
    const btnDownload = document.getElementById("btnDownload");
    btnDownload.href = data.download_url;
    btnDownload.download = data.filename;
    btnDownload.style.display = "inline-flex";

    // Show Eureka 3X Buttons
    const btnESim = document.getElementById("btnEurekaSim");
    if (btnESim) btnESim.style.display = "inline-flex";
    const btnELaunch = document.getElementById("btnEurekaLaunch");
    if (btnELaunch) btnELaunch.style.display = "inline-flex";
    const statE = document.getElementById("statEureka");
    if (statE) {
        statE.textContent = "Ready for Check";
        statE.style.color = "#00d2ff";
    }

    // Render 3D Toolpaths
    renderToolpathsInViewer(sim.toolpaths, data.model_info);
}

function runEurekaVerification() {
    if (!currentGCodeData) return;
    const btn = document.getElementById("btnEurekaSim");
    btn.disabled = true;
    btn.textContent = "⏳ Running Eureka 3X...";
    updateStatus("Running Eureka 3X virtual simulation...", "cyan");

    // 1. Create project
    fetch("/api/eureka/create-project", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            filename: currentGCodeData.filename,
            stock_dims: (currentGCodeData.model_info && currentGCodeData.model_info.recommended_stock) 
                ? currentGCodeData.model_info.recommended_stock.dimensions 
                : [100.0, 100.0, 30.0]
        })
    })
    .then(r => r.json())
    .then(pdata => {
        if (pdata.status === "success") {
            // 2. Simulate
            return fetch("/api/eureka/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ epf_filename: pdata.epf_filename })
            });
        } else {
            throw new Error(pdata.message || "Failed to create Eureka project");
        }
    })
    .then(r => r.json())
    .then(simData => {
        btn.disabled = false;
        btn.textContent = "🛡️ Eureka 3X Verify";
        if (simData.status === "success") {
            const cols = simData.collision_count;
            if (cols === 0) {
                const statE = document.getElementById("statEureka");
                if (statE) {
                    statE.textContent = "✓ 0 Collisions (Safe)";
                    statE.style.color = "#00ff88";
                }
                showToast("Eureka 3X: 0 collisions detected! CNC program safe.", "success");
                updateStatus("Eureka 3X: Verified Safe (0 Collisions)", "green");
            } else {
                const statE = document.getElementById("statEureka");
                if (statE) {
                    statE.textContent = `⚠️ ${cols} Collisions`;
                    statE.style.color = "#ff3366";
                }
                showToast(`Eureka 3X: ${cols} collisions detected!`, "danger");
                updateStatus(`Eureka 3X Warning: ${cols} collisions`, "red");
            }
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.textContent = "🛡️ Eureka 3X Verify";
        showToast("Eureka 3X error: " + err.message, "danger");
    });
}

function launchEurekaApp() {
    if (!currentGCodeData) return;
    const base = currentGCodeData.filename.replace(/\.[^/.]+$/, "");
    const epf = base + "_eureka.epf";
    fetch("/api/eureka/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ epf_filename: epf })
    })
    .then(r => r.json())
    .then(res => {
        showToast("Eureka 3X application launched!", "success");
    })
    .catch(err => {
        showToast("Failed to launch Eureka: " + err.message, "danger");
    });
}

// ----------------------------------------------------
// 5. Render 3D Toolpaths in WebGL
// ----------------------------------------------------
function renderToolpathsInViewer(toolpaths, modelInfo) {
    // Clear previous toolpaths
    while (toolpathLinesGroup.children.length > 0) {
        toolpathLinesGroup.remove(toolpathLinesGroup.children[0]);
    }

    if (!toolpaths || toolpaths.length === 0) return;

    const cutPositions = [];
    const rapidPositions = [];

    toolpaths.forEach(tp => {
        const s = tp.start;
        const e = tp.end;
        if (tp.type === "cut") {
            cutPositions.push(s[0], s[1], s[2], e[0], e[1], e[2]);
        } else {
            rapidPositions.push(s[0], s[1], s[2], e[0], e[1], e[2]);
        }
    });

    // Cutting Moves (Neon Green G1/G2/G3)
    if (cutPositions.length > 0) {
        const cutGeom = new THREE.BufferGeometry();
        cutGeom.setAttribute('position', new THREE.Float32BufferAttribute(cutPositions, 3));
        const cutMat = new THREE.LineBasicMaterial({
            color: 0x00e676,
            linewidth: 1.5
        });
        const cutLines = new THREE.LineSegments(cutGeom, cutMat);
        toolpathLinesGroup.add(cutLines);
    }

    // Rapid Clearance Moves (Orange/Red Dashed G0)
    if (rapidPositions.length > 0) {
        const rapidGeom = new THREE.BufferGeometry();
        rapidGeom.setAttribute('position', new THREE.Float32BufferAttribute(rapidPositions, 3));
        const rapidMat = new THREE.LineBasicMaterial({
            color: 0xff3366,
            opacity: 0.6,
            transparent: true
        });
        const rapidLines = new THREE.LineSegments(rapidGeom, rapidMat);
        toolpathLinesGroup.add(rapidLines);
    }

    // Stock Boundary Box
    if (stockBoundingBox) scene.remove(stockBoundingBox);
    if (modelInfo && modelInfo.recommended_stock) {
        const st = modelInfo.recommended_stock;
        const dims = st.dimensions;
        const offsets = st.origin_offset;
        const boxGeom = new THREE.BoxGeometry(dims[0], dims[1], dims[2]);
        const edgesGeom = new THREE.EdgesGeometry(boxGeom);
        const boxMat = new THREE.LineBasicMaterial({ color: 0x00d2ff, opacity: 0.4, transparent: true });
        stockBoundingBox = new THREE.LineSegments(edgesGeom, boxMat);
        stockBoundingBox.position.set(
            offsets[0] + dims[0] / 2,
            offsets[1] + dims[1] / 2,
            offsets[2] + dims[2] / 2
        );
        scene.add(stockBoundingBox);
    }
}

// ----------------------------------------------------
// 6. Utility Functions
// ----------------------------------------------------
function updateStatus(text, color) {
    const el = document.getElementById("statusBadge");
    if (!el) return;
    el.textContent = text;
    el.style.color = color === "green" ? "#00e676" : (color === "cyan" ? "#00d2ff" : (color === "red" ? "#ff3366" : "#ffb300"));
}

function showToast(message, type) {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.position = "fixed";
    toast.style.bottom = "85px";
    toast.style.right = "25px";
    toast.style.backgroundColor = type === "success" ? "#00b050" : (type === "warning" ? "#ffb300" : "#ff3366");
    toast.style.color = "#fff";
    toast.style.padding = "10px 18px";
    toast.style.borderRadius = "6px";
    toast.style.fontSize = "13px";
    toast.style.fontWeight = "600";
    toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.5)";
    toast.style.zIndex = "9999";
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}
