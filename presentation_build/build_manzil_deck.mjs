import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/X1 Carbon/Desktop/7th Semester/FYP/fyp-kaam";
const skillDir = "C:/Users/X1 Carbon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11127/skills/presentations";
const buildDir = path.join(workspaceDir, "presentation_build");
const previewDir = path.join(buildDir, "previews");
const outputDir = path.join(workspaceDir, "presentation_output");
const finalPath = path.join(outputDir, "Manzil_Presentation.pptx");
const draftPath = path.join(buildDir, "Manzil_Deliverable_2_Presentation_draft.pptx");
const runtimePython = "C:/Users/X1 Carbon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const { makeNativeBulletParagraphs, finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);

const W = 1280;
const H = 720;
const FONT = "Segoe UI";
const C = {
  navy: "#0D2742",
  blue: "#1F5B83",
  teal: "#159A9C",
  tealDark: "#0E6F73",
  amber: "#E6A33D",
  red: "#C94C4C",
  ink: "#183041",
  muted: "#5D6E7A",
  pale: "#EEF4F6",
  paleTeal: "#E7F4F2",
  paleAmber: "#FBF3E4",
  white: "#FFFFFF",
  line: "#C9D5DC",
  green: "#2E8B72",
};

async function imageBytes(filePath) {
  const bytes = await fs.readFile(filePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function addText(slide, text, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: opts.size ?? 22,
    bold: opts.bold ?? false,
    color: opts.color ?? C.ink,
    autoFit: "shrinkText",
    alignment: opts.align ?? "left",
    verticalAlignment: opts.valign ?? "top",
  };
  return shape;
}

function addBox(slide, x, y, w, h, fill, opts = {}) {
  const config = {
    geometry: opts.geometry ?? "roundRect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: opts.line ?? fill, width: opts.lineWidth ?? 0 },
  };
  if ((opts.geometry ?? "roundRect") === "roundRect") config.borderRadius = opts.radius ?? "rounded-lg";
  return slide.shapes.add(config);
}

function addHeader(slide, title, number, subtitle = "") {
  addText(slide, title, 68, 42, 1010, 52, { size: 39, bold: true, color: C.navy });
  if (subtitle) addText(slide, subtitle, 70, 96, 1040, 32, { size: 18, color: C.muted });
  addBox(slide, 68, subtitle ? 132 : 108, 1144, 5, C.teal, { geometry: "rect", radius: "none" });
  addText(slide, String(number).padStart(2, "0"), 1152, 48, 58, 30, { size: 18, bold: true, color: C.teal, align: "right" });
}

function addFooter(slide) {
  addText(slide, "MANZIL  •  FYP DELIVERABLE 2", 70, 684, 430, 18, { size: 11, bold: true, color: "#78909C" });
  addText(slide, "FAST–NUCES", 1040, 684, 170, 18, { size: 11, bold: true, color: "#78909C", align: "right" });
}

function addBullets(slide, items, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = makeNativeBulletParagraphs(items, {
    marginLeftPoints: opts.marginLeft ?? 18,
    hangingPoints: opts.hanging ?? 8,
    spaceAfterPoints: opts.spaceAfter ?? 8,
  });
  shape.text.style = {
    typeface: FONT,
    fontSize: opts.size ?? 22,
    color: opts.color ?? C.ink,
    autoFit: "shrinkText",
  };
  return shape;
}

function addLabel(slide, text, x, y, w, color = C.teal) {
  addBox(slide, x, y + 5, 7, 24, color, { geometry: "rect", radius: "none" });
  addText(slide, text, x + 17, y, w - 17, 34, { size: 20, bold: true, color: C.navy });
}

function addNotes(slide, lines) {
  slide.speakerNotes.text = lines.join("\n");
  slide.speakerNotes.setVisible(true);
}

const pres = Presentation.create({ slideSize: { width: W, height: H } });

// 1 — Cover
{
  const s = pres.slides.add();
  s.background.fill = C.white;
  addBox(s, 0, 0, W, 720, C.navy, { geometry: "rect", radius: "none" });
  addBox(s, 0, 0, W, 15, C.teal, { geometry: "rect", radius: "none" });
  const nu = await imageBytes(path.join(workspaceDir, "FYPFast/Figures/fastlogo.png"));
  const fast = await imageBytes(path.join(workspaceDir, "FYPFast/Figures/fast.png"));
  s.images.add({ blob: nu, contentType: "image/png", alt: "National University emblem", fit: "contain", position: { left: 78, top: 52, width: 118, height: 118 } });
  s.images.add({ blob: fast, contentType: "image/png", alt: "FAST logo", fit: "contain", position: { left: 1030, top: 72, width: 150, height: 62 } });
  addText(s, "MANZIL", 78, 212, 800, 82, { size: 64, bold: true, color: C.white });
  addText(s, "Intelligent Traffic and Emergency Routing", 82, 292, 850, 48, { size: 30, color: "#D6E5EE" });
  addBox(s, 82, 365, 88, 6, C.amber, { geometry: "rect", radius: "none" });
  addText(s, "Final Year Project · Deliverable 2 Presentation", 82, 394, 760, 38, { size: 22, bold: true, color: C.white });
  addText(s, "Muhammad Ali Mahoon  ·  23L-0531\nMuzammil Ahmed Bhatti  ·  23L-0688\nMohammad Ibrahim Salman  ·  23L-0723", 82, 468, 540, 112, { size: 20, color: "#E8F0F5" });
  addText(s, "Supervisor\nMiss Umm-e-Ammarah", 828, 494, 360, 72, { size: 20, bold: true, color: C.white, align: "right" });
  addText(s, "National University of Computer and Emerging Sciences", 82, 646, 780, 26, { size: 16, color: "#AFC4D2" });
  addNotes(s, ["Source: Manzil Deliverable 2 report front matter and project context."]);
}

// 2 — Problem statement
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Problem statement", 2, "A single traffic event can expose weaknesses in sensing, control, routing, and recovery"); addFooter(s);
  addText(s, "Current gap", 72, 160, 420, 38, { size: 27, bold: true, color: C.red });
  addText(s, "The project lacks one reproducible environment that can compare normal signal-control strategies and isolate the effects of emergency routing and coordinated signal priority under the same demand conditions.", 72, 207, 500, 158, { size: 25, color: C.ink });
  addBox(s, 70, 410, 500, 170, C.paleAmber, { line: "#EDD4A8", lineWidth: 1 });
  addText(s, "Why integration is difficult", 95, 432, 420, 32, { size: 22, bold: true, color: C.navy });
  addBullets(s, ["Measurements need defined units, freshness, and provenance.", "Routes must remain legal from the ambulance’s current position.", "Signal transitions must preserve minimum green, clearance, and recovery."], 92, 475, 430, 92, { size: 18, spaceAfter: 5 });
  const nodes = [
    ["Observe", "Video or SUMO state", C.blue],
    ["Decide", "Control and routing", C.teal],
    ["Act safely", "Validated signal action", C.amber],
    ["Explain", "Versioned evidence", C.green],
  ];
  const shapes = [];
  nodes.forEach((n, i) => {
    const y = 160 + i * 116;
    const box = addBox(s, 690, y, 430, 78, i === 2 ? C.paleAmber : C.paleTeal, { line: n[2], lineWidth: 2 });
    addText(s, n[0], 718, y + 12, 140, 30, { size: 22, bold: true, color: n[2] });
    addText(s, n[1], 860, y + 14, 230, 28, { size: 19, color: C.ink });
    shapes.push(box);
  });
  for (let i = 0; i < shapes.length - 1; i++) s.shapes.connect(shapes[i], shapes[i + 1], { fromSide: "bottom", toSide: "top", kind: "straight", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Sections 2.2 and 2.3."]);
}

// 3 — Problem elaboration
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Five connected research problems", 3); addFooter(s);
  const items = [
    ["01", "Traffic observation", "Detection must become stable tracks, counts, and queue-related observations."],
    ["02", "Normal signal control", "Fixed and transparent adaptive baselines must work before RL can be judged."],
    ["03", "Dynamic routing", "Time-based costs must avoid double counting and support stable rerouting."],
    ["04", "Moving priority corridor", "Activation, clearance, passage, cancellation, and recovery require one safe lifecycle."],
    ["05", "Reproducible evaluation", "Matched demand, seeds, timing, and metrics must remain fixed across comparisons."],
  ];
  items.forEach((it, i) => {
    const y = 142 + i * 101;
    addText(s, it[0], 76, y + 2, 66, 42, { size: 28, bold: true, color: i === 3 ? C.amber : C.teal });
    addText(s, it[1], 158, y, 315, 34, { size: 23, bold: true, color: C.navy });
    addText(s, it[2], 470, y, 710, 58, { size: 20, color: C.ink });
    if (i < items.length - 1) addBox(s, 158, y + 73, 1020, 1, C.line, { geometry: "rect", radius: "none" });
  });
  addText(s, "Dependencies matter: stale observations can change route costs, route revisions can invalidate priority requests, and emergency gains can shift delay to ordinary traffic.", 158, 624, 1020, 48, { size: 20, bold: true, color: C.tealDark });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Section 2.3 Problem Elaboration."]);
}

// 4 — Scope
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Project scope", 4, "The prototype is deliberately narrower than an operational city traffic system"); addFooter(s);
  addBox(s, 64, 154, 555, 470, C.paleTeal, { line: "#B4DCD7", lineWidth: 1 });
  addBox(s, 661, 154, 555, 470, "#F5F7F8", { line: C.line, lineWidth: 1 });
  addText(s, "Included", 92, 178, 480, 38, { size: 28, bold: true, color: C.green });
  addBullets(s, ["Recorded-video vehicle detection, tracking, counts, and queue proxies", "A manageable multi-intersection SUMO network with repeatable demand", "Fixed-time, rule-adaptive, and one feasible RL controller", "One active ambulance with congestion-aware routing and a moving priority corridor", "React dashboard, FastAPI boundary, run manifests, and experimental records", "Controlled closures or incidents for rerouting experiments"], 92, 232, 480, 340, { size: 20, spaceAfter: 9 });
  addText(s, "Excluded from the current project", 690, 178, 470, 38, { size: 28, bold: true, color: C.red });
  addBullets(s, ["Live government CCTV integration or citywide camera calibration", "Direct control of public signals or safety-certified field deployment", "All-Lahore coverage and multiple competing emergency fleets", "Accident classification, forecasting, enforcement, or plate and face recognition", "Claims about patient outcomes, certified emergency preemption, or deployment readiness", "A guarantee that imported map attributes are complete or current"], 690, 232, 470, 340, { size: 20, spaceAfter: 9 });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Section 2.5 and Table 2.1 Scope Boundaries."]);
}

