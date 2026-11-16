"""Raw pre-label detections for the Lahore frames (W2 step 4). GPU kernel.

Inputs (kernel_sources): the frames from `manzil-lahore-frames` and the fine-tuned four-class
model `out/best.pt` from `manzil-yolo-train` (= models/yolo/manzil_yolo11s_best.pt, sha256
checked). Three detectors run on every frame at a low confidence (CONF), so that merging and
thresholds can be tuned later without the GPU:
  * manzil4: the fine-tuned YOLO11s (car, bus, truck, motorcycle);
  * coco_x:  COCO-pretrained YOLO11x (car, bus, truck, motorcycle; a stronger general model);
  * world:   open-vocabulary YOLO-World v2 (x) with the prompts in WORLD_PROMPTS, which brings
             the new classes rickshaw (auto / loader rickshaw) and van.
Output: /kaggle/working/raw_detections.json = {image: {source: [[cls, conf, x1, y1, x2, y2]]}}
with source class ids (mapping to the six W2 classes is in manzil/perception/lahore_labels.py).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys
import time

ULTRALYTICS = "ultralytics==8.4.210"
WEIGHTS_SHA256 = "0022c8a0394bf8a583ef0d21e324853a73251ca86a3ac6caab656fd65ae8dc2f"
WORLD_PROMPTS = ["car", "bus", "truck", "motorcycle", "auto rickshaw", "loader rickshaw", "van"]
COCO_KEEP = [2, 3, 5, 7]
IMGSZ = 1280
CONF = 0.05
INPUT = "/kaggle/input"
OUT = "/kaggle/working"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(result):
    b = result.boxes
    return [[int(c), round(float(p), 4), *[round(float(v), 1) for v in xy]]
            for c, p, xy in zip(b.cls.tolist(), b.conf.tolist(), b.xyxy.tolist(), strict=True)]


def main():
    subprocess.run(f"pip install -q {ULTRALYTICS}", shell=True, check=True)
    import torch
    import ultralytics
    from ultralytics import YOLO, YOLOWorld

    weights = sorted(glob.glob(f"{INPUT}/**/out/best.pt", recursive=True))[0]
    w_sha = sha256(weights)
    if w_sha != WEIGHTS_SHA256:
        raise RuntimeError(f"weights sha256 {w_sha}")
    images = sorted(glob.glob(f"{INPUT}/**/frames/*.jpg", recursive=True))
    print(len(images), "images", flush=True)
    models = {"manzil4": (YOLO(weights), None),
              "coco_x": (YOLO("yolo11x.pt"), COCO_KEEP)}
    world = YOLOWorld("yolov8x-worldv2.pt")
    world.set_classes(WORLD_PROMPTS)
    models["world"] = (world, None)
    det = {os.path.basename(p): {} for p in images}
    timing = {}
    for name, (m, keep) in models.items():
        t = time.time()
        for i in range(0, len(images), 16):
            batch = images[i:i + 16]
            res = m.predict(batch, imgsz=IMGSZ, conf=CONF, iou=0.6, classes=keep, device=0,
                            max_det=500, verbose=False)
            for p, r in zip(batch, res, strict=True):
                det[os.path.basename(p)][name] = rows(r)
        timing[name] = round(time.time() - t, 1)
        print(name, timing[name], "s", flush=True)
    meta = {"imgsz": IMGSZ, "conf": CONF, "nms_iou": 0.6, "world_prompts": WORLD_PROMPTS,
            "coco_keep": COCO_KEEP, "weights_sha256": w_sha,
            "models": {"manzil4": "manzil_yolo11s_best.pt", "coco_x": "yolo11x.pt",
                       "world": "yolov8x-worldv2.pt"},
            "versions": {"ultralytics": ultralytics.__version__, "torch": torch.__version__,
                         "python": sys.version.split()[0]},
            "device": torch.cuda.get_device_name(0), "seconds": timing, "images": len(images)}
    json.dump({"meta": meta, "detections": det}, open(f"{OUT}/raw_detections.json", "w"))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
