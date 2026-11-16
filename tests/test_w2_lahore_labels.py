"""Tests for the W2 six-class label tools (manzil/perception/lahore_labels.py)."""

import json
from pathlib import Path

import pytest

from manzil.perception import lahore_labels as ll

ROOT = Path(__file__).resolve().parents[1]


def test_class_ids_keep_the_old_four_class_model():
    assert ll.CLASS_NAMES[:4] == ["car", "bus", "truck", "motorcycle"]
    assert ll.CLASS_NAMES[4:] == ["rickshaw", "van"]
    from manzil.perception.counting import CLASS_NAMES as OLD

    assert ll.OLD_CLASS_NAMES == OLD


def test_maps_cover_prompts_and_coco():
    assert set(ll.WORLD_MAP) == set(range(len(ll.WORLD_PROMPTS)))
    assert ll.WORLD_MAP[ll.WORLD_PROMPTS.index("auto rickshaw")] == 4
    assert ll.WORLD_MAP[ll.WORLD_PROMPTS.index("loader rickshaw")] == 4
    assert ll.WORLD_MAP[ll.WORLD_PROMPTS.index("van")] == 5
    assert ll.COCO_MAP == {2: 0, 5: 1, 7: 2, 3: 3}
    dets = ll.map_dets([[2, 0.9, 0, 0, 10, 10], [0, 0.9, 0, 0, 10, 10]], ll.COCO_MAP, "coco")
    assert [d.cls for d in dets] == [0]  # COCO person (0) is dropped


def test_iou():
    assert ll.iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert ll.iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert ll.iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_merge_new_class_overrides_and_weighted_box():
    dets = [
        ll.Det(0, 0.8, (0, 0, 40, 40), "manzil4"),
        ll.Det(0, 0.6, (2, 0, 42, 40), "coco_x"),
        ll.Det(4, 0.4, (1, 0, 41, 40), "world"),
    ]
    (lab,) = ll.merge(dets)
    assert lab.cls == 4
    assert lab.sources == ["coco_x", "manzil4", "world"]
    assert lab.box[0] == pytest.approx((0 * 0.8 + 2 * 0.6 + 1 * 0.4) / 1.8)


def test_merge_keeps_confident_or_agreed_and_drops_weak_single():
    dets = [
        ll.Det(3, 0.5, (0, 0, 20, 20), "a"),  # confident single -> kept
        ll.Det(0, 0.2, (100, 100, 140, 140), "a"),  # two weak but agreeing -> kept
        ll.Det(0, 0.2, (101, 100, 141, 140), "b"),
        ll.Det(0, 0.2, (300, 300, 340, 340), "a"),  # weak single -> dropped
        ll.Det(0, 0.9, (500, 500, 505, 505), "a"),
    ]  # too small -> dropped
    labs = ll.merge(dets)
    assert sorted(lab.cls for lab in labs) == [0, 3]


def test_merge_class_vote_without_new_class():
    dets = [
        ll.Det(0, 0.5, (0, 0, 40, 40), "a"),
        ll.Det(2, 0.4, (0, 0, 40, 40), "b"),
        ll.Det(2, 0.3, (0, 0, 40, 40), "c"),
        ll.Det(5, 0.1, (0, 0, 40, 40), "world"),
    ]
    (lab,) = ll.merge(dets)
    assert lab.cls == 2  # 0.7 truck vs 0.5 car; the van at 0.1 is below new_class_conf


def test_yolo_line_roundtrip_and_clipping():
    lab = ll.Label(5, (10, 20, 110, 70))
    line = ll.to_yolo_line(lab, 200, 100)
    assert line == "5 0.300000 0.450000 0.500000 0.500000"
    back = ll.from_yolo_line(line, 200, 100)
    assert back.cls == 5 and back.box == pytest.approx((10, 20, 110, 70))
    clipped = ll.to_yolo_line(ll.Label(0, (-10, 0, 50, 120)), 100, 100)
    assert clipped == "0 0.250000 0.500000 0.500000 1.000000"


def test_apply_review_ops_and_log():
    labs = [ll.Label(0, (0, 0, 10, 10)), ll.Label(0, (20, 0, 30, 10)), ll.Label(3, (40, 0, 50, 9))]
    out, log = ll.apply_review(
        labs,
        [
            {"op": "del", "id": 1},
            {"op": "cls", "id": 0, "to": 4},
            {"op": "add", "cls": 5, "box": [60, 0, 80, 20]},
            {"op": "cls", "id": 2, "to": 3},
        ],
    )
    assert [lab.cls for lab in out] == [4, 3, 5]
    assert labs[0].cls == 0  # input untouched
    assert (log["deleted"], log["reclassed"], log["added"]) == (1, 1, 1)
    assert log["by_class"]["car"] == {
        "deleted": 1,
        "reclassed_from": 1,
        "reclassed_to": 0,
        "added": 0,
    }
    assert log["by_class"]["rickshaw"]["reclassed_to"] == 1
    with pytest.raises(ValueError):
        ll.apply_review(labs, [{"op": "del", "id": 7}])
    with pytest.raises(ValueError):
        ll.apply_review(labs, [{"op": "add", "cls": 1, "box": [5, 5, 1, 1]}])
    with pytest.raises(ValueError):
        ll.apply_review(labs, [{"op": "del", "id": 0}, {"op": "del", "id": 0}])


