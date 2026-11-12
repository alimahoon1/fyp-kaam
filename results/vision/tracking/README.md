# Vision V.4 + V.5: tracking, line-crossing counts, queue estimate and counting error (real, Kaggle GPU, 12 Nov 2026)

Everything here is a real result. It was produced by the Kaggle kernel
`mibrahimsalman022/manzil-yolo-track` (`kaggle/yolo_track/`, version 1) on one Tesla T4 and pulled
back with `kaggle kernels output`. The figures and tables come from
`python scripts/vision_tracking_report.py`.

## What was run

- **Data:** all **40 official UA-DETRAC test sequences** (the held-out split, never used for training or model selection), every frame at 25 fps: **56,340 frames, about 37.6 minutes of video**.
- **Detector:** the fine-tuned YOLO11s from V.3 (`models/yolo/manzil_yolo11s_best.pt`, sha256 `0022c8a0…dc2f`, checked inside the kernel), image size 640. Ignored regions are filled grey, the same as in training.
- **Tracker:** ByteTrack, from Ultralytics 8.4.210 `model.track(..., tracker="bytetrack.yaml")` with the default settings. The tracker is reset for each sequence.
- **Counting** (`manzil/perception/counting.py`, unit-tested in `tests/test_counting.py`):
  - The counting line runs across the full image width at 60 % of the height.
  - A track is counted once, when its box centre crosses the line. The direction is "down" or "up" in the image.
  - Crossings inside DETRAC ignored regions are dropped.
  - The class is the majority class over the whole track.
- **Ground truth:** the UA-DETRAC annotation boxes with their target ids (the true track ids) go through **the same counter**. The counting error therefore measures detection plus tracking only, not a difference in counting rules.
- **Queue estimate (a proxy):**
  - It is the number of tracked vehicles in view that are *stopped*. A vehicle counts as stopped when its centre moved less than 0.25 × its box height over the last 1 s.
  - UA-DETRAC has no stop lines or signal states, so this measures "stopped vehicles in view", not a queue behind a specific stop line.
  - It is computed the same way from the true tracks, for comparison.
- Speed: 40 to 66 frames/s for detection and tracking together. The whole run took 17 min.

## Counting error (V.5): one clip = one test sequence (`mae_table.md`)

| group | clips | true | counted | MAE | bias | RMSE | WAPE | MAPE | exact clips |
|---|---|---|---|---|---|---|---|---|---|
| all vehicles | 40 | 870 | 972 | **2.60** | +2.55 | 3.78 | **12.0 %** | 44.1 % | 11 |
| car + bus + truck | 40 | 870 | 933 | **1.62** | +1.57 | 2.52 | **7.5 %** | 15.0 % | 15 |
| car | 40 | 800 | 852 | 1.35 | +1.30 | 2.07 | 6.8 % | 17.4 % | 17 |
| bus | 40 | 61 | 77 | 0.40 | +0.40 | 1.02 | 26.2 % | 17.3 % | 31 |
| truck | 40 | 9 | 4 | 0.17 | −0.12 | 0.52 | 77.8 % | 57.1 % | 35 |
| motorcycle | 40 | 0 | 39 | 0.97 | +0.97 | 2.58 | – | – | 31 |
| direction down | 40 | 576 | 633 | 1.62 | +1.43 | 2.75 | 11.3 % | 26.4 % | 15 |
| direction up | 40 | 294 | 339 | 1.12 | +1.12 | 2.07 | 15.3 % | 19.9 % | 21 |

- MAE is the mean of |counted − true| per sequence, in vehicles.
- WAPE is Σ|error| / Σtrue, the share of vehicles miscounted.
- MAPE is the mean of |error| / true over the sequences that have at least one true crossing. It is inflated by sequences with only 0–5 true crossings (for example 9 counted against 1 true in MVI_40901).
- Queue: the mean per-frame absolute error is **0.80 stopped vehicles**. The MAE of the per-sequence mean queue is 0.68 (bias −0.43, so the queue is slightly underestimated).

## What the numbers say

- The system **over-counts slightly** (bias +2.6 per sequence). It never under-counts by more than 1. 11 of 40 sequences are exact, and 15 of 40 are exact for car + bus + truck.
- **38 % of the over-count is "motorcycles"** (39 of the +102). UA-DETRAC does not label two-wheelers at all, so these are not necessarily wrong. Some are real scooters or bicycles that the ground truth leaves out, and some are false detections; this run cannot tell which. Without motorcycles, the error is MAE 1.62 / WAPE 7.5 %.
- Other over-counts we saw:
  - one sample frame shows a stationary false "bus" on the kerb island (`sample_frame_MVI_40714_00376.png`);
  - extra "up" crossings appear in dense, slow traffic (MVI_40864: 6 extra "up" against 0 true).

  These are **likely** detection false positives and ID switches near the line. That is an inference from the per-direction numbers and has not been checked frame by frame.
- **Truck** stays the weak class, as in V.3: 4 counted against 9 true. Many trucks are counted as cars or buses, so the totals still line up.
- **The queue estimate tracks the truth closely.** On the busiest sample (MVI_40714: about 30 stopped vehicles, which then clear) the two curves almost overlap (`queue_sample.png`).
- Limits:
  - There is one line position (60 % of the height), not tuned per camera.
  - The ground-truth counts come from the DETRAC boxes, and DETRAC leaves some vehicles unlabelled.
  - The queue is a stopped-vehicle proxy, not a per-lane queue length.
  - Lahore footage has not been tested yet (V.6, deferred).

## Files

| File | What it is |
|---|---|
| `sample_MVI_40714_tracking.mp4` | **Annotated sample video**: the first 30 s of MVI_40714 (H.264, 960×540, 3.5 MB, sha256 `d05301a56a0f419f493f16b2e75e7bf1b11b0a22cc30794731164aecf1cbea95`). It shows boxes with track id and class (red = stopped), the yellow counting line, a running count with the true count, the direction split, and the queue with its true value. The sequence was chosen automatically as the one with the most stopped vehicles among sequences with at least 20 true crossings. |
| `sample_frame_MVI_40714_*.png` | Three frames from the sample video |
| `counts.csv` | **Counts per sequence**: true and counted totals, by direction and by class, mean queue (true and estimated), per-frame queue error, and speed |
| `events.csv` | Every crossing event (1,842 rows; `source` = true/pred): frame, track id, class, direction, crossing point |
| `queue.csv` | Queue estimate and true queue once per second for every sequence |
| `summary.json` | All error metrics, settings, versions (Ultralytics 8.4.210, torch 2.11 + CUDA, T4), weights checksum, timings |
| `mae_table.csv`, `mae_table.md` | The MAE table above |
| `count_pred_vs_true.png` | Counted vs true count per sequence |
| `count_error_per_sequence.png` | Signed error per sequence, sorted by true count |
| `queue_sample.png` | Estimated vs true stopped-vehicle count over time on MVI_40714 |

To reproduce:

```bash
python kaggle/yolo_track/build.py
```

```bash
kaggle kernels push -p kaggle/yolo_track
```

```bash
kaggle kernels output mibrahimsalman022/manzil-yolo-track -p <dir>
```

Then copy `<dir>/out/*` here and run `python scripts/vision_tracking_report.py`.
