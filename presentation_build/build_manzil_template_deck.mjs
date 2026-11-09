import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "C:/Users/X1 Carbon/Desktop/7th Semester/FYP/fyp-kaam";
const SKILL = "C:/Users/X1 Carbon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11127/skills/presentations";
const TEMPLATE = path.join(ROOT, "template_for_presentation.pptx");
const BUILD = path.join(ROOT, "presentation_build", "template_redesign");
const PREVIEW = path.join(BUILD, "previews");
const DRAFT = path.join(BUILD, "Manzil_Template_Design_v5_draft.pptx");
const FINAL = path.join(ROOT, "presentation_output", "Manzil_Presentation_Clear_Workflow_v5.pptx");
const PYTHON = "C:/Users/X1 Carbon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const { makeNativeBulletParagraphs, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL, "container_tools", "artifact_tool_utils.mjs")).href
);

const W = 960;
const H = 540;
const TITLE = "Kulim Park";
const BODY = "Manrope";
const C = {
  ink: "#282421",
  brown: "#6D4A32",
  taupe: "#9A8B70",
  coral: "#E8937F",
  blush: "#F0D8D2",
  cream: "#E8E3D8",
  ivory: "#F8F5EF",
  white: "#FFFFFF",
  teal: "#3F7771",
  green: "#527A63",
  amber: "#B7803E",
  red: "#A85F59",
  grey: "#6F6A65",
  paleGreen: "#E4EDE5",
  paleAmber: "#F2E7D6",
  paleRed: "#F1DEDB",
};

async function bytes(file) {
  const b = await fs.readFile(file);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

function box(slide, x, y, w, h, fill, opts = {}) {
  const shape = slide.shapes.add({
    geometry: opts.geometry ?? "roundRect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: opts.line ?? fill, width: opts.lineWidth ?? 0 },
  });
  if ((opts.geometry ?? "roundRect") === "roundRect") shape.borderRadius = opts.radius ?? "rounded-md";
  return shape;
}

function text(slide, value, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: opts.typeface ?? BODY,
    fontSize: opts.size ?? 18,
    color: opts.color ?? C.ink,
    bold: opts.bold ?? false,
    alignment: opts.align ?? "left",
    verticalAlignment: opts.valign ?? "top",
    autoFit: opts.autoFit ?? "shrinkText",
  };
  return shape;
}

function bullets(slide, items, x, y, w, h, opts = {}) {
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
    typeface: BODY,
    fontSize: opts.size ?? 16,
    color: opts.color ?? C.ink,
    autoFit: "shrinkText",
  };
  return shape;
}

function title(slide, heading, number, subtitle = "") {
  text(slide, heading.toUpperCase(), 75, 42, 760, 56, { typeface: TITLE, size: 31, color: C.ink });
  if (subtitle) text(slide, subtitle, 77, 99, 735, 28, { size: 14, color: C.grey });
  text(slide, String(number).padStart(2, "0"), 846, 46, 45, 28, { typeface: TITLE, size: 18, color: C.brown, align: "right" });
  text(slide, "MANZIL  •  DELIVERABLE 2", 76, 507, 280, 14, { size: 9.5, color: C.taupe });
}

function notes(slide, lines) {
  slide.speakerNotes.text = lines.join("\n");
  slide.speakerNotes.setVisible(true);
}

function clearSlide(slide) {
  for (const shape of [...slide.shapes.items]) shape.delete();
  try { for (const image of [...slide.images.items]) image.delete(); } catch {}
  try { for (const table of [...slide.tables.items]) table.delete(); } catch {}
  try { for (const chart of [...slide.charts.items]) chart.delete(); } catch {}
}

function connect(slide, from, to, opts = {}) {
  return slide.shapes.connect(from, to, {
    fromSide: opts.fromSide ?? "right",
    toSide: opts.toSide ?? "left",
    kind: opts.kind ?? "straight",
    line: { style: "solid", fill: opts.color ?? C.taupe, width: opts.width ?? 1.5 },
    tail: { type: "triangle", width: "sm", length: "sm" },
  });
}

