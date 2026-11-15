"""Six-class label tools for the Lahore footage (workstream W2).

Pure Python (standard library only), so the same code runs in Kaggle kernels and in the unit
tests (`tests/test_w2_lahore_labels.py`).

Classes (W2): ``0 car, 1 bus, 2 truck, 3 motorcycle, 4 rickshaw, 5 van``. "rickshaw" covers all
three-wheelers seen in Lahore (auto rickshaw, chingchi, loader rickshaw); "van" covers
passenger vans and Suzuki-type carry/pick-up vans. The first four ids are the same as the
four-class Manzil model (`models/yolo/manzil_yolo11s_best.pt`), so old labels stay valid.

What is here:
  * class maps from the pre-labelling detectors to the six classes;
  * IoU and a greedy cross-detector merge that turns raw detections into pre-labels;
  * reading/writing YOLO label lines (normalised centre x, centre y, width, height);
  * applying a review correction list (delete / change class / add box) to a pre-label set;
  * the split manifest (``data/lahore_video/split_manifest.csv``) loader and checks.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field

CLASS_NAMES = ["car", "bus", "truck", "motorcycle", "rickshaw", "van"]
OLD_CLASS_NAMES = CLASS_NAMES[:4]  # the four-class Manzil model uses the same first ids
NEW_CLASSES = (4, 5)

# COCO-80 index -> six-class id (car 2, motorcycle 3, bus 5, truck 7)
COCO_MAP = {2: 0, 5: 1, 7: 2, 3: 3}
# the fine-tuned four-class Manzil model -> six-class id (identity)
MANZIL4_MAP = {0: 0, 1: 1, 2: 2, 3: 3}
# open-vocabulary prompts (YOLO-World) in this order -> six-class id
WORLD_PROMPTS = ["car", "bus", "truck", "motorcycle", "auto rickshaw", "loader rickshaw", "van"]
WORLD_MAP = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 4, 6: 5}

SPLITS = ("train", "val", "test")
UNUSED = "unused"  # guard-band frames next to a boundary between two splits

Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


@dataclass
class Det:
    cls: int
    conf: float
    box: Box
    source: str = ""


@dataclass
class Label:
    cls: int
    box: Box
    sources: list = field(default_factory=list)
    conf: float = 1.0


# ---------------------------------------------------------------- geometry


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def map_dets(raw, cmap: dict[int, int], source: str) -> list[Det]:
    """``raw`` rows ``[cls, conf, x1, y1, x2, y2]`` -> Det list; classes not in cmap dropped."""
    out = []
    for c, conf, *b in raw:
        c = int(c)
        if c in cmap:
            out.append(Det(cmap[c], float(conf), tuple(float(v) for v in b), source))
    return out


# ---------------------------------------------------------------- merge


@dataclass
class MergeConfig:
    iou_thr: float = 0.5  # detections of different sources with IoU above this are one vehicle
    keep_conf: float = 0.35  # a cluster is kept if its best confidence reaches this ...
    agree_conf: float = 0.15  # ... or if >= 2 sources agree with at least this confidence
    new_class_conf: float = 0.2  # an open-vocabulary rickshaw/van this sure overrides car etc.
    min_side_px: float = 12.0  # boxes smaller than this (both sides) are ignored
    prefer_source: str = ""  # if set, a detection from this source decides the class ...
    prefer_conf: float = 0.25  # ... when it is at least this confident


def merge(dets: list[Det], cfg: MergeConfig | None = None) -> list[Label]:
    """Greedy cross-detector merge into one pre-label per vehicle.

    Detections are sorted by confidence; each seeds a cluster that absorbs every remaining
    detection with IoU >= ``iou_thr``. The box is the confidence-weighted mean of the cluster.
    Class: if ``prefer_source`` is set and that source has a detection in the cluster with
    confidence >= ``prefer_conf``, its class wins. Otherwise, if the cluster holds a rickshaw/van
    (from the open-vocabulary detector) with confidence >= ``new_class_conf``, the more
    confident of the two wins; otherwise the class
    with the largest summed confidence. These are *pre-labels*; review decides the final label.
    """
    cfg = cfg or MergeConfig()
    pool = sorted((d for d in dets if max(d.box[2] - d.box[0], d.box[3] - d.box[1])
                   >= cfg.min_side_px), key=lambda d: -d.conf)
    used = [False] * len(pool)
    labels = []
    for i, seed in enumerate(pool):
        if used[i]:
            continue
        used[i] = True
        cluster = [seed]
        for j in range(i + 1, len(pool)):
            if not used[j] and iou(seed.box, pool[j].box) >= cfg.iou_thr:
                used[j] = True
                cluster.append(pool[j])
        best = max(d.conf for d in cluster)
        sources = sorted({d.source for d in cluster})
        agreeing = {d.source for d in cluster if d.conf >= cfg.agree_conf}
        if best < cfg.keep_conf and len(agreeing) < 2:
            continue
        new = [d for d in cluster if d.cls in NEW_CLASSES and d.conf >= cfg.new_class_conf]
        pref = [d for d in cluster if cfg.prefer_source and d.source == cfg.prefer_source
                and d.conf >= cfg.prefer_conf]
        if pref:
            cls = max(pref, key=lambda d: d.conf).cls
        elif new:
            cls = max(new, key=lambda d: d.conf).cls
        else:
            score: dict[int, float] = {}
            for d in cluster:
                score[d.cls] = score.get(d.cls, 0.0) + d.conf
            cls = min(score, key=lambda c: (-score[c], c))
        wsum = sum(d.conf for d in cluster)
        box = tuple(sum(d.box[k] * d.conf for d in cluster) / wsum for k in range(4))
        labels.append(Label(cls, box, sources, round(best, 4)))
    return labels


# ---------------------------------------------------------------- YOLO label format


def to_yolo_line(lab: Label, w: float, h: float) -> str:
    x1, y1, x2, y2 = (max(0.0, min(v, lim)) for v, lim in zip(lab.box, (w, h, w, h), strict=True))
    return (f"{lab.cls} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
            f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")


def from_yolo_line(line: str, w: float, h: float) -> Label:
    c, cx, cy, bw, bh = line.split()
    cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
    return Label(int(c), (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))


# ---------------------------------------------------------------- review corrections


def apply_review(labels: list[Label], ops: list[dict]) -> tuple[list[Label], dict]:
    """Apply review operations for one image to its pre-labels (indexed as rendered, 0-based).

    ops: ``{"op": "del", "id": i}``, ``{"op": "cls", "id": i, "to": c}``,
    ``{"op": "add", "cls": c, "box": [x1, y1, x2, y2]}``.
    Returns the corrected labels and a change log ``{"deleted": n, "reclassed": n, "added": n,
    "by_class": {name: {"deleted", "reclassed_to", "reclassed_from", "added"}}}``.
    """
    out = [Label(lab.cls, lab.box, list(lab.sources), lab.conf) for lab in labels]
    dead = set()
    log = {"deleted": 0, "reclassed": 0, "added": 0,
           "by_class": {n: {"deleted": 0, "reclassed_from": 0, "reclassed_to": 0, "added": 0}
                        for n in CLASS_NAMES}}
    added = []
    for op in ops:
        kind = op["op"]
        if kind in ("del", "cls"):
            i = int(op["id"])
            if not 0 <= i < len(out) or i in dead:
                raise ValueError(f"bad box id {i} in {op}")
            if kind == "del":
                dead.add(i)
                log["deleted"] += 1
                log["by_class"][CLASS_NAMES[out[i].cls]]["deleted"] += 1
            else:
                to = int(op["to"])
                if to == out[i].cls:
                    continue
                log["reclassed"] += 1
                log["by_class"][CLASS_NAMES[out[i].cls]]["reclassed_from"] += 1
                log["by_class"][CLASS_NAMES[to]]["reclassed_to"] += 1
                out[i].cls = to
                out[i].sources.append("review")
        elif kind == "add":
            c = int(op["cls"])
            x1, y1, x2, y2 = (float(v) for v in op["box"])
            if not (x2 > x1 and y2 > y1) or c not in range(len(CLASS_NAMES)):
                raise ValueError(f"bad add {op}")
            added.append(Label(c, (x1, y1, x2, y2), ["review"], 1.0))
            log["added"] += 1
            log["by_class"][CLASS_NAMES[c]]["added"] += 1
        else:
            raise ValueError(f"unknown op {op}")
    return [lab for i, lab in enumerate(out) if i not in dead] + added, log


# ---------------------------------------------------------------- split manifest


def load_manifest(path) -> list[dict]:
    """Read the split manifest CSV and check it: known splits, unique images, and no shot in
    more than one split (the split is by shot, never by frame)."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    check_manifest(rows)
    return rows


