"""Fine-tune YOLO11s on the Manzil 4-class dataset on the Kaggle GPU (vision task V.3).

Input: the output of the `manzil-yolo-data` kernel (kaggle/yolo_data), attached via kernel_sources.
Steps:
  1. Baseline: the COCO-pretrained yolo11s.pt, unchanged, evaluated on the same test sets
     (labels mapped back to COCO ids; predictions limited to car/motorcycle/bus/truck).
  2. Fine-tune yolo11s.pt on train, select the best epoch on val.
  3. Evaluate best.pt on the UA-DETRAC test split and on the COCO val2017 motorcycle set.
Everything needed later is copied to /kaggle/working/out (pulled back with `kaggle kernels output`).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import time

ULTRALYTICS = "ultralytics==8.4.210"
MODEL = "yolo11s.pt"
# environment overrides exist only for a local CPU smoke test; Kaggle runs use the defaults
EPOCHS = int(os.environ.get("MANZIL_EPOCHS", 50))
IMGSZ = 640
BATCH = 32
SEED = 0
PATIENCE = 15

NAMES = ["car", "bus", "truck", "motorcycle"]
# our id -> COCO-80 class index (car 2, motorcycle 3, bus 5, truck 7)
TO_COCO = {0: 2, 1: 5, 2: 7, 3: 3}

W = os.environ.get("MANZIL_WORK", "/kaggle/working")
INPUT = os.environ.get("MANZIL_INPUT", "/kaggle/input")
CPU = os.environ.get("MANZIL_CPU") == "1"
OUT = f"{W}/out"


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def find_data_root() -> str:
    hits = glob.glob(f"{INPUT}/**/manzil_yolo/data.yaml", recursive=True)
    if not hits:
        raise FileNotFoundError(f"manzil_yolo/data.yaml not found under {INPUT}")
    return os.path.dirname(hits[0])


def write_yaml(path, root, names, test_split):
    with open(path, "w") as f:
        f.write(f"path: {root}\ntrain: images/train\nval: images/val\n"
                f"test: images/{test_split}\nnames: {dict(enumerate(names))}\n")


def coco_label_copy(src_root, dst_root, split):
    """Symlink the images and rewrite labels with COCO-80 class ids, for the baseline model."""
    os.makedirs(f"{dst_root}/images/{split}", exist_ok=True)
    os.makedirs(f"{dst_root}/labels/{split}", exist_ok=True)
    for img in glob.glob(f"{src_root}/images/{split}/*.jpg"):
        name = os.path.basename(img)
        dst = f"{dst_root}/images/{split}/{name}"
        if not os.path.exists(dst):
            os.symlink(img, dst)
        with open(f"{src_root}/labels/{split}/{name[:-4]}.txt") as fh:
            lines = [ln.split() for ln in fh if ln.strip()]
        with open(f"{dst_root}/labels/{split}/{name[:-4]}.txt", "w") as fh:
            for p in lines:
                fh.write(" ".join([str(TO_COCO[int(p[0])]), *p[1:]]) + "\n")


def summarise(metrics, names_of_interest):
    """Overall + per-class precision / recall / mAP50 / mAP50-95 from an Ultralytics val run."""
    box = metrics.box
    per_class = {}
    for i, c in enumerate(box.ap_class_index):
        name = metrics.names[int(c)]
        if name in names_of_interest:
            per_class[name] = {"precision": float(box.p[i]), "recall": float(box.r[i]),
                               "mAP50": float(box.ap50[i]), "mAP50_95": float(box.ap[i])}
    keys = list(per_class)

    def mean(k):
        return sum(per_class[c][k] for c in keys) / len(keys) if keys else float("nan")

    return {"classes_evaluated": keys,
            "precision": mean("precision"), "recall": mean("recall"),
            "mAP50": mean("mAP50"), "mAP50_95": mean("mAP50_95"),
            "per_class": per_class,
            "speed_ms_per_image": {k: float(v) for k, v in metrics.speed.items()}}


def evaluate(model, data_yaml, name, **kw):
    t = time.time()
    m = model.val(data=data_yaml, split="test", imgsz=IMGSZ, batch=32, device="cpu" if CPU else 0,
                  project=f"{W}/runs", name=name, plots=True, verbose=True, **kw)
    s = summarise(m, set(NAMES))
    s["eval_seconds"] = round(time.time() - t, 1)
    print(name, json.dumps(s, indent=2), flush=True)
    return s


def main():
    if not CPU:
        sh(f"pip install -q {ULTRALYTICS}")
        sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
    import torch
    from ultralytics import YOLO, __version__

    data_root = find_data_root()
    print("data root", data_root, flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(f"{data_root}/dataset_stats.json") as fh:
        stats = json.load(fh)
    shutil.copy(f"{data_root}/dataset_stats.json", OUT)

    ours = {}
    for split in ("test", "test_motorcycle"):
        ours[split] = f"{W}/data_{split}.yaml"
        write_yaml(ours[split], data_root, NAMES, split)

    # 1. baseline: COCO-pretrained model, no fine-tuning
    coco_root = f"{W}/coco_ids"
    results = {"versions": {"ultralytics": __version__, "torch": torch.__version__,
                            "python": sys.version.split()[0]},
               "config": {"model": MODEL, "epochs": EPOCHS, "imgsz": IMGSZ, "batch": BATCH,
                          "seed": SEED, "patience": PATIENCE, "gpus": torch.cuda.device_count()},
               "dataset_labels_sha256": stats.get("labels_sha256")}
    coco_names = YOLO(MODEL).names
    base = {}
    for split in ("test", "test_motorcycle"):
        coco_label_copy(data_root, coco_root, split)
        y = f"{W}/coco_{split}.yaml"
        with open(y, "w") as f:
            f.write(f"path: {coco_root}\ntrain: images/{split}\nval: images/{split}\n"
                    f"test: images/{split}\nnames: {dict(coco_names)}\n")
        base[split] = evaluate(YOLO(MODEL), y, f"baseline_{split}", classes=list(TO_COCO.values()))
    results["baseline_pretrained_coco"] = base

    # 2. fine-tune
    t0 = time.time()
    model = YOLO(MODEL)
    gpus = torch.cuda.device_count()
    model.train(data=ours["test"], epochs=EPOCHS, imgsz=IMGSZ, batch=BATCH, seed=SEED,
                deterministic=True, patience=PATIENCE, workers=4,
                device="cpu" if CPU else (list(range(gpus)) if gpus > 1 else 0),
                project=f"{W}/runs", name="finetune", exist_ok=True, plots=True)
    results["train_seconds"] = round(time.time() - t0, 1)
    run = f"{W}/runs/finetune"

    # 3. evaluate best.pt on held-out test sets
    best = YOLO(f"{run}/weights/best.pt")
    results["finetuned"] = {s: evaluate(best, ours[s], f"finetuned_{s}") for s in ours}

    for f in ["results.csv", "results.png", "args.yaml", "confusion_matrix.png",
              "confusion_matrix_normalized.png", "BoxPR_curve.png", "labels.jpg"]:
        if os.path.exists(f"{run}/{f}"):
            shutil.copy(f"{run}/{f}", OUT)
    shutil.copy(f"{run}/weights/best.pt", f"{OUT}/best.pt")
    for name in ("finetuned_test", "finetuned_test_motorcycle", "baseline_test"):
        for f in ("confusion_matrix_normalized.png", "BoxPR_curve.png", "val_batch0_pred.jpg"):
            p = f"{W}/runs/{name}/{f}"
            if os.path.exists(p):
                shutil.copy(p, f"{OUT}/{name}_{f}")
    with open(f"{OUT}/metrics.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print(json.dumps(results, indent=2))
    # keep the downloadable output small: only OUT matters
    shutil.rmtree(coco_root, ignore_errors=True)


if __name__ == "__main__":
    main()
