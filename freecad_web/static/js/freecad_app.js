// FreeCAD Interactive 3D Model & 2D Sketch Studio

let scene, camera, renderer, controls;
let currentCadMesh = null;
let currentSketchEntities = [];

document.addEventListener("DOMContentLoaded", () => {
    init3D();
    initUI();
    // Run default prompt on startup
    buildFromPrompt("flange with outer diameter 100, bore 35, thickness 16, and 6 bolt holes on PCD 70");
});

// ----------------------------------------------------
// 1. Initialize Three.js 3D CAD Viewport
// ----------------------------------------------------
function init3D() {
    const container = document.getElementById("freecadViewer3d");
    if (!container) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e17);

    camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 5000);
    camera.position.set(120, -160, 140);
    camera.up.set(0, 0, 1);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(200, 200, 400);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x00e5ff, 0.4);
    dirLight2.position.set(-200, -200, -100);
    scene.add(dirLight2);

    // Floor Grid
    const grid = new THREE.GridHelper(300, 30, 0x0088ff, 0x1a2638);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);

    // Origin Axes
    const axes = new THREE.AxesHelper(40);
    scene.add(axes);

    window.addEventListener("resize", onResize);
    animate();
}

function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) renderer.render(scene, camera);
}

function onResize() {
    const container = document.getElementById("freecadViewer3d");
    if (!container || !camera || !renderer) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
    render2DSketch();
}

// ----------------------------------------------------
// 2. UI Event Handlers & Tabs
// ----------------------------------------------------
function initUI() {
    const btnBuild = document.getElementById("btnBuild");
    const promptInput = document.getElementById("promptInput");

    btnBuild.addEventListener("click", () => {
        const text = promptInput.value.trim();
        if (text) buildFromPrompt(text);
    });

    promptInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            const text = promptInput.value.trim();
            if (text) buildFromPrompt(text);
        }
    });

    // Preset pills click
    document.querySelectorAll(".preset-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            const prompt = pill.getAttribute("data-prompt");
            promptInput.value = prompt;
            buildFromPrompt(prompt);
        });
    });

    // Tabs
    document.querySelectorAll(".v-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".v-tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".v-tab-content").forEach(c => c.classList.remove("active"));
            btn.classList.add("active");
            const tabId = btn.getAttribute("data-vtab");
            document.getElementById(tabId).classList.add("active");
            if (tabId === "vtab-3d") onResize();
            if (tabId === "vtab-sketch") render2DSketch();
        });
    });
}

