"""Six-class fine-tuning on the Lahore frames + evaluation + line counting (W2 step 6). GPU kernel.

Inputs (kernel-metadata.json):
  * frames from kernel `manzil-lahore-frames` (frames/*.jpg, frames.csv, shots.json);
  * labels dataset `manzil-lahore-labels` (labels/*.txt, split_manifest.csv, far_field.json):
    model-assisted, Claude-reviewed; the test split is preliminary until a team member checks it;
  * the two videos (dataset `manzil-lahore-videos`) for full-frame-rate tracking on the test shots;
  * base weights `out/best.pt` of kernel `manzil-yolo-train` (four classes, sha256 checked);
  * the old training data `manzil_yolo/` of kernel `manzil-yolo-data` for the replay sample and
    for the "forgetting" check on the old test sets.
Steps:
  1. Build the YOLO dataset. In every Lahore image the far-field band (rows above
     far_field.json[image]) is filled grey, in train, val and test alike. Train = Lahore train
     frames repeated REPEAT times + a replay sample (REPLAY_DETRAC + REPLAY_COCO old images).
  2. Fine-tune from the four-class weights to six classes; best epoch chosen on Lahore val.
  3. Lahore TEST (video 1 test shots, video 2, both): the new model on the six-class labels; the
     old model on the same images with rickshaw and van labels removed ("old4") and with the old
     label convention (van -> car, rickshaw removed; "oldconv"). Own confusion matrices at
     conf 0.25 / IoU 0.5 against the six-class labels for both models.
  4. Forgetting check: the new model on the old UA-DETRAC test split and COCO motorcycle set.
  5. Line counting per test shot: reference = reviewed labels (about 2 fps) linked into tracks
     (GreedyLinker) -> LineCounter; prediction = model + ByteTrack on every video frame ->
     the same LineCounter; and model detections on the labelled frames linked like the reference.
Outputs in /kaggle/working/out.
"""

# ruff: noqa: F821  (names inlined at the @@INLINE markers by build.py)
from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time

ULTRALYTICS = "ultralytics==8.4.210"
WEIGHTS_SHA256 = "0022c8a0394bf8a583ef0d21e324853a73251ca86a3ac6caab656fd65ae8dc2f"
VIDEOS = {"v1": "manzil-lahore-video.mp4", "v2": "manzil-lahore-video-2.mov"}
IMGSZ = 1280
EPOCHS = int(os.environ.get("MANZIL_EPOCHS", 60))
PATIENCE = 20
BATCH_PER_GPU = 8
SEED = 0
REPEAT = 3
REPLAY_DETRAC = 150
REPLAY_COCO = 150
CM_CONF = 0.25
CM_IOU = 0.5
LINE_FRAC = 0.5  # counting line: this fraction of the way from the far-field row to the bottom
TRACKER = "bytetrack.yaml"
INPUT = "/kaggle/input"
W = "/kaggle/working"
OUT = f"{W}/out"
GREY = 114

# @@INLINE manzil/perception/counting.py@@
# @@INLINE manzil/perception/linking.py@@
# @@INLINE manzil/perception/lahore_labels.py@@

NAMES = CLASS_NAMES  # six classes (lahore_labels)


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


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


def write_yaml(path, root, test_dir, names):
    with open(path, "w") as f:
        f.write(f"path: {root}\ntrain: images/train\nval: images/val\ntest: images/{test_dir}\n"
                f"names: {dict(enumerate(names))}\n")


def read_labels(path):
    rows = []
    with open(path) as f:
        for ln in f:
            p = ln.split()
            if p:
                rows.append((int(p[0]), *map(float, p[1:])))
    return rows


def summarise(m):
    box = m.box
    per = {}
    for i, c in enumerate(box.ap_class_index):
        per[m.names[int(c)]] = {"precision": float(box.p[i]), "recall": float(box.r[i]),
                                "mAP50": float(box.ap50[i]), "mAP50_95": float(box.ap[i])}
    n = max(1, len(per))
    return {"classes_evaluated": list(per),
            "precision": sum(v["precision"] for v in per.values()) / n,
            "recall": sum(v["recall"] for v in per.values()) / n,
            "mAP50": sum(v["mAP50"] for v in per.values()) / n,
            "mAP50_95": sum(v["mAP50_95"] for v in per.values()) / n,
            "per_class": per}


