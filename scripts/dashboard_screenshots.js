// Drives the real dashboard (API on :8000 with the built frontend) and saves screenshots to
// results/phase5/. Usage: python -m manzil.api  (other terminal), then
//   node scripts/dashboard_screenshots.js
// Every value on the screenshots comes from the live SUMO run started here.
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.env.MANZIL_URL || "http://127.0.0.1:8000";
const OUT = path.join(__dirname, "..", "results", "phase5");
const api = async (p, body) => {
  const r = await fetch(BASE + p, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  return r.json();
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitState(pred, timeoutMs = 120000) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const s = await api("/api/state");
    if (pred(s)) return s;
    if (s.status === "error") throw new Error(s.error);
    await sleep(100);
  }
  throw new Error("timeout");
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await page.goto(BASE);
  await page.waitForSelector("svg.map");
  await page.screenshot({ path: path.join(OUT, "01_idle.png") });

  // Start through the UI: DQN controller, heavy demand.
  await page.selectOption("label:has-text('Controller') select", "dqn");
  await page.selectOption("label:has-text('Demand') select", "heavy");
  await page.click("button:has-text('Start run')");
  await waitState((s) => s.status === "running" && s.sim_time_s >= 400, 180000);
  await api("/api/run/speed", { speed: 4 });
  await sleep(1500);
  await page.screenshot({ path: path.join(OUT, "02_running_dqn_heavy.png") });

  // Select a road on the default ambulance route and close it, then dispatch through the UI.
  await page.click("button:has-text('Dispatch ambulance')");
  await waitState((s) => s.ambulance && s.ambulance.status === "ACTIVE" && s.ambulance.position);
  await api("/api/roads/close", { edge_id: "B0B1" });
  await waitState((s) => s.ambulance && s.ambulance.route_version >= 2);
  await page.evaluate(() => {}); // let the socket deliver
  await sleep(600);
  await page.screenshot({ path: path.join(OUT, "03_closure_reroute.png") });

  await waitState((s) => s.ambulance && Object.values(s.ambulance.corridor).includes("ACTIVE_PRIORITY"));
  await sleep(300);
  await page.screenshot({ path: path.join(OUT, "04_corridor_active.png") });

  const done = await waitState((s) => s.ambulance && s.ambulance.status === "ARRIVED", 180000);
  await sleep(600);
  await page.screenshot({ path: path.join(OUT, "05_arrived.png") });
  await api("/api/run/stop", {});
  await sleep(500);
  const fs = require("fs");
  fs.writeFileSync(path.join(OUT, "demo_run_state.json"), JSON.stringify({
    note: "API state at ambulance arrival during the screenshot run (scripts/dashboard_screenshots.js)",
    run_id: done.run_id, config: done.config, sim_time_s: done.sim_time_s, stats: done.stats,
    closed_edges: done.closed_edges, ambulance: done.ambulance,
  }, null, 2) + "\n");
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
