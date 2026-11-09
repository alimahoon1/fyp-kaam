"""Documented synthetic network used when SUMO/OSM assets are unavailable."""

NODES = {
    "I-01": {"x": 90, "y": 185, "label": "Origin Gate"},
    "I-02": {"x": 245, "y": 90, "label": "Canal North"},
    "I-03": {"x": 245, "y": 280, "label": "Canal South"},
    "I-04": {"x": 430, "y": 90, "label": "Liberty Link"},
    "I-05": {"x": 430, "y": 280, "label": "Jail Road Link"},
    "I-06": {"x": 590, "y": 185, "label": "Central Hospital"},
}

_UNDIRECTED = [
    ("I-01", "I-02", 14), ("I-01", "I-03", 12),
    ("I-02", "I-04", 12), ("I-03", "I-05", 11),
    ("I-04", "I-06", 13), ("I-05", "I-06", 12),
    ("I-02", "I-03", 9), ("I-04", "I-05", 9),
    ("I-02", "I-05", 18), ("I-03", "I-04", 18),
]

EDGES = {}
for source, target, travel_time in _UNDIRECTED:
    for a, b in ((source, target), (target, source)):
        edge_id = f"{a}>{b}"
        dx = NODES[b]["x"] - NODES[a]["x"]
        dy = NODES[b]["y"] - NODES[a]["y"]
        direction = "EW" if abs(dx) >= abs(dy) else "NS"
        EDGES[edge_id] = {
            "id": edge_id,
            "source": a,
            "target": b,
            "freeFlowSeconds": travel_time,
            "direction": direction,
        }

ADJACENCY = {node: [] for node in NODES}
for edge in EDGES.values():
    ADJACENCY[edge["source"]].append(edge)
