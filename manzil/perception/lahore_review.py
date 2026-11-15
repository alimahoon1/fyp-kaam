"""Review workflow for the W2 Lahore labels: pre-labels -> rendered frames -> corrections -> labels.

The frames themselves live on Kaggle (kernel `manzil-lahore-frames`) and are pulled into a scratch
folder for review only; they are not committed. Steps (run from the repository root):

    python -m manzil.perception.lahore_review prelabel RAW.json OUT_DIR [BOOT.json]
        merge the raw detections of kernel `manzil-lahore-prelabel` into pre-labels
        (OUT_DIR/prelabels.json: kept labels + lower-confidence "candidates" per image)
    python -m manzil.perception.lahore_review render FRAMES_DIR OUT_DIR [IMAGE ...]
        draw each frame with numbered pre-labels (solid, colour = class) and numbered
        candidates (thin grey, "c<n>") plus a 100-px grid, for visual review
    python -m manzil.perception.lahore_review manifest FRAMES.csv SHOTS.json OUT.csv
        split by shot (TEST_SHOTS / VAL_SHOTS below) -> data/lahore_video/split_manifest.csv
    python -m manzil.perception.lahore_review apply FRAMES_DIR OUT_DIR REVIEW.jsonl
        apply the review operations and write YOLO label files + review_log.json

REVIEW.jsonl has one JSON object per reviewed image: ``{"image": ..., "ops": [...]}`` where ops
are those of ``lahore_labels.apply_review`` plus ``{"op": "acc", "cand": j, "cls": c}`` (accept
candidate j as class c) and ``{"op": "far", "y": Y}`` (far-field row for this frame, see
FAR_DEFAULT; labels whose centre lies above it are dropped and the band is greyed later).
An image with no line has not been reviewed; ``"ops": []`` means reviewed and every pre-label
accepted.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from manzil.perception import lahore_labels as ll

# candidate settings: clusters that missed the label thresholds but are still plausible
CAND_CFG = ll.MergeConfig(keep_conf=0.15, agree_conf=0.08, new_class_conf=0.15)
COLORS = {0: (60, 220, 60), 1: (255, 160, 0), 2: (60, 140, 255), 3: (255, 60, 255),
          4: (255, 255, 0), 5: (0, 255, 255)}
SHORT = ["car", "bus", "trk", "moto", "rick", "van"]

# Far field: above this image row the vehicles are too small (under ~16 px) and too dense to label
# reliably, so that band is not labelled and is filled grey for training and evaluation alike.
# Per segment (video, shot): the row at the first and the last frame, linearly interpolated in
# between (the camera drifts slowly); a review op {"op": "far", "y": Y} overrides one frame.
FAR_DEFAULT = {("v1", 0): (200, 330), ("v1", 1): (330, 380), ("v1", 2): (360, 400),
               ("v1", 3): (380, 380), ("v1", 4): (220, 220), ("v2", 0): (760, 760)}


def seg_of(img: str) -> tuple[str, int, int]:
    """'v1_s2_f01805.jpg' -> ('v1', 2, 1805)."""
    v, s, f = Path(img).stem.split("_")
    return v, int(s[1:]), int(f[1:])


def far_default(img: str, all_images) -> float:
    v, s, f = seg_of(img)
    frames = sorted(seg_of(i)[2] for i in all_images if seg_of(i)[:2] == (v, s))
    y0, y1 = FAR_DEFAULT[(v, s)]
    if len(frames) < 2:
        return float(y0)
    t = (f - frames[0]) / (frames[-1] - frames[0])
    return round(y0 + t * (y1 - y0), 1)


SIX = {i: i for i in range(len(ll.CLASS_NAMES))}


def detections(raw_one: dict) -> list[ll.Det]:
    return (ll.map_dets(raw_one.get("manzil4", []), ll.MANZIL4_MAP, "manzil4")
            + ll.map_dets(raw_one.get("coco_x", []), ll.COCO_MAP, "coco_x")
            + ll.map_dets(raw_one.get("world", []), ll.WORLD_MAP, "world")
            + ll.map_dets(raw_one.get("boot", []), SIX, "boot"))


def prelabel_one(raw_one: dict, cfg=None, cand_cfg=None) -> tuple[list[ll.Label], list[ll.Label]]:
    dets = detections(raw_one)
    labels = ll.merge(dets, cfg)
    cands = [c for c in ll.merge(dets, cand_cfg or CAND_CFG)
             if all(ll.iou(c.box, lab.box) < 0.3 for lab in labels)]
    return labels, cands


def _lab(d):
    return {"cls": d.cls, "box": [round(v, 1) for v in d.box], "conf": d.conf,
            "sources": d.sources}


def cmd_prelabel(raw_path, out_dir, boot_path=None):
    """Round 1: three detectors. Round 2 (``boot_path`` given): plus the bootstrap six-class
    model, which then decides the class of any cluster it is confident about."""
    raw = json.load(open(raw_path))
    cfg, cand_cfg = ll.MergeConfig(), CAND_CFG
    if boot_path:
        boot = json.load(open(boot_path))
        for img, r in boot["detections"].items():
            raw["detections"][img]["boot"] = r["boot"]
        raw["meta"]["boot"] = boot["meta"]
        cfg = ll.MergeConfig(prefer_source="boot", prefer_conf=0.25)
        cand_cfg = ll.MergeConfig(keep_conf=0.15, agree_conf=0.08, new_class_conf=0.15,
                                  prefer_source="boot", prefer_conf=0.15)
    out = {}
    for img, r in sorted(raw["detections"].items()):
        labels, cands = prelabel_one(r, cfg, cand_cfg)
        out[img] = {"labels": [_lab(x) for x in labels], "candidates": [_lab(x) for x in cands]}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    json.dump({"meta": raw["meta"], "merge": vars(cfg), "candidates": vars(cand_cfg),
               "images": out}, open(Path(out_dir) / "prelabels.json", "w"))
    c = Counter(lab["cls"] for v in out.values() for lab in v["labels"])
    print(len(out), "images;", {ll.CLASS_NAMES[k]: c[k] for k in sorted(c)},
          "candidates", sum(len(v["candidates"]) for v in out.values()))


def render(img_path, labels, cands, out_path, scale=1.0, far_y=None):
    from PIL import Image, ImageDraw

    im = Image.open(img_path).convert("RGB")
    if far_y is not None:
        ov = Image.new("RGB", (im.width, round(far_y)), (114, 114, 114))
        im.paste(Image.blend(im.crop((0, 0, im.width, round(far_y))), ov, 0.6), (0, 0))
    if scale != 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)))
    d = ImageDraw.Draw(im)
    for x in range(0, im.width, round(100 * scale)):
        d.line([(x, 0), (x, 6)], fill=(255, 0, 0))
        d.line([(x, im.height - 6), (x, im.height)], fill=(255, 0, 0))
        d.text((x + 1, 7), str(round(x / scale)), fill=(255, 0, 0))
    for y in range(0, im.height, round(100 * scale)):
        d.line([(0, y), (6, y)], fill=(255, 0, 0))
        d.text((8, y + 1), str(round(y / scale)), fill=(255, 0, 0))
    if far_y is not None:
        d.line([(0, far_y * scale), (im.width, far_y * scale)], fill=(255, 0, 0), width=1)
    for j, c in enumerate(cands):
        b = [v * scale for v in c["box"]]
        d.rectangle(b, outline=(170, 170, 170), width=1)
        d.text((b[0] + 1, b[3] - 10), f"c{j}", fill=(200, 200, 200))
    for i, lab in enumerate(labels):
        b = [v * scale for v in lab["box"]]
        col = COLORS[lab["cls"]]
        d.rectangle(b, outline=col, width=2)
        tag = f"{i}{SHORT[lab['cls']][0]}"
        tw = 6 * len(tag) + 2
        d.rectangle([b[0], b[1] - 10, b[0] + tw, b[1]], fill=(0, 0, 0))
        d.text((b[0] + 1, b[1] - 11), tag, fill=col)
    im.save(out_path, quality=90)


def cmd_render(frames_dir, out_dir, images=None, scale=1.0):
    pre = json.load(open(Path(out_dir) / "prelabels.json"))["images"]
    rdir = Path(out_dir) / "render"
    rdir.mkdir(parents=True, exist_ok=True)
    for img in images or sorted(pre):
        p = pre[img]
        far = far_default(img, pre)
        render(Path(frames_dir) / img, p["labels"], p["candidates"], rdir / img, scale, far)


def load_review(path) -> dict:
    out = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            out[r["image"]] = r["ops"]  # a later line for the same image replaces the earlier
    return out


def cmd_apply(frames_dir, out_dir, review_path):
    from PIL import Image

    pre = json.load(open(Path(out_dir) / "prelabels.json"))["images"]
    review = load_review(review_path)
    ldir = Path(out_dir) / "labels"
    ldir.mkdir(parents=True, exist_ok=True)
    totals = {"images_reviewed": 0, "images_not_reviewed": [], "prelabels": Counter(),
              "final": Counter(), "deleted": 0, "reclassed": 0, "added": 0,
              "accepted_candidates": 0, "by_class": {}}
    far_rows = {}
    for img, p in sorted(pre.items()):
        labels = [ll.Label(x["cls"], tuple(x["box"]), x["sources"], x["conf"])
                  for x in p["labels"]]
        totals["prelabels"].update(ll.CLASS_NAMES[x.cls] for x in labels)
        far_rows[img] = far_default(img, pre)
        if img not in review:
            totals["images_not_reviewed"].append(img)
            continue
        ops = []
        far = far_default(img, pre)
        for op in review[img]:
            if op["op"] == "far":
                far = float(op["y"])
            elif op["op"] == "acc":
                ops.append({"op": "add", "cls": op["cls"],
                            "box": p["candidates"][int(op["cand"])]["box"]})
                totals["accepted_candidates"] += 1
            else:
                ops.append(op)
        final, log = ll.apply_review(labels, ops)
        n_before = len(final)
        final = [x for x in final if (x.box[1] + x.box[3]) / 2 >= far]
        totals["far_field_dropped"] = totals.get("far_field_dropped", 0) + n_before - len(final)
        far_rows[img] = far
        totals["images_reviewed"] += 1
        for k in ("deleted", "reclassed", "added"):
            totals[k] += log[k]
        for name, v in log["by_class"].items():
            agg = totals["by_class"].setdefault(name, Counter())
            agg.update(v)
        totals["final"].update(ll.CLASS_NAMES[x.cls] for x in final)
        w, h = Image.open(Path(frames_dir) / img).size
        (ldir / (Path(img).stem + ".txt")).write_text(
            "".join(ll.to_yolo_line(x, w, h) + "\n" for x in final))
    json.dump(far_rows, open(Path(out_dir) / "far_field.json", "w"), indent=0)
    totals["added_by_hand"] = totals["added"] - totals["accepted_candidates"]
    totals = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in totals.items()}
    totals["by_class"] = {k: dict(v) for k, v in totals["by_class"].items()}
    json.dump(totals, open(Path(out_dir) / "review_log.json", "w"), indent=2)
    print(json.dumps({k: v for k, v in totals.items() if k != "images_not_reviewed"}, indent=1))
    print("not reviewed:", len(totals["images_not_reviewed"]))


# Split by shot (W2 step 3). Video 1: segment 0 (0-15.5 s) is val, segments 1-2 (15.5-87 s) are
# train, segments 3-4 (87-125.6 s, including the railing shot after the hard cut) are test;
# all of video 2 is test. Frames within GUARD_S of a boundary between two splits are unused.
TEST_SHOTS = {("v1", 3), ("v1", 4), ("v2", 0)}
VAL_SHOTS = {("v1", 0)}
GUARD_S = 2.0


def cmd_manifest(frames_csv, shots_json, out_csv):
    import csv

    frames = list(csv.DictReader(open(frames_csv)))
    shots = json.load(open(shots_json))["videos"]
    bounds = {(v, s["shot"]): (s["start_s"], s["end_s"]) for v, x in shots.items()
              for s in x["shots"]}
    rows = ll.split_by_shot(frames, TEST_SHOTS, VAL_SHOTS, bounds, GUARD_S)
    keep = ["image", "video", "shot", "frame", "time_s", "width", "height", "split", "sha256"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(Counter((r["video"], r["split"]) for r in rows))


def main(argv=None):
    a = argv or sys.argv[1:]
    if a[0] == "prelabel":
        cmd_prelabel(a[1], a[2], a[3] if len(a) > 3 else None)
    elif a[0] == "render":
        cmd_render(a[1], a[2], a[3:] or None)
    elif a[0] == "manifest":
        cmd_manifest(a[1], a[2], a[3])
    elif a[0] == "apply":
        cmd_apply(a[1], a[2], a[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
