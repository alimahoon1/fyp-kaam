from app.engine import CONTROLLERS, Engine, compare_controllers


def test_seeded_runs_are_reproducible():
    first = Engine(seed=17, scenario="rush_hour", controller="adaptive")
    second = Engine(seed=17, scenario="rush_hour", controller="adaptive")
    assert first.step(40)["metrics"] == second.step(40)["metrics"]


def test_every_controller_uses_valid_signal_states():
    for controller in CONTROLLERS:
        engine = Engine(controller=controller)
        state = engine.step(80)
        assert all(node["signal"]["displayPhase"] in {"EW", "NS", "CLEARANCE"} for node in state["nodes"])
        assert state["metrics"]["throughput"] > 0


def test_dispatch_corridor_and_arrival():
    engine = Engine(seed=8)
    state = engine.dispatch("I-01", "I-06")
    assert state["mission"]["routeVersion"] == 1
    assert state["corridor"]
    for _ in range(120):
        state = engine.step(1)
        if state["mission"]["status"] == "ARRIVED":
            break
    assert state["mission"]["status"] == "ARRIVED"
    assert state["corridor"] == {}


def test_closure_forces_versioned_reroute():
    engine = Engine(seed=3)
    engine.dispatch("I-01", "I-06")
    route = engine.mission.route[:]
    engine.set_closure(f"{route[0]}>{route[1]}", True)
    assert engine.mission.route_version == 2
    assert engine.mission.route != route
    assert any(event["kind"] == "REROUTE" for event in engine.events)


def test_comparison_discloses_prototype_source():
    result = compare_controllers(steps=30)
    assert result["sourceMode"] == "prototype-sim"
    assert len(result["results"]) == 3
    assert "not SUMO" in result["warning"]
