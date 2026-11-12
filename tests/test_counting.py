"""Tests for line-crossing counting, the queue estimate and DETRAC track parsing (V.4, V.5)."""

import sys
from pathlib import Path

import pytest

from manzil.perception.counting import (
    LineCounter,
    QueueEstimator,
    count_errors,
    counts_by_class,
    horizontal_line,
    parse_detrac_tracks,
    segment_intersection,
    side,
)

ROOT = Path(__file__).resolve().parents[1]
LINE = horizontal_line(100, 100, 0.5)  # y = 50, left -> right


def box_at(cx, cy, w=10, h=10):
    return (cx - w / 2, cy - h / 2, w, h)


def test_side_and_intersection():
    a, b = LINE
    assert side((10, 60), a, b) == 1  # below (image y down)
    assert side((10, 40), a, b) == -1
    assert side((10, 50), a, b) == 0
    assert segment_intersection((10, 40), (10, 60), a, b) == (10, 50)
    assert segment_intersection((10, 40), (10, 45), a, b) is None
    assert segment_intersection((150, 40), (150, 60), a, b) is None  # outside the line segment


def test_vehicle_moving_down_is_counted_once():
    c = LineCounter(*LINE)
    for f, y in enumerate([30, 40, 48, 55, 49, 60, 70], start=1):  # jitters back over the line
        c.update(f, [(7, 0, *box_at(20, y))])
    ev = c.finalize()
    assert len(ev) == 1
    assert ev[0].direction == "down" and ev[0].frame == 4 and ev[0].track_id == 7


def test_directions_and_no_count_without_crossing():
    c = LineCounter(*LINE)
    for f in range(1, 6):
        c.update(f, [(1, 0, *box_at(20, 80 - 10 * f)),  # 70 -> 30: up
                     (2, 1, *box_at(40, 10 + 5 * f)),  # 15 -> 35: never reaches the line
                     (3, 2, *box_at(60, 20 + 10 * f))])  # 30 -> 70: down
    ev = {e.track_id: e for e in c.finalize()}
    assert set(ev) == {1, 3}
    assert ev[1].direction == "up" and ev[3].direction == "down"


def test_point_exactly_on_line_then_across():
    c = LineCounter(*LINE)
    for f, y in enumerate([40, 50, 50, 60], start=1):
        c.update(f, [(1, 0, *box_at(20, y))])
    assert len(c.finalize()) == 1


def test_crossing_in_ignored_region_dropped_and_not_recounted():
    c = LineCounter(*LINE, ignored=[(0, 40, 30, 20)])  # covers x 0..30 around the line
    for f, y in enumerate([40, 60, 40, 60], start=1):
        c.update(f, [(1, 0, *box_at(20, y))])
    assert c.finalize() == []


def test_majority_class_and_counts_by_class():
    c = LineCounter(*LINE)
    classes = [2, 0, 0, 0, 2]
    for f, (y, cls) in enumerate(zip([30, 40, 60, 70, 80], classes, strict=True), start=1):
        c.update(f, [(5, cls, *box_at(20, y))])
    ev = c.finalize()
    assert ev[0].class_id == 0
    assert counts_by_class(ev) == [1, 0, 0, 0]


def test_queue_estimator_stopped_vs_moving():
    q = QueueEstimator(window=5, stop_frac=0.25)
    n = 0
    for f in range(1, 12):
        n, ids = q.update(f, [(1, 0, *box_at(20, 20 + 0.1 * f, h=20)),  # nearly still
                              (2, 0, *box_at(50, 10 + 5 * f, h=20))])  # moving fast
    assert n == 1 and ids == {1}


def test_queue_needs_full_window_and_respects_roi():
    q = QueueEstimator(window=5, stop_frac=0.25, roi=(0, 0, 30, 100))
    assert q.update(1, [(1, 0, *box_at(20, 20))])[0] == 0  # too new
    for f in range(2, 8):
        n, _ = q.update(f, [(1, 0, *box_at(20, 20)), (2, 0, *box_at(60, 20))])
    assert n == 1  # track 2 is stopped but outside the ROI


def test_queue_history_restarts_after_gap():
    q = QueueEstimator(window=5, stop_frac=0.25, max_gap=2)
    for f in range(1, 8):
        q.update(f, [(1, 0, *box_at(20, 20))])
    assert q.update(20, [(1, 0, *box_at(20, 20))])[0] == 0  # history restarted


XML = """<?xml version="1.0" encoding="utf-8"?>
<sequence name="MVI_1">
  <ignored_region><box left="0" top="0" width="10" height="10"/></ignored_region>
  <frame density="2" num="1"><target_list>
    <target id="1"><box left="10" top="30" width="10" height="10"/>
      <attribute vehicle_type="van"/></target>
    <target id="2"><box left="50" top="70" width="10" height="10"/>
      <attribute vehicle_type="bus"/></target>
  </target_list></frame>
  <frame density="1" num="2"><target_list>
    <target id="1"><box left="10" top="60" width="10" height="10"/>
      <attribute vehicle_type="van"/></target>
  </target_list></frame>
</sequence>"""


def test_parse_detrac_tracks_and_ground_truth_count():
    ignored, frames = parse_detrac_tracks(XML)
    assert ignored == [(0.0, 0.0, 10.0, 10.0)]
    assert frames[1][0] == (1, 0, 10.0, 30.0, 10.0, 10.0)  # van -> car (0)
    assert frames[1][1][:2] == (2, 1)
    c = LineCounter(*LINE, ignored=ignored)
    for f in sorted(frames):
        c.update(f, frames[f])
    ev = c.finalize()
    assert [(e.track_id, e.class_id, e.direction) for e in ev] == [(1, 0, "down")]


def test_parse_rejects_unknown_type():
    with pytest.raises(ValueError):
        parse_detrac_tracks(XML.replace('"bus"', '"tram"'))


def test_count_errors():
    m = count_errors([(10, 12), (5, 5), (0, 0), (9, 6)])
    assert m["n"] == 4
    assert m["mae"] == pytest.approx(5 / 4)
    assert m["bias"] == pytest.approx(1 / 4)
    assert m["wape"] == pytest.approx(5 / 23)
    assert m["mape"] == pytest.approx((2 / 12 + 0 + 3 / 6) / 3)
    assert m["exact_clips"] == 2
    assert count_errors([]) == {"n": 0}


def test_kaggle_kernel_is_built_from_current_sources():
    sys.path.insert(0, str(ROOT / "kaggle" / "yolo_track"))
    try:
        import build
    finally:
        sys.path.pop(0)
    committed = (ROOT / "kaggle" / "yolo_track" / "track_count.py").read_text()
    assert committed == build.build(), "run: python kaggle/yolo_track/build.py"
    compile(committed, "track_count.py", "exec")