const deck = await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));
const sourceSlides = [...deck.slides.items];
const sourceNumbers = [1, 10, 12, 17, 47, 15, 13, 21, 20, 48, 26, 60];
const slides = sourceNumbers.map((n) => sourceSlides[n - 1].duplicate());
for (const source of sourceSlides) source.delete();
slides.forEach((slide, i) => slide.moveTo(i));
slides.forEach(clearSlide);

// 1 — cover
{
  const s = slides[0];
  text(s, "MANZIL", 80, 126, 800, 80, { typeface: TITLE, size: 52, color: C.ink, align: "center" });
  text(s, "INTELLIGENT TRAFFIC & EMERGENCY ROUTING", 100, 205, 760, 36, { typeface: TITLE, size: 21, color: C.brown, align: "center" });
  text(s, "Final Year Project • Deliverable 2", 100, 249, 760, 25, { size: 14, color: C.grey, align: "center" });
  box(s, 390, 291, 180, 2, C.coral, { geometry: "rect" });
  text(s, "Muhammad Ali Mahoon  •  23L-0531\nMuzammil Ahmed Bhatti  •  23L-0688\nMohammad Ibrahim Salman  •  23L-0723", 185, 316, 590, 78, { size: 15.5, color: C.ink, align: "center" });
  text(s, "Supervisor: Miss Umm-e-Ammarah", 180, 407, 600, 25, { size: 14.5, color: C.brown, align: "center" });
  text(s, "National University of Computer and Emerging Sciences", 160, 466, 640, 20, { size: 12, color: C.grey, align: "center" });
  notes(s, ["Project and team details are taken from the Manzil Deliverable 2 report."]);
}

// 2 — problem statement
{
  const s = slides[1]; title(s, "Problem statement", 2, "Emergency mobility fails when sensing, routing, signal priority, and recovery are treated as separate tasks.");
  text(s, "THE GAP", 82, 161, 190, 30, { typeface: TITLE, size: 19, color: C.brown });
  text(s, "An ambulance may receive a fast route yet remain blocked at signals. A priority action may help the ambulance but create unsafe transitions or excessive delay for ordinary traffic.", 82, 202, 360, 138, { size: 20, color: C.ink });
  box(s, 80, 371, 365, 74, C.paleRed, { line: C.blush, lineWidth: 0.8 });
  text(s, "Manzil studies the complete chain in one controlled and reproducible environment.", 104, 389, 320, 42, { size: 17, bold: true, color: C.red, align: "center" });
  const items = [
    ["01", "Observe traffic", "Create fresh traffic-state evidence"],
    ["02", "Select a route", "Use current time-based road costs"],
    ["03", "Create a corridor", "Apply safe and bounded priority"],
    ["04", "Measure impact", "Compare emergency benefit and network cost"],
  ];
  items.forEach((d, i) => {
    const y = 151 + i * 78;
    text(s, d[0], 522, y + 1, 40, 22, { typeface: TITLE, size: 15, color: i === 2 ? C.coral : C.taupe });
    text(s, d[1], 575, y, 260, 24, { size: 17.5, bold: true, color: C.ink });
    text(s, d[2], 575, y + 27, 300, 32, { size: 14, color: C.grey });
  });
  const signalCar = await bytes(path.join(ROOT, "presentation_build", "assets", "traffic_signal_car.png"));
  s.images.add({
    blob: signalCar,
    contentType: "image/png",
    alt: "Minimal traffic signal with a compact car",
    fit: "contain",
    position: { left: 452, top: 327, width: 66, height: 112 },
  });
  notes(s, ["Source: Manzil Deliverable 2 report, problem statement and elaboration sections.", "The traffic signal and car illustration is AI-generated for this presentation."]);
}

