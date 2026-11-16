# Lahore footage: six-class detector (rickshaw, van) and line counting (W2, FYP-II)

Workstream W2, 16 Nov 2026. Everything here is a **real run** on Kaggle (2× Tesla T4, Ultralytics
8.4.210). It is **one location and about 2.3 minutes of video (126 s + 12.5 s)**, so treat every number as preliminary.

**Label status: model-assisted, Claude-reviewed. The test split is preliminary until a team member
has checked it.** A model proposed the boxes and Claude (the AI assistant) reviewed every frame. No
person on the team has checked them yet.

## Data

| | |
|---|---|
| Videos | 2 phone videos of Ferozepur Road at Ichhra, Lahore (see `data/lahore_video/SOURCES.md`). Private Kaggle dataset `mibrahimsalman022/manzil-lahore-videos`. They are for research use in this FYP only and are never published. |
| Frames | about 2 fps, near-duplicates dropped; 273 frames (kernel `kaggle/lahore_frames/`; `frames.csv`, `shots.json`, `cut_scores.csv`) |
| Split | by camera segment, never by frame, with a 2 s guard band (`data/lahore_video/split_manifest.csv`). Train = video 1 segments 1–2 (134 frames). Val = video 1 segment 0 (14 frames). Test = video 1 segments 3–4 (72 frames, 30 % of video 1) plus all of video 2 (25 frames). Unused = 28 frames (guard band, plus the title caption in the first 6.6 s). |
| Classes | 0 car, 1 bus, 2 truck, 3 motorcycle, **4 rickshaw** (auto, chingchi and loader three-wheelers), **5 van**. Ids 0–3 are the same as in the old four-class model. |
| Far field | Vehicles too small to label reliably (rows above `far_field.json[image]`) are not labelled. That band is filled grey in train, val and test. |
| Labels | 247 frames, 11,033 boxes (`label_stats.csv`). Private Kaggle dataset `mibrahimsalman022/manzil-lahore-labels`. sha256 of the label set (sorted file names + contents, 247 files): `38e2943b31251df29df250d70ca32076f06eb872a782ac4288a017bf8a573191` |

How the labels were made (kernels `kaggle/lahore_prelabel/` and `kaggle/lahore_bootstrap/`, tools in
`manzil/perception/lahore_review.py`):

1. Three detectors proposed boxes: the fine-tuned four-class YOLO11s, COCO YOLO11x, and
   open-vocabulary YOLOv8x-World with rickshaw and van prompts.
2. A small six-class "bootstrap" model was trained on the frames already reviewed and used as a
   fourth proposer. Without it, almost every rickshaw was proposed as "car".
3. Claude reviewed every rendered frame. The correction list is in `review_ops.jsonl` and the totals
   are in `review_log.json`: 241 boxes deleted, 924 class changes, 430 low-confidence candidates
   accepted, 53 boxes drawn by hand, and 415 far-field boxes dropped.

Labelling conventions:

- Box or tarp pickups and the water tanker are labelled truck.
- The yellow Mazda minibus, and the Metro and university buses, are labelled bus.
- The Suzuki Wagon R is labelled car. The Changan Karvaan passenger van is labelled van.
- A motorcycle box includes the rider.

**Test-review caveat:** on the test frames, the review focused on fixing classes and deleting false
boxes. It searched less thoroughly for boxes the models missed: in video 1 test, 3 candidates were
accepted and 1 box was added; in video 2, 17 boxes were added. Some unlabelled vehicles near the
far-field line are therefore likely. If they exist, they count against the new model as false
positives.

| Split | Frames | Boxes | car | bus | truck | motorcycle | rickshaw | van |
|---|---|---|---|---|---|---|---|---|
| train | 134 | 6531 | 3026 | 76 | 200 | 1599 | 1313 | 317 |
| val | 14 | 928 | 324 | 6 | 45 | 280 | 230 | 43 |
| test, video 1 | 72 | 3185 | 1443 | 65 | 101 | 1021 | 377 | 178 |
| test, video 2 | 25 | 389 | 210 | 0 | 0 | 66 | 102 | 11 |

## Training

