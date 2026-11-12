"""Tests for the UA-DETRAC + COCO -> YOLO converter (kaggle/yolo_data/prepare_yolo_data.py)."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare_yolo_data",
    Path(__file__).resolve().parents[1] / "kaggle" / "yolo_data" / "prepare_yolo_data.py",
)
pyd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pyd)

XML = """<?xml version="1.0" encoding="utf-8"?>
<sequence name="MVI_1">
  <sequence_attribute camera_state="unstable" sence_weather="sunny"/>
  <ignored_region>
    <box left="0" top="0" width="100" height="50"/>
  </ignored_region>
  <frame density="3" num="1">
    <target_list>
      <target id="1"><box left="200" top="100" width="100" height="60"/>
        <attribute vehicle_type="car"/></target>
      <target id="2"><box left="400" top="200" width="80" height="40"/>
        <attribute vehicle_type="van"/></target>
      <target id="3"><box left="10" top="10" width="20" height="20"/>
        <attribute vehicle_type="bus"/></target>
    </target_list>
  </frame>
  <frame density="1" num="2">
    <target_list>
      <target id="4"><box left="900" top="500" width="100" height="100"/>
        <attribute vehicle_type="others"/></target>
    </target_list>
  </frame>
</sequence>"""


def test_class_mapping_matches_plan():
    assert pyd.CLASS_NAMES == ["car", "bus", "truck", "motorcycle"]
    assert pyd.DETRAC_MAP == {"car": 0, "van": 0, "bus": 1, "others": 2}
    # COCO ids: car 3, motorcycle 4, bus 6, truck 8
    assert pyd.COCO_MAP == {3: 0, 6: 1, 8: 2, 4: 3}


def test_parse_and_convert_detrac():
    ignored, frames = pyd.parse_detrac_xml(XML)
    assert ignored == [(0.0, 0.0, 100.0, 50.0)]
    assert sorted(frames) == [1, 2]
    lines = pyd.detrac_frame_labels(frames[1], ignored, 960, 540)
    # the bus centre (20, 20) is inside the ignored region -> dropped; van -> car
    assert [ln.split()[0] for ln in lines] == ["0", "0"]
    cls, cx, cy, w, h = lines[0].split()
    assert float(cx) == pytest.approx(250 / 960, abs=1e-6)
    assert float(cy) == pytest.approx(130 / 540, abs=1e-6)
    assert float(w) == pytest.approx(100 / 960, abs=1e-6)
    assert float(h) == pytest.approx(60 / 540, abs=1e-6)
    # the 'others' box goes past the image corner: clipped to 60 x 40 px, class truck
    (line,) = pyd.detrac_frame_labels(frames[2], ignored, 960, 540)
    cls, cx, cy, w, h = line.split()
    assert cls == "2"
    assert float(w) == pytest.approx(60 / 960, abs=1e-6)
    assert float(h) == pytest.approx(40 / 540, abs=1e-6)


def test_unknown_vehicle_type_fails_loudly():
    with pytest.raises(ValueError):
        pyd.detrac_frame_labels([("tram", 1, 1, 10, 10)], [], 960, 540)


def test_val_split_is_by_whole_sequence():
    seqs = [f"MVI_{i:05d}" for i in range(60)]
    train, val = pyd.split_detrac_sequences(seqs)
    assert len(val) == 6 and len(train) == 54
    assert not set(train) & set(val)


def test_coco_motorcycle_selection_keeps_all_four_classes():
    coco = {
        "images": [{"id": 1, "width": 640, "height": 480}, {"id": 2, "width": 640, "height": 480}],
        "annotations": [
            {"image_id": 1, "category_id": 4, "bbox": [10, 10, 50, 50], "iscrowd": 0},
            {"image_id": 1, "category_id": 3, "bbox": [100, 100, 50, 50], "iscrowd": 0},
            {"image_id": 1, "category_id": 1, "bbox": [200, 100, 50, 50], "iscrowd": 0},  # person
            {"image_id": 1, "category_id": 8, "bbox": [300, 100, 50, 50], "iscrowd": 1},  # crowd
            {"image_id": 2, "category_id": 3, "bbox": [10, 10, 50, 50], "iscrowd": 0},  # no moto
        ],
    }
    out = pyd.coco_images_with_motorcycle(coco)
    assert list(out) == [1]
    assert sorted(ln.split()[0] for ln in out[1]) == ["0", "3"]


def test_tiny_box_dropped():
    assert pyd.to_yolo_line(0, 5, 5, 1, 1, 100, 100) is None