// 3 — problem elaboration
{
  const s = slides[2]; title(s, "One connected decision chain", 3, "A result is credible only when every upstream decision remains traceable.");
  const data = [
    ["SENSE", "Counts, queues,\nand timestamps"],
    ["DECIDE", "Control action\nand route version"],
    ["VALIDATE", "Legal phase and\ncorridor ownership"],
    ["ACT", "Advance the\nsimulation"],
    ["RECORD", "Metrics, failures,\nand recovery"],
  ];
  const nodes = [];
  data.forEach((d, i) => {
    const x = 57 + i * 177;
    const fill = i === 2 ? C.paleAmber : (i % 2 ? C.cream : C.ivory);
    const n = box(s, x, 205, 142, 119, fill, { line: i === 2 ? C.amber : C.taupe, lineWidth: 1.2 });
    text(s, String(i + 1).padStart(2, "0"), x + 14, 218, 30, 18, { typeface: TITLE, size: 13, color: i === 2 ? C.amber : C.teal });
    text(s, d[0], x + 14, 250, 114, 24, { size: 16, bold: true, color: C.ink, align: "center" });
    text(s, d[1], x + 12, 280, 118, 36, { size: 12.7, color: C.grey, align: "center" });
    nodes.push(n);
  });
  for (let i = 0; i < nodes.length - 1; i++) connect(s, nodes[i], nodes[i + 1], { color: C.coral, width: 1.4 });
  text(s, "Why this matters", 82, 370, 210, 25, { typeface: TITLE, size: 17, color: C.brown });
  text(s, "Stale observations alter route costs. A route change alters which intersection may receive priority. Priority can reduce ambulance delay while shifting delay to ordinary traffic. Manzil records each dependency before comparing outcomes.", 82, 405, 790, 68, { size: 16.5, color: C.ink });
  notes(s, ["Source: Manzil Deliverable 2 report, connected problem and evidence-chain discussion."]);
}

// 4 — scope
{
  const s = slides[3]; title(s, "Project scope", 4, "The prototype supports controlled research; it is not an operational city deployment.");
  text(s, "INCLUDED", 105, 159, 300, 27, { typeface: TITLE, size: 19, color: C.green, align: "center" });
  bullets(s, [
    "Recorded-video traffic observation",
    "Repeatable multi-intersection SUMO network",
    "Fixed, adaptive, and one feasible RL controller",
    "One ambulance with dynamic routing and priority",
    "Dashboard, run records, and comparison evidence",
  ], 105, 205, 330, 225, { size: 16.5, spaceAfter: 8 });
  box(s, 480, 154, 1.2, 305, C.coral, { geometry: "rect" });
  text(s, "OUTSIDE THE CURRENT PROJECT", 530, 159, 330, 27, { typeface: TITLE, size: 19, color: C.red, align: "center" });
  bullets(s, [
    "Live government CCTV integration",
    "Direct control of public traffic signals",
    "Multiple emergency fleets across Lahore",
    "Accident, plate, or face recognition",
    "Claims about patient outcomes or field readiness",
  ], 530, 205, 330, 225, { size: 16.5, spaceAfter: 8 });
  text(s, "All conclusions remain limited to the declared simulation or recorded-video condition.", 140, 463, 680, 24, { size: 13.5, color: C.brown, align: "center" });
  notes(s, ["Source: Manzil Deliverable 2 report, project scope and exclusions."]);
}