The model was trained in kernel `kaggle/lahore_train/` (built from `lahore_train_main.py` by
`build.py`), version 1.

- It starts from `manzil_yolo11s_best.pt` (four classes, sha256 `0022c8a0…dc2f`) and is fine-tuned
  to six classes.
- Image size 1280, batch 16, seed 0, up to 60 epochs, patience 20.
- Training data: the Lahore train frames repeated 3 times, plus a replay of 150 UA-DETRAC and 150
  COCO images from the old training set.
- Training stopped early at epoch 32. The best epoch was 12, chosen on Lahore val (val mAP50 0.827,
  mAP50-95 0.755). Training took 0.19 h. The training curves are in `training/`.
- Weights: `manzil_yolo11s_lahore6_best.pt`, 19.2 MB, sha256
  `0bdad8c2e2d29138a106e14790ecf393726e3fc65a0a5c1e57067d8af7f683cb`. They are stored in the private
  Kaggle dataset `mibrahimsalman022/manzil-lahore-weights`, not in git.

Version 2 of the kernel reused these weights and ran all the evaluation below (979 s). Its output is
`metrics.json`.

The val split is only 14 frames from a single segment, so the val numbers are optimistic. Use the
test numbers.

## Results on the Lahore test set (video 1 test segments + video 2: 97 frames)

Image size 1280. The old model can only predict 4 classes, so it is scored on the same images with
the rickshaw and van labels removed ("old4"). Scored the old way instead (van labels counted as car,
"oldconv"), the old model gets mAP50 0.536.

| Model | Classes scored | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|
| Old four-class model | car, bus, truck, motorcycle | 0.461 | 0.594 | 0.529 | 0.387 |
| **New six-class model** | all six | 0.702 | 0.591 | **0.660** | **0.566** |

Per class (mAP50 / mAP50-95):

| Class | Old model | New model |
|---|---|---|
| car | 0.764 / 0.630 | **0.910 / 0.802** |
| bus | 0.518 / 0.386 | 0.567 / 0.506 |
| truck | 0.109 / 0.079 | 0.467 / 0.372 |
| motorcycle | 0.724 / 0.451 | **0.899 / 0.702** |
| rickshaw | cannot detect | 0.743 / 0.676 |
| van | cannot detect | 0.371 / 0.340 |

On the four old classes alone, the new model's mean mAP50 is 0.711 against 0.529 for the old model.

By video:

| Test set | Model | mAP50 | mAP50-95 |
|---|---|---|---|
| video 1 test segments (72 frames) | new model, 6 classes | 0.673 | 0.582 |
| video 1 test segments | old model, 4 classes | 0.527 | 0.387 |
| video 2 (25 frames, a different camera position, never seen in training) | new model (car, motorcycle, rickshaw, van) | 0.654 | 0.515 |
| video 2 | old model (car, motorcycle) | 0.862 | 0.604 |

On video 2, the new model is good on car (0.884) and motorcycle (0.893). Rickshaw precision is
high (0.92) but recall is only 0.45, and van is almost never right (mAP50 0.08). Video 2 has only
11 vans. Video 2 is the only test of a new viewpoint, and it shows that the model does not yet
generalise beyond the one camera position.

**Confusion** at conf 0.25 and IoU 0.5 on the whole test set (`eval/confusion_new_test.csv`; rows
are the true class, columns the prediction):

- Rickshaw: 331 of 479 found correctly, 39 called car, 24 called truck, 73 missed.
- Van: 57 of 189 found correctly, 56 called car, 41 called rickshaw. Van is the weakest class.
- The old model calls 103 rickshaws "car" and misses 586 of the 1,087 motorcycles. The new model
  misses 129 of them.
- Plots: `eval/*_confusion_matrix*.png`, `eval/*_BoxPR_curve.png`. All numbers are in
  `eval/lahore_test_metrics.csv`.

## Forgetting check (the new model on the old test sets, image size 640)

