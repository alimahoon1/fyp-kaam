"""G01 configuration check (FR-01, W5): every field is checked before a live run may start.

``validate_live_config`` returns a list of checks, each ``{field, level, message}`` with level
``ok``, ``info``, ``warning`` or ``error``. The dashboard shows them in the validation panel
and keeps *Start run* disabled while any check is an error; the API's ``/api/run/start``
runs the same check and refuses a config with errors (422), so the browser cannot bypass it.
"""

from __future__ import annotations

import hashlib
import importlib.util
from functools import lru_cache
from pathlib import Path

from manzil.control.fixed_time import SignalTiming
from manzil.experiments.metrics import METRIC_VERSION
from manzil.experiments.runner import REPO_ROOT
from manzil.routing.graph import RoutingGraph
from manzil.scenarios.demand import PROFILES
from manzil.sim.network import NetworkModel


@lru_cache(maxsize=4)
def _network(scenario: str) -> NetworkModel:
    return NetworkModel.from_file(REPO_ROOT / "scenarios" / scenario / f"{scenario}.net.xml")


@lru_cache(maxsize=4)
def _graph(scenario: str) -> RoutingGraph:
    return RoutingGraph(_network(scenario))


@lru_cache(maxsize=8)
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(field: str, level: str, message: str) -> dict:
    return {"field": field, "level": level, "message": message}


def validate_live_config(cfg: dict) -> list[dict]:
    """``cfg`` is the start request body (already type-checked by pydantic)."""
    out: list[dict] = []
    scenario = cfg.get("scenario", "grid3x3")
    sdir = REPO_ROOT / "scenarios" / scenario
    if not (sdir / f"{scenario}.net.xml").is_file():
        return [_check("scenario", "error", f"unknown scenario {scenario!r}")]
    net = _network(scenario)
    out.append(_check("scenario", "ok", f"network {net.network_id}, {len(net.tls_ids)} signals"))
    out.append(_check("scenario", "info", "synthetic 3x3 grid (the Lahore network is W1)"))

    profile = cfg.get("profile")
    if profile in PROFILES:
        out.append(_check("profile", "ok", f"{profile}: {PROFILES[profile].description}"))
    else:
        out.append(_check("profile", "error", f"unknown demand profile {profile!r}"))

    timing = SignalTiming.load(sdir / "signals.json")
    ctrl = cfg.get("controller")
    if ctrl == "fixed_time":
        out.append(
            _check(
                "controller",
                "ok",
                f"fixed-time plan for {profile}, signals.json version {timing.version}",
            )
        )
    elif ctrl == "adaptive":
        out.append(
            _check("controller", "ok", f"rule-adaptive (Eq 5.2), parameters {timing.adaptive}")
        )
    elif ctrl == "dqn":
        rel = timing.dqn.get("checkpoint", "")
        path = REPO_ROOT / rel
        if importlib.util.find_spec("torch") is None:
            out.append(_check("controller", "error", 'DQN needs PyTorch: pip install -e ".[rl]"'))
        elif not rel or not Path(path).is_file():
            out.append(_check("controller", "error", f"DQN checkpoint missing: {rel!r}"))
        else:
            out.append(
                _check(
                    "controller", "ok", f"DQN checkpoint {rel}, sha256 {_sha256(str(path))[:12]}"
                )
            )
    else:
        out.append(_check("controller", "error", f"unknown controller {ctrl!r}"))

    seed, dur = cfg.get("seed", 0), cfg.get("duration_s", 0)
    out.append(_check("seed", "ok" if seed >= 0 else "error", f"seed {seed}"))
    if dur < 60 or dur % 1:
        out.append(_check("duration_s", "error", "duration must be whole seconds, >= 60"))
    else:
        out.append(_check("duration_s", "ok", f"{dur} s simulated"))
    out.append(
        _check(
            "duration_s",
            "warning",
            "live runs start empty with no warm-up: a demonstration, not the D2"
            " protocol (900 s warm-up + 3,600 s, 10 seeds)",
        )
    )

    graph = _graph(scenario)
    m = cfg.get("mission")
    route = None
    if m:
        o, d = m.get("origin"), m.get("destination")
        bad = [e for e in (o, d) if e not in graph.succ]
        if bad:
            out.append(_check("mission", "error", f"unknown or forbidden road(s): {bad}"))
        elif o == d:
            out.append(_check("mission", "error", "origin and destination are the same road"))
        else:
            closed = {cfg["incident"]["edge_id"]} if cfg.get("incident") else set()
            path, cost, _ = graph.shortest_path(o, d, graph.free_flow_snapshot(), False)
            if path is None:
                out.append(_check("mission", "error", f"no route from {o} to {d} (NO_ROUTE)"))
            else:
                route = path
                out.append(
                    _check(
                        "mission",
                        "ok",
                        f"route {o} -> {d}: {len(path)} roads,"
                        f" free-flow {cost:.0f} s after the first road",
                    )
                )
                if closed:
                    p2, _, _ = graph.shortest_path(o, d, graph.free_flow_snapshot(closed), False)
                    if p2 is None or (closed & {o, d}):
                        out.append(
                            _check(
                                "mission",
                                "error",
                                "the planned closure leaves no route for the ambulance",
                            )
                        )
        ds = m.get("dispatch_s", 0)
        if not 0 <= ds < dur - 1:
            out.append(_check("mission", "error", f"dispatch at {ds} s is outside the run"))
        else:
            out.append(
                _check(
                    "mission",
                    "ok",
                    f"dispatch at {ds:.0f} s, corridor"
                    f" {'on' if m.get('corridor', True) else 'off'}",
                )
            )
    else:
        out.append(_check("mission", "info", "no planned mission (dispatch from G04 instead)"))

    inc = cfg.get("incident")
    if inc:
        e, t = inc.get("edge_id"), inc.get("time_s", 0)
        if e not in {x.getID() for x in net.net.getEdges()}:
            out.append(_check("incident", "error", f"unknown road {e!r}"))
        elif not 0 <= t < dur:
            out.append(_check("incident", "error", f"closure at {t} s is outside the run"))
        else:
            on_route = route is not None and e in route
            out.append(
                _check(
                    "incident",
                    "ok",
                    f"close {e} at {t:.0f} s"
                    + (
                        "; it is on the ambulance's free-flow route, so a reroute is expected"
                        if on_route
                        else ""
                    ),
                )
            )
    else:
        out.append(_check("incident", "info", "no planned closure"))

    out.append(
        _check(
            "metrics",
            "info",
            f"live runs record counts, missions and warnings"
            f" (summary.json); batch metric schema v{METRIC_VERSION}"
            " is for experiments",
        )
    )
    out.append(
        _check(
            "perception",
            "info",
            "video is a separate evidence path (D2): G03 shows"
            " prepared results; no video drives this run",
        )
    )
    return out


def has_errors(checks: list[dict]) -> bool:
    return any(c["level"] == "error" for c in checks)
