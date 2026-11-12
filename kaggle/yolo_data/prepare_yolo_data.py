"""Build the Manzil 4-class YOLO dataset on Kaggle (vision tasks V.1 + V.2).

Sources (attached as Kaggle datasets, never downloaded to the laptop or cloud session):
  * UA-DETRAC (bratjay/ua-detrac-orig): 60 train + 40 test sequences, XML boxes.
  * COCO 2017 (awsaf49/coco-2017-dataset): only images that contain a motorcycle,
    because UA-DETRAC has no motorcycle labels (decision 10 in PLAN.md).

Classes (PLAN.md decision 10 / context section 49 Q10):
  0 car         <- DETRAC car, DETRAC van;   COCO car
  1 bus         <- DETRAC bus;               COCO bus
  2 truck       <- DETRAC others;            COCO truck
  3 motorcycle  <-                            COCO motorcycle

Splits:
  train  = DETRAC train sequences minus the validation ones (every FRAME_STRIDE-th frame)
           + COCO train2017 motorcycle images minus COCO_VAL_IMAGES
  val    = VAL_SEQUENCES of the DETRAC train split (whole sequences, so no near-duplicate
           frames leak between train and val) + COCO_VAL_IMAGES COCO train2017 motorcycle images
  test   = DETRAC official test split (all 40 sequences, every FRAME_STRIDE-th frame)
  test_motorcycle = COCO val2017 images that contain a motorcycle (COCO's own held-out split)

DETRAC "ignored regions" contain vehicles that were deliberately not labelled; they are filled
with grey (114) so the model is not punished for detecting them. Boxes whose centre lies inside
an ignored region are dropped as well.

The functions are pure and are unit-tested in tests/test_yolo_data.py; main() runs on Kaggle.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

CLASS_NAMES = ["car", "bus", "truck", "motorcycle"]
DETRAC_MAP = {"car": 0, "van": 0, "bus": 1, "others": 2}
COCO_MAP = {3: 0, 6: 1, 8: 2, 4: 3}  # COCO category ids: car=3, motorcycle=4, bus=6, truck=8
COCO_MOTORCYCLE = 4

FRAME_STRIDE = 10  # DETRAC is 25 fps; every 10th frame keeps 2.5 fps, removing near-duplicates
VAL_EVERY = 10  # every 10th sorted DETRAC train sequence goes to val (6 of 60)
COCO_VAL_IMAGES = 300
SEED = 0
GREY = (114, 114, 114)
MIN_BOX_PX = 2.0


# ---------------------------------------------------------------- pure helpers (tested)


def parse_detrac_xml(text: str) -> tuple[list[tuple[float, float, float, float]], dict]:
    """Return (ignored regions as (left, top, w, h), {frame_num: [(type, l, t, w, h), ...]})."""
    root = ET.fromstring(text)
    ignored = []
    ign = root.find("ignored_region")
    if ign is not None:
        for b in ign.findall("box"):
            ignored.append(tuple(float(b.get(k)) for k in ("left", "top", "width", "height")))
    frames: dict[int, list] = {}
    for fr in root.iter("frame"):
        boxes = []
        for tgt in fr.iter("target"):
            b = tgt.find("box")
            a = tgt.find("attribute")
            vals = tuple(float(b.get(k)) for k in ("left", "top", "width", "height"))
            boxes.append((a.get("vehicle_type"), *vals))
        frames[int(fr.get("num"))] = boxes
    return ignored, frames


def in_any_region(x: float, y: float, regions) -> bool:
    return any(x0 <= x <= x0 + w and y0 <= y <= y0 + h for (x0, y0, w, h) in regions)


def to_yolo_line(cls: int, left, top, w, h, img_w, img_h) -> str | None:
    """Clip a pixel box to the image and return a normalised YOLO label line (or None)."""
    x0, y0 = max(0.0, left), max(0.0, top)
    x1, y1 = min(float(img_w), left + w), min(float(img_h), top + h)
    if x1 - x0 < MIN_BOX_PX or y1 - y0 < MIN_BOX_PX:
        return None
    cx, cy = (x0 + x1) / 2 / img_w, (y0 + y1) / 2 / img_h
    return f"{cls} {cx:.6f} {cy:.6f} {(x1 - x0) / img_w:.6f} {(y1 - y0) / img_h:.6f}"


def detrac_frame_labels(boxes, ignored, img_w, img_h) -> list[str]:
    lines = []
    for vtype, x0, y0, w, h in boxes:
        if vtype not in DETRAC_MAP:
            raise ValueError(f"unknown DETRAC vehicle_type {vtype!r}")
        if in_any_region(x0 + w / 2, y0 + h / 2, ignored):
            continue
        line = to_yolo_line(DETRAC_MAP[vtype], x0, y0, w, h, img_w, img_h)
        if line:
            lines.append(line)
    return lines


def split_detrac_sequences(train_seqs: list[str]) -> tuple[list[str], list[str]]:
    seqs = sorted(train_seqs)
    val = seqs[::VAL_EVERY]
    return [s for s in seqs if s not in val], val


def coco_images_with_motorcycle(coco: dict) -> dict[int, list[str]]:
    """Map image id -> YOLO lines (all 4 classes) for COCO images that contain a motorcycle.

    Crowd annotations are skipped (they are not single objects)."""
    imgs = {im["id"]: im for im in coco["images"]}
    per_img: dict[int, list] = {}
    has_moto = set()
    for ann in coco["annotations"]:
        if ann.get("iscrowd", 0) or ann["category_id"] not in COCO_MAP:
            continue
        per_img.setdefault(ann["image_id"], []).append(ann)
        if ann["category_id"] == COCO_MOTORCYCLE:
            has_moto.add(ann["image_id"])
    out = {}
    for iid in sorted(has_moto):
        im = imgs[iid]
        lines = []
        for ann in per_img[iid]:
            cls = COCO_MAP[ann["category_id"]]
            line = to_yolo_line(cls, *ann["bbox"], im["width"], im["height"])
            if line:
                lines.append(line)
        out[iid] = lines
    return out


# ---------------------------------------------------------------- Kaggle-side I/O


def find_one(pattern: str) -> str:
    hits = sorted(glob.glob(pattern, recursive=True))
    if not hits:
        raise FileNotFoundError(pattern)
    return hits[0]


def write_detrac_image(job):
    src, dst_img, dst_lbl, ignored, boxes = job
    from PIL import Image, ImageDraw

    im = Image.open(src).convert("RGB")
    if ignored:
        d = ImageDraw.Draw(im)
        for x0, y0, w, h in ignored:
            d.rectangle([x0, y0, x0 + w, y0 + h], fill=GREY)
    im.save(dst_img, quality=92)
    lines = detrac_frame_labels(boxes, ignored, im.width, im.height)
    with open(dst_lbl, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    return Counter(int(x.split()[0]) for x in lines)


def build_detrac(root: str, out: str, split_seqs: dict[str, list[str]], ann_dir_of: dict):
    img_root = find_one(f"{root}/**/DETRAC-Images/MVI_20011").rsplit("/", 1)[0]
    stats = {}
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        for split, seqs in split_seqs.items():
            os.makedirs(f"{out}/images/{split}", exist_ok=True)
            os.makedirs(f"{out}/labels/{split}", exist_ok=True)
            jobs = []
            for seq in seqs:
                with open(f"{ann_dir_of[seq]}/{seq}.xml") as fh:
                    ignored, frames = parse_detrac_xml(fh.read())
                for num in sorted(frames):
                    if (num - 1) % FRAME_STRIDE:
                        continue
                    name = f"detrac_{seq}_{num:05d}"
                    jobs.append((f"{img_root}/{seq}/img{num:05d}.jpg",
                                 f"{out}/images/{split}/{name}.jpg",
                                 f"{out}/labels/{split}/{name}.txt", ignored, frames[num]))
            c = Counter()
            for r in pool.map(write_detrac_image, jobs, chunksize=32):
                c.update(r)
            stats[split] = {"images": len(jobs), "sequences": len(seqs),
                            "boxes": {CLASS_NAMES[k]: v for k, v in sorted(c.items())}}
            print(split, stats[split], flush=True)
    return stats


def build_coco(coco_root: str, out: str, split_ids: dict[str, tuple[str, dict]]):
    stats = {}
    for split, (src_dir, labels) in split_ids.items():
        os.makedirs(f"{out}/images/{split}", exist_ok=True)
        os.makedirs(f"{out}/labels/{split}", exist_ok=True)
        c = Counter()
        for iid, lines in labels.items():
            name = f"coco_{iid:012d}"
            dst = f"{out}/images/{split}/{name}.jpg"
            if not os.path.exists(dst):
                shutil.copyfile(f"{src_dir}/{iid:012d}.jpg", dst)
            with open(f"{out}/labels/{split}/{name}.txt", "w") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
            c.update(int(x.split()[0]) for x in lines)
        stats[split] = {"images": len(labels),
                        "boxes": {CLASS_NAMES[k]: v for k, v in sorted(c.items())}}
        print("coco", split, stats[split], flush=True)
    return stats


def main(input_root: str = "/kaggle/input", out: str = "/kaggle/working/manzil_yolo"):
    detrac = find_one(f"{input_root}/**/ua-detrac-orig")
    coco = find_one(f"{input_root}/**/coco2017")
    train_ann = find_one(f"{detrac}/**/DETRAC-Train-Annotations-XML/MVI_*.xml").rsplit("/", 1)[0]
    test_ann = find_one(f"{detrac}/**/DETRAC-Test-Annotations-XML/MVI_*.xml").rsplit("/", 1)[0]
    train_all = [os.path.basename(p)[:-4] for p in glob.glob(f"{train_ann}/MVI_*.xml")]
    test_seqs = sorted(os.path.basename(p)[:-4] for p in glob.glob(f"{test_ann}/MVI_*.xml"))
    train_seqs, val_seqs = split_detrac_sequences(train_all)
    ann_dir_of = {s: train_ann for s in train_all} | {s: test_ann for s in test_seqs}
    print("DETRAC train/val/test sequences:", len(train_seqs), len(val_seqs), len(test_seqs))

    stats = {"detrac": build_detrac(detrac, out, {"train": train_seqs, "val": val_seqs,
                                                  "test": test_seqs}, ann_dir_of)}

    with open(f"{coco}/annotations/instances_train2017.json") as fh:
        coco_train = coco_images_with_motorcycle(json.load(fh))
    with open(f"{coco}/annotations/instances_val2017.json") as fh:
        coco_val2017 = coco_images_with_motorcycle(json.load(fh))
    ids = sorted(coco_train)
    random.Random(SEED).shuffle(ids)
    val_ids = set(ids[:COCO_VAL_IMAGES])
    stats["coco"] = build_coco(coco, out, {
        "train": (f"{coco}/train2017", {i: coco_train[i] for i in ids if i not in val_ids}),
        "val": (f"{coco}/train2017", {i: coco_train[i] for i in sorted(val_ids)}),
        "test_motorcycle": (f"{coco}/val2017", coco_val2017),
    })

    stats["config"] = {"classes": CLASS_NAMES, "detrac_map": DETRAC_MAP,
                       "coco_map": {str(k): CLASS_NAMES[v] for k, v in COCO_MAP.items()},
                       "frame_stride": FRAME_STRIDE, "val_sequences": val_seqs,
                       "coco_val_images": COCO_VAL_IMAGES, "seed": SEED,
                       "sources": ["bratjay/ua-detrac-orig", "awsaf49/coco-2017-dataset"]}
    # checksum over the sorted label files: identifies this exact dataset version
    h = hashlib.sha256()
    for p in sorted(glob.glob(f"{out}/labels/**/*.txt", recursive=True)):
        h.update(os.path.relpath(p, out).encode())
        with open(p, "rb") as fh:
            h.update(fh.read())
    stats["labels_sha256"] = h.hexdigest()

    with open(f"{out}/data.yaml", "w") as f:
        f.write("# Manzil 4-class vehicle dataset (UA-DETRAC + COCO motorcycle images)\n"
                "path: .\ntrain: images/train\nval: images/val\ntest: images/test\n"
                f"names: {dict(enumerate(CLASS_NAMES))}\n")
    with open(f"{out}/dataset_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
