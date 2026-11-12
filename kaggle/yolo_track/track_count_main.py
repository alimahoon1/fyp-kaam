"""YOLO + ByteTrack line-crossing counts and queue estimate on UA-DETRAC test videos (V.4, V.5).

Runs on Kaggle (GPU). Inputs, attached through kernel-metadata.json:
  * UA-DETRAC (bratjay/ua-detrac-orig): images of the 40 official test sequences + annotation XML;
  * the output of `manzil-yolo-train` (kernel_sources), which holds the fine-tuned `out/best.pt`
    (the same file as models/yolo/manzil_yolo11s_best.pt; its sha256 is checked).

For every test sequence, at the full 25 fps:
  1. Ground truth: the DETRAC boxes with their target ids go through the counter and queue
     estimator in manzil/perception/counting.py (inlined below by build.py).
  2. Prediction: ignored regions are filled grey (as in training), YOLO11s + ByteTrack
     (Ultralytics `model.track`, default bytetrack.yaml) gives tracks, which go through the same
     counter and queue estimator.
Outputs in /kaggle/working/out: counts.csv, events.csv, queue.csv, summary.json, one annotated
sample video and a few annotated sample frames.

Settings are module constants so that every run is described by the code and summary.json.
"""

# ruff: noqa: F821  (counting names are inlined at the @@INLINE marker by build.py)
from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ULTRALYTICS = "ultralytics==8.4.210"
WEIGHTS_SHA256 = "0022c8a0394bf8a583ef0d21e324853a73251ca86a3ac6caab656fd65ae8dc2f"
IMGSZ = 640
TRACKER = "bytetrack.yaml"  # Ultralytics default ByteTrack settings
LINE_FRAC = 0.6  # counting line: full width, at 60 % of the image height
QUEUE_WINDOW = 25  # frames = 1 s
QUEUE_STOP_FRAC = 0.25
QUEUE_SAMPLE_EVERY = 25  # queue.csv keeps one row per second
SAMPLE_SECONDS = 30
TIME_BUDGET_S = float(os.environ.get("MANZIL_TIME_BUDGET_S", 8 * 3600))
MAX_SEQS = int(os.environ.get("MANZIL_MAX_SEQS", 0))  # 0 = all (local smoke tests use a few)
FRAME_LIMIT = int(os.environ.get("MANZIL_FRAME_LIMIT", 0))  # 0 = all frames

INPUT = os.environ.get("MANZIL_INPUT", "/kaggle/input")
OUT = os.environ.get("MANZIL_OUT", "/kaggle/working/out")
CPU = os.environ.get("MANZIL_CPU") == "1"
GREY = (114, 114, 114)
COLORS = {0: (60, 200, 60), 1: (230, 160, 30), 2: (40, 120, 255), 3: (220, 60, 220)}  # BGR

# @@INLINE manzil/perception/counting.py@@


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def find_one(pattern):
    hits = sorted(glob.glob(pattern, recursive=True))
    if not hits:
        raise FileNotFoundError(pattern)
    return hits[0]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ground_truth(frames_gt, line, ignored):
    """Run the counter + queue estimator over the DETRAC ground-truth tracks."""
    counter = LineCounter(*line, ignored=ignored)
    queue = QueueEstimator(QUEUE_WINDOW, QUEUE_STOP_FRAC, ignored=ignored)
    q_series = {}
    for f in sorted(frames_gt):
        rows = frames_gt[f]
        counter.update(f, rows)
        q_series[f] = queue.update(f, rows)[0]
    return counter.finalize(), q_series