// 5 — goals and milestone plan
{
  const s = slides[4]; title(s, "Goals achieved and future goals", 5, "A milestone view makes completed design work and dependent implementation work easy to distinguish.");
  const phases = [
    ["01", "RESEARCH & DESIGN", "Completed", C.green],
    ["02", "NETWORK & BASELINES", "Next", C.teal],
    ["03", "SYSTEM INTEGRATION", "Future", C.coral],
    ["04", "EVALUATION", "Future", C.amber],
  ];
  const trafficArt = await bytes(path.join(ROOT, "presentation_build", "assets", "traffic_ambulance_corridor.png"));
  s.images.add({
    blob: trafficArt,
    contentType: "image/png",
    alt: "Minimal illustration of cars opening a corridor for an ambulance",
    fit: "contain",
    position: { left: 674, top: 128, width: 205, height: 82 },
  });
  box(s, 130, 271, 700, 2, C.taupe, { geometry: "rect" });
  phases.forEach((p, i) => {
    const x = 105 + i * 210;
    box(s, x + 52, 245, 54, 54, i === 0 ? C.green : C.ivory, { geometry: "ellipse", line: p[3], lineWidth: 1.7 });
    text(s, p[0], x + 52, 259, 54, 22, { typeface: TITLE, size: 16, color: i === 0 ? C.white : p[3], align: "center" });
    text(s, p[1], x, 326, 160, 42, { size: 15.5, bold: true, color: C.ink, align: "center" });
    text(s, p[2], x + 20, 378, 120, 23, { size: 13, color: p[3], bold: true, align: "center" });
  });
  box(s, 105, 423, 750, 36, C.cream, { line: C.taupe, lineWidth: 0.7 });
  box(s, 105, 423, 185, 36, C.paleGreen, { line: C.green, lineWidth: 0.7 });
  text(s, "Completed", 105, 432, 185, 18, { size: 12.5, color: C.green, bold: true, align: "center" });
  text(s, "Implementation and evaluation proceed after each dependency is stable and testable.", 307, 431, 530, 20, { size: 12.5, color: C.grey, align: "center" });
  notes(s, ["Completed means Deliverable 2 research, requirements, architecture, and interface design. No unverified implementation or performance claim is made.", "The ambulance and cars illustration is AI-generated for this presentation."]);
}

// 6 — R&D and related applications
{
  const s = slides[5]; title(s, "Development and R&D", 6, "Prior work defines strong baselines and design rules; it does not become a claimed Manzil result.");
  const groups = [
    ["PERCEPTION", "YOLO, DeepSORT, ByteTrack", "Validate complete counts and queue estimates, not detector output alone."],
    ["TRAFFIC CONTROL", "Max-pressure, PressLight, CoLight", "Establish fixed and transparent adaptive baselines before one RL policy."],
    ["ROUTING & PRIORITY", "Dijkstra, A*, SUMO + TraCI", "Use fresh time costs, stable rerouting, and a bounded emergency corridor."],
  ];
  groups.forEach((g, i) => {
    const x = 70 + i * 295;
    text(s, `0${i + 1}`, x, 166, 42, 25, { typeface: TITLE, size: 18, color: [C.teal, C.brown, C.coral][i] });
    text(s, g[0], x, 207, 245, 28, { size: 18, bold: true, color: C.ink });
    text(s, g[1], x, 247, 245, 38, { size: 14, color: C.brown });
    box(s, x, 297, 245, 1.2, C.coral, { geometry: "rect" });
    text(s, g[2], x, 321, 245, 92, { size: 15, color: C.grey });
  });
  text(s, "Related applications", 76, 447, 170, 22, { typeface: TITLE, size: 16.5, color: C.brown });
  text(s, "SUMO and TraCI form the controlled simulation environment. CityFlow is a documented alternative; PressLight and CoLight inform the learned-control design.", 250, 443, 625, 41, { size: 13.5, color: C.ink });
  notes(s, ["Sources summarized in the Manzil Deliverable 2 literature review: YOLO, DeepSORT, ByteTrack, max-pressure control, PressLight, CoLight, Dijkstra, A*, SUMO, and TraCI."]);
}

