"""Line-crossing counting and a queue (stopped-vehicle) estimate for tracked vehicles (V.4, V.5).

Pure Python, standard library only, so the same code runs in the Kaggle kernel
(`kaggle/yolo_track`, which inlines this file) and in the unit tests (`tests/test_counting.py`).

Inputs are per-frame lists of tracked boxes ``(track_id, class_id, left, top, width, height)`` in
pixels. They come either from YOLO + ByteTrack (predictions) or from the UA-DETRAC annotation XML,
whose target ids are the ground-truth track ids. Both pass through exactly the same counter, so the
counting error measures detection + tracking, not a difference in counting rules.

Counting rule (one count per track at most):
  * the reference point of a box is its centre;
  * a track is counted when the segment between two consecutive observed centres properly crosses
    the counting line segment (side changes from one strict side to the other);
  * every track is counted at most once, so a track that jitters on the line is not counted twice;
  * crossings whose intersection point lies inside a DETRAC ignored region are dropped (the
    ground truth has no labels there);
  * the class of a counted vehicle is the majority class over the whole track.

Queue estimate (a proxy, because UA-DETRAC has no stop lines or signal states): the number of
tracked vehicles in the region of interest that are *stopped*, i.e. whose centre moved less than
``stop_frac`` x (box height) over the last ``window`` frames. Dividing by the box height makes the
threshold roughly independent of the distance to the camera.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field

CLASS_NAMES = ["car", "bus", "truck", "motorcycle"]
DETRAC_MAP = {"car": 0, "van": 0, "bus": 1, "others": 2}

Point = tuple[float, float]
Box = tuple[float, float, float, float]  # left, top, width, height
Region = tuple[float, float, float, float]  # left, top, width, height


# ---------------------------------------------------------------- geometry


def centre(box: Box) -> Point:
    left, top, w, h = box
    return (left + w / 2.0, top + h / 2.0)


def side(p: Point, a: Point, b: Point) -> int:
    """+1 / -1 for the two sides of the directed line a->b, 0 if exactly on it."""
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return (cross > 0) - (cross < 0)


def segment_intersection(p: Point, q: Point, a: Point, b: Point) -> Point | None:
    """Intersection of segment p-q with segment a-b, or None if they do not meet."""
    rx, ry = q[0] - p[0], q[1] - p[1]
    sx, sy = b[0] - a[0], b[1] - a[1]
    den = rx * sy - ry * sx
    if den == 0:
        return None
    t = ((a[0] - p[0]) * sy - (a[1] - p[1]) * sx) / den
    u = ((a[0] - p[0]) * ry - (a[1] - p[1]) * rx) / den
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (p[0] + t * rx, p[1] + t * ry)
    return None


def in_any_region(p: Point, regions) -> bool:
    return any(x0 <= p[0] <= x0 + w and y0 <= p[1] <= y0 + h for (x0, y0, w, h) in regions)


def horizontal_line(img_w: float, img_h: float, frac: float) -> tuple[Point, Point]:
    """A full-width counting line at ``frac`` of the image height, directed left -> right.

    With image y pointing down, side() is +1 below the line and -1 above it, so a crossing from
    -1 to +1 is a vehicle moving down the image ("down")."""
    y = frac * img_h
    return (0.0, y), (float(img_w), y)


# ---------------------------------------------------------------- counting


@dataclass
class CrossingEvent:
    frame: int
    track_id: int
    direction: str  # "down"/"up" for horizontal lines: "neg_to_pos" is reported as "down"
    x: float
    y: float
    class_id: int = -1  # filled in by LineCounter.finalize() (majority vote over the track)


@dataclass
class LineCounter:
    a: Point
    b: Point
    ignored: list = field(default_factory=list)

    def __post_init__(self):
        self._last: dict[int, tuple[Point, int]] = {}  # track -> (last centre, last strict side)
        self._counted: set[int] = set()
        self._votes: dict[int, Counter] = defaultdict(Counter)
        self.events: list[CrossingEvent] = []

    def update(self, frame: int, tracks) -> list[CrossingEvent]:
        """Feed one frame of ``(track_id, class_id, left, top, w, h)``; return new crossings."""
        new = []
        for tid, cls, *box in tracks:
            tid = int(tid)
            self._votes[tid][int(cls)] += 1
            c = centre(tuple(box))
            s = side(c, self.a, self.b)
            prev = self._last.get(tid)
            if s == 0:  # exactly on the line: wait for a strict side, keep the old one
                if prev is not None:
                    self._last[tid] = (c, prev[1])
                continue
            if prev is not None and prev[1] != s and tid not in self._counted:
                hit = segment_intersection(prev[0], c, self.a, self.b)
                if hit is not None:
                    self._counted.add(tid)  # counted (or deliberately dropped) once only
                    if not in_any_region(hit, self.ignored):
                        ev = CrossingEvent(frame, tid, "down" if s > 0 else "up", hit[0], hit[1])
                        self.events.append(ev)
                        new.append(ev)
            self._last[tid] = (c, s)
        return new

    def majority_class(self, tid: int) -> int:
        votes = self._votes.get(tid)
        if not votes:
            return -1
        best = max(votes.values())
        return min(k for k, v in votes.items() if v == best)  # ties -> lowest class id

    def finalize(self) -> list[CrossingEvent]:
        for ev in self.events:
            ev.class_id = self.majority_class(ev.track_id)
        return self.events

    def running_count(self) -> int:
        return len(self.events)


def counts_by_class(events, n_classes: int = len(CLASS_NAMES)) -> list[int]:
    out = [0] * n_classes
    for ev in events:
        if 0 <= ev.class_id < n_classes:
            out[ev.class_id] += 1
    return out


# ---------------------------------------------------------------- queue estimate


@dataclass
class QueueEstimator:
    window: int = 25  # frames (1 s at UA-DETRAC's 25 fps)
    stop_frac: float = 0.25  # stopped if moved < stop_frac * box height over `window` frames
    roi: Region | None = None  # None = whole frame
    ignored: list = field(default_factory=list)
    max_gap: int = 5  # a track history is restarted after a gap of more than this many frames

    def __post_init__(self):
        self._hist: dict[int, deque] = {}

    def update(self, frame: int, tracks) -> tuple[int, set[int]]:
        """Feed one frame; return (number of stopped vehicles, their track ids)."""
        stopped = set()
        seen = set()
        for tid, _cls, *box in tracks:
            tid = int(tid)
            seen.add(tid)
            c = centre(tuple(box))
            h = self._hist.get(tid)
            if h is None or frame - h[-1][0] > self.max_gap:
                h = self._hist[tid] = deque()
            h.append((frame, c, float(box[3])))
            while h and h[0][0] < frame - self.window:
                h.popleft()
            if h[0][0] > frame - self.window:  # not observed for a full window yet
                continue
            if self.roi is not None and not in_any_region(c, [self.roi]):
                continue
            if in_any_region(c, self.ignored):
                continue
            _f0, c0, _ = h[0]
            moved = ((c[0] - c0[0]) ** 2 + (c[1] - c0[1]) ** 2) ** 0.5
            mean_h = sum(e[2] for e in h) / len(h)
            if moved < self.stop_frac * mean_h:
                stopped.add(tid)
        stale = [t for t in self._hist
                 if t not in seen and frame - self._hist[t][-1][0] > self.max_gap]
        for tid in stale:
            del self._hist[tid]
        return len(stopped), stopped


# ---------------------------------------------------------------- UA-DETRAC ground truth


def parse_detrac_tracks(text: str) -> tuple[list[Region], dict[int, list]]:
    """Parse a UA-DETRAC annotation XML into (ignored regions, {frame: [(id, cls, l, t, w, h)]}).

    The target ``id`` attribute is the ground-truth track id within the sequence."""
    root = ET.fromstring(text)
    ignored = []
    ign = root.find("ignored_region")
    if ign is not None:
        for b in ign.findall("box"):
            ignored.append(tuple(float(b.get(k)) for k in ("left", "top", "width", "height")))
    frames: dict[int, list] = {}
    for fr in root.iter("frame"):
        rows = []
        for tgt in fr.iter("target"):
            b = tgt.find("box")
            vtype = tgt.find("attribute").get("vehicle_type")
            if vtype not in DETRAC_MAP:
                raise ValueError(f"unknown DETRAC vehicle_type {vtype!r}")
            rows.append((int(tgt.get("id")), DETRAC_MAP[vtype],
                         *(float(b.get(k)) for k in ("left", "top", "width", "height"))))
        frames[int(fr.get("num"))] = rows
    return ignored, frames


# ---------------------------------------------------------------- error metrics


def count_errors(pairs) -> dict:
    """``pairs`` = [(predicted, true), ...], one per clip: MAE, bias, RMSE, relative errors."""
    pairs = list(pairs)
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    err = [p - t for p, t in pairs]
    abs_err = [abs(e) for e in err]
    total_true = sum(t for _, t in pairs)
    with_true = [(p, t) for p, t in pairs if t > 0]
    return {
        "n": n,
        "mae": sum(abs_err) / n,
        "bias": sum(err) / n,
        "rmse": (sum(e * e for e in err) / n) ** 0.5,
        "max_abs_error": max(abs_err),
        "total_true": total_true,
        "total_pred": sum(p for p, _ in pairs),
        # sum |error| / sum true: the share of vehicles miscounted, weighted by clip size
        "wape": (sum(abs_err) / total_true) if total_true else None,
        # mean of per-clip |error| / true over clips with at least one true crossing
        "mape": (sum(abs(p - t) / t for p, t in with_true) / len(with_true)) if with_true else None,
        "exact_clips": sum(1 for e in err if e == 0),
    }
