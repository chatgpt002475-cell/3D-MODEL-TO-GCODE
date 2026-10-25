// FreeCAD Advanced 3D CAD & Wire Studio

let scene, camera, renderer, controls;
let currentCadMesh = null;
let currentWireLinesGroup = null;
let currentSketchEntities = [];
let currentWiresGraph = [];

document.addEventListener("DOMContentLoaded", () => {
    init3D();
    initUI();
    // Default build on startup: advanced Loft
    buildFromPrompt("loft square 80x80 to circle 40 at height 60 with bore 18");
});

// ----------------------------------------------------
// 1. Initialize Three.js 3D Viewport
// ----------------------------------------------------
function init3D() {
    const container = document.getElementById("freecadViewer3d");
    if (!container) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e17);

    camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 5000);
    camera.position.set(130, -170, 150);
    camera.up.set(0, 0, 1); // Z is UP

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambientLight);

    const dir1 = new THREE.DirectionalLight(0xffffff, 0.85);
    dir1.position.set(250, 200, 450);
    scene.add(dir1);

    const dir2 = new THREE.DirectionalLight(0x00e5ff, 0.45);
    dir2.position.set(-250, -200, -100);
    scene.add(dir2);

    // Floor Grid
    const grid = new THREE.GridHelper(300, 30, 0x0088ff, 0x162438);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);

    // Coordinate Axes
    const axes = new THREE.AxesHelper(45);
    scene.add(axes);

    // Group for 3D B-Rep Wire Edges
    currentWireLinesGroup = new THREE.Group();
    scene.add(currentWireLinesGroup);

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
// 2. UI Event Handlers & View Toggles
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

    // Viewport Tabs
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

    // Wire Edges Toggle
    document.getElementById("chkWireEdges").addEventListener("change", (e) => {
        if (currentWireLinesGroup) {
            currentWireLinesGroup.visible = e.target.checked;
        }
    });

    // Wireframe Only Toggle
    document.getElementById("chkWireframe").addEventListener("change", (e) => {
        if (currentCadMesh && currentCadMesh.material) {
            currentCadMesh.material.wireframe = e.target.checked;
        }
    });
}

// ----------------------------------------------------
// 3. Build CAD Model from Prompt
// ----------------------------------------------------
function buildFromPrompt(promptText) {
    const btn = document.getElementById("btnBuild");
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Building CAD & Wires...</span>`;
    document.getElementById("statusText").textContent = "FreeCAD is solving wire geometry...";

    fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptText })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = `⚡ Build 3D CAD with Advanced Wiring`;

        if (data.status === "success") {
            onBuildSuccess(data);
        } else {
            alert("FreeCAD modeling error: " + data.message);
            document.getElementById("statusText").textContent = "Error: " + data.message;
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.innerHTML = `⚡ Build 3D CAD with Advanced Wiring`;
        alert("Server request failed: " + err.message);
        document.getElementById("statusText").textContent = "Request failed";
    });
}

function onBuildSuccess(data) {
    document.getElementById("statusText").textContent = `Built: ${data.params.category.toUpperCase()}`;
    document.getElementById("activeModelName").textContent = `${data.params.category.toUpperCase()} Solid`;

    const m = data.metadata;
    const dims = m.dimensions || [0, 0, 0];
    document.getElementById("statSize").textContent = `${dims[0]} x ${dims[1]} x ${dims[2]} mm`;
    document.getElementById("statVolume").textContent = `${(m.volume / 1000).toFixed(2)} cm³`;
    document.getElementById("statArea").textContent = `${(m.area / 100).toFixed(1)} cm²`;
    document.getElementById("statWires").textContent = `${m.wires_count || 0} Loops`;
    document.getElementById("statTopology").textContent = `${m.faces_count} Faces, ${m.edges_count} Edges`;
    document.getElementById("wireSummaryText").textContent = `${m.wires_count || 0} OpenCASCADE Wire Loops`;

    // Download Links
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

    // Script editor
    document.getElementById("codeEditor").value = data.script_code;

    // Load 3D Solid Mesh
    loadSTLFromUrl(data.files.stl);

    // Render 3D B-Rep Wire Edges
    currentWiresGraph = m.wires_graph || [];
    render3DBRepWireEdges(currentWiresGraph);

    // Render Wire Graph Inspector Tab
    renderWireGraphInspector(currentWiresGraph);

    // Render 2D Sketch Blueprint
    currentSketchEntities = m.sketch_entities || [];
    render2DSketch();
}

// ----------------------------------------------------
// 4. Load & Frame 3D Solid Mesh in WebGL
// ----------------------------------------------------
function loadSTLFromUrl(url) {
    const loader = new THREE.STLLoader();
    loader.load(url, (geometry) => {
        if (currentCadMesh) scene.remove(currentCadMesh);

        geometry.computeVertexNormals();
        const isWireframe = document.getElementById("chkWireframe").checked;

        const material = new THREE.MeshStandardMaterial({
            color: 0x0088ee,
            metalness: 0.3,
            roughness: 0.5,
            wireframe: isWireframe
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
        const maxDim = Math.max(size.x, size.y, size.z, 20.0);
        camera.position.set(center.x + maxDim * 1.5, center.y - maxDim * 1.8, center.z + maxDim * 1.5);
        controls.update();
    });
}

// ----------------------------------------------------
// 5. Render 3D OpenCASCADE B-Rep Wire Edges
// ----------------------------------------------------
function render3DBRepWireEdges(wiresGraph) {
    // Clear previous wire lines
    while (currentWireLinesGroup.children.length > 0) {
        currentWireLinesGroup.remove(currentWireLinesGroup.children[0]);
    }

    if (!wiresGraph || wiresGraph.length === 0) return;

    const linePositions = [];

    wiresGraph.forEach(w => {
        if (!w.edges) return;
        w.edges.forEach(e => {
            const pts = e.points;
            if (!pts || pts.length < 2) return;
            for (let i = 0; i < pts.length - 1; i++) {
                linePositions.push(pts[i][0], pts[i][1], pts[i][2]);
                linePositions.push(pts[i+1][0], pts[i+1][1], pts[i+1][2]);
            }
        });
    });

    if (linePositions.length > 0) {
        const wireGeom = new THREE.BufferGeometry();
        wireGeom.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
        const wireMat = new THREE.LineBasicMaterial({
            color: 0x00e5ff,
            linewidth: 2.0,
            transparent: true,
            opacity: 0.95
        });
        const wireLines = new THREE.LineSegments(wireGeom, wireMat);
        currentWireLinesGroup.add(wireLines);
    }

    currentWireLinesGroup.visible = document.getElementById("chkWireEdges").checked;
}

// ----------------------------------------------------
// 6. Render Wire Graph Topology Inspector
// ----------------------------------------------------
function renderWireGraphInspector(wiresGraph) {
    const container = document.getElementById("wireGraphContainer");
    if (!container) return;
    container.innerHTML = "";

    if (!wiresGraph || wiresGraph.length === 0) {
        container.innerHTML = "<div style='color: var(--text-muted);'>No wire graph data available.</div>";
        return;
    }

    wiresGraph.forEach((w, idx) => {
        const card = document.createElement("div");
        card.style.background = "#131e30";
        card.style.border = "1px solid var(--border-cad)";
        card.style.borderRadius = "8px";
        card.style.padding = "14px 18px";
        card.style.display = "flex";
        card.style.flexDirection = "column";
        card.style.gap = "8px";

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 700; color: var(--accent-cyan);">
                    ➰ Wire Loop #${idx + 1}
                </span>
                <span style="font-size: 11px; background: rgba(0, 255, 136, 0.15); color: var(--accent-green); padding: 2px 8px; border-radius: 10px;">
                    ${w.is_closed ? "Closed Loop (Boundary)" : "Open Spine Wire"}
                </span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); display: flex; gap: 20px;">
                <span><strong>Edges:</strong> ${w.edges_count} segments</span>
                <span><strong>Perimeter Length:</strong> ${w.length} mm</span>
            </div>
        `;
        container.appendChild(card);
    });
}

