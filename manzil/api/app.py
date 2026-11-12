"""FastAPI service for the Manzil dashboard (PLAN task 5.1).

Endpoints (all JSON)::

    GET  /api/health                 service is up
    GET  /api/options                controllers (and whether each can run), profiles, defaults
    GET  /api/network                road geometry, junctions and signal links from the .net.xml
    GET  /api/state                  latest live state (signals, vehicles, ambulance, corridor)
    POST /api/run/start              {controller, profile, seed, duration_s, speed}
    POST /api/run/stop
    POST /api/run/speed              {speed}
    POST /api/ambulance              {origin, destination, corridor}
    POST /api/roads/close            {edge_id}
    WS   /ws/state                   pushes the state about 10 times a second

If the built dashboard exists (``dashboard/dist``), it is served at ``/``.

Run::

    python -m manzil.api            # http://127.0.0.1:8000
"""

from __future__ import annotations

import asyncio
import importlib.util
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from manzil.api.live import CommandError, LiveConfig, LiveSession
from manzil.control.fixed_time import SignalTiming
from manzil.experiments.emergency import MissionConfig
from manzil.experiments.runner import REPO_ROOT
from manzil.scenarios.demand import PROFILES, fringe_edges
from manzil.sim.network import NetworkModel

DASHBOARD_DIST = REPO_ROOT / "dashboard" / "dist"
CONTROLLER_LABELS = {
    "fixed_time": "Fixed-time (tuned plan per profile)",
    "adaptive": "Rule-adaptive (pressure, Eq 5.2)",
    "dqn": "DQN (parameter-sharing, trained checkpoint)",
}


class StartRequest(BaseModel):
    controller: Literal["fixed_time", "adaptive", "dqn"] = "fixed_time"
    profile: Literal["light", "medium", "heavy", "uneven"] = "medium"
    seed: int = Field(0, ge=0)
    duration_s: int = Field(3600, ge=60, le=4 * 3600)
    speed: float = Field(10.0, ge=0, le=1000)  # sim seconds per wall second; 0 = max


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=0, le=1000)


class DispatchRequest(BaseModel):
    origin: str = MissionConfig.origin
    destination: str = MissionConfig.destination
    corridor: bool = True


class CloseRequest(BaseModel):
    edge_id: str


def _round_shape(shape) -> list[list[float]]:
    return [[round(x, 2), round(y, 2)] for x, y in shape]


@lru_cache(maxsize=4)
def network_geometry(scenario: str = "grid3x3") -> dict:
    """Everything the map needs, read from the SUMO network file (no hard-coded IDs)."""
    net_file = REPO_ROOT / "scenarios" / scenario / f"{scenario}.net.xml"
    model = NetworkModel.from_file(net_file)
    net = model.net
    (xmin, ymin), (xmax, ymax) = net.getBBoxXY()
    entries, exits = fringe_edges(net)
    edges = [
        {
            "id": e.getID(),
            "from": e.getFromNode().getID(),
            "to": e.getToNode().getID(),
            "lanes": [
                {"id": ln.getID(), "width": ln.getWidth(), "shape": _round_shape(ln.getShape())}
                for ln in e.getLanes()
            ],
        }
        for e in sorted(net.getEdges(), key=lambda e: e.getID())
    ]
    junctions = [
        {
            "id": n.getID(),
            "x": round(n.getCoord()[0], 2),
            "y": round(n.getCoord()[1], 2),
            "type": n.getType(),
            "shape": _round_shape(n.getShape()),
        }
        for n in sorted(net.getNodes(), key=lambda n: n.getID())
    ]
    tls = [
        {
            "id": x.tls_id,
            "junction": x.junction_ids[0],
            "links": [
                {
                    "index": lk.index,
                    "from_lane": lk.from_lane,
                    "to_lane": lk.to_lane,
                    "dir": lk.direction,
                }
                for lk in x.links
            ],  # fmt: skip
            "green_phases": [g.state for g in x.green_phases],
        }
        for x in (model.intersections[t] for t in model.tls_ids)
    ]
    return {
        "scenario": scenario,
        "network_id": model.network_id,
        "bounds": [round(v, 2) for v in (xmin, ymin, xmax, ymax)],
        "edges": edges,
        "junctions": junctions,
        "tls": tls,
        "entry_edges": [f.edge_id for f in entries],
        "exit_edges": [f.edge_id for f in exits],
    }


def controller_options() -> list[dict]:
    timing = SignalTiming.load(REPO_ROOT / "scenarios" / "grid3x3" / "signals.json")
    ckpt = REPO_ROOT / timing.dqn.get("checkpoint", "")
    has_torch = importlib.util.find_spec("torch") is not None
    out = []
    for cid, label in CONTROLLER_LABELS.items():
        available, note = True, ""
        if cid == "dqn" and not has_torch:
            available, note = False, 'needs PyTorch: pip install -e ".[rl]" (see README)'
        elif cid == "dqn" and not ckpt.is_file():
            available, note = False, f"checkpoint missing: {timing.dqn.get('checkpoint')}"
        out.append({"id": cid, "label": label, "available": available, "note": note})
    return out


def create_app(runs_dir: Path | None = None, serve_dashboard: bool = True) -> FastAPI:
    session = LiveSession(runs_dir)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        session.stop()  # never leave a SUMO process behind

    app = FastAPI(title="Manzil API", version="0.1.0", lifespan=lifespan)
    # The Vite dev server (npm run dev) runs on another port and calls this API.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=["*"])  # fmt: skip
    app.state.session = session

    def _guard(fn, *args):
        try:
            return fn(*args)
        except CommandError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/health")
    def health():
        return {"ok": True, "status": session.status}

    @app.get("/api/options")
    def options():
        return {
            "controllers": controller_options(),
            "profiles": [{"id": p.name, "description": p.description} for p in PROFILES.values()],
            "defaults": {
                "controller": "fixed_time", "profile": "medium", "seed": 0, "duration_s": 3600,
                "speed": 10.0, "origin": MissionConfig.origin,
                "destination": MissionConfig.destination, "corridor": True,
            },
        }  # fmt: skip

    @app.get("/api/network")
    def network():
        return network_geometry("grid3x3")

    @app.get("/api/state")
    def state():
        return session.state

    @app.post("/api/run/start")
    def start(req: StartRequest):
        avail = {c["id"]: c for c in controller_options()}[req.controller]
        if not avail["available"]:
            raise HTTPException(422, f"controller {req.controller} unavailable: {avail['note']}")
        cfg = LiveConfig(req.controller, req.profile, req.seed, float(req.duration_s), req.speed)
        return _guard(session.start, cfg)

    @app.post("/api/run/stop")
    def stop():
        return session.stop()

    @app.post("/api/run/speed")
    def speed(req: SpeedRequest):
        _guard(session.set_speed, req.speed)
        return {"speed": session.speed}

    @app.post("/api/ambulance")
    def dispatch(req: DispatchRequest):
        return _guard(session.dispatch, req.origin, req.destination, req.corridor)

    @app.post("/api/roads/close")
    def close_road(req: CloseRequest):
        return _guard(session.close_road, req.edge_id)

    @app.websocket("/ws/state")
    async def ws_state(ws: WebSocket):
        await ws.accept()
        sent = -1
        try:
            while True:
                s = session.state
                if s["version"] != sent:
                    await ws.send_json(s)
                    sent = s["version"]
                await asyncio.sleep(0.1)
        except (WebSocketDisconnect, RuntimeError):
            return

    if serve_dashboard and (DASHBOARD_DIST / "index.html").is_file():
        app.mount("/", StaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")
    return app