def confusion(model, img_dir, lab_dir, n_model_classes):
    """Rows = true class (6 + background), columns = predicted class (+ missed)."""
    from PIL import Image

    k = len(NAMES)
    mat = [[0] * (k + 1) for _ in range(k + 1)]
    for p in sorted(glob.glob(f"{img_dir}/*.jpg")):
        w, h = Image.open(p).size
        gts = [from_yolo_line(" ".join(map(str, r)), w, h)
               for r in read_labels(f"{lab_dir}/{os.path.basename(p)[:-4]}.txt")]
        r = model.predict(p, imgsz=IMGSZ, conf=CM_CONF, iou=0.6, device=0, max_det=500,
                          verbose=False)[0]
        preds = sorted(zip(r.boxes.conf.tolist(), r.boxes.cls.int().tolist(),
                           r.boxes.xyxy.tolist(), strict=True), reverse=True)
        used = set()
        for _conf, pc, pb in preds:
            best, bj = CM_IOU, None
            for j, g in enumerate(gts):
                if j in used:
                    continue
                v = iou(tuple(pb), g.box)
                if v >= best:
                    best, bj = v, j
            if bj is None:
                mat[k][pc] += 1  # false positive (background predicted as pc)
            else:
                used.add(bj)
                mat[gts[bj].cls][pc] += 1
        for j, g in enumerate(gts):
            if j not in used:
                mat[g.cls][k] += 1  # missed
    return {"rows_true": [*NAMES, "background"], "cols_pred": [*NAMES, "missed"],
            "matrix": mat, "conf": CM_CONF, "iou": CM_IOU, "model_classes": n_model_classes}