// 7 — concise professional bullets
{
  const s = slides[6]; title(s, "Requirements, constraints, and limitations", 7, "Short operational statements define what must remain true during implementation and evaluation.");
  const groups = [
    ["REQUIREMENTS", C.teal, [
      "One validated owner applies each signal action.",
      "Every observation carries source and simulation time.",
      "Routes use the active version and current ambulance position.",
    ]],
    ["CONSTRAINTS", C.amber, [
      "The core scenario contains one ambulance.",
      "The validated SUMO network remains intentionally small.",
      "Recorded video stays separate from simulator ground truth.",
    ]],
    ["LIMITATIONS", C.red, [
      "Simulation does not prove public-road performance.",
      "Queue estimates depend on camera viewpoint and calibration.",
      "Final model performance has not yet been measured.",
    ]],
  ];
  groups.forEach((g, i) => {
    const x = 66 + i * 295;
    box(s, x, 158, 260, 300, C.ivory, { line: g[1], lineWidth: 1.2 });
    box(s, x, 158, 260, 45, i === 0 ? C.paleGreen : i === 1 ? C.paleAmber : C.paleRed, { line: g[1], lineWidth: 0.8 });
    text(s, g[0], x + 18, 170, 224, 23, { typeface: TITLE, size: 16, color: g[1], align: "center" });
    bullets(s, g[2], x + 20, 226, 218, 190, { size: 16, spaceAfter: 13, marginLeft: 17, hanging: 7 });
  });
  text(s, "Fallback rule: invalid data, routes, timing, or model output must stop the run or activate a declared baseline.", 100, 472, 760, 24, { size: 13, color: C.brown, align: "center" });
  notes(s, ["Source: Manzil Deliverable 2 report, software requirements and design constraints."]);
}

// 8 — one continuous system workflow
{
  const s = slides[7]; title(s, "How Manzil works", 8, "A single control loop connects traffic observation, ambulance priority, safe signal control, and the mobile view.");

  const stages = [
    ["1", "OBSERVE", "Camera + SUMO", "Detector / TraCI", C.teal],
    ["2", "BUILD STATE", "Traffic and queues", "State service", C.teal],
    ["3", "DECIDE", "Route + controller", "Router / policy", C.coral],
    ["4", "MAKE WAY", "Safe green corridor", "Safety manager", C.amber],
    ["5", "APPLY", "Signals change", "TraCI / SUMO", C.green],
    ["6", "SHOW RESULT", "App + evaluation", "Dashboard / evidence", C.brown],
  ];

  // One uninterrupted visual path. Every label belongs to the same workflow.
  box(s, 93, 286, 774, 8, C.cream, { geometry: "rect" });
  stages.forEach((d, i) => {
    const x = 70 + i * 148;
    box(s, x + 42, 261, 58, 58, d[4], { geometry: "ellipse", line: C.white, lineWidth: 2 });
    text(s, d[0], x + 42, 277, 58, 24, { typeface: TITLE, size: 19, bold: true, color: C.white, align: "center" });
    text(s, d[1], x, 178, 142, 27, { typeface: TITLE, size: 17, bold: true, color: d[4], align: "center" });
    text(s, d[2], x, 211, 142, 25, { size: 15, color: C.ink, align: "center" });
    text(s, d[3], x, 341, 142, 22, { size: 12.8, color: C.grey, align: "center" });
    if (i < stages.length - 1) text(s, "→", x + 113, 269, 42, 32, { typeface: TITLE, size: 25, color: C.taupe, align: "center" });
  });

  const signalArt = await bytes(path.join(ROOT, "presentation_build", "assets", "traffic_signal_intersection.png"));
  s.images.add({
    blob: signalArt,
    contentType: "image/png",
    alt: "Intersection where coordinated traffic signals create a corridor for an ambulance",
    fit: "contain",
    position: { left: 465, top: 372, width: 126, height: 105 },
  });
  text(s, "AMBULANCE MISSION", 319, 400, 145, 20, { typeface: TITLE, size: 13.5, color: C.coral, align: "right" });
  text(s, "destination and live position", 305, 425, 159, 20, { size: 12.3, color: C.grey, align: "right" });
  text(s, "NORMAL TRAFFIC", 593, 400, 145, 20, { typeface: TITLE, size: 13.5, color: C.green });
  text(s, "continues after safe recovery", 593, 425, 175, 20, { size: 12.3, color: C.grey });
  text(s, "↺  Each SUMO step creates the next traffic observation", 270, 474, 420, 23, { size: 13.5, color: C.brown, align: "center" });
  notes(s, ["This is one continuous diagram, not separate architecture panels.", "Read left to right: Manzil observes the current network, creates a fresh traffic state, selects normal control and an ambulance route, validates a safe green corridor, applies the signal action through TraCI, then shows the result and stores evidence for evaluation.", "The next SUMO step returns to observation, forming the closed control loop. The mobile interface displays the route, corridor state, warnings, and run status but does not directly advance the simulator."]);
}

