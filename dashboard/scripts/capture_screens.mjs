// W5: drive one real live run through the dashboard and save a screenshot of every screen and
// of each FR-16 warning state. Needs the API on http://127.0.0.1:8000 (python -m manzil.api)
// with the built dashboard. Usage: node dashboard/scripts/capture_screens.mjs <out_dir>
// Stale and disconnected are produced for real: the SUMO processes of the run are frozen with
// SIGSTOP (then resumed), and at the end the API process (env API_PID) is stopped.
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright"); // global install (cloud image) or local
import { execSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const BASE = "http://127.0.0.1:8000";
const out = process.argv[2] ?? "results/fyp2/dashboard";
const log = [];
const note = (m) => { console.log(m); log.push(m); };
const state = () => fetch(`${BASE}/api/state`).then((r) => r.json());
const post = (p, b = {}) => fetch(`${BASE}${p}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(`${p}: ${JSON.stringify(j)}`); return j; });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(pred, what, timeout = 180000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const s = await state(); if (pred(s)) return s; await sleep(200); }
  throw new Error(`timeout waiting for ${what}`);
}
const sumoPids = (runId) => execSync(`pgrep -f "sumo .*${runId}" || true`).toString().trim().split("\n").filter(Boolean);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const shot = async (name, full = false) => { await sleep(700); await page.screenshot({ path: `${out}/${name}.png`, fullPage: full }); note(`saved ${name}.png`); };
const go = async (screen) => { await page.evaluate((s) => { location.hash = `#/${s}`; }, screen); await sleep(500); };

await page.goto(`${BASE}/#/config`);
await page.waitForSelector("[data-testid=checks] li");

// G01 with an error first: origin = destination keeps Start disabled
const sel = (label) => page.locator("label", { hasText: label }).locator("select").first();
const num = (label) => page.locator("label", { hasText: label }).locator("input").first();
await sel("Signal controller").selectOption("dqn");
await sel("Demand profile").selectOption("heavy");
await num("Duration (s)").fill("1200");
await num("Speed").fill("4");
await page.getByLabel("Plan an ambulance mission").check();
await sel(/^To/).selectOption("left0A0");
await sleep(800);
await shot("01b_g01_validation_error", true);
// then a valid config: mission left0A0 -> C2top2 at 120 s, planned closure of B1C1 at 100 s
await sel(/^To/).selectOption("C2top2");
await num("Dispatch at (s)").fill("120");
await page.getByLabel("Plan a road closure").check();
await sel("Road").selectOption("B1C1");
await num(/^At \(s\)/).fill("100");
await sleep(900);
await shot("01_g01_configuration", true);
await page.getByRole("button", { name: "Validate and start run" }).click();
const s0 = await until((s) => s.status === "running", "start");
note(`run ${s0.run_id} started`);

// The route depends on live costs, so the closure that forces a reroute is chosen from the
// route actually planned: the road two ahead of the ambulance, closed through the API (G02).
const sa = await until((s) => s.ambulance?.status === "ACTIVE" && s.ambulance.edge, "ambulance on the road");
const r = sa.ambulance.route;
const ahead = r[Math.min(r.indexOf(sa.ambulance.edge) + 2, r.length - 2)];
note(`route v1 ${r.join(" > ")}; ambulance on ${sa.ambulance.edge}; closing ${ahead} at ${sa.sim_time_s} s`);
await post("/api/roads/close", { edge_id: ahead });
await until((s) => s.ambulance && s.ambulance.route_version >= 2, "reroute");
const s1 = await until((s) => Object.values(s.ambulance.corridor).includes("ACTIVE_PRIORITY") || s.ambulance.status !== "ACTIVE", "active corridor");
note(`sim ${s1.sim_time_s} s: route v${s1.ambulance.route_version} (${s1.ambulance.route_triggers.join(" > ")}), corridor ${JSON.stringify(s1.ambulance.corridor)}`);
await go("overview");
await shot("02_g02_traffic_overview");
await go("emergency");
await shot("04_g04_emergency_dispatch");
const s2 = await until((s) => s.ambulance?.status === "ARRIVED", "arrival");
note(`ambulance arrived at ${s2.ambulance.arrival_s} s: ${JSON.stringify(s2.ambulance.metrics?.amb_travel_time_s)} s travel, ${s2.ambulance.stops} stops`);
await shot("04b_g04_mission_arrived");

// G03
await go("perception");
await page.locator(".tls-hit").nth(4).click(); // B1
await shot("03_g03_perception_intersection", true);

// FR-02 pause
await go("overview");
await page.getByRole("button", { name: "Pause" }).click();
await until((s) => s.status === "paused", "paused");
await sleep(1500);
await shot("06_fr02_paused");
await page.getByRole("button", { name: "Resume" }).click();
await until((s) => s.status === "running", "resumed");

// FR-16 fallback: operator fault injection
await page.getByRole("button", { name: "Inject fault: RL service loss" }).click();
const s3 = await until((s) => (s.warnings ?? []).some((w) => w.code === "fallback") && s.controller_decisions.fallback > 50, "fallback");
note(`fallback: ${JSON.stringify(s3.warnings.find((w) => w.code === "fallback"))}`);
await shot("07_fr16_fallback");

// FR-16 invalid: close both roads into C2, dispatch to C2top2 -> NO_ROUTE
await post("/api/roads/close", { edge_id: "C1C2" });
await post("/api/roads/close", { edge_id: "B2C2" });
await post("/api/ambulance", { origin: "left0A0", destination: "C2top2", corridor: true });
const s4 = await until((s) => s.ambulance?.status === "NO_ROUTE", "NO_ROUTE");
note(`invalid: ${JSON.stringify(s4.warnings.filter((w) => w.code === "invalid"))}`);
await go("emergency");
await shot("10_fr16_invalid_no_route");

// FR-16 stale: freeze the SUMO processes for real
await go("overview");
const pids = sumoPids(s4.run_id);
note(`freezing SUMO pids ${pids.join(",")}`);
execSync(`kill -STOP ${pids.join(" ")}`);
await sleep(3500);
const s5 = await state();
note(`stale: age ${s5.age_s} s, ${JSON.stringify((s5.warnings ?? []).find((w) => w.code === "stale"))}`);
await shot("08_fr16_stale");
execSync(`kill -CONT ${pids.join(" ")}`);
await until((s) => s.age_s < 1 && !(s.warnings ?? []).some((w) => w.code === "stale"), "fresh again");
await post("/api/run/stop");
const s6 = await until((s) => s.status === "stopped", "stopped");
note(`stopped at ${s6.sim_time_s} s; safety violations ${s6.stats.safety_violations}`);

// G05 on the committed Phase 4 comparison (heavy), and with the live run in the store
await go("analytics");
await page.waitForSelector("[data-testid=comparability]");
await shot("05_g05_comparative_analytics", true);
await sel("Study").selectOption("results/phase3/corridor_v2/dqn");
await sel("Demand profile").selectOption("");
await sleep(1500);
await shot("05b_g05_comparability_warning", true);

writeFileSync(`${out}/capture_log.txt`, log.join("\n") + "\n");
// FR-16 disconnected: stop the API process (pid in API_PID) with the page still open
await go("overview");
note(`stopping the API process ${process.env.API_PID}`);
execSync(`kill ${process.env.API_PID}`);
await sleep(4000);
await shot("09_fr16_disconnected");
writeFileSync(`${out}/capture_log.txt`, log.join("\n") + "\n");
await browser.close();