// 5 — Goals achieved/future
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Goals achieved and future goals", 5, "Repository evidence supports design completion, not implementation or measured performance"); addFooter(s);
  addText(s, "Completed for Deliverable 2", 72, 155, 500, 38, { size: 27, bold: true, color: C.green });
  addBullets(s, ["Defined the bounded problem, stakeholders, scope, and measurable objectives", "Reviewed verified literature across perception, signal control, RL, routing, and emergency priority", "Specified functional requirements, use cases, interfaces, risks, and failure behavior", "Designed the architecture, data model, algorithms, wireframes, and evaluation protocol", "Established reproducibility rules for configurations, route versions, applied actions, and retained failures"], 78, 214, 505, 336, { size: 21, spaceAfter: 11 });
  addText(s, "Next implementation goals", 690, 155, 470, 38, { size: 27, bold: true, color: C.amber });
  addBullets(s, ["Prepare and validate the selected SUMO network and demand scenarios", "Evaluate the detector and tracker on held-out, source-separated video", "Implement fixed and rule-based controllers before training one RL policy", "Integrate stable rerouting with the corridor lifecycle and safety filter", "Build the dashboard and persistence layer, then run matched repeated experiments", "Report positive, negative, or mixed results against the predeclared metrics"], 696, 214, 485, 356, { size: 21, spaceAfter: 10 });
  addBox(s, 612, 174, 2, 402, C.line, { geometry: "rect", radius: "none" });
  addText(s, "Status rule", 72, 592, 130, 28, { size: 18, bold: true, color: C.red });
  addText(s, "No slide claims implementation, accuracy, travel-time improvement, or field readiness until traceable evidence exists.", 205, 592, 968, 34, { size: 19, color: C.ink });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Sections 1.1 and 2.4; Manzil_FYP_Context.md implementation-status notes."]);
}

