// Builds the Deliverable III slides: presentation_output/Manzil_D3_Presentation.pptx
// Run from this folder:  npm install  (once), then  node build_d3_deck.js
// Every number comes from the report (Chapters 7, 9, 10) and results/*/README.md.
// To change the look later, edit THEME (colours, fonts) and the layouts in defineLayouts();
// the slide content below does not need to change.
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("./apply_theme.js");

const ROOT = path.resolve(__dirname, "..", "..");
const FIG = path.join(ROOT, "Manzil_D2_Report", "figures", "results");
const OUT = path.join(ROOT, "presentation_output", "Manzil_D3_Presentation.pptx");

// Colours of the report's figures: blue, teal (green signal), amber, red.
const THEME = {
  name: "Manzil D3",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "17242B", lt1: "FFFFFF", dk2: "184E77", lt2: "EEF3F6",
    accent1: "184E77", accent2: "2A9D8F", accent3: "E9C46A", accent4: "D1495B",
    accent5: "5C6B73", accent6: "8FB8DE", hlink: "184E77", folHlink: "5C6B73",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Muhammad Ali Mahoon, Muzammil Ahmed Bhatti, Mohammad Ibrahim Salman";
pres.title = "Manzil: Intelligent Traffic and Emergency Routing - Deliverable III";
const C = pres.SchemeColor;

const W = 13.333;
const MX = 0.6; // side margin

function defineLayouts() {
  pres.defineSlideMaster({
    title: "MZ_TITLE",
    background: { color: HEX.dk1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 1.9, w: 9.2, h: 1.3,
        fontSize: 60, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "subtitle", type: "body", x: MX, y: 3.25, w: 9.2, h: 0.7,
        fontSize: 26, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "MZ_CONTENT",
    background: { color: HEX.lt1 },
    margin: [0.5, 0.6, 0.6, 0.6],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: W - 2 * MX, h: 0.75,
        fontSize: 36, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "msg", type: "body", x: MX, y: 1.1, w: W - 2 * MX, h: 0.5,
        fontSize: 18, color: C.accent5, valign: "top", margin: 0 }, text: "" } },
      { text: { text: "Manzil  |  F26-104  |  Deliverable III", options: { x: MX, y: 7.0, w: 6, h: 0.3,
        fontSize: 10, color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: W - MX - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
  });
}

// ---------- small drawing helpers (scheme colours only, fresh option objects each call) ----------
function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill },
    line: { color: fill, width: 0 }, rectRadius: 0.12, objectName: name });
}
function badge(slide, x, y, label, fill, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.5, h: 0.5, fill: { color: fill },
    line: { color: fill, width: 0 }, objectName: name });
  slide.addText(label, { x, y, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.background1,
    align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: name + " label" });
}
function txt(slide, text, x, y, w, h, o = {}) {
  slide.addText(text, { x, y, w, h, fontSize: o.size ?? 16, bold: o.bold ?? false,
    italic: o.italic ?? false, color: o.color ?? C.text1, align: o.align ?? "left",
    valign: o.valign ?? "top", margin: o.margin ?? 0, isTextBox: true, objectName: o.name ?? "text",
    paraSpaceAfter: o.paraSpaceAfter ?? 0 });
}
function bullets(slide, items, x, y, w, h, o = {}) {
  const runs = items.map((t, i) => ({ text: t, options: { bullet: true,
    breakLine: i < items.length - 1 } }));
  slide.addText(runs, { x, y, w, h, fontSize: o.size ?? 16, color: o.color ?? C.text1,
    valign: "top", margin: 0, paraSpaceAfter: 8, isTextBox: true, objectName: o.name ?? "bullets" });
}
function lights(slide, x, y, d, name) { // the traffic-light motif
  [C.accent4, C.accent3, C.accent2].forEach((col, i) => slide.addShape(pres.shapes.OVAL, {
    x, y: y + i * (d + 0.18), w: d, h: d, fill: { color: col }, line: { color: col, width: 0 },
    objectName: `${name} ${["red", "amber", "green"][i]}` }));
}
function content(section, title, msg) {
  const s = pres.addSlide({ masterName: "MZ_CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  s.addText(msg, { placeholder: "msg" });
  return s;
}
function barChart(slide, labels, series, x, y, w, h, title, colors, name) {
  slide.addChart(pres.charts.BAR, series.map((s) => ({ name: s.name, labels, values: s.values })), {
    x, y, w, h, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
    chartColors: colors, showTitle: true, title, titleFontSize: 14, titleColor: HEX.dk1,
    titleFontFace: "+mn-lt", showLegend: series.length > 1, legendPos: "b", legendFontSize: 12,
    legendFontFace: "+mn-lt", legendColor: HEX.dk1,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.0",
    catAxisLabelFontSize: 12, catAxisLabelColor: HEX.accent5, catAxisLabelFontFace: "+mn-lt",
    valAxisLabelFontSize: 11, valAxisLabelColor: HEX.accent5, valAxisLabelFontFace: "+mn-lt",
    valAxisTitle: "seconds", showValAxisTitle: true, valAxisTitleFontSize: 11,
    valAxisTitleColor: HEX.accent5, valGridLine: { color: "D9E1E6", size: 0.75 },
    catGridLine: { style: "none" }, objectName: name });
}

defineLayouts();

// ---------- 1. Title ----------
pres.addSection({ title: "Opening" });
{
  const s = pres.addSlide({ masterName: "MZ_TITLE", sectionTitle: "Opening" });
  s.addText("MANZIL", { placeholder: "title" });
  s.addText("Intelligent Traffic & Emergency Routing", { placeholder: "subtitle" });
  txt(s, "Final Year Project  |  Deliverable III  |  F26-104", MX, 4.25, 9, 0.4,
    { size: 18, color: C.background1, name: "deliverable line" });
  txt(s, "Muhammad Ali Mahoon (23L-0531)   Muzammil Ahmed Bhatti (23L-0688)   Mohammad Ibrahim Salman (23L-0723)",
    MX, 5.3, 11.5, 0.4, { size: 15, color: C.accent6, name: "team" });
  txt(s, "Supervisor: Miss Umm-e-Ammarah   |   22 November 2026", MX, 5.75, 11.5, 0.4,
    { size: 15, color: C.accent6, name: "supervisor and date" });
  lights(s, 11.3, 1.5, 0.75, "traffic light");
  s.addNotes("Introduce the team and the project. Deliverable 2 was the design; this deliverable shows what we built in FYP-I and what we measured.");
}

// ---------- 2. At a glance ----------
{
  const s = content("Opening", "FYP-I at a glance", "Designed in Deliverable 2, built and measured in FYP-I");
  const stats = [
    ["-9 to -11%", "mean travel time with the DQN signal controller vs tuned fixed-time", C.accent1],
    ["-49 to -53%", "ambulance travel time with live rerouting around an obstruction", C.accent2],
    ["-34 to -59%", "ambulance travel time with the moving green corridor", C.accent4],
    ["0.799", "detection mAP50 of the fine-tuned YOLO11s on UA-DETRAC test video", C.text2],
  ];
  const cw = 2.85, gap = 0.2;
  stats.forEach(([big, label, col], i) => {
    const x = MX + i * (cw + gap);
    card(s, x, 2.0, cw, 3.1, `stat card ${i + 1}`);
    txt(s, big, x + 0.25, 2.3, cw - 0.5, 1.0, { size: 36, bold: true, color: col, name: `stat ${i + 1}` });
    txt(s, label, x + 0.25, 3.3, cw - 0.5, 1.5, { size: 15, color: C.text1, name: `stat label ${i + 1}` });
  });
  card(s, MX, 5.45, W - 2 * MX, 1.15, "evidence strip", C.background1);
  bullets(s, [
    "147 automated tests pass; no unsafe signal state in any reported run",
    "Evidence: repeated, seeded SUMO runs on a synthetic 3x3 grid and public UA-DETRAC video, not Lahore roads yet",
  ], MX + 0.1, 5.55, W - 2 * MX - 0.2, 1.0, { size: 15, name: "evidence bullets" });
  s.addNotes("Main message: every component of the design now exists and was measured against a baseline on held-out seeds. Be clear that results are from a synthetic grid and public video.");
}

// ---------- 3. What we built ----------
pres.addSection({ title: "System" });
{
  const s = content("System", "What we built", "One simulation core, one safety filter, and every decision recorded");
  const mods = [
    ["1", "Simulation core", "SUMO 1.28 grid; one adapter is the only code that touches SUMO", C.accent1],
    ["2", "Signal controllers", "Fixed-time, pressure-based adaptive, and a parameter-sharing Double DQN", C.accent1],
    ["3", "Safety filter", "Every signal change passes minimum green, yellow and all-red", C.accent4],
    ["4", "Ambulance routing", "Dijkstra and A* on live travel-time costs; reroutes on closures", C.accent2],
    ["5", "Green corridor", "Holds the next two junctions green for the ambulance, then recovers", C.accent2],
    ["6", "Vision pipeline", "YOLO11s + ByteTrack counting on Kaggle GPUs; live React dashboard", C.text2],
  ];
  const cw = 3.85, ch = 2.2, gx = 0.3, gy = 0.3;
  mods.forEach(([n, head, body, col], i) => {
    const x = MX + (i % 3) * (cw + gx), y = 1.95 + Math.floor(i / 3) * (ch + gy);
    card(s, x, y, cw, ch, `module card ${n}`);
    badge(s, x + 0.25, y + 0.25, n, col, `module badge ${n}`);
    txt(s, head, x + 0.9, y + 0.28, cw - 1.1, 0.45, { size: 20, bold: true, color: C.text2, name: `module title ${n}` });
    txt(s, body, x + 0.25, y + 0.95, cw - 0.5, 1.1, { size: 15, name: `module text ${n}` });
  });
  s.addNotes("Walk through the six modules. The key design rule: controllers and the corridor only request a phase; the safety filter decides, and only the adapter talks to SUMO.");
}

// ---------- 4. Test track ----------
{
  const s = content("System", "The test track", "A synthetic 3x3 SUMO grid with seeded demand, so every run can be repeated");
  s.addImage({ path: path.join(FIG, "dashboard_01_idle.png"), x: MX, y: 1.85, w: 6.5, h: 4.06,
    altText: "Dashboard map of the 3x3 grid with nine signalised junctions A0 to C2", objectName: "grid map" });
  s.addTable([
    [{ text: "Demand profile", options: { bold: true, color: C.background1, fill: { color: C.accent1 } } },
     { text: "Vehicles per hour per entry road", options: { bold: true, color: C.background1, fill: { color: C.accent1 } } }],
    ["Light", "200"], ["Medium", "400"], ["Heavy", "600"], ["Uneven", "800 north-south, 100 east-west"],
  ], { x: 7.5, y: 1.85, w: 5.2, colW: [1.7, 3.5], fontSize: 14, color: C.text1,
    border: { type: "solid", pt: 0.75, color: "D9E1E6" }, rowH: 0.42, margin: 0.08, objectName: "demand table" });
  bullets(s, [
    "200 m blocks, 2 lanes each way, 50 km/h, 9 signals",
    "Training seeds 1001+, checkpoint selection 100-101",
    "Evaluation seeds 0-4, never used for tuning",
    "Measure 3,600 s after a 900 s warm-up",
  ], 7.5, 4.25, 5.2, 2.3, { size: 15, name: "track facts" });
  s.addNotes("Why synthetic first: it lets us validate controllers, routing and corridor before cleaning a real map. Stress the seed discipline: evaluation seeds were never used to tune anything.");
}

// ---------- 5. Safety ----------
{
  const s = content("System", "Safety comes first", "Controllers only request a phase; the safety filter decides when it is applied");
  const steps = [["Request", C.accent5], ["Min green 10 s", C.accent2], ["Yellow 3 s", C.accent3],
    ["All-red 2 s", C.accent4], ["New green", C.accent2]];
  const bw = 2.2, gap = 0.3;
  steps.forEach(([label, col], i) => {
    const x = MX + i * (bw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.0, w: bw, h: 0.9, fill: { color: col },
      line: { color: col, width: 0 }, rectRadius: 0.12, objectName: `step ${i + 1}` });
    txt(s, label, x, 2.0, bw, 0.9, { size: 18, bold: true, color: i === 2 ? C.text1 : C.background1,
      align: "center", valign: "middle", name: `step label ${i + 1}` });
    if (i < steps.length - 1) {
      s.addShape(pres.shapes.RIGHT_ARROW, { x: x + bw + 0.05, y: 2.3, w: 0.2, h: 0.3,
        fill: { color: C.accent5 }, line: { color: C.accent5, width: 0 }, objectName: `arrow ${i + 1}` });
    }
  });
  card(s, MX, 3.35, 5.9, 3.2, "guards card");
  txt(s, "Extra guards", MX + 0.3, 3.55, 5.3, 0.45, { size: 20, bold: true, color: C.text2, name: "guards title" });
  bullets(s, [
    "Maximum red 90 s: the filter forces service of a waiting phase",
    "Corridor exception: a corridor request may end a green after 5 s; yellow and all-red are never shortened",
    "An independent safety monitor checks every state SUMO actually shows",
  ], MX + 0.3, 4.1, 5.3, 2.3, { size: 15, name: "guards" });
  card(s, 6.8, 3.35, 5.93, 3.2, "zero card");
  txt(s, "0", 7.1, 3.5, 2.0, 1.6, { size: 96, bold: true, color: C.accent2, name: "zero" });
  txt(s, "safety violations in every reported run", 9.0, 3.9, 3.5, 1.0, { size: 18, bold: true, color: C.text2, name: "zero label" });
  txt(s, "A random controller ran 5,000 steps, and 600 steps in real SUMO, without a single unsafe signal.",
    7.1, 5.25, 5.4, 1.1, { size: 15, name: "random test" });
  s.addNotes("This is why we can compare controllers fairly: all share the same legal transitions. The 5 s corridor exception is the one deliberate rule for ambulances; the monitor still checks it.");
}

// ---------- 6. Signal control ----------
pres.addSection({ title: "Results" });
{
  const s = content("Results", "Signal control results", "The DQN cut mean travel time by 9-11% on every profile and every seed");
  barChart(s, ["Light", "Medium", "Heavy", "Uneven"], [
    { name: "Fixed-time (tuned)", values: [98.8, 109.0, 172.9, 118.5] },
    { name: "Adaptive", values: [99.3, 104.3, 175.7, 121.6] },
    { name: "DQN", values: [87.9, 98.6, 155.7, 108.0] },
  ], MX, 1.8, 7.6, 5.0, "Mean travel time (mean of 5 evaluation seeds)", [HEX.accent5, HEX.accent3, HEX.accent2], "travel time chart");
  card(s, 8.5, 1.8, 4.23, 5.0, "findings card");
  txt(s, "What it means", 8.8, 2.0, 3.7, 0.45, { size: 20, bold: true, color: C.text2, name: "findings title" });
  bullets(s, [
    "DQN: waiting time -24 to -40%, throughput unchanged",
    "Trade-off: the longest red rose from 30-55 s to 62-76 s",
    "Adaptive: less waiting, but shorter trips only on medium demand",
    "Trained on CPU in 17 minutes",
  ], 8.8, 2.6, 3.7, 4.0, { size: 15, name: "findings" });
  s.addNotes("Read the chart: green bars are lower everywhere. Mention the honest trade-off: the DQN makes minor phases wait longer; the safety filter's 90 s guard bounds it.");
}

// ---------- 7. Routing ----------
{
  const s = content("Results", "Emergency routing results", "Live travel-time routing roughly halved the ambulance's trip around an obstruction");
  barChart(s, ["Medium demand", "Heavy demand"], [
    { name: "Static route", values: [309.0, 587.8] },
    { name: "Dynamic routing", values: [145.4, 302.0] },
  ], MX, 1.8, 7.0, 5.0, "Ambulance travel time (mean of 5 seeds)", [HEX.accent5, HEX.accent2], "routing chart");
  card(s, 7.9, 1.8, 4.83, 5.0, "routing card");
  txt(s, "-53% and -49%", 8.2, 2.0, 4.3, 0.9, { size: 40, bold: true, color: C.accent2, name: "routing stat" });
  bullets(s, [
    "Better on 5 of 5 seeds for both demand levels",
    "A road on the planned route was slowed to 2 m/s (walking pace)",
    "Ordinary traffic not harmed: network queue fell 5–8%",
    "The ambulance never crossed a red light",
  ], 8.2, 3.1, 4.3, 3.5, { size: 15, name: "routing facts" });
  s.addNotes("Static routing plans once on free-flow costs; dynamic routing sees the slow road in live costs and avoids it. The corridor is off here, so this effect is routing alone.");
}

// ---------- 8. Corridor ----------
{
  const s = content("Results", "Green corridor results", "Turning the next signals green cut the ambulance's trip by 34-59%");
  barChart(s, ["Medium demand", "Heavy demand"], [
    { name: "Corridor off", values: [155.8, 313.6] },
    { name: "Corridor on", values: [102.6, 127.8] },
  ], MX, 1.8, 7.0, 5.0, "Ambulance travel time (mean of 5 seeds)", [HEX.accent5, HEX.accent4], "corridor chart");
  card(s, 7.9, 1.8, 4.83, 5.0, "corridor card");
  bullets(s, [
    "Time standing still: 45 to 4 s (medium), 173 to 12 s (heavy)",
    "Ordinary-traffic queues +2.5 to +3.0%, within run-to-run noise",
    "0 red lights crossed, 0 safety violations",
  ], 8.2, 2.05, 4.3, 3.0, { size: 15, name: "corridor facts" });
  txt(s, "The 5 s corridor rule was chosen on the same 5 seeds, so these numbers are an early estimate; the version designed beforehand already gave -34% and -57%.",
    8.2, 3.7, 4.3, 1.6, { size: 14, italic: true, color: C.accent5, name: "corridor caveat" });
  s.addNotes("Routing avoids slow roads; the corridor removes waiting at signals on the chosen road, so the two add up. Say the caveat openly: FYP-II re-checks the 5 s rule on new seeds.");
}

// ---------- 9. Bug found ----------
{
  const s = content("Results", "Measuring found a real defect", "Recording why the ambulance stopped exposed a rerouting bug");
  s.addImage({ path: path.join(FIG, "corridor_stop_reasons.png"), x: MX, y: 1.8, w: 7.2, h: 4.37,
    altText: "Stacked bars of seconds the ambulance stood still, by reason, for each corridor variant",
    objectName: "stop reasons chart" });
  const steps = [
    ["1", "Observed", "In a live demo the ambulance met red lights on its route"],
    ["2", "Measured", "Logged the reason for every second it stood still, in 20 runs"],
    ["3", "Fixed", "After a reroute the corridor skipped the junction ahead; now fixed"],
    ["4", "Improved", "5 s corridor minimum: DQN heavy 130.6 s to 124.2 s, 5/5 seeds"],
  ];
  steps.forEach(([n, head, body], i) => {
    const y = 1.85 + i * 1.2;
    badge(s, 8.2, y, n, [C.accent4, C.accent3, C.accent2, C.accent1][i], `story badge ${n}`);
    txt(s, head, 8.9, y - 0.02, 3.8, 0.4, { size: 18, bold: true, color: C.text2, name: `story head ${n}` });
    txt(s, body, 8.9, y + 0.4, 3.8, 0.7, { size: 14, name: `story text ${n}` });
  });
  s.addNotes("This shows the value of measuring: a demo looked fine at a glance, the per-second record showed the cause, and a test now guards against it.");
}

// ---------- 10. Vision ----------
{
  const s = content("Results", "Vehicle detection and counting", "Fine-tuned YOLO11s with ByteTrack counts vehicles within about 12%");
  s.addImage({ path: path.join(FIG, "tracking_sample_frame.png"), x: MX, y: 1.8, w: 6.4, h: 3.6,
    sizing: { type: "contain", w: 6.4, h: 3.6 },
    altText: "UA-DETRAC test frame with tracked vehicle boxes and the counting line", objectName: "tracking frame" });
  txt(s, "UA-DETRAC test sequence MVI_40714 with the counting line", MX, 5.5, 6.4, 0.35,
    { size: 12, color: C.accent5, name: "frame caption" });
  s.addTable([
    [{ text: "Measure", options: { bold: true, color: C.background1, fill: { color: C.accent1 } } },
     { text: "Result", options: { bold: true, color: C.background1, fill: { color: C.accent1 } } }],
    ["Detection mAP50", "0.752 pretrained to 0.799 fine-tuned"],
    ["Precision", "0.748 to 0.889"],
    ["Count error per clip", "MAE 2.60 vehicles, WAPE 12.0%"],
    ["Without motorcycles", "MAE 1.62, WAPE 7.5%"],
    ["Queue estimate", "0.80 vehicles mean error"],
  ], { x: 7.3, y: 1.8, w: 5.43, colW: [2.2, 3.23], fontSize: 14, color: C.text1,
    border: { type: "solid", pt: 0.75, color: "D9E1E6" }, rowH: 0.45, margin: 0.08, objectName: "vision table" });
  bullets(s, [
    "40 official test sequences, 56,340 frames",
    "Weak class: trucks (only 274 training boxes)",
  ], 7.3, 5.0, 5.43, 1.2, { size: 15, name: "vision notes" });
  s.addNotes("Trained on Kaggle T4 GPUs. True counts come from UA-DETRAC's own track ids through the same counter, so the error is detection plus tracking only. Lahore video comes in FYP-II.");
}

// ---------- 11. Dashboard ----------
{
  const s = content("Results", "Live dashboard", "Run, dispatch, close a road and watch the corridor, all on real SUMO state");
  s.addImage({ path: path.join(ROOT, "results", "phase5", "04_corridor_active.png"), x: MX, y: 1.75, w: 8.0, h: 5.0,
    altText: "Dashboard during a DQN run with a closed road, rerouted ambulance and an active corridor junction",
    objectName: "dashboard screenshot" });
  bullets(s, [
    "Choose controller, demand and seed",
    "Dispatch an ambulance between two roads",
    "Close a road: a new route version appears at once",
    "Corridor state of each junction shown live",
    "FastAPI + WebSocket, React SVG map",
  ], 9.0, 1.9, 3.73, 4.6, { size: 15, name: "dashboard bullets" });
  s.addNotes("Switch to the live demo here (see docs/demo_script.md).");
}

// ---------- 12. Testing ----------
{
  const s = content("Results", "Testing and requirements", "147 automated tests pass, most of them on real SUMO runs");
  const stats = [["147", "automated tests in 17 files, all passing"], ["13", "documented test cases, all passed"],
    ["17 / 20", "functional requirements covered by a test case"]];
  stats.forEach(([big, label], i) => {
    const y = 1.85 + i * 1.6;
    card(s, MX, y, 5.6, 1.4, `test stat ${i + 1}`);
    txt(s, big, MX + 0.3, y + 0.2, 2.2, 1.0, { size: 40, bold: true, color: C.accent2, valign: "middle", name: `test big ${i + 1}` });
    txt(s, label, MX + 2.6, y + 0.2, 2.8, 1.0, { size: 16, valign: "middle", name: `test label ${i + 1}` });
  });
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Requirements", labels: ["Implemented", "Partial", "Planned"], values: [13, 6, 1] }], {
    x: 6.8, y: 1.8, w: 5.9, h: 4.9, holeSize: 55, chartColors: [HEX.accent2, HEX.accent3, HEX.accent5],
    showTitle: true, title: "FYP-I status of the 20 functional requirements", titleFontSize: 14, titleColor: HEX.dk1,
    titleFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt",
    legendColor: HEX.dk1, showValue: true, showPercent: false, dataLabelColor: HEX.dk1, dataLabelFontSize: 14,
    dataLabelFontFace: "+mn-lt", objectName: "requirements chart" });
  s.addNotes("Partial items: no pause button yet, perception runs offline, export is via files. Planned: stale-data warnings on the dashboard.");
}