// ----------------------------------------------------
// 7. Render 2D Sketch Blueprint on Canvas
// ----------------------------------------------------
function render2DSketch() {
    const canvas = document.getElementById("sketchCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const w = canvas.parentElement.clientWidth - 40;
    const h = canvas.parentElement.clientHeight - 40;
    canvas.width = Math.max(300, w);
    canvas.height = Math.max(300, h);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw Blueprint Grid
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

    // If no 2D sketch elements, project the first wire loop from wire graph
    let entities = currentSketchEntities;
    if ((!entities || entities.length === 0) && currentWiresGraph && currentWiresGraph.length > 0) {
        entities = [];
        const firstWire = currentWiresGraph[0];
        if (firstWire && firstWire.edges) {
            firstWire.edges.forEach(e => {
                const pts = e.points;
                if (pts && pts.length >= 2) {
                    for (let i = 0; i < pts.length - 1; i++) {
                        entities.push({
                            type: "line",
                            x1: pts[i][0], y1: pts[i][1],
                            x2: pts[i+1][0], y2: pts[i+1][1]
                        });
                    }
                }
            });
        }
    }

    if (!entities || entities.length === 0) {
        ctx.fillStyle = "#8ca3c7";
        ctx.font = "14px monospace";
        ctx.fillText("(3D Wire preview active in 3D Viewport)", canvas.width / 2 - 120, canvas.height / 2);
        return;
    }

    // Scale and center
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    entities.forEach(e => {
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
    const centerY = canvas.height / 2 + ((minY + maxY) / 2) * scale;

    const toCanvasX = (x) => centerX + x * scale;
    const toCanvasY = (y) => centerY - y * scale;

    // Origin crosshair
    ctx.strokeStyle = "#ff3366";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(toCanvasX(0) - 15, toCanvasY(0));
    ctx.lineTo(toCanvasX(0) + 15, toCanvasY(0));
    ctx.moveTo(toCanvasX(0), toCanvasY(0) - 15);
    ctx.lineTo(toCanvasX(0), toCanvasY(0) + 15);
    ctx.stroke();

    // Draw entities
    entities.forEach(e => {
        if (e.type === "line") {
            ctx.strokeStyle = "#00e5ff";
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(toCanvasX(e.x1), toCanvasY(e.y1));
            ctx.lineTo(toCanvasX(e.x2), toCanvasY(e.y2));
            ctx.stroke();

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

            ctx.fillStyle = "#ffb300";
            ctx.beginPath();
            ctx.arc(toCanvasX(e.cx), toCanvasY(e.cy), 3, 0, Math.PI * 2);
            ctx.fill();
        }
    });
}