// 6 — Literature review
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Research and development evidence", 6, "The literature supports building blocks and also defines what Manzil must validate itself"); addFooter(s);
  const themes = [
    ["Perception", "YOLO enables one-stage detection. ByteTrack and DeepSORT address temporal identity, but local viewpoint, occlusion, and region mapping still require validation.", "Detection boxes alone are not traffic state."],
    ["Signal control", "Max-pressure research motivates a transparent adaptive baseline. PressLight and related RL studies show feasible learning formulations under declared simulations.", "RL needs fair baselines and a shared safety envelope."],
    ["Routing", "Dijkstra supplies the reference optimum for nonnegative time costs. A* remains valid only with an admissible lower bound.", "Dynamic behavior comes from costs, freshness, and rerouting rules."],
    ["Emergency priority", "Preemption research emphasizes lawful transition, bounded service, queue clearance, passage detection, cancellation, and recovery.", "Ambulance benefit must be reported with ordinary-traffic impact."],
  ];
  themes.forEach((t, i) => {
    const y = 148 + i * 122;
    addText(s, `0${i + 1}`, 72, y + 3, 58, 32, { size: 23, bold: true, color: i === 3 ? C.amber : C.teal });
    addText(s, t[0], 148, y, 210, 32, { size: 23, bold: true, color: C.navy });
    addText(s, t[1], 360, y, 570, 72, { size: 19, color: C.ink });
    addText(s, t[2], 952, y, 245, 74, { size: 18, bold: true, color: C.tealDark });
    if (i < 3) addBox(s, 148, y + 94, 1048, 1, C.line, { geometry: "rect", radius: "none" });
  });
  addText(s, "Manzil’s contribution is the controlled evaluation of an integrated, traceable prototype. It does not claim a new detector, shortest-path algorithm, or RL family.", 148, 636, 1048, 36, { size: 20, bold: true, color: C.navy });
  addNotes(s, ["Sources: Manzil Deliverable 2 report, Chapter 3.", "Redmon et al. (2016), DOI 10.1109/CVPR.2016.91.", "Wojke et al. (2017), DOI 10.1109/ICIP.2017.8296962.", "Zhang et al. (2022), DOI 10.1007/978-3-031-20047-2_1.", "Varaiya (2013), DOI 10.1016/j.trc.2013.08.014.", "Wei et al. (2019), DOI 10.1145/3292500.3330949.", "Qin and Khan (2012), DOI 10.1016/j.trc.2012.04.004."]);
}