def draw(cv2, img, tracks, stopped, line, n_pred, n_gt, by_dir, q_pred, q_gt, names):
    a, b = line
    cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 255, 255), 2)
    for tid, cls, x, y, w, h in tracks:
        col = (0, 0, 255) if tid in stopped else COLORS.get(cls, (255, 255, 255))
        cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), col, 2)
        cv2.putText(img, f"{tid} {names[cls]}", (int(x), max(12, int(y) - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
    lines = [f"count {n_pred}  (true {n_gt})",
             f"down {by_dir['down']}  up {by_dir['up']}",
             f"queue (stopped) {q_pred}  (true {q_gt})"]
    cv2.rectangle(img, (0, 0), (330, 24 * len(lines) + 8), (0, 0, 0), -1)
    for i, t in enumerate(lines):
        cv2.putText(img, t, (8, 24 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
                    cv2.LINE_AA)
    cv2.putText(img, "Manzil YOLO11s + ByteTrack (red = stopped)", (8, img.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def main():
    t_start = time.time()
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        sh(f"pip install -q {ULTRALYTICS}")
    import cv2
    import ultralytics
    from ultralytics import YOLO

    os.makedirs(OUT, exist_ok=True)
    weights = find_one(f"{INPUT}/**/out/best.pt")
    w_sha = sha256(weights)
    print("weights", weights, w_sha, flush=True)
    if w_sha != WEIGHTS_SHA256:
        raise RuntimeError(f"weights checksum {w_sha} != expected {WEIGHTS_SHA256}")

    ann_dir = find_one(f"{INPUT}/**/DETRAC-Test-Annotations-XML/MVI_*.xml").rsplit("/", 1)[0]
    seqs = sorted(os.path.basename(p)[:-4] for p in glob.glob(f"{ann_dir}/MVI_*.xml"))
    img_root = find_one(f"{INPUT}/**/DETRAC-Images/{seqs[0]}").rsplit("/", 1)[0]
    if MAX_SEQS:
        seqs = seqs[:MAX_SEQS]
    print(len(seqs), "test sequences", flush=True)

    # ---- pass 1: ground truth for every sequence (cheap) and choice of the sample video
    gt = {}
    for s in seqs:
        ignored, frames_gt = parse_detrac_tracks(open(f"{ann_dir}/{s}.xml").read())
        files = sorted(glob.glob(f"{img_root}/{s}/*.jpg"))
        if FRAME_LIMIT:
            files = files[:FRAME_LIMIT]
            frames_gt = {f: r for f, r in frames_gt.items() if f <= FRAME_LIMIT}
        h, w = cv2.imread(files[0]).shape[:2]
        line = horizontal_line(w, h, LINE_FRAC)
        events, q = ground_truth(frames_gt, line, ignored)
        gt[s] = dict(ignored=ignored, frames=frames_gt, files=files, size=(w, h), line=line,
                     events=events, queue=q)
        print(s, len(files), "frames", len(events), "true crossings", flush=True)
    # sample = the sequence with the most stopped vehicles on average among busy ones
    busy = [s for s in seqs if len(gt[s]["events"]) >= 20] or seqs
    sample = max(busy, key=lambda s: (sum(gt[s]["queue"].values()) / max(1, len(gt[s]["queue"])),
                                      len(gt[s]["events"])))
    print("sample video sequence:", sample, flush=True)

    # ---- pass 2: YOLO + ByteTrack on every frame
    device = "cpu" if CPU else 0
    rows, all_events, queue_rows, timing = [], [], [], {}
    pool = ThreadPoolExecutor(8)
    done = []
    for s in seqs:
        if time.time() - t_start > TIME_BUDGET_S:
            print("time budget reached, stopping before", s, flush=True)
            break
        g = gt[s]
        model = YOLO(weights)  # a fresh model per sequence = a fresh ByteTrack state
        names = CLASS_NAMES
        counter = LineCounter(*g["line"], ignored=g["ignored"])
        queue = QueueEstimator(QUEUE_WINDOW, QUEUE_STOP_FRAC, ignored=g["ignored"])
        gt_ev_frames = sorted(ev.frame for ev in g["events"])
        writer, sample_frames = None, []
        n_sample = min(SAMPLE_SECONDS * 25, len(g["files"]))
        if s == sample:
            tmp = f"{OUT}/_sample.avi"
            writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"MJPG"), 25, g["size"])
        t0 = time.time()
        futures = [pool.submit(cv2.imread, p) for p in g["files"][:16]]
        q_pred_series = {}
        for i, path in enumerate(g["files"]):
            img = futures[i].result()
            futures[i] = None
            if i + 16 < len(g["files"]):
                futures.append(pool.submit(cv2.imread, g["files"][i + 16]))
            frame = int(os.path.basename(path)[3:-4])  # img00001.jpg -> 1
            for (x0, y0, w, h) in g["ignored"]:
                img[int(y0):int(y0 + h), int(x0):int(x0 + w)] = GREY
            r = model.track(img, persist=True, tracker=TRACKER, imgsz=IMGSZ, device=device,
                            verbose=False)[0]
            tracks = []
            if r.boxes is not None and r.boxes.id is not None:
                for (x1, y1, x2, y2), tid, cls in zip(r.boxes.xyxy.tolist(),
                                                      r.boxes.id.int().tolist(),
                                                      r.boxes.cls.int().tolist(), strict=True):
                    tracks.append((tid, cls, x1, y1, x2 - x1, y2 - y1))
            counter.update(frame, tracks)
            n_q, stopped = queue.update(frame, tracks)
            q_pred_series[frame] = n_q
            if writer is not None and i < n_sample:
                n_gt = sum(1 for fr in gt_ev_frames if fr <= frame)
                by_dir = {"down": 0, "up": 0}
                for ev in counter.events:
                    by_dir[ev.direction] += 1
                draw(cv2, img, tracks, stopped, g["line"], counter.running_count(), n_gt, by_dir,
                     n_q, g["queue"].get(frame, 0), names)
                writer.write(img)
                if i in (n_sample // 4, n_sample // 2, 3 * n_sample // 4):
                    cv2.imwrite(f"{OUT}/sample_frame_{s}_{frame:05d}.png", img)
                    sample_frames.append(frame)
        dt = time.time() - t0
        pred_events = counter.finalize()
        if writer is not None:
            writer.release()
            if shutil.which("ffmpeg"):
                sh(f"ffmpeg -y -loglevel error -i {OUT}/_sample.avi -c:v libx264 -crf 28 "
                   f"-preset slow -pix_fmt yuv420p {OUT}/sample_{s}_tracking.mp4")
                os.remove(f"{OUT}/_sample.avi")
            else:
                os.rename(f"{OUT}/_sample.avi", f"{OUT}/sample_{s}_tracking.avi")
        pc, tc = counts_by_class(pred_events), counts_by_class(g["events"])
        pd = {d: sum(1 for e in pred_events if e.direction == d) for d in ("down", "up")}
        td = {d: sum(1 for e in g["events"] if e.direction == d) for d in ("down", "up")}
        qp = list(q_pred_series.values())
        qt = [g["queue"].get(f, 0) for f in q_pred_series]
        row = {"sequence": s, "frames": len(g["files"]), "seconds": round(len(g["files"]) / 25, 1),
               "true_total": len(g["events"]), "pred_total": len(pred_events),
               "abs_error": abs(len(pred_events) - len(g["events"])),
               "true_down": td["down"], "pred_down": pd["down"],
               "true_up": td["up"], "pred_up": pd["up"]}
        for c, n in enumerate(CLASS_NAMES):
            row[f"true_{n}"], row[f"pred_{n}"] = tc[c], pc[c]
        row["true_queue_mean"] = round(sum(qt) / max(1, len(qt)), 3)
        row["pred_queue_mean"] = round(sum(qp) / max(1, len(qp)), 3)
        q_abs = sum(abs(a - b) for a, b in zip(qp, qt, strict=True))
        row["queue_mae_per_frame"] = round(q_abs / max(1, len(qp)), 3)
        row["fps"] = round(len(g["files"]) / dt, 1)
        rows.append(row)
        for src, evs in (("true", g["events"]), ("pred", pred_events)):
            for e in evs:
                all_events.append({"sequence": s, "source": src, "frame": e.frame,
                                   "track_id": e.track_id, "class": CLASS_NAMES[e.class_id],
                                   "direction": e.direction,
                                   "x": round(e.x, 1), "y": round(e.y, 1)})
        for f in sorted(q_pred_series):
            if f % QUEUE_SAMPLE_EVERY == 0:
                queue_rows.append({"sequence": s, "frame": f, "second": f / 25,
                                   "pred_queue": q_pred_series[f],
                                   "true_queue": g["queue"].get(f, 0)})
        timing[s] = round(dt, 1)
        done.append(s)
        print(s, row, flush=True)

    def write_csv(name, data):
        with open(f"{OUT}/{name}", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            wr.writeheader()
            wr.writerows(data)

    write_csv("counts.csv", rows)
    write_csv("events.csv", all_events)
    write_csv("queue.csv", queue_rows)

    summary = {
        "sequences_done": len(done), "sequences_total": len(gt), "sample_sequence": sample,
        "total": count_errors((r["pred_total"], r["true_total"]) for r in rows),
        "per_class": {n: count_errors((r[f"pred_{n}"], r[f"true_{n}"]) for r in rows)
                      for n in CLASS_NAMES},
        "per_direction": {d: count_errors((r[f"pred_{d}"], r[f"true_{d}"]) for r in rows)
                          for d in ("down", "up")},
        "queue": {"mae_per_frame_mean_over_seqs":
                  sum(r["queue_mae_per_frame"] for r in rows) / max(1, len(rows)),
                  "mean_queue_error": count_errors((r["pred_queue_mean"], r["true_queue_mean"])
                                                   for r in rows)},
        "settings": {"imgsz": IMGSZ, "tracker": TRACKER, "line_frac": LINE_FRAC,
                     "queue_window_frames": QUEUE_WINDOW, "queue_stop_frac": QUEUE_STOP_FRAC,
                     "frame_limit": FRAME_LIMIT, "fps": 25},
        "versions": {"ultralytics": ultralytics.__version__, "python": sys.version.split()[0]},
        "weights_sha256": w_sha,
        "seconds": {"total": round(time.time() - t_start, 1), "per_sequence": timing},
        "frames_processed": sum(r["frames"] for r in rows),
    }
    try:
        import torch
        summary["versions"]["torch"] = torch.__version__
        summary["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        pass
    json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=2)
    print(json.dumps({k: summary[k] for k in ("total", "per_class", "queue")}, indent=2))


if __name__ == "__main__":
    main()