// ---------- 13. Limits ----------
pres.addSection({ title: "Next" });
{
  const s = content("Next", "What these results do not show yet", "Every number is bounded by the network, data and seeds it was measured on");
  const lim = [
    ["Synthetic grid", "Not yet a Lahore road network", "FYP-II: Lahore OpenStreetMap network with a hospital"],
    ["5 seeds, one route", "Full protocol uses 10 seeds and held-out demand", "FYP-II: rerun every experiment under the full protocol"],
    ["One DQN training run", "Variance between training runs is unknown", "FYP-II: several training seeds and a fairness variant"],
    ["Public video only", "Detector not yet tested on Lahore traffic", "FYP-II: local clips with rickshaw and van classes"],
  ];
  lim.forEach(([head, body, next], i) => {
    const x = MX + (i % 2) * 6.17, y = 1.9 + Math.floor(i / 2) * 2.4;
    card(s, x, y, 5.9, 2.1, `limit card ${i + 1}`);
    badge(s, x + 0.3, y + 0.3, String(i + 1), C.accent3, `limit badge ${i + 1}`);
    txt(s, head, x + 1.0, y + 0.32, 4.6, 0.45, { size: 20, bold: true, color: C.text2, name: `limit head ${i + 1}` });
    txt(s, body, x + 1.0, y + 0.85, 4.6, 0.45, { size: 16, name: `limit text ${i + 1}` });
    txt(s, next, x + 1.0, y + 1.35, 4.6, 0.6, { size: 15, italic: true, color: C.accent2, name: `limit next ${i + 1}` });
  });
  s.addNotes("Being explicit about limits is part of the method; each one becomes an FYP-II task on the next slide.");
}