// 7 — Related applications/systems
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Related systems and research applications", 7, "Each reference solves part of the problem; none substitutes for Manzil’s controlled integration"); addFooter(s);
  const vals = [
    ["System or method", "Primary strength", "Boundary for Manzil", "Use in this project"],
    ["SUMO + TraCI", "Detailed microscopic simulation and external control", "Simulation behavior depends on network and demand configuration", "Core controlled experiment environment"],
    ["CityFlow", "High-throughput traffic RL at larger scale", "Migration would add scope and equivalence work", "Documented alternative, not selected"],
    ["YOLO + tracker", "Vehicle detection and temporal association", "Does not produce calibrated queues or complete network state", "Recorded-video perception path"],
    ["PressLight / CoLight", "Pressure-informed or cooperative RL control", "Training complexity and transfer remain scenario dependent", "Design evidence, not copied result"],
    ["Dijkstra / A*", "Minimum-cost graph routing", "Needs legal movement graph, time costs, freshness, and stability", "Reference route and conditional optimization"],
  ];
  const table = s.tables.add({ rows: vals.length, columns: 4, left: 66, top: 158, width: 1148, height: 430, values: vals, columnWidths: [210, 292, 360, 286] });
  table.borders.assign({ style: "solid", fill: C.line, width: 1 });
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 4 }).assign({ fill: C.navy, textStyle: { typeface: FONT, fontSize: 18, bold: true, color: C.white }, margins: { left: 10, right: 10, top: 7, bottom: 7 } });
  table.cells.block({ row: 1, column: 0, rowCount: 5, columnCount: 4 }).assign({ textStyle: { typeface: FONT, fontSize: 17, color: C.ink }, margins: { left: 10, right: 10, top: 7, bottom: 7 } });
  table.cells.block({ row: 1, column: 0, rowCount: 5, columnCount: 1 }).assign({ fill: C.paleTeal, textStyle: { typeface: FONT, fontSize: 17, bold: true, color: C.tealDark } });
  addText(s, "Selection principle", 70, 612, 180, 28, { size: 18, bold: true, color: C.amber });
  addText(s, "Choose tools that preserve reproducibility, inspectable signal behavior, legal routing, and feasible integration on the team’s available hardware.", 250, 610, 960, 40, { size: 19, color: C.ink });
  addNotes(s, ["Sources: Manzil Deliverable 2 report, Chapter 3 and Section 6.4.1.", "Alvarez Lopez et al. (2018), DOI 10.1109/ITSC.2018.8569938.", "Zhang et al. (2019), DOI 10.1145/3308558.3314139.", "Wei et al. (2019), DOI 10.1145/3292500.3330949 and 10.1145/3357384.3357902.", "Dijkstra (1959), DOI 10.1007/BF01386390; Hart et al. (1968), DOI 10.1109/TSSC.1968.300136."]);
}