def test_split_by_shot_and_manifest_checks():
    frames = [
        {"image": f"v1_s{s}_f{i}.jpg", "video": "v1", "shot": s} for s in range(3) for i in range(2)
    ]
    frames.append({"image": "v2_s0_f0.jpg", "video": "v2", "shot": 0})
    rows = ll.split_by_shot(frames, test_shots={("v1", 2), ("v2", 0)}, val_shots={("v1", 0)})
    assert [r["split"] for r in rows] == ["val", "val", "train", "train", "test", "test", "test"]
    timed = [{**f, "time_s": t} for f, t in zip(frames, [1, 9, 11, 19, 21, 29, 5], strict=True)]
    bounds = {("v1", 0): (0, 10), ("v1", 1): (10, 20), ("v1", 2): (20, 30), ("v2", 0): (0, 10)}
    rows_g = ll.split_by_shot(timed, {("v1", 2), ("v2", 0)}, {("v1", 0)}, bounds, guard_s=2)
    assert [r["split"] for r in rows_g] == [
        "val",
        "unused",
        "unused",
        "unused",
        "unused",
        "test",
        "test",
    ]
    bad = [dict(rows[0]), {**rows[1], "split": "train"}]
    with pytest.raises(ValueError, match="more than one split"):
        ll.check_manifest(bad)
    with pytest.raises(ValueError, match="duplicate"):
        ll.check_manifest([rows[0], rows[0]])


def test_committed_manifest_is_valid_if_present():
    path = ROOT / "data" / "lahore_video" / "split_manifest.csv"
    if not path.exists():
        pytest.skip("manifest not written yet")
    rows = ll.load_manifest(path)
    test_v1 = [r for r in rows if r["video"] == "v1" and r["split"] == "test"]
    used_v1 = [r for r in rows if r["video"] == "v1" and r["split"] in ll.SPLITS]
    assert all(r["split"] == "test" for r in rows if r["video"] == "v2")
    assert {r["split"] for r in rows} <= {*ll.SPLITS, ll.UNUSED}
    assert 0.2 <= len(test_v1) / len(used_v1) <= 0.35


def test_merge_prefer_source_decides_class():
    dets = [
        ll.Det(0, 0.9, (0, 0, 40, 40), "coco_x"),
        ll.Det(5, 0.6, (0, 0, 40, 40), "world"),
        ll.Det(4, 0.3, (1, 0, 41, 40), "boot"),
    ]
    (lab,) = ll.merge(dets, ll.MergeConfig(prefer_source="boot", prefer_conf=0.25))
    assert lab.cls == 4
    (lab,) = ll.merge(dets, ll.MergeConfig(prefer_source="boot", prefer_conf=0.5))
    assert lab.cls == 5  # boot too unsure -> the open-vocabulary van wins


def test_review_prelabel_and_apply_roundtrip(tmp_path):
    from PIL import Image

    from manzil.perception import lahore_review as lr

    img = "v1_s1_f00010.jpg"
    Image.new("RGB", (200, 100)).save(tmp_path / img)
    raw = {
        "meta": {},
        "detections": {
            img: {
                "manzil4": [[0, 0.9, 10, 50, 50, 90], [3, 0.2, 120, 50, 140, 90]],
                "coco_x": [[2, 0.8, 11, 50, 51, 90], [3, 0.2, 121, 50, 141, 90]],
                "world": [[4, 0.5, 10, 51, 50, 90]],
            }
        },
    }
    (tmp_path / "raw.json").write_text(json.dumps(raw))
    lr.cmd_prelabel(tmp_path / "raw.json", tmp_path / "rev")
    pre = json.loads((tmp_path / "rev" / "prelabels.json").read_text())
    labs = pre["images"][img]["labels"]
    assert [x["cls"] for x in labs] == [4, 3]  # rickshaw override; weak moto kept by agreement
    ops = [
        {"op": "far", "y": 0},
        {"op": "cls", "id": 1, "to": 0},
        {"op": "add", "cls": 5, "box": [60, 60, 90, 95]},
    ]
    (tmp_path / "review.jsonl").write_text(json.dumps({"image": img, "ops": ops}) + "\n")
    lr.cmd_apply(tmp_path, tmp_path / "rev", tmp_path / "review.jsonl")
    lines = (tmp_path / "rev" / "labels" / "v1_s1_f00010.txt").read_text().split("\n")
    assert [ln.split()[0] for ln in lines if ln] == ["4", "0", "5"]
