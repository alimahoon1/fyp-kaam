"""Tests for linking sparse labelled boxes into tracks (manzil/perception/linking.py)."""

from manzil.perception.counting import LineCounter, counts_by_class, horizontal_line
from manzil.perception.linking import GreedyLinker


def box(cx, cy, w=20, h=20):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def test_two_vehicles_keep_their_ids():
    lk = GreedyLinker()
    a = lk.update([(0, *box(50, 50)), (4, *box(150, 50))])
    b = lk.update([(4, *box(150, 70)), (0, *box(50, 65))])  # order swapped
    ids_a = {r[1]: r[0] for r in a}
    ids_b = {r[1]: r[0] for r in b}
    assert ids_a == ids_b and len(set(ids_a.values())) == 2


def test_far_jump_or_size_change_starts_a_new_track():
    lk = GreedyLinker(gate=1.5)
    (a,) = lk.update([(0, *box(50, 50))])
    (b,) = lk.update([(0, *box(50, 200))])  # 150 px with a 28 px diagonal: too far
    assert a[0] != b[0]
    lk = GreedyLinker()
    (a,) = lk.update([(0, *box(50, 50, 20, 20))])
    (b,) = lk.update([(0, *box(52, 52, 80, 80))])  # 4x larger
    assert a[0] != b[0]


def test_track_survives_one_missed_frame_only():
    lk = GreedyLinker(max_missed=1)
    (a,) = lk.update([(3, *box(50, 50))])
    assert lk.update([]) == []
    (b,) = lk.update([(3, *box(55, 55))])
    assert a[0] == b[0]
    lk.update([])
    lk.update([])
    (c,) = lk.update([(3, *box(55, 55))])
    assert c[0] != a[0]


def test_linked_tracks_feed_the_line_counter():
    lk = GreedyLinker()
    counter = LineCounter(*horizontal_line(200, 200, 0.5))
    for f, y in enumerate([60, 80, 95, 110, 130]):
        counter.update(f, lk.update([(4, *box(50, y)), (0, *box(150, 200 - y))]))
    events = counter.finalize()
    assert sorted(e.direction for e in events) == ["down", "up"]
    assert counts_by_class(events, 6) == [1, 0, 0, 0, 1, 0]


def test_lahore_train_kernel_is_built_from_current_sources():
    import importlib.util
    from pathlib import Path

    here = Path(__file__).resolve().parents[1] / "kaggle" / "lahore_train"
    spec = importlib.util.spec_from_file_location("lahore_train_build", here / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    committed = (here / "lahore_train.py").read_text()
    assert committed == mod.build(), "run: python kaggle/lahore_train/build.py"
    compile(committed, "lahore_train.py", "exec")