// 8 — Architecture
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Proposed system architecture", 8, "One controlled actuation path separates commands, evidence, and presentation"); addFooter(s);
  const img = await imageBytes(path.join(buildDir, "source_pages/p74-74.png"));
  s.images.add({ blob: img, contentType: "image/png", alt: "High-level architecture from the Manzil report", fit: "cover", crop: { left: 0.11, top: 0.12, right: 0.11, bottom: 0.51 }, position: { left: 60, top: 152, width: 710, height: 454 } });
  addText(s, "Design rules", 822, 155, 330, 34, { size: 26, bold: true, color: C.navy });
  addLabel(s, "Single actuation owner", 822, 214, 330, C.teal);
  addText(s, "Only the SUMO/TraCI adapter advances time and applies validated signal changes.", 839, 252, 342, 74, { size: 19, color: C.ink });
  addLabel(s, "Safety before application", 822, 346, 330, C.amber);
  addText(s, "Controllers request actions. The safety filter enforces legal phases and timing before actuation.", 839, 384, 342, 72, { size: 19, color: C.ink });
  addLabel(s, "Evidence remains traceable", 822, 480, 330, C.green);
  addText(s, "Snapshots, route versions, requested actions, applied actions, metrics, and failures retain causal links.", 839, 518, 342, 78, { size: 19, color: C.ink });
  addNotes(s, ["Source image and content: Manzil Deliverable 2 report, Figure 6.1 and Section 6.1.4."]);
}