def check_manifest(rows: list[dict]) -> None:
    seen = set()
    shot_split: dict[tuple[str, str], str] = {}
    for r in rows:
        if r["split"] not in (*SPLITS, UNUSED):
            raise ValueError(f"unknown split {r['split']!r} for {r['image']}")
        if r["image"] in seen:
            raise ValueError(f"duplicate image {r['image']}")
        seen.add(r["image"])
        if r["split"] == UNUSED:
            continue
        key = (r["video"], str(r["shot"]))
        if shot_split.setdefault(key, r["split"]) != r["split"]:
            raise ValueError(f"shot {key} appears in more than one split")


def split_by_shot(frames: list[dict], test_shots: set, val_shots: set,
                  boundaries: dict | None = None, guard_s: float = 0.0) -> list[dict]:
    """Assign every frame row (``video``, ``shot``, ``image``, ``time_s``...) to a split by its
    shot key ``(video, shot)``; shots in neither set are train.

    ``boundaries`` maps ``(video, shot)`` to ``(start_s, end_s)``. A frame within ``guard_s``
    seconds of a boundary shared with the neighbouring shot (shot +- 1) of a *different* split is
    marked ``unused``, so the same vehicles never appear in two splits."""

    def split_of(key):
        return "test" if key in test_shots else "val" if key in val_shots else "train"

    out = []
    for r in frames:
        key = (r["video"], int(r["shot"]))
        split = split_of(key)
        if boundaries and guard_s > 0:
            t = float(r["time_s"])
            start, end = boundaries[key]
            prev_key, next_key = (key[0], key[1] - 1), (key[0], key[1] + 1)
            if (prev_key in boundaries and split_of(prev_key) != split and t - start < guard_s) \
                    or (next_key in boundaries and split_of(next_key) != split
                        and end - t < guard_s):
                split = UNUSED
        out.append({**r, "split": split})
    check_manifest(out)
    return out