def main():
    t_start = time.time()
    sh(f"pip install -q {ULTRALYTICS}")
    import cv2
    import torch
    import ultralytics
    from ultralytics import YOLO

    os.makedirs(OUT, exist_ok=True)
    base = one(f"{INPUT}/**/out/best.pt")
    assert sha256(base) == WEIGHTS_SHA256, "base weights checksum"
    frames_dir = os.path.dirname(one(f"{INPUT}/**/frames/v1_s0_*.jpg"))
    shots = json.load(open(one(f"{INPUT}/**/shots.json")))["videos"]
    lab_root = os.path.dirname(one(f"{INPUT}/**/split_manifest.csv"))
    manifest = list(csv.DictReader(open(f"{lab_root}/split_manifest.csv")))
    check_manifest(manifest)
    far = json.load(open(f"{lab_root}/far_field.json"))
    old_root = os.path.dirname(one(f"{INPUT}/**/manzil_yolo/data.yaml"))

    # labels checksum (sorted file names + contents) for the record
    hsh = hashlib.sha256()
    for p in sorted(glob.glob(f"{lab_root}/labels/*.txt")):
        hsh.update(os.path.basename(p).encode())
        hsh.update(open(p, "rb").read())
    labels_sha = hsh.hexdigest()

    # ---- 1. dataset
    D = f"{W}/lahore"
    splits = {"train": [], "val": [], "test_v1": [], "test_v2": []}
    for r in manifest:
        if r["split"] == "unused":
            continue
        key = r["split"] if r["split"] != "test" else f"test_{r['video']}"
        stem = r["image"][:-4]
        if not os.path.exists(f"{lab_root}/labels/{stem}.txt"):
            raise FileNotFoundError(f"no reviewed label file for {r['image']} ({r['split']})")
        splits[key].append(r)
    for d in ("train", "val", "test_v1", "test_v2", "test"):
        for kind in ("images", "labels"):
            os.makedirs(f"{D}/{kind}/{d}", exist_ok=True)
    box_counts = {}
    for key, rows in splits.items():
        cnt = [0] * len(NAMES)
        for r in rows:
            stem = r["image"][:-4]
            img = cv2.imread(f"{frames_dir}/{r['image']}")
            img[:int(round(far[r["image"]]))] = GREY
            lab = open(f"{lab_root}/labels/{stem}.txt").read()
            for row in read_labels(f"{lab_root}/labels/{stem}.txt"):
                cnt[row[0]] += 1
            targets = [(key, stem)]
            if key == "train":
                targets += [(key, f"{stem}_rep{i}") for i in range(1, REPEAT)]
            if key.startswith("test_"):
                targets.append(("test", stem))
            for d, name in targets:
                cv2.imwrite(f"{D}/images/{d}/{name}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                with open(f"{D}/labels/{d}/{name}.txt", "w") as f:
                    f.write(lab)
        box_counts[key] = {"images": len(rows), "boxes": dict(zip(NAMES, cnt, strict=True))}
    rng = random.Random(SEED)
    old_train = sorted(os.listdir(f"{old_root}/images/train"))
    replay = (rng.sample([f for f in old_train if f.startswith("detrac_")], REPLAY_DETRAC)
              + rng.sample([f for f in old_train if f.startswith("coco_")], REPLAY_COCO))
    for f in replay:
        os.symlink(f"{old_root}/images/train/{f}", f"{D}/images/train/{f}")
        shutil.copy(f"{old_root}/labels/train/{f[:-4]}.txt", f"{D}/labels/train/{f[:-4]}.txt")
    print(json.dumps(box_counts, indent=1), flush=True)
    yamls = {}
    for t in ("test", "test_v1", "test_v2"):
        yamls[t] = f"{W}/lahore_{t}.yaml"
        write_yaml(yamls[t], D, t, NAMES)
    # label variants for the old four-class model
    for variant in ("old4", "oldconv"):
        for t in ("test", "test_v1", "test_v2"):
            os.makedirs(f"{W}/{variant}/images", exist_ok=True)
            os.makedirs(f"{W}/{variant}/labels/{t}", exist_ok=True)
            if not os.path.exists(f"{W}/{variant}/images/{t}"):
                os.symlink(f"{D}/images/{t}", f"{W}/{variant}/images/{t}")
            for p in glob.glob(f"{D}/labels/{t}/*.txt"):
                rows = []
                for c, *xywh in read_labels(p):
                    if c == 5 and variant == "oldconv":
                        c = 0
                    if c < 4:
                        rows.append(" ".join([str(c), *(f"{v:.6f}" for v in xywh)]))
                with open(f"{W}/{variant}/labels/{t}/{os.path.basename(p)}", "w") as f:
                    f.write("\n".join(rows) + ("\n" if rows else ""))
            y = f"{W}/{variant}_{t}.yaml"
            with open(y, "w") as f:
                f.write(f"path: {W}/{variant}\ntrain: images/{t}\nval: images/{t}\n"
                        f"test: images/{t}\nnames: {dict(enumerate(OLD_CLASS_NAMES))}\n")
            yamls[f"{variant}_{t}"] = y

    gpus = torch.cuda.device_count()
    results = {"versions": {"ultralytics": ultralytics.__version__, "torch": torch.__version__,
                            "python": sys.version.split()[0]},
               "config": {"imgsz": IMGSZ, "epochs": EPOCHS, "patience": PATIENCE,
                          "batch": BATCH_PER_GPU * max(1, gpus), "seed": SEED, "gpus": gpus,
                          "repeat_lahore_train": REPEAT, "replay_detrac": REPLAY_DETRAC,
                          "replay_coco": REPLAY_COCO, "base_weights_sha256": WEIGHTS_SHA256},
               "labels_sha256": labels_sha, "dataset": box_counts,
               "label_status": "model-assisted, Claude-reviewed; test split preliminary "
                               "(not yet checked by a team member)"}

    def evaluate(model, yaml_path, name, imgsz=IMGSZ):
        m = model.val(data=yaml_path, split="test", imgsz=imgsz, batch=8, device=0,
                      project=f"{W}/runs", name=name, plots=True, verbose=False, exist_ok=True)
        s = summarise(m)
        print(name, json.dumps(s), flush=True)
        return s

    # ---- 2. train
    t0 = time.time()
    model = YOLO(base)
    model.train(data=yamls["test"], epochs=EPOCHS, imgsz=IMGSZ, batch=BATCH_PER_GPU * max(1, gpus),
                seed=SEED, deterministic=True, patience=PATIENCE, workers=4,
                device=list(range(gpus)) if gpus > 1 else 0,
                project=f"{W}/runs", name="lahore6", exist_ok=True, plots=True)
    results["train_seconds"] = round(time.time() - t0, 1)
    run = f"{W}/runs/lahore6"
    shutil.copy(f"{run}/weights/best.pt", f"{OUT}/manzil_yolo11s_lahore6_best.pt")
    results["weights_sha256"] = sha256(f"{OUT}/manzil_yolo11s_lahore6_best.pt")
    with open(f"{run}/results.csv") as f:
        rows = list(csv.DictReader(f))
    key = next(k for k in rows[0] if "mAP50-95" in k)
    best_row = max(rows, key=lambda r: float(r[key]))
    results["best_epoch"] = int(float(best_row[next(k for k in best_row if "epoch" in k)]))
    results["epochs_run"] = len(rows)

    # ---- 3. Lahore test
    new = YOLO(f"{OUT}/manzil_yolo11s_lahore6_best.pt")
    old = YOLO(base)
    results["lahore_test"] = {"new_six_class": {}, "old_model_old4": {}, "old_model_oldconv": {},
                              "confusion": {}}
    for t in ("test", "test_v1", "test_v2"):
        results["lahore_test"]["new_six_class"][t] = evaluate(new, yamls[t], f"new_{t}")
        results["lahore_test"]["old_model_old4"][t] = evaluate(old, yamls[f"old4_{t}"],
                                                               f"old4_{t}")
        results["lahore_test"]["old_model_oldconv"][t] = evaluate(old, yamls[f"oldconv_{t}"],
                                                                  f"oldconv_{t}")
        results["lahore_test"]["confusion"][t] = {
            "new": confusion(new, f"{D}/images/{t}", f"{D}/labels/{t}", 6),
            "old": confusion(old, f"{D}/images/{t}", f"{D}/labels/{t}", 4)}
    results["lahore_val_new"] = summarise(new.val(
        data=yamls["test"], split="val", imgsz=IMGSZ, batch=8, device=0, project=f"{W}/runs",
        name="new_val", plots=False, verbose=False, exist_ok=True))

    # ---- 4. forgetting check on the old test sets (imgsz 640, as in results/vision)
    results["old_test_sets_new_model"] = {}
    for t in ("test", "test_motorcycle"):
        y = f"{W}/oldset_{t}.yaml"
        write_yaml(y, old_root, t, NAMES)
        results["old_test_sets_new_model"][t] = evaluate(new, y, f"new_oldset_{t}", imgsz=640)

    # ---- 5. line counting on the test shots
    by_shot = {}
    for r in manifest:
        if r["split"] == "test":
            by_shot.setdefault((r["video"], int(r["shot"])), []).append(r)
    count_rows, event_rows = [], []
    for (vid, shot), rows in sorted(by_shot.items()):
        rows.sort(key=lambda r: int(r["frame"]))
        wd, ht = int(rows[0]["width"]), int(rows[0]["height"])
        far_y = max(far[r["image"]] for r in rows)
        y_line = far_y + LINE_FRAC * (ht - far_y)
        line = ((0.0, y_line), (float(wd), y_line))
        f0, f1 = int(rows[0]["frame"]), int(rows[-1]["frame"])
        fps = shots[vid]["fps"]
        info = {"video": vid, "shot": shot, "first_frame": f0, "last_frame": f1,
                "seconds": round((f1 - f0) / fps, 2), "labelled_frames": len(rows),
                "far_row": far_y, "line_y": round(y_line, 1)}

        def keep(tracks, far_y=far_y):
            return [t for t in tracks if t[3] + t[5] / 2.0 >= far_y]

        def record(method, model_name, events, info=info):
            pc = counts_by_class(events, len(NAMES))
            row = {**info, "method": method, "model": model_name, "total": len(events),
                   "down": sum(1 for e in events if e.direction == "down"),
                   "up": sum(1 for e in events if e.direction == "up")}
            for c, n in enumerate(NAMES):
                row[n] = pc[c]
            count_rows.append(row)
            for e in events:
                event_rows.append({"video": info["video"], "shot": info["shot"], "method": method,
                                   "model": model_name, "frame": e.frame, "track_id": e.track_id,
                                   "class": NAMES[e.class_id], "direction": e.direction,
                                   "x": round(e.x, 1), "y": round(e.y, 1)})
            print(row, flush=True)

        # reference: reviewed labels linked at ~2 fps
        linker, counter = GreedyLinker(), LineCounter(*line)
        for r in rows:
            labs = [from_yolo_line(" ".join(map(str, x)), wd, ht)
                    for x in read_labels(f"{lab_root}/labels/{r['image'][:-4]}.txt")]
            counter.update(int(r["frame"]), keep(linker.update([(g.cls, *g.box) for g in labs])))
        record("labels_linked_2fps", "reviewed labels", counter.finalize())

        for mname, mpath in (("new6", f"{OUT}/manzil_yolo11s_lahore6_best.pt"), ("old4", base)):
            # detections on the labelled frames, linked the same way as the reference
            m = YOLO(mpath)
            linker, counter = GreedyLinker(), LineCounter(*line)
            for r in rows:
                res = m.predict(f"{D}/images/test/{r['image']}", imgsz=IMGSZ, conf=CM_CONF,
                                iou=0.6, device=0, max_det=500, verbose=False)[0]
                boxes = [(c, *b) for c, b in zip(res.boxes.cls.int().tolist(),
                                                 res.boxes.xyxy.tolist(), strict=True)]
                counter.update(int(r["frame"]), keep(linker.update(boxes)))
            record("detections_linked_2fps", mname, counter.finalize())

            # every video frame + ByteTrack
            m = YOLO(mpath)
            counter = LineCounter(*line)
            cap = cv2.VideoCapture(one(f"{INPUT}/**/{VIDEOS[vid]}"))
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            i = 0
            samples = {f0 + (f1 - f0) // 3, f0 + 2 * (f1 - f0) // 3}
            while True:
                ok, fr = cap.read()
                if not ok or i > f1:
                    break
                if i >= f0:
                    if fr.shape[1] != wd:
                        fr = cv2.resize(fr, (wd, ht), interpolation=cv2.INTER_AREA)
                    fr[:int(round(far_y))] = GREY
                    res = m.track(fr, persist=True, tracker=TRACKER, imgsz=IMGSZ, device=0,
                                  verbose=False)[0]
                    tracks = []
                    if res.boxes is not None and res.boxes.id is not None:
                        for (x1, y1, x2, y2), tid, c in zip(res.boxes.xyxy.tolist(),
                                                            res.boxes.id.int().tolist(),
                                                            res.boxes.cls.int().tolist(),
                                                            strict=True):
                            tracks.append((tid, c, x1, y1, x2 - x1, y2 - y1))
                    tracks = keep(tracks)
                    counter.update(i, tracks)
                    if mname == "new6" and i in samples:
                        cv2.line(fr, (0, int(y_line)), (wd, int(y_line)), (0, 255, 255), 2)
                        for tid, c, x, y, bw, bh in tracks:
                            cv2.rectangle(fr, (int(x), int(y)), (int(x + bw), int(y + bh)),
                                          (60, 220, 60), 2)
                            cv2.putText(fr, f"{tid} {NAMES[c]}", (int(x), max(12, int(y) - 4)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
                                        cv2.LINE_AA)
                        cv2.putText(fr, f"count {counter.running_count()}", (8, int(far_y) + 28),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
                        small = cv2.resize(fr, (960, int(960 * ht / wd)),
                                           interpolation=cv2.INTER_AREA)
                        cv2.imwrite(f"{OUT}/sample_{vid}_s{shot}_f{i:05d}.jpg", small,
                                    [cv2.IMWRITE_JPEG_QUALITY, 80])
                i += 1
            cap.release()
            record("bytetrack_all_frames", mname, counter.finalize())

    def write_csv(name, data):
        with open(f"{OUT}/{name}", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            wr.writeheader()
            wr.writerows(data)

    write_csv("counts.csv", count_rows)
    if event_rows:
        write_csv("events.csv", event_rows)

    for f in ["results.csv", "results.png", "args.yaml", "labels.jpg"]:
        if os.path.exists(f"{run}/{f}"):
            shutil.copy(f"{run}/{f}", OUT)
    for name in ("new_test", "new_test_v1", "new_test_v2", "old4_test", "oldconv_test"):
        for f in ("confusion_matrix.png", "confusion_matrix_normalized.png", "BoxPR_curve.png"):
            p = f"{W}/runs/{name}/{f}"
            if os.path.exists(p):
                shutil.copy(p, f"{OUT}/{name}_{f}")
    results["seconds_total"] = round(time.time() - t_start, 1)
    results["device"] = torch.cuda.get_device_name(0)
    json.dump(results, open(f"{OUT}/metrics.json", "w"), indent=2)
    for d in ("lahore", "old4", "oldconv", "runs"):
        shutil.rmtree(f"{W}/{d}", ignore_errors=True)
    print("done", results["seconds_total"], "s")


if __name__ == "__main__":
    main()
