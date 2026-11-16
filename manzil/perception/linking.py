"""Link labelled boxes of sparse frames (about 2 fps) into tracks (workstream W2).

The reviewed Lahore labels exist only on frames sampled at about 2 fps and have no track ids.
To get reference line-crossing counts from them, boxes of consecutive labelled frames are linked
greedily: a box continues the nearest previous box if the centre distance, divided by the mean of
the two box diagonals, is below ``gate`` and the sizes are similar. The result goes through the
same ``LineCounter`` as the tracker output. This is an approximation (fast vehicles in dense
traffic can be linked wrongly), so counts from it are a *reference*, not exact ground truth.

Pure Python, standard library only (inlined into the Kaggle kernel `kaggle/lahore_train`).
"""

from __future__ import annotations


def _diag(b) -> float:
    return ((b[2] - b[0]) ** 2 + (b[3] - b[1]) ** 2) ** 0.5


def _centre(b) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


class GreedyLinker:
    """Feed frames in time order: ``update([(cls, x1, y1, x2, y2), ...])`` returns
    ``[(track_id, cls, left, top, width, height), ...]`` (the LineCounter input format)."""

    def __init__(self, gate: float = 1.5, max_size_ratio: float = 2.0, max_missed: int = 1):
        self.gate = gate
        self.max_size_ratio = max_size_ratio
        self.max_missed = max_missed  # a track survives this many frames without a match
        self._tracks: dict[int, tuple[tuple, int]] = {}  # id -> (last box, frames missed)
        self._next = 1

    def update(self, boxes) -> list[tuple]:
        boxes = [(int(c), float(x1), float(y1), float(x2), float(y2))
                 for c, x1, y1, x2, y2 in boxes]
        pairs = []
        for tid, (tb, _missed) in self._tracks.items():
            tc, td = _centre(tb), _diag(tb)
            for j, (_c, *b) in enumerate(boxes):
                bd = _diag(b)
                if td <= 0 or bd <= 0 or max(td, bd) / min(td, bd) > self.max_size_ratio:
                    continue
                bc = _centre(b)
                cost = ((tc[0] - bc[0]) ** 2 + (tc[1] - bc[1]) ** 2) ** 0.5 / ((td + bd) / 2.0)
                if cost < self.gate:
                    pairs.append((cost, tid, j))
        pairs.sort()
        used_t, used_b, assigned = set(), set(), {}
        for _cost, tid, j in pairs:
            if tid in used_t or j in used_b:
                continue
            used_t.add(tid)
            used_b.add(j)
            assigned[j] = tid
        out = []
        new_tracks: dict[int, tuple[tuple, int]] = {}
        for j, (c, *b) in enumerate(boxes):
            tid = assigned.get(j)
            if tid is None:
                tid = self._next
                self._next += 1
            new_tracks[tid] = (tuple(b), 0)
            out.append((tid, c, b[0], b[1], b[2] - b[0], b[3] - b[1]))
        for tid, (tb, missed) in self._tracks.items():
            if tid not in new_tracks and missed < self.max_missed:
                new_tracks[tid] = (tb, missed + 1)
        self._tracks = new_tracks
        return out
