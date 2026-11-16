"""Full evaluation protocol (D2 section 5.8) for any Manzil scenario (W3, FYP-II).

One command runs every controller arm on every demand profile and every matched evaluation
seed with the D2 protocol (900 s warm-up + 3,600 s measurement by default), keeps failed runs,
and writes one results table plus paired statistics against a reference arm.

What makes it a protocol rather than a single comparison:

- **Seed discipline.** Evaluation seeds (default 20-29, ten matched seeds) are disjoint from DQN
  training seeds (1001+), dev / checkpoint-selection seeds (100-101) and the FYP-1 evaluation
  seeds 0-4, which the team had already looked at. Every arm sees exactly the same vehicles on a
  given (profile, seed).
- **Held-out demand.** Profiles in ``HELDOUT_PROFILES`` were never used for training, checkpoint
  selection or tuning. Fixed-time has no declared plan for them, so its plan is chosen *on dev
  seeds* among the scenario's existing plans (``select_plans``), never on evaluation seeds. This
  gives fixed-time the advantage of knowing the demand; the learned and adaptive controllers do
  not get any.
- **Any network.** Nothing here names grid edges: the scenario is a folder with
  ``<name>.net.xml``, ``network.json`` and ``signals.json`` (``scenario_root`` allows a folder
  outside ``scenarios/``), demand comes from the network's fringe roads, and plan selection
  uses whatever plans the scenario declares.
- **Statistics.** Paired differences against the reference arm per profile: mean, SD, 95 %
  Student-t interval, percentage change and the number of seeds on which the arm was better.
  ``mean_arm`` averages several arms per seed (e.g. three DQN training seeds) so that
  training variance and evaluation variance can be separated.
- **Fairness metrics** from each run's signal events: mean, 95th percentile and share above
  60 s of all red intervals (``max_red_s`` alone is one extreme value).

Usage::

    python -m manzil.experiments.protocol run --out results/fyp2/protocol/main \\
        --arms fixed_time adaptive dqn_s0=dqn@models/dqn/grid3x3/best.pt
    python -m manzil.experiments.protocol report --out results/fyp2/protocol/main \\
        --group dqn_avg3=dqn_s0,dqn_s1,dqn_s2
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from manzil.control.fixed_time import SignalTiming
from manzil.experiments.batch import _run_one, check_compatible, read_table, write_table
from manzil.experiments.compare import METRICS, _count_better, mean_sd, t95
from manzil.experiments.runner import CONTROLLERS, REPO_ROOT, RunConfig
from manzil.scenarios.demand import ALL_PROFILES, HELDOUT_PROFILES, PROFILES
from manzil.sim.network import NetworkModel

EVAL_SEEDS = tuple(range(20, 30))
DEV_SEEDS = (100, 101)
DETAIL_FILES = ("timeseries.csv", "signal_events.csv", "applied_controls.csv")
LONG_RED_S = 60.0

FAIRNESS_METRICS = {
    "red_mean_s": ("Mean red interval", "s", True),
    "red_p95_s": ("95th percentile red interval", "s", True),
    "red_share_over_60": ("Red intervals longer than 60 s", "%", True),
}
METRICS.update(FAIRNESS_METRICS)
for _k, _label in (("safety_violations", "Safety violations"), ("teleports", "Teleports"),
                   ("collisions", "Collisions")):  # fmt: skip
    METRICS.setdefault(_k, (_label, "count", True))
PROTOCOL_METRICS = [
    "travel_time_all_mean_s", "waiting_time_mean_s", "queue_mean_veh", "queue_max_veh",
    "throughput_veh", "phase_changes", "max_red_s", "red_p95_s", "red_share_over_60",
]  # fmt: skip
PROFILE_ORDER = (*PROFILES, *HELDOUT_PROFILES)


@dataclass(frozen=True)
class ProtocolRunConfig(RunConfig):
    """A RunConfig that also accepts held-out profiles and scenario folders outside the repo."""

    scenario_root: str = ""  # absolute folder of the scenario; "" = scenarios/<scenario>

    @property
    def scenario_dir(self) -> Path:
        return Path(self.scenario_root) if self.scenario_root else super().scenario_dir

    def validate(self) -> None:
        if self.profile not in ALL_PROFILES:
            raise ValueError(f"invalid run config: unknown demand profile {self.profile!r}")
        # The base check knows only the training profiles; check everything else with one.
        probe = self if self.profile in PROFILES else replace(self, profile=next(iter(PROFILES)))
        RunConfig.validate(probe)


@dataclass(frozen=True)
class Arm:
    name: str
    controller: str
    plan: str = "auto"
    checkpoint: str = ""

    @classmethod
    def parse(cls, spec: str) -> Arm:
        """``name=controller[:plan][@checkpoint]``; a bare controller name is also accepted."""
        name, _, rest = spec.partition("=")
        if not rest:
            name, rest = spec.split(":")[0].split("@")[0], spec
        rest, _, ckpt = rest.partition("@")
        controller, _, plan = rest.partition(":")
        if controller not in CONTROLLERS:
            raise ValueError(f"unknown controller in arm {spec!r}")
        return cls(name, controller, plan or "auto", ckpt)


# ---------------------------------------------------------------- red-interval fairness metrics


def red_intervals(events: list[dict], n_phases: dict[str, int], warmup_s, end_s) -> list[float]:
    """Every red interval of every phase inside the window (same rule as ``max_red_s``)."""
    gaps: list[float] = []
    by_tls: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_tls[e["intersection_id"]].append(e)
    for tls, evs in by_tls.items():
        last_end = dict.fromkeys(range(n_phases[tls]), 0.0)
        current = None
        for e in evs:
            t = float(e["sim_time_s"])
            if t >= end_s:
                break
            if e["kind"] == "green":
                phase = int(e["phase_id"])
                if t > warmup_s:
                    gaps.append(t - max(last_end[phase], warmup_s))
                current = phase
            elif e["kind"] == "yellow" and current is not None:
                last_end[current] = t
                current = None
        for p, last in last_end.items():
            if p != current:
                gaps.append(end_s - max(last, warmup_s))
    return gaps


def fairness_metrics(gaps: list[float]) -> dict:
    if not gaps:
        return {k: None for k in FAIRNESS_METRICS}
    s = sorted(gaps)
    p95 = s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]
    return {
        "red_mean_s": round(sum(s) / len(s), 2),
        "red_p95_s": round(p95, 2),
        "red_share_over_60": round(100.0 * sum(g > LONG_RED_S for g in s) / len(s), 2),
    }


def run_fairness(run_dir: Path, net_file: Path, warmup_s: float, end_s: float) -> dict:
    with (Path(run_dir) / "signal_events.csv").open(encoding="utf-8") as f:
        events = list(csv.DictReader(f))
    net = NetworkModel.from_file(net_file)
    n_phases = {t: len(x.green_phases) for t, x in net.intersections.items()}
    return fairness_metrics(red_intervals(events, n_phases, warmup_s, end_s))


# ---------------------------------------------------------------------------------- running


def _protocol_one(job: tuple[ProtocolRunConfig, str]) -> dict:
    """One run; failures are kept as rows (D2: failed runs are retained, not dropped)."""
    config, run_dir = job
    net_file = config.scenario_dir / f"{config.scenario}.net.xml"
    try:
        row = _run_one((config, run_dir, False))
        row.update(run_fairness(Path(run_dir), net_file, config.warmup_s, config.end_s))
    except Exception as exc:  # noqa: BLE001 - recorded in the table, reported by the caller
        row = {"arm": config.label, "profile": config.profile, "seed": config.seed,
               "termination": f"error: {type(exc).__name__}: {exc}",
               "run_dir": run_dir}  # fmt: skip
    for name in DETAIL_FILES:  # per-run detail is large; the table keeps what is needed
        (Path(run_dir) / name).unlink(missing_ok=True)
    try:
        row["run_dir"] = Path(run_dir).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        pass
    return row


def run_jobs(configs: list[ProtocolRunConfig], out: Path, workers: int = 0) -> list[dict]:
    jobs = []
    for i, c in enumerate(configs):
        c.validate()
        jobs.append((c, str(Path(out) / "runs" / f"{i:03d}_{c.label}_{c.profile}_s{c.seed}")))
    workers = workers or min(len(jobs), mp.cpu_count())
    if workers <= 1:
        return [_protocol_one(j) for j in jobs]
    with ProcessPoolExecutor(workers, mp_context=mp.get_context("spawn")) as pool:
        return list(pool.map(_protocol_one, jobs))


def base_config(scenario: str, scenario_root: str, warmup_s: float, measure_s: float):
    return ProtocolRunConfig(scenario=scenario, scenario_root=scenario_root,
                             warmup_s=warmup_s, measure_s=measure_s)  # fmt: skip


def select_plans(
    base: ProtocolRunConfig, profiles, out: Path, dev_seeds=DEV_SEEDS, workers: int = 0
) -> dict[str, str]:
    """Fixed-time plan per profile: the declared plan, or for profiles without one (held-out),
    the existing plan with the lowest mean ``travel_time_all_mean_s`` on the dev seeds."""
    timing = SignalTiming.load(base.scenario_dir / "signals.json")
    chosen = {p: timing.profile_plans[p] for p in profiles if p in timing.profile_plans}
    todo = [p for p in profiles if p not in chosen]
    if not todo:
        return chosen
    configs = [
        replace(
            base, controller="fixed_time", plan=plan, profile=p, seed=s, label=f"plan_{plan}"
        )  # fmt: skip
        for p in todo
        for plan in sorted(timing.plans)
        for s in dev_seeds
    ]
    with_dir = Path(out) / "plan_selection"
    rows = run_jobs(configs, with_dir, workers)
    shutil.rmtree(with_dir, ignore_errors=True)  # dev runs are not evaluation results
    table = []
    for p in todo:
        scores = {}
        for plan in sorted(timing.plans):
            rs = [r for r in rows if r["profile"] == p and r["arm"] == f"plan_{plan}"]
            ok = [r for r in rs if r["termination"] == "completed"]
            if len(ok) == len(rs) and ok:
                scores[plan] = sum(float(r["travel_time_all_mean_s"]) for r in ok) / len(ok)
            table.append({"profile": p, "plan": plan, "dev_seeds": " ".join(map(str, dev_seeds)),
                          "travel_time_all_mean_s": round(scores.get(plan, math.nan), 2),
                          "completed": f"{len(ok)}/{len(rs)}"})  # fmt: skip
        if not scores:
            raise RuntimeError(f"no fixed-time plan completed on profile {p!r}")
        chosen[p] = min(scores, key=scores.get)
        for row in table:
            if row["profile"] == p:
                row["chosen"] = row["plan"] == chosen[p]
    write_table(table, Path(out) / "plan_selection.csv")
    return chosen


def protocol_configs(base: ProtocolRunConfig, arms: list[Arm], profiles, seeds, plans):
    out = []
    for p in profiles:
        for arm in arms:
            plan = arm.plan
            if arm.controller == "fixed_time" and plan == "auto":
                plan = plans[p]
            out += [replace(base, controller=arm.controller, plan=plan, profile=p, seed=s,
                            checkpoint=arm.checkpoint, label=arm.name) for s in seeds]  # fmt: skip
    return out


# ------------------------------------------------------------------------------- statistics


def mean_arm(rows: list[dict], name: str, members: list[str], metrics) -> list[dict]:
    """Rows of a virtual arm: per (profile, seed) the mean over ``members`` (all must exist)."""
    by = defaultdict(dict)
    for r in rows:
        if r["arm"] in members:
            by[(r["profile"], r["seed"])][r["arm"]] = r
    out = []
    for (p, s), rs in sorted(by.items()):
        if set(rs) != set(members):
            raise ValueError(f"{name}: missing member runs for {p} seed {s}")
        first = next(iter(rs.values()))
        row = {
            k: first[k]
            for k in (
                "profile",
                "seed",
                "network_id",
                "demand_generator",
                "warmup_s",
                "measure_s",
                "metric_version",
                "termination",
            )
        }
        row["arm"] = name  # fmt: skip
        for m in metrics:
            vals = [_val(r, m) for r in rs.values()]
            row[m] = sum(vals) / len(vals) if all(v is not None for v in vals) else None
        out.append(row)
    return out


def _val(r, m):
    v = r.get(m)
    return None if v in ("", None) else float(v)


def summarise(rows: list[dict], reference: str, arms: list[str], metrics) -> dict:
    """Same structure as ``compare.summarise`` (so ``compare.markdown`` can print it), for any
    profile names; paired differences of every arm against ``reference`` on matched seeds."""
    check_compatible([r for r in rows if r["arm"] in arms])
    by = defaultdict(dict)
    for r in rows:
        if r["arm"] not in arms:
            continue
        if r["seed"] in by[(r["profile"], r["arm"])]:
            raise ValueError(f"duplicate run for {r['profile']} {r['arm']} seed {r['seed']}")
        by[(r["profile"], r["arm"])][r["seed"]] = r
    profiles = [p for p in PROFILE_ORDER if any(k[0] == p for k in by)]
    profiles += sorted({k[0] for k in by} - set(profiles))
    controllers = [reference] + [a for a in arms if a != reference]
    metrics = [m for m in metrics if any(_val(r, m) is not None for r in rows)]
    out = {"profiles": profiles, "controllers": controllers, "reference": reference,
           "metrics": metrics, "summary": {}, "paired": {}}  # fmt: skip
    for p in profiles:
        ref = by.get((p, reference), {})
        for c in controllers:
            runs = by.get((p, c), {})
            if not runs:
                continue
            entry = {"seeds": sorted(runs)}
            for m in metrics:
                vals = [v for r in runs.values() if (v := _val(r, m)) is not None]
                mu, sd = mean_sd(vals) if vals else (None, None)
                entry[m] = {"mean": mu, "sd": sd, "n": len(vals)} if vals else None
            out["summary"].setdefault(p, {})[c] = entry
            if c == reference or not ref:
                continue
            if set(runs) != set(ref):
                raise ValueError(f"{p}: {c} and {reference} were not run on the same seeds")
            paired = {}
            for m in metrics:
                pairs = [(_val(runs[s], m), _val(ref[s], m)) for s in sorted(runs)]
                pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
                if not pairs:
                    continue
                diffs = [a - b for a, b in pairs]
                d, sd = mean_sd(diffs)
                n = len(diffs)
                half = t95(n - 1) * sd / math.sqrt(n) if n > 1 else None
                base = sum(b for _, b in pairs) / n
                paired[m] = {
                    "mean_diff": d, "sd_diff": sd,
                    "ci95": [d - half, d + half] if half is not None else None,
                    "pct_change": 100 * d / base if base else None,
                    "seeds_better": _count_better(diffs, METRICS[m][2]), "n": n,
                }  # fmt: skip
            out["paired"].setdefault(p, {})[c] = paired
    return out


def training_variance(rows: list[dict], members: list[str], reference: str, metrics) -> list[dict]:
    """Per profile and metric: each trained model's mean, and the spread between models.

    ``between_sd`` is the SD of the per-model means (training variance); ``within_sd_mean`` is
    the mean over models of the SD across evaluation seeds (evaluation variance)."""
    out = []
    profiles = [p for p in PROFILE_ORDER if any(r["profile"] == p for r in rows)]
    for p in profiles:
        ref = [r for r in rows if r["profile"] == p and r["arm"] == reference]
        for m in metrics:
            ref_mean = mean_sd([_val(r, m) for r in ref])[0] if ref else None
            per = {}
            within = []
            for a in members:
                vals = [_val(r, m) for r in rows if r["profile"] == p and r["arm"] == a]
                vals = [v for v in vals if v is not None]
                if vals:
                    mu, sd = mean_sd(vals)
                    per[a] = mu
                    within.append(sd)
            if len(per) < 2:
                continue
            mu, sd = mean_sd(list(per.values()))
            row = {"profile": p, "metric": m, **{a: round(v, 3) for a, v in per.items()},
                   "between_mean": round(mu, 3), "between_sd": round(sd, 3),
                   "between_range": round(max(per.values()) - min(per.values()), 3),
                   "within_sd_mean": round(sum(within) / len(within), 3)}  # fmt: skip
            lower = METRICS[m][2]
            if ref_mean is not None:
                row[f"{reference}_mean"] = round(ref_mean, 3)
                if lower is not None:
                    row["models_better_than_ref"] = sum(
                        (v < ref_mean) if lower else (v > ref_mean) for v in per.values()
                    )
            out.append(row)
    return out


# --------------------------------------------------------------------------------- reporting


def _fmt(x, nd=1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def _cell(s: dict, arm: str, m: str) -> str:
    x = (s.get(arm) or {}).get(m)
    return f"{_fmt(x['mean'])} ± {_fmt(x['sd'])}" if x else "—"


def compact_markdown(summary: dict, metrics, title: str = "") -> str:
    """One table per metric: profiles as rows, arms as columns (mean ± SD), and for every arm
    the paired difference vs the reference with its 95 % CI and seeds better."""
    ref = summary["reference"]
    arms = [c for c in summary["controllers"] if c != ref]
    lines = [f"## {title}", ""] if title else []
    for m in metrics:
        if m not in summary["metrics"]:
            continue
        label, unit, _ = METRICS[m]
        lines += [f"**{label} ({unit})**", ""]
        head = f"| Profile | {ref} |" + "".join(f" {a} | Δ vs {ref} [95 % CI], better |"
                                             for a in arms)  # fmt: skip
        lines += [head, "|" + "---|" * (head.count("|") - 1)]
        for p in summary["profiles"]:
            s = summary["summary"].get(p, {})
            row = f"| {p}{' (held out)' if p in HELDOUT_PROFILES else ''} | {_cell(s, ref, m)} |"
            for a in arms:
                d = summary["paired"].get(p, {}).get(a, {}).get(m)
                if not d:
                    row += f" {_cell(s, a, m)} | — |"
                    continue
                ci = d["ci95"]
                ci_s = f"[{_fmt(ci[0])}, {_fmt(ci[1])}]" if ci else "n/a"
                pct = f" ({d['pct_change']:+.1f} %)" if d["pct_change"] is not None else ""
                better = "" if d["seeds_better"] is None else f", {d['seeds_better']}/{d['n']}"
                row += f" {_cell(s, a, m)} | {d['mean_diff']:+.1f} {ci_s}{pct}{better} |"
            lines.append(row)
        lines.append("")
    return "\n".join(lines)


def plot_paired(summary: dict, metrics, path: Path, title: str) -> None:
    """Paired difference vs the reference (metric units) with 95 % CI, per profile and arm."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ref = summary["reference"]
    arms = [c for c in summary["controllers"] if c != ref]
    profiles = summary["profiles"]
    metrics = [m for m in metrics if m in summary["metrics"]]
    cols = 2
    rows_n = math.ceil(len(metrics) / cols)
    fig, axes = plt.subplots(rows_n, cols, figsize=(12, 3.2 * rows_n), squeeze=False)
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"]
    width = 0.8 / max(len(arms), 1)
    for ax, m in zip(axes.flat, metrics, strict=False):
        label, unit, lower = METRICS[m]
        for pi, p in enumerate(profiles):
            if p in HELDOUT_PROFILES:
                ax.axvspan(pi - 0.5, pi + 0.5, color="#f2e6c9", alpha=0.6, lw=0)
        for ai, a in enumerate(arms):
            xs, ys, lo, hi = [], [], [], []
            for pi, p in enumerate(profiles):
                d = summary["paired"].get(p, {}).get(a, {}).get(m)
                if not d or not d["ci95"]:
                    continue
                xs.append(pi + (ai - (len(arms) - 1) / 2) * width)
                ys.append(d["mean_diff"])
                lo.append(d["mean_diff"] - d["ci95"][0])
                hi.append(d["ci95"][1] - d["mean_diff"])
            ax.errorbar(xs, ys, yerr=[lo, hi], fmt="o", capsize=3, label=a,
                        color=colors[ai % len(colors)])  # fmt: skip
        ax.axhline(0, color="grey", lw=0.8)
        ax.set_xlim(-0.5, len(profiles) - 0.5)
        ax.set_xticks(range(len(profiles)), profiles, fontsize=8)
        better = "" if lower is None else (" (below 0 = better)" if lower else
                                           " (above 0 = better)")  # fmt: skip
        ax.set_title(f"{label}, Δ vs {ref} ({unit}){better}", fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    for ax in list(axes.flat)[len(metrics) :]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(f"{title}: mean paired difference with 95 % CI; shaded = held-out profile",
                 fontsize=10)  # fmt: skip
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def per_model_rows(summary: dict, members) -> list[dict]:
    """Flat table: paired difference of every model against the reference, per profile."""
    out = []
    for p in summary["profiles"]:
        for a in members:
            for m, d in summary["paired"].get(p, {}).get(a, {}).items():
                ci = d["ci95"] or [None, None]
                out.append({"profile": p, "arm": a, "metric": m,
                            "mean": round(summary["summary"][p][a][m]["mean"], 3),
                            "mean_diff": round(d["mean_diff"], 3),
                            "ci95_low": None if ci[0] is None else round(ci[0], 3),
                            "ci95_high": None if ci[1] is None else round(ci[1], 3),
                            "seeds_better": d["seeds_better"], "n": d["n"]})  # fmt: skip
    return out


def report(out: Path, reference: str, groups: dict[str, list[str]], comparisons) -> dict:
    """Recompute every table and plot from ``results.csv`` (no simulation)."""
    out = Path(out)
    rows = read_table(out / "results.csv")
    failed = [r for r in rows if r["termination"] != "completed"]
    ok = [r for r in rows if r["termination"] == "completed"]
    allm = [*PROTOCOL_METRICS, "red_mean_s", "travel_time_mean_s", "safety_violations",
            "teleports", "collisions"]  # fmt: skip
    for name, members in groups.items():
        ok += mean_arm(ok, name, members, allm)
    results = {"failed_runs": [r["run_dir"] for r in failed], "comparisons": {}}
    md = []
    for title, ref, arms in comparisons(reference, groups):
        s = summarise(ok, ref, arms, allm)
        results["comparisons"][title] = s
        md.append(compact_markdown(s, PROTOCOL_METRICS, title))
        slug = "".join(ch if ch.isalnum() else "_" for ch in title.lower()).strip("_")[:40]
        plot_paired(s, PROTOCOL_METRICS[:6] + ["red_p95_s", "red_share_over_60"],
                    out / f"paired_{slug}.png", title)  # fmt: skip
    for name, members in groups.items():
        tv = training_variance(ok, members, reference, PROTOCOL_METRICS)
        write_table(tv, out / f"training_variance_{name}.csv")
        s = summarise(ok, reference, [reference, *members], allm)
        md.append(compact_markdown(s, PROTOCOL_METRICS[:1] + ["teleports"],
                                   f"Each trained model of {name} vs {reference}"))  # fmt: skip
        write_table(per_model_rows(s, members), out / f"per_model_{name}.csv")
    safety = {k: sum(int(r.get(k) or 0) for r in rows if r["termination"] == "completed")
              for k in ("safety_violations", "teleports", "collisions")}  # fmt: skip
    results["totals"] = {"runs": len(rows), "failed": len(failed), **safety}
    (out / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    head = [f"Runs: {len(rows)}, failed: {len(failed)}; safety violations "
            f"{safety['safety_violations']}, teleports {safety['teleports']}, collisions "
            f"{safety['collisions']} (totals over completed runs).", ""]  # fmt: skip
    (out / "tables.md").write_text("\n".join(head + md) + "\n")
    return results


def default_comparisons(reference, groups):
    """Controllers vs the reference; then, if present, the fairness variant vs base DQN."""
    names = list(groups)
    main = ["adaptive", *[n for n in names if not n.startswith("dqn_fair")]]
    yield "Controllers vs tuned fixed-time", reference, [reference, *main]
    fair = [n for n in names if n.startswith("dqn_fair")]
    base = [n for n in names if n.startswith("dqn") and not n.startswith("dqn_fair")]
    if fair and base:
        yield "Fairness variant vs base DQN", base[0], [base[0], *fair]
        yield "Fairness variant vs tuned fixed-time", reference, [reference, *fair]


def _parse_groups(specs) -> dict[str, list[str]]:
    out = {}
    for g in specs or []:
        name, _, members = g.partition("=")
        out[name] = members.split(",")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the protocol, then write the report")
    r.add_argument("--scenario", default="grid3x3")
    r.add_argument("--scenario-root", default="", help="scenario folder outside scenarios/")
    r.add_argument("--arms", nargs="+", default=["fixed_time", "adaptive"])
    r.add_argument("--profiles", nargs="+", default=list(PROFILE_ORDER),
                   choices=sorted(ALL_PROFILES))  # fmt: skip
    r.add_argument("--seeds", nargs="+", type=int, default=list(EVAL_SEEDS))
    r.add_argument("--warmup", type=float, default=900.0)
    r.add_argument("--measure", type=float, default=3600.0)
    r.add_argument("--workers", type=int, default=0)
    for p in (r, sub.add_parser("report", help="tables and plots from results.csv")):
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--reference", default="fixed_time")
        p.add_argument("--group", nargs="*", default=[], help="name=arm1,arm2,... (mean arm)")
    a = ap.parse_args(argv)
    groups = _parse_groups(a.group)
    if a.cmd == "run":
        arms = [Arm.parse(s) for s in a.arms]
        base = base_config(a.scenario, a.scenario_root, a.warmup, a.measure)
        plans = select_plans(base, a.profiles, a.out, workers=a.workers)
        (Path(a.out) / "protocol.json").write_text(json.dumps({
            "scenario": a.scenario, "scenario_root": a.scenario_root,
            "arms": [vars(x) for x in arms], "profiles": a.profiles, "seeds": a.seeds,
            "warmup_s": a.warmup, "measure_s": a.measure, "fixed_time_plans": plans,
            "heldout_profiles": [p for p in a.profiles if p in HELDOUT_PROFILES],
            "dev_seeds_for_plan_selection": list(DEV_SEEDS),
        }, indent=2) + "\n")  # fmt: skip
        rows = run_jobs(protocol_configs(base, arms, a.profiles, a.seeds, plans), a.out,
                        a.workers)  # fmt: skip
        write_table(rows, Path(a.out) / "results.csv")
    res = report(a.out, a.reference, groups, default_comparisons)
    print(json.dumps(res["totals"]))
    print((Path(a.out) / "tables.md").read_text())


if __name__ == "__main__":
    main()