// 9 — GUI concept
{
  const s = slides[8]; title(s, "Graphical user interface", 9, "Generated concept screens show the intended mobile experience, not a completed application screenshot.");
  const image = await bytes(path.join(ROOT, "presentation_build", "assets", "manzil_mobile_app_concept.png"));
  s.images.add({
    blob: image,
    contentType: "image/png",
    alt: "Generated Manzil mobile interface concept with traffic map, ambulance route, corridor status, and ETA",
    fit: "contain",
    position: { left: 385, top: 137, width: 515, height: 348 },
  });
  text(s, "THE OPERATOR MUST SEE", 78, 165, 260, 26, { typeface: TITLE, size: 17, color: C.brown });
  bullets(s, [
    "Ambulance position, destination, and remaining route",
    "Next signal and current emergency-corridor state",
    "Congestion, queue, incident, and data-freshness warnings",
    "Controller, route version, run identifier, and failures",
  ], 78, 214, 270, 205, { size: 16, spaceAfter: 10 });
  text(s, "UI CONCEPT", 78, 451, 130, 20, { size: 12.5, bold: true, color: C.coral });
  text(s, "Final visual design remains subject to implementation and usability review.", 78, 474, 285, 30, { size: 13.5, color: C.grey });
  notes(s, ["The mobile visual is an AI-generated interface concept prepared for this presentation. It is not evidence of implementation."]);
}

// 10 — methodology
{
  const s = slides[9]; title(s, "Methodology of work", 10, "Each stage produces evidence that becomes the input and acceptance check for the next stage.");
  const steps = [
    ["01", "PREPARE", "Validate network, demand, signal plans, video provenance, and metrics."],
    ["02", "BASELINE", "Run fixed-time and transparent adaptive control before learning."],
    ["03", "INTEGRATE", "Add routing, bounded priority, cancellation, and recovery."],
    ["04", "EVALUATE", "Use matched seeds and demand; retain failures and trade-offs."],
  ];
  box(s, 130, 270, 700, 1.4, C.taupe, { geometry: "rect" });
  steps.forEach((d, i) => {
    const x = 82 + i * 212;
    box(s, x + 52, 239, 62, 62, C.ivory, { geometry: "ellipse", line: [C.teal, C.brown, C.coral, C.amber][i], lineWidth: 1.6 });
    text(s, d[0], x + 52, 257, 62, 24, { typeface: TITLE, size: 16, color: [C.teal, C.brown, C.coral, C.amber][i], align: "center" });
    text(s, d[1], x, 329, 165, 24, { size: 16, bold: true, color: C.ink, align: "center" });
    text(s, d[2], x, 366, 165, 78, { size: 13.5, color: C.grey, align: "center" });
  });
  notes(s, ["Source: Manzil Deliverable 2 report, methodology and evaluation chapters."]);
}

