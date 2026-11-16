"""Shot boundaries + frame extraction for the two Lahore videos (W2 step 2). CPU kernel.

Input: the private dataset mibrahimsalman022/manzil-lahore-videos (attached, never downloaded
elsewhere). For each video:
  1. Read every frame, compute a cut score between consecutive frames on a 160x90 copy:
     1 - correlation of the H-S colour histograms, plus the mean absolute grey difference / 255.
     A cut is a frame whose score is a clear local peak (> CUT_ABS and > CUT_REL x the median of
     the surrounding 2 s). Shots shorter than MIN_SHOT_S are merged into the previous shot.
  2. Inside every shot, take one frame every FRAME_STEP_S seconds (about 2 fps), skipping
     EDGE_S seconds at both ends of the shot (transition frames), and drop near-duplicates
     (mean absolute grey difference on a 64x36 copy < DEDUP_THR against the last kept frame).
  3. Save the frames as JPEG (video 2 downscaled to MAX_W wide) + frames.csv, shots.json,
     scores.csv (the per-frame cut score) and one 320-px thumbnail per second for checking cuts.
Shot list overrides (if the automatic cuts are wrong) go into SHOT_OVERRIDES.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os

import cv2
import numpy as np

INPUT = os.environ.get("MANZIL_INPUT", "/kaggle/input")
OUT = os.environ.get("MANZIL_OUT", "/kaggle/working")
VIDEOS = {"v1": "manzil-lahore-video.mp4", "v2": "manzil-lahore-video-2.mov"}
SHA256 = {"v1": "d6debb6a663b1f731ae3d81e74e2508c9d332ffe890e98c7e22f90517fa97d9c",
          "v2": "b7f4f90647f3c1fcc7580acae0533382cc6e6eb3ae3a4980891a8a08e78e08c9"}
CUT_ABS = 0.35
CUT_REL = 4.0
MIN_SHOT_S = 2.0
FRAME_STEP_S = 0.5
EDGE_S = 0.25
DEDUP_THR = 1.5
MAX_W = 1920
JPEG_Q = 95
# video -> segment boundaries in seconds, used instead of the automatic cuts. Video 1 has one hard
# cut (101.635 s, found automatically by version 1 of this kernel); the other framing changes are
# camera moves that a cut detector cannot see: a zoom near 15.5 s, a tilt up at 60-64 s and a tilt
# back down at 84-87 s (read off one thumbnail per second, see results/fyp2/vision_lahore/).
SHOT_OVERRIDES: dict[str, list[float]] = {"v1": [15.5, 60.0, 87.0, 101.635]}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def small_feats(frame):
    s = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    grey = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return hist, grey


def detect_cuts(scores, fps):
    win = int(round(fps))
    cuts = []
    for i in range(1, len(scores)):
        lo, hi = max(1, i - win), min(len(scores), i + win + 1)
        local = np.median(scores[lo:hi])
        if scores[i] > CUT_ABS and scores[i] > CUT_REL * max(local, 1e-3) \
                and scores[i] == max(scores[lo:hi]):
            cuts.append(i)
    return cuts


def main():
    os.makedirs(f"{OUT}/frames", exist_ok=True)
    os.makedirs(f"{OUT}/thumbs", exist_ok=True)
    rows, shots_all, score_rows = [], {}, []
    for vid, fname in VIDEOS.items():
        path = glob.glob(f"{INPUT}/**/{fname}", recursive=True)[0]
        digest = sha256(path)
        print(vid, path, digest, flush=True)
        if digest != SHA256[vid]:
            raise RuntimeError(f"{vid} sha256 mismatch: {digest}")
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        scores = [0.0]
        prev = None
        n = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            hist, grey = small_feats(fr)
            if prev is not None:
                corr = cv2.compareHist(prev[0], hist, cv2.HISTCMP_CORREL)
                scores.append(float((1 - corr) + np.abs(grey - prev[1]).mean() / 255.0))
            prev = (hist, grey)
            if n % int(round(fps)) == 0:
                t = cv2.resize(fr, (320, int(320 * fr.shape[0] / fr.shape[1])))
                cv2.imwrite(f"{OUT}/thumbs/{vid}_{n // int(round(fps)):04d}s.jpg", t)
            n += 1
        cap.release()
        scores = np.array(scores)
        for i, s in enumerate(scores):
            score_rows.append({"video": vid, "frame": i, "time_s": round(i / fps, 3),
                               "cut_score": round(float(s), 4)})
        if vid in SHOT_OVERRIDES:
            cuts = [int(round(t * fps)) for t in SHOT_OVERRIDES[vid]]
            how = "manual segments (camera moves) + automatic hard cut"
        else:
            cuts = detect_cuts(scores, fps)
            how = "automatic"
        bounds = [0, *cuts, n]
        shots = []
        for a, b in zip(bounds[:-1], bounds[1:], strict=True):
            if shots and (b - a) / fps < MIN_SHOT_S:
                shots[-1]["end_frame"] = b
                continue
            shots.append({"start_frame": a, "end_frame": b})
        for k, s in enumerate(shots):
            s["shot"] = k
            s["start_s"] = round(s["start_frame"] / fps, 3)
            s["end_s"] = round(s["end_frame"] / fps, 3)
            s["peak_score_at_start"] = round(float(scores[s["start_frame"]]), 4)
        print(vid, "cuts", [round(c / fps, 2) for c in cuts], flush=True)

        # pass 2: extract frames
        cap = cv2.VideoCapture(path)
        wanted = {}
        for s in shots:
            t = s["start_s"] + EDGE_S
            while t < s["end_s"] - EDGE_S:
                wanted[int(round(t * fps))] = s["shot"]
                t += FRAME_STEP_S
        last_kept = {}
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if i in wanted:
                shot = wanted[i]
                g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (64, 36),
                               interpolation=cv2.INTER_AREA).astype(np.float32)
                diff = None if shot not in last_kept else float(np.abs(g - last_kept[shot]).mean())
                if diff is not None and diff < DEDUP_THR:
                    shots[shot].setdefault("dropped_duplicates", 0)
                    shots[shot]["dropped_duplicates"] += 1
                else:
                    last_kept[shot] = g
                    if fr.shape[1] > MAX_W:
                        fr = cv2.resize(fr, (MAX_W, int(round(MAX_W * fr.shape[0] / fr.shape[1]))),
                                        interpolation=cv2.INTER_AREA)
                    name = f"{vid}_s{shot}_f{i:05d}.jpg"
                    cv2.imwrite(f"{OUT}/frames/{name}", fr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q])
                    rows.append({"image": name, "video": vid, "shot": shot, "frame": i,
                                 "time_s": round(i / fps, 3), "width": fr.shape[1],
                                 "height": fr.shape[0],
                                 "diff_to_prev_kept": "" if diff is None else round(diff, 2),
                                 "sha256": sha256(f"{OUT}/frames/{name}")})
            i += 1
        cap.release()
        for s in shots:
            s["frames_kept"] = sum(1 for r in rows if r["video"] == vid and r["shot"] == s["shot"])
            s.setdefault("dropped_duplicates", 0)
        shots_all[vid] = {"file": fname, "sha256": digest, "fps": fps, "frames_total": n,
                          "duration_s": round(n / fps, 3), "cut_method": how,
                          "cuts_s": [round(c / fps, 3) for c in cuts], "shots": shots}
    with open(f"{OUT}/frames.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(f"{OUT}/scores.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(score_rows[0]))
        w.writeheader()
        w.writerows(score_rows)
    settings = {k: globals()[k] for k in ("CUT_ABS", "CUT_REL", "MIN_SHOT_S", "FRAME_STEP_S",
                                          "EDGE_S", "DEDUP_THR", "MAX_W", "JPEG_Q")}
    json.dump({"settings": settings, "opencv": cv2.__version__, "videos": shots_all},
              open(f"{OUT}/shots.json", "w"), indent=2)
    print(json.dumps(shots_all, indent=2))
    print("frames kept", len(rows))


if __name__ == "__main__":
    main()