// ----------------------------------------------------
// 3. Build CAD Model from Prompt
// ----------------------------------------------------
function buildFromPrompt(promptText) {
    const btn = document.getElementById("btnBuild");
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Building CAD in FreeCAD...</span>`;
    document.getElementById("statusText").textContent = "FreeCAD is solving sketch & generating 3D solid...";

    fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptText })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = `⚡ Build 2D Sketch & 3D Solid`;

        if (data.status === "success") {
            onBuildSuccess(data);
        } else {
            alert("FreeCAD modeling error: " + data.message);
            document.getElementById("statusText").textContent = "Error: " + data.message;
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.innerHTML = `⚡ Build 2D Sketch & 3D Solid`;
        alert("Server request failed: " + err.message);
        document.getElementById("statusText").textContent = "Request failed";
    });
}

function onBuildSuccess(data) {
    document.getElementById("statusText").textContent = `Built: ${data.params.category.toUpperCase()}`;

    // Update Stats
    const m = data.metadata;
    const dims = m.dimensions || [0, 0, 0];
    document.getElementById("statSize").textContent = `${dims[0]} x ${dims[1]} x ${dims[2]} mm`;
    document.getElementById("statVolume").textContent = `${(m.volume / 1000).toFixed(2)} cm³`;
    document.getElementById("statArea").textContent = `${(m.area / 100).toFixed(1)} cm²`;
    document.getElementById("statTopology").textContent = `${m.faces_count} Faces, ${m.edges_count} Edges`;

    // Update Download Links
    const btnFcstd = document.getElementById("dlFcstd");
    const btnStep = document.getElementById("dlStep");
    const btnStl = document.getElementById("dlStl");

    btnFcstd.href = data.files.fcstd;
    btnFcstd.download = data.filenames.fcstd;
    btnFcstd.style.display = "inline-flex";

    btnStep.href = data.files.step;
    btnStep.download = data.filenames.step;
    btnStep.style.display = "inline-flex";

    btnStl.href = data.files.stl;
    btnStl.download = data.filenames.stl;
    btnStl.style.display = "inline-flex";

    // Update Python Script Code Tab
    document.getElementById("codeEditor").value = data.script_code;

    // Load 3D STL Model
    loadSTLFromUrl(data.files.stl);

    // Store & Render 2D Sketch
    currentSketchEntities = m.sketch_entities || [];
    render2DSketch();
}

// ----------------------------------------------------
// 4. Load & Render 3D Solid in WebGL
// ----------------------------------------------------
function loadSTLFromUrl(url) {
    const loader = new THREE.STLLoader();
    loader.load(url, (geometry) => {
        if (currentCadMesh) scene.remove(currentCadMesh);

        geometry.computeVertexNormals();
        const material = new THREE.MeshStandardMaterial({
            color: 0x0099ff,
            metalness: 0.35,
            roughness: 0.45
        });

        currentCadMesh = new THREE.Mesh(geometry, material);
        scene.add(currentCadMesh);

        // Center and frame camera
        geometry.computeBoundingBox();
        const bb = geometry.boundingBox;
        const center = new THREE.Vector3();
        bb.getCenter(center);
        controls.target.copy(center);

        const size = new THREE.Vector3();
        bb.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        camera.position.set(center.x + maxDim * 1.6, center.y - maxDim * 1.8, center.z + maxDim * 1.6);
        controls.update();
    });
}

// ----------------------------------------------------
// 5. Render 2D Sketch Blueprint on Canvas
// ----------------------------------------------------
function render2DSketch() {
    const canvas = document.getElementById("sketchCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // Match display size
    const w = canvas.parentElement.clientWidth - 40;
    const h = canvas.parentElement.clientHeight - 40;
    canvas.width = Math.max(300, w);
    canvas.height = Math.max(300, h);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw Engineering Blueprint Grid
    ctx.strokeStyle = "#14253d";
    ctx.lineWidth = 1;
    const gridStep = 25;
    for (let x = 0; x < canvas.width; x += gridStep) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += gridStep) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
    }

    if (!currentSketchEntities || currentSketchEntities.length === 0) {
        ctx.fillStyle = "#8ca3c7";
        ctx.font = "14px monospace";
        ctx.fillText("(No 2D sketch elements to display)", canvas.width / 2 - 100, canvas.height / 2);
        return;
    }

    // Determine scale & center
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    currentSketchEntities.forEach(e => {
        if (e.type === "line") {
            minX = Math.min(minX, e.x1, e.x2);
            maxX = Math.max(maxX, e.x1, e.x2);
            minY = Math.min(minY, e.y1, e.y2);
            maxY = Math.max(maxY, e.y1, e.y2);
        } else if (e.type === "circle") {
            minX = Math.min(minX, e.cx - e.r);
            maxX = Math.max(maxX, e.cx + e.r);
            minY = Math.min(minY, e.cy - e.r);
            maxY = Math.max(maxY, e.cy + e.r);
        }
    });

    const spanX = Math.max(10, maxX - minX);
    const spanY = Math.max(10, maxY - minY);
    const scale = Math.min((canvas.width - 100) / spanX, (canvas.height - 100) / spanY);
    const centerX = canvas.width / 2 - ((minX + maxX) / 2) * scale;
    const centerY = canvas.height / 2 + ((minY + maxY) / 2) * scale; // Invert Y

    const toCanvasX = (x) => centerX + x * scale;
    const toCanvasY = (y) => centerY - y * scale;

    // Origin crosshair (0,0)
    ctx.strokeStyle = "#ff3366";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(toCanvasX(0) - 15, toCanvasY(0));
    ctx.lineTo(toCanvasX(0) + 15, toCanvasY(0));
    ctx.moveTo(toCanvasX(0), toCanvasY(0) - 15);
    ctx.lineTo(toCanvasX(0), toCanvasY(0) + 15);
    ctx.stroke();

    // Draw entities
    currentSketchEntities.forEach(e => {
        if (e.type === "line") {
            ctx.strokeStyle = "#00e5ff";
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(toCanvasX(e.x1), toCanvasY(e.y1));
            ctx.lineTo(toCanvasX(e.x2), toCanvasY(e.y2));
            ctx.stroke();

            // Endpoints
            ctx.fillStyle = "#ffffff";
            ctx.beginPath();
            ctx.arc(toCanvasX(e.x1), toCanvasY(e.y1), 3, 0, Math.PI * 2);
            ctx.arc(toCanvasX(e.x2), toCanvasY(e.y2), 3, 0, Math.PI * 2);
            ctx.fill();
        } else if (e.type === "circle") {
            ctx.strokeStyle = "#00ff88";
            ctx.lineWidth = 2.0;
            ctx.beginPath();
            ctx.arc(toCanvasX(e.cx), toCanvasY(e.cy), e.r * scale, 0, Math.PI * 2);
            ctx.stroke();

            // Center mark
            ctx.fillStyle = "#ffb300";
            ctx.beginPath();
            ctx.arc(toCanvasX(e.cx), toCanvasY(e.cy), 3, 0, Math.PI * 2);
            ctx.fill();
        }
    });
}