// 11 — evaluation plan
{
  const s = slides[10]; title(s, "Evaluation plan", 11, "Success is measured across emergency movement, ordinary traffic, safety, reproducibility, and runtime.");
  const metrics = [
    ["AMBULANCE", "Travel time and excess delay"],
    ["NETWORK", "Delay, waiting time, queues, fairness"],
    ["ROUTING", "Reroutes, freshness, and stability"],
    ["SAFETY", "Blocked actions and legal transitions"],
  ];
  metrics.forEach((m, i) => {
    const x = 72 + i * 215;
    text(s, m[0], x, 181, 170, 25, { typeface: TITLE, size: 16.5, color: [C.teal, C.brown, C.coral, C.amber][i], align: "center" });
    box(s, x + 55, 226, 60, 60, C.ivory, { geometry: "ellipse", line: [C.teal, C.brown, C.coral, C.amber][i], lineWidth: 1.5 });
    text(s, ["A", "N", "R", "S"][i], x + 55, 243, 60, 23, { typeface: TITLE, size: 17, color: [C.teal, C.brown, C.coral, C.amber][i], align: "center" });
    text(s, m[1], x, 315, 170, 62, { size: 15, color: C.ink, align: "center" });
  });
  box(s, 155, 414, 650, 53, C.cream, { line: C.taupe, lineWidth: 0.8 });
  text(s, "Decision rule", 176, 430, 118, 22, { size: 13, bold: true, color: C.brown });
  text(s, "Report positive, negative, and mixed outcomes under the same declared conditions.", 300, 429, 480, 24, { size: 14, color: C.ink, align: "center" });
  notes(s, ["No performance figures are claimed because final implementation experiments have not yet been completed."]);
}

// 12 — close
{
  const s = slides[11];
  text(s, "MANZIL", 110, 126, 740, 63, { typeface: TITLE, size: 45, color: C.ink, align: "center" });
  text(s, "A controlled platform for studying traffic management and one emergency mission", 170, 203, 620, 52, { size: 17, color: C.brown, align: "center" });
  box(s, 392, 282, 176, 2, C.coral, { geometry: "rect" });
  text(s, "QUESTIONS", 110, 325, 740, 60, { typeface: TITLE, size: 34, color: C.ink, align: "center" });
  box(s, 180, 418, 600, 42, C.cream, { line: C.taupe, lineWidth: 0.6 });
  text(s, "Muhammad Ali Mahoon  •  Muzammil Ahmed Bhatti  •  Mohammad Ibrahim Salman", 198, 429, 564, 20, { size: 11.5, color: C.grey, align: "center" });
  notes(s, ["Closing slide."]);
}

await fs.mkdir(BUILD, { recursive: true });
await fs.mkdir(PREVIEW, { recursive: true });
await fs.mkdir(path.dirname(FINAL), { recursive: true });

for (const [i, slide] of slides.entries()) {
  const png = await deck.export({ slide, format: "png", scale: 1.35 });
  await fs.writeFile(path.join(PREVIEW, `slide-${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
}
const montage = await deck.export({ format: "webp", montage: { columns: 3, width: 1800, gap: 18, padding: 18, background: "#E8E3D8" } });
await fs.writeFile(path.join(BUILD, "montage.webp"), new Uint8Array(await montage.arrayBuffer()));
await (await PresentationFile.exportPptx(deck)).save(DRAFT);

const templateHash = crypto.createHash("sha256").update(await fs.readFile(TEMPLATE)).digest("hex");
const result = await finalizePresentation({
  workspaceDir: ROOT,
  explicitTotalSlideCount: 12,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  verifyArtifactToolImport: true,
  candidatePath: DRAFT,
  finalPath: FINAL,
  pythonExecutable: PYTHON,
  integrityValidatorPath: path.join(SKILL, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "9144000,5143500",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: {
    basis: "reference",
    families: [TITLE, BODY],
    referencePath: TEMPLATE,
    referenceSha256: templateHash,
  },
  receiptPath: path.join(BUILD, "Manzil_Presentation_Clear_Workflow_v5.validation.json"),
});

console.log(JSON.stringify({ FINAL, DRAFT, PREVIEW, result }, null, 2));