| Test set | Old fine-tuned model (`results/vision/`) | New six-class model |
|---|---|---|
| UA-DETRAC test, mAP50 / mAP50-95 | 0.799 / 0.586 | 0.740 / 0.514 |
| … car | 0.924 / 0.671 | 0.900 / 0.623 |
| … bus | 0.918 / 0.659 | 0.901 / 0.610 |
| … truck | 0.555 / 0.427 | 0.419 / 0.309 |
| COCO motorcycle images, motorcycle mAP50 / mAP50-95 | 0.749 / 0.479 | 0.678 / 0.402 |

There is real forgetting despite the replay sample (300 old images): −5.9 points mAP50 on
UA-DETRAC, mostly from truck, and −7.1 points on COCO motorcycles. Two things probably add to it:
the new model was trained at image size 1280 and is tested here at 640, and the Lahore convention
labels box pickups as truck. The SUMO pipeline uses the Lahore view, so the new model is the better
choice for Manzil. For a UA-DETRAC-style view, keep the old model.

## Line counting on the test segments (`counting/counts.csv`, `counting/events.csv`)

The counting line is horizontal and halfway down the labelled part of the frame. Counts use the
same `LineCounter` as before (`manzil/perception/counting.py`). The reference is the reviewed
labels (about 2 fps) linked into tracks with `GreedyLinker` (`manzil/perception/linking.py`).

| Segment | Length | Reference (labels) | New model, 2 fps linked | New model + ByteTrack, all frames | Old model, 2 fps linked | Old model + ByteTrack |
|---|---|---|---|---|---|---|
| video 1, segment 3 | 12.0 s | 28 | 33 (+5) | 35 (+7) | 11 (−17) | 20 (−8) |
| video 1, segment 4 | 23.0 s | 46 | 48 (+2) | 67 (+21) | 38 (−8) | 56 (+10) |
| video 2 | 12.5 s | 15 | 15 (0) | 16 (+1) | 14 (−1) | 16 (+1) |
| **Mean absolute error** | | | **2.3** | 9.7 | 8.7 | 6.3 |

How to read this table:

- The fair comparison is "2 fps linked". It runs the same linking and counting on model detections
  instead of labels, at the same frames. Here the new model is within 2–5 vehicles per segment,
  with a total of 96 against 89.
- ByteTrack on every frame over-counts, mostly motorcycles: 33 against 21 in segment 4. This comes
  from ID switches in dense, occluded two-wheeler traffic. The 2 fps reference can also miss a
  vehicle that crosses the line between two labelled frames, so the ByteTrack error is partly a
  limit of the reference.
- The old model's count errors also include the rickshaws and vans it cannot detect.

Sample frames with tracks and the counting line: `counting/sample_v1_*.jpg`. These are video 1
only, 960 px wide, and number plates and faces are not readable. Video 2 samples are not committed
because its plates are readable.

## What this means, and what to do next

- Adding rickshaw and van is feasible with very little data. Rickshaws reach mAP50 0.74 from
  134 training frames. On the Lahore view, the new model is also clearly better on the old four
  classes (mAP50 0.71 against 0.53).
- **Small-data caveat:** all of this comes from one road, one day, and about 2.3 minutes of
  footage. Val is 14 frames and test is 97 frames, and many frames show the same vehicles a
  second apart. The confidence intervals are wide, and video 2 shows weak generalisation to a new
  camera position, especially for vans.
- **Recommendation:** film more footage before the final report. Aim for 3–5 more locations, at
  different times of day, each 5–10 minutes from a fixed elevated position (a footbridge or
  rooftop). Keep whole videos for test. A team member should check the test labels, then raise
  them from "preliminary".
- Van needs clearer examples, and the definition of van versus car/pickup should be agreed with
  the team.

## Reproduce

```bash
python kaggle/lahore_train/build.py          # inline helpers into lahore_train.py
kaggle kernels push -p kaggle/lahore_train   # GPU kernel; reuses the stored weights if present
kaggle kernels output mibrahimsalman022/manzil-lahore-train -p OUT --file-pattern '^out/'
```

The label pipeline is: `kaggle/lahore_frames/` → `kaggle/lahore_prelabel/` →
`kaggle/lahore_bootstrap/` → `python -m manzil.perception.lahore_review prelabel|render|apply`.
