from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import CONTROLLERS, SCENARIOS, Engine, compare_controllers
from .network import NODES


app = FastAPI(title="Manzil Prototype API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
engine = Engine()


class ResetRequest(BaseModel):
    seed: int = 104
    scenario: str = "balanced"
    controller: str = "adaptive"


class StepRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=500)


class ControllerRequest(BaseModel):
    controller: str


class DispatchRequest(BaseModel):
    origin: str = "I-01"
    destination: str = "I-06"


class ClosureRequest(BaseModel):
    edgeId: str
    closed: bool = True


def handle_value_error(action):
    try:
        return action()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "manzil-prototype", "simulationAdapter": "prototype-sim"}


@app.get("/api/config")
def config():
    return {
        "controllers": CONTROLLERS,
        "scenarios": SCENARIOS,
        "intersections": [{"id": key, **value} for key, value in NODES.items()],
        "limitations": [
            "Fallback simulator is not SUMO.",
            "Perception stream is synthetic and not YOLO output.",
            "q_learning is a tabular prototype policy, not the proposed DQN.",
        ],
    }


@app.get("/api/state")
def state():
    return engine.snapshot()


@app.post("/api/simulation/reset")
def reset(request: ResetRequest):
    return handle_value_error(lambda: engine.reset(request.seed, request.scenario, request.controller))


@app.post("/api/simulation/step")
def step(request: StepRequest):
    return engine.step(request.steps)


@app.post("/api/controller")
def controller(request: ControllerRequest):
    handle_value_error(lambda: engine.set_controller(request.controller))
    return engine.snapshot()


@app.post("/api/emergency/dispatch")
def dispatch(request: DispatchRequest):
    return handle_value_error(lambda: engine.dispatch(request.origin, request.destination))


@app.post("/api/incidents/closure")
def closure(request: ClosureRequest):
    handle_value_error(lambda: engine.set_closure(request.edgeId, request.closed))
    return engine.snapshot()


@app.get("/api/perception")
def perception():
    return engine.perception_snapshot()


@app.get("/api/compare")
def compare(seed: int = 104, scenario: str = "rush_hour", steps: int = 120):
    if scenario not in SCENARIOS:
        raise HTTPException(status_code=422, detail="Unknown scenario")
    return compare_controllers(seed=seed, scenario=scenario, steps=max(10, min(steps, 500)))


@app.get("/api/export")
def export():
    return JSONResponse({
        "manifest": {"schemaVersion": "1.0", "simulationAdapter": "prototype-sim",
                     "seed": engine.seed, "scenario": engine.scenario, "controller": engine.controller,
                     "terminalState": "active-prototype"},
        "state": engine.snapshot(),
        "perception": engine.perception_snapshot(),
        "limitations": config()["limitations"],
    }, headers={"Content-Disposition": "attachment; filename=manzil-run-export.json"})


@app.websocket("/ws/state")
async def state_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            engine.step(1)
            await websocket.send_json(engine.snapshot())
            await asyncio.sleep(0.65)
    except WebSocketDisconnect:
        return


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