// ---------- 14. FYP-II plan ----------
{
  const s = content("Next", "Plan for FYP-II", "Move to Lahore and complete the full evaluation protocol, January to May 2027");
  const months = ["Jan", "Feb", "Mar", "Apr", "May"];
  const x0 = 4.7, mw = 1.6, y0 = 1.85, rh = 0.52;
  months.forEach((m, i) => txt(s, m, x0 + i * mw, y0, mw, 0.35, { size: 14, bold: true, color: C.accent5, align: "center", name: `month ${m}` }));
  const items = [
    ["Lahore road network", 0, 2], ["Local video and new classes", 0, 3], ["Full evaluation protocol", 1, 4],
    ["Controller improvements", 2, 4], ["Corridor completion", 2, 4], ["Dashboard and database", 1, 4],
    ["Video-to-simulation study", 3, 4], ["Final report and demo", 4, 5],
  ];
  items.forEach(([name, a, b], i) => {
    const y = y0 + 0.5 + i * rh;
    txt(s, name, MX, y, 3.9, rh - 0.08, { size: 15, valign: "middle", name: `plan item ${i + 1}` });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x0 + a * mw + 0.05, y: y + 0.07, w: (b - a) * mw - 0.1, h: rh - 0.22,
      fill: { color: i === 7 ? C.accent4 : C.accent2 }, line: { color: i === 7 ? C.accent4 : C.accent2, width: 0 },
      rectRadius: 0.08, objectName: `plan bar ${i + 1}` });
  });
  s.addNotes("Order follows dependencies: the Lahore network comes first because the full protocol and the video-to-simulation study run on it.");
}

// ---------- 15. Closing ----------
{
  const s = pres.addSlide({ masterName: "MZ_TITLE", sectionTitle: "Next" });
  s.addText("Thank you", { placeholder: "title" });
  s.addText("Questions, and a live demo", { placeholder: "subtitle" });
  txt(s, "Manzil: a controlled, reproducible prototype for traffic control and one emergency mission",
    MX, 4.25, 9.5, 0.8, { size: 18, color: C.background1, name: "closing line" });
  lights(s, 11.3, 1.5, 0.75, "closing traffic light");
  s.addNotes("Invite questions. Keep the dashboard ready for a second demo run if asked.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT);
})();
