"""Bootstrap pre-labeller for the Lahore frames (W2 step 4b). GPU kernel.

The first pre-labels (kernel manzil-lahore-prelabel: fine-tuned YOLO11s + YOLO11x + YOLO-World)
called almost every Lahore rickshaw a car. So a first batch of TRAIN frames was reviewed by hand
(labels in the private dataset manzil-lahore-labels), and this kernel fine-tunes a six-class
YOLO11s on that batch only, then predicts every frame. Its detections are a fourth pre-label
source ("boot"); they are never used as ground truth. Test and val frames are not trained on.

Inputs: frames (kernel manzil-lahore-frames), labels dataset (labels/*.txt, split_manifest.csv,
far_field.json), base weights out/best.pt (kernel manzil-yolo-train, sha256 checked).
The far-field band of every frame (rows above far_field.json[image]) is filled grey (114), the
same as in training and evaluation.
Output: /kaggle/working/raw_boot.json = {image: {"boot": [[cls, conf, x1, y1, x2, y2]]}}.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

ULTRALYTICS = "ultralytics==8.4.210"
WEIGHTS_SHA256 = "0022c8a0394bf8a583ef0d21e324853a73251ca86a3ac6caab656fd65ae8dc2f"
NAMES = ["car", "bus", "truck", "motorcycle", "rickshaw", "van"]
IMGSZ = 1280
EPOCHS = 60
BATCH = 8
SEED = 0
CONF = 0.05
INPUT = "/kaggle/input"
W = "/kaggle/working"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def one(pattern):
    hits = sorted(glob.glob(pattern, recursive=True))
    if not hits:
        raise FileNotFoundError(pattern)
    return hits[0]


def main():
    subprocess.run(f"pip install -q {ULTRALYTICS}", shell=True, check=True)
    import cv2
    import torch
    import ultralytics
    from ultralytics import YOLO

    weights = one(f"{INPUT}/**/out/best.pt")
    assert sha256(weights) == WEIGHTS_SHA256, "weights checksum"
    frames_dir = os.path.dirname(one(f"{INPUT}/**/frames/v1_s0_*.jpg"))
    lab_root = os.path.dirname(one(f"{INPUT}/**/split_manifest.csv"))
    manifest = list(csv.DictReader(open(f"{lab_root}/split_manifest.csv")))
    far = json.load(open(f"{lab_root}/far_field.json"))
    reviewed = {os.path.basename(p)[:-4] for p in glob.glob(f"{lab_root}/labels/*.txt")}

    data = f"{W}/boot"
    grey = f"{W}/grey"
    for d in ("images/train", "labels/train", "images/val", "labels/val"):
        os.makedirs(f"{data}/{d}", exist_ok=True)
    os.makedirs(grey, exist_ok=True)
    train = []
    for r in manifest:
        img = cv2.imread(f"{frames_dir}/{r['image']}")
        y = int(round(far[r["image"]]))
        img[:y] = 114
        cv2.imwrite(f"{grey}/{r['image']}", img)
        stem = r["image"][:-4]
        if r["split"] == "train" and stem in reviewed:
            train.append(stem)
            for split in ("train", "val"):  # val = train: this model only pre-labels
                os.symlink(f"{grey}/{r['image']}", f"{data}/images/{split}/{r['image']}")
                with open(f"{lab_root}/labels/{stem}.txt") as src, \
                        open(f"{data}/labels/{split}/{stem}.txt", "w") as dst:
                    dst.write(src.read())
    print(len(train), "reviewed train frames", flush=True)
    with open(f"{data}/data.yaml", "w") as f:
        f.write(f"path: {data}\ntrain: images/train\nval: images/val\n"
                f"names: {dict(enumerate(NAMES))}\n")
    t0 = time.time()
    model = YOLO(weights)
    model.train(data=f"{data}/data.yaml", epochs=EPOCHS, imgsz=IMGSZ, batch=BATCH, seed=SEED,
                device=0, workers=4, project=f"{W}/runs", name="boot", exist_ok=True,
                plots=False, val=False, mosaic=1.0, close_mosaic=10)
    t_train = round(time.time() - t0, 1)
    best = YOLO(f"{W}/runs/boot/weights/last.pt")
    images = sorted(glob.glob(f"{grey}/*.jpg"))
    det = {}
    for i in range(0, len(images), 8):
        batch = images[i:i + 8]
        for p, res in zip(batch, best.predict(batch, imgsz=IMGSZ, conf=CONF, iou=0.6, device=0,
                                              max_det=500, verbose=False), strict=True):
            b = res.boxes
            det[os.path.basename(p)] = {"boot": [
                [int(c), round(float(s), 4), *[round(float(v), 1) for v in xy]]
                for c, s, xy in zip(b.cls.tolist(), b.conf.tolist(), b.xyxy.tolist(),
                                    strict=True)]}
    meta = {"train_frames": train, "imgsz": IMGSZ, "epochs": EPOCHS, "batch": BATCH, "seed": SEED,
            "conf": CONF, "train_seconds": t_train, "base_weights_sha256": WEIGHTS_SHA256,
            "versions": {"ultralytics": ultralytics.__version__, "torch": torch.__version__,
                         "python": sys.version.split()[0]},
            "device": torch.cuda.get_device_name(0)}
    json.dump({"meta": meta, "detections": det}, open(f"{W}/raw_boot.json", "w"))
    print(json.dumps(meta, indent=1))
    subprocess.run(f"rm -rf {grey} {data} {W}/runs", shell=True, check=False)


if __name__ == "__main__":
    main()