// 9 — Core workflow
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Core decision workflow", 9, "The same safety and evidence rules apply to normal control and emergency priority"); addFooter(s);
  const steps = [
    ["1", "Advance", "SUMO moves exactly one configured step"],
    ["2", "Observe", "Build a timestamped traffic snapshot"],
    ["3", "Route", "Refresh time costs and assess rerouting"],
    ["4", "Select owner", "Corridor or normal controller requests an action"],
    ["5", "Validate", "Safety filter checks phase and timing rules"],
    ["6", "Apply and record", "Adapter acts; evidence is stored before display"],
  ];
  const boxes = [];
  steps.forEach((st, i) => {
    const col = i < 3 ? 0 : 1;
    const row = i % 3;
    const x = col === 0 ? 84 : 680;
    const y = 158 + row * 147;
    const b = addBox(s, x, y, 505, 102, i === 4 ? C.paleAmber : C.paleTeal, { line: i === 4 ? C.amber : C.teal, lineWidth: 1.5 });
    addText(s, st[0], x + 20, y + 22, 45, 40, { size: 30, bold: true, color: i === 4 ? C.amber : C.teal });
    addText(s, st[1], x + 78, y + 15, 390, 32, { size: 22, bold: true, color: C.navy });
    addText(s, st[2], x + 78, y + 51, 392, 38, { size: 18, color: C.ink });
    boxes.push(b);
  });
  s.shapes.connect(boxes[0], boxes[1], { fromSide: "bottom", toSide: "top", kind: "straight", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  s.shapes.connect(boxes[1], boxes[2], { fromSide: "bottom", toSide: "top", kind: "straight", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  s.shapes.connect(boxes[2], boxes[3], { fromSide: "right", toSide: "left", kind: "elbow", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  s.shapes.connect(boxes[3], boxes[4], { fromSide: "bottom", toSide: "top", kind: "straight", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  s.shapes.connect(boxes[4], boxes[5], { fromSide: "bottom", toSide: "top", kind: "straight", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  addText(s, "Control invariant", 84, 618, 165, 26, { size: 18, bold: true, color: C.red });
  addText(s, "The dashboard, perception worker, controller, and repository cannot advance simulation time or bypass backend validation.", 250, 616, 940, 40, { size: 19, color: C.ink });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Algorithm 3 Integrated Control Loop and Figure 6.1."]);
}

// 10 — Methodology
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Methodology of work", 10, "Validation proceeds from definitions and baselines to integration and held-out evaluation"); addFooter(s);
  const img = await imageBytes(path.join(buildDir, "source_pages/p59-59.png"));
  s.images.add({ blob: img, contentType: "image/png", alt: "Research and evaluation workflow from the Manzil report", fit: "cover", crop: { left: 0.16, top: 0.47, right: 0.10, bottom: 0.16 }, position: { left: 58, top: 150, width: 680, height: 475 } });
  addText(s, "Methodological safeguards", 790, 154, 385, 36, { size: 26, bold: true, color: C.navy });
  addBullets(s, ["Freeze objectives, metrics, baselines, and exclusions before final runs.", "Keep recorded-video perception evidence separate from exact SUMO state.", "Validate fixed and rule-based controllers before training the RL policy.", "Use development, tuning, and held-out scenario families.", "Run matched seeds and retain failed, stopped, and no-route outcomes.", "Aggregate variability and component ablations before drawing conclusions."], 798, 214, 390, 330, { size: 20, spaceAfter: 10 });
  addBox(s, 790, 566, 390, 64, C.paleAmber, { line: "#EDD4A8", lineWidth: 1 });
  addText(s, "The workflow prevents a polished integrated demo from hiding a weak measurement, unsafe transition, or unstable baseline.", 810, 578, 350, 44, { size: 18, bold: true, color: C.tealDark });
  addNotes(s, ["Source image and content: Manzil Deliverable 2 report, Figure 5.1 and Chapter 5."]);
}

// 11 — Requirements and constraints
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Important requirements, constraints, and limitations", 11); addFooter(s);
  const cols = [
    ["Requirements", C.teal, ["Versioned traffic snapshots with source, time, unit, confidence, and validity", "Legal signal actions through one safety filter", "Stable route revisions with no-route handling and cancellation", "Reproducible manifests, metrics, checksums, and visible failures"]],
    ["Constraints", C.amber, ["One active ambulance in the core case", "Small validated network suitable for repeated runs", "Recorded video for perception validation, not citywide live sensing", "Finite hardware may require offline inference or a compact network"]],
    ["Limitations", C.red, ["Simulation results do not establish public-road performance", "Queue length remains a proxy without camera calibration", "Final tracker, RL hyperparameters, database, and hardware remain to be confirmed", "No authority approval, roadside integration, or field trial exists"]],
  ];
  cols.forEach((c, i) => {
    const x = 64 + i * 400;
    addText(s, c[0], x + 10, 150, 350, 38, { size: 28, bold: true, color: c[1] });
    addBox(s, x + 10, 196, 350, 5, c[1], { geometry: "rect", radius: "none" });
    addBullets(s, c[2], x + 10, 226, 350, 325, { size: 20, spaceAfter: 13 });
  });
  addBox(s, 74, 580, 1120, 62, C.pale, { line: C.line, lineWidth: 1 });
  addText(s, "Fallback principle", 96, 596, 170, 28, { size: 19, bold: true, color: C.navy });
  addText(s, "When data, maps, models, or routes fail validation, the system reports the condition or uses a declared fallback. It does not silently change the experiment.", 265, 593, 895, 40, { size: 19, color: C.ink });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Sections 2.7, 4.3–4.5, and 6.2."]);
}

// 12 — Interface
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Proposed graphical user interface", 12, "The interface makes configuration, evidence, warnings, and mission state visible without granting direct signal control"); addFooter(s);
  const img = await imageBytes(path.join(buildDir, "source_pages/p50-50.png"));
  s.images.add({ blob: img, contentType: "image/png", alt: "Traffic overview and perception-detail wireframes", fit: "contain", crop: { left: 0.13, top: 0.11, right: 0.12, bottom: 0.34 }, position: { left: 56, top: 150, width: 720, height: 476 } });
  addText(s, "Five planned screens", 822, 152, 330, 34, { size: 26, bold: true, color: C.navy });
  addBullets(s, ["Experiment configuration", "Traffic overview", "Perception and intersection detail", "Emergency dispatch and route", "Comparative analytics"], 830, 210, 330, 190, { size: 21, spaceAfter: 9 });
  addText(s, "Interface principles", 822, 430, 330, 34, { size: 24, bold: true, color: C.tealDark });
  addBullets(s, ["Warnings remain visible beside the map or metric.", "Provenance and freshness accompany estimated observations.", "Charts disclose run compatibility and failed runs.", "All figures are wireframes, not implemented screenshots."], 830, 476, 340, 142, { size: 18, spaceAfter: 7 });
  addNotes(s, ["Source image and content: Manzil Deliverable 2 report, Figures 4.3–4.7 and Section 4.8."]);
}

// 13 — Evaluation plan
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Planned evaluation", 13, "Each claim has a controlled comparison and a metric that exposes tradeoffs"); addFooter(s);
  const rows = [
    ["Perception", "Predictions versus held-out annotations", "Count error, tracking stability, queue-proxy error, throughput"],
    ["Normal control", "Fixed vs rule-adaptive vs one RL policy", "Delay, waiting, queues, throughput, fairness, interventions"],
    ["Routing", "Unassisted vs dynamic time-cost routing", "Ambulance travel time, excess delay, revisions, no-route rate"],
    ["Corridor", "Routing alone vs routing with moving priority", "Ambulance benefit, ordinary-traffic impact, recovery time"],
    ["Robustness", "Demand, incidents, seeds, and approved noise conditions", "Variability, failures, sensitivity, reproducibility artifacts"],
  ];
  addText(s, "Evaluation area", 72, 154, 210, 30, { size: 18, bold: true, color: C.muted });
  addText(s, "Controlled comparison", 322, 154, 400, 30, { size: 18, bold: true, color: C.muted });
  addText(s, "Primary evidence", 760, 154, 430, 30, { size: 18, bold: true, color: C.muted });
  rows.forEach((r, i) => {
    const y = 200 + i * 82;
    addText(s, r[0], 72, y, 220, 34, { size: 22, bold: true, color: i === 3 ? C.amber : C.tealDark });
    addText(s, r[1], 322, y, 395, 54, { size: 19, color: C.ink });
    addText(s, r[2], 760, y, 430, 54, { size: 19, color: C.ink });
    if (i < rows.length - 1) addBox(s, 72, y + 66, 1118, 1, C.line, { geometry: "rect", radius: "none" });
  });
  addBox(s, 70, 624, 1120, 42, C.paleAmber, { line: "#EDD4A8", lineWidth: 1 });
  addText(s, "Protocol: 900-second warm-up, 3,600-second measurement interval, and ten matched seeds; a pilot may increase but not reduce repetitions.", 92, 633, 1078, 24, { size: 18, bold: true, color: C.navy });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Chapter 5 and Table 5.1.", "The durations and matched-seed count are predeclared protocol settings, not experimental results."]);
}

// 14 — Roadmap
{
  const s = pres.slides.add(); s.background.fill = C.white; addHeader(s, "Development roadmap", 14, "Implementation proceeds in dependency order so later components cannot hide earlier faults"); addFooter(s);
  const phases = [
    ["D2 complete", "Research, SRS, architecture, methodology, diagrams, wireframes", C.green],
    ["Foundation", "Network validation, manifests, fixed controller, metric collection", C.teal],
    ["Research modules", "Perception evaluation, rule controller, RL training, dynamic routing", C.blue],
    ["Integration", "Corridor lifecycle, safety filter, dashboard, persistence", C.amber],
    ["Evaluation", "Matched held-out runs, ablations, error analysis, final conclusions", C.red],
  ];
  const boxes = [];
  phases.forEach((p, i) => {
    const x = 70 + i * 236;
    const b = addBox(s, x, 206, 196, 228, i === 0 ? C.paleTeal : "#F5F7F8", { line: p[2], lineWidth: 2 });
    addText(s, `0${i + 1}`, x + 18, 224, 50, 32, { size: 23, bold: true, color: p[2] });
    addText(s, p[0], x + 18, 272, 160, 48, { size: 23, bold: true, color: C.navy });
    addText(s, p[1], x + 18, 334, 160, 82, { size: 18, color: C.ink });
    boxes.push(b);
  });
  for (let i = 0; i < boxes.length - 1; i++) s.shapes.connect(boxes[i], boxes[i + 1], { fromSide: "right", toSide: "left", kind: "straight", line: { style: "solid", fill: C.line, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
  addText(s, "Decision gates", 72, 496, 180, 30, { size: 22, bold: true, color: C.navy });
  addBullets(s, ["Do not train RL until baseline actions, safety transitions, and metrics are stable.", "Do not interpret integrated results until the detector, routing, and corridor modules pass their own checks.", "Freeze final scenarios and metric definitions before held-out evaluation."], 80, 540, 1100, 102, { size: 20, spaceAfter: 8 });
  addNotes(s, ["Source: Manzil Deliverable 2 report, Figure 5.1 and Chapters 5–6."]);
}

// 15 — Closing
{
  const s = pres.slides.add(); s.background.fill = C.navy;
  addText(s, "Manzil", 72, 74, 600, 70, { size: 58, bold: true, color: C.white });
  addText(s, "A controlled platform for studying normal traffic control and one emergency mission", 76, 150, 940, 52, { size: 26, color: "#D6E5EE" });
  addBox(s, 76, 238, 86, 6, C.amber, { geometry: "rect", radius: "none" });
  addText(s, "What the project contributes", 76, 278, 420, 38, { size: 27, bold: true, color: C.white });
  addBullets(s, ["A traceable architecture that separates observation, decision, safe application, and evidence", "A staged method for comparing perception, normal control, routing, and corridor effects", "Clear scope boundaries that prevent simulation and wireframes from being presented as field deployment"], 82, 338, 690, 174, { size: 22, color: "#E8F0F5", spaceAfter: 13 });
  addBox(s, 840, 272, 350, 240, "#143B5E", { line: "#2D628A", lineWidth: 1 });
  addText(s, "Next milestone", 872, 300, 286, 34, { size: 24, bold: true, color: C.amber });
  addText(s, "Implement the validated foundation, then generate evidence through matched, repeatable experiments.", 872, 356, 286, 112, { size: 23, bold: true, color: C.white });
  addText(s, "Questions", 78, 602, 500, 54, { size: 40, bold: true, color: C.white });
  addText(s, "Muhammad Ali Mahoon  ·  Muzammil Ahmed Bhatti  ·  Mohammad Ibrahim Salman", 78, 668, 930, 22, { size: 15, color: "#AFC4D2" });
  addNotes(s, ["Source: Manzil Deliverable 2 report conclusions and project context."]);
}

await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });

for (const [i, slide] of pres.slides.items.entries()) {
  const png = await pres.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(previewDir, `slide-${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
}
const montage = await pres.export({ format: "webp", montage: true });
await fs.writeFile(path.join(buildDir, "montage.webp"), new Uint8Array(await montage.arrayBuffer()));

const draft = await PresentationFile.exportPptx(pres);
await draft.save(draftPath);

const requirements = {
  explicitTotalSlideCount: 15,
  requiredNativeTableOwnerSlides: [7],
  requiredNativeChartOwnerSlides: [],
};
const fontPolicy = { basis: "design", families: [FONT] };
await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath: draftPath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit", "--require-native-table-slide", "7"],
  requiredNativeTableOwnerSlides: [7],
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, "Manzil_Presentation.validation.json"),
});

console.log(finalPath);
