# Vision track V.1–V.3: YOLO fine-tuning results (real, Kaggle GPU, 11–12 Nov 2026)

Everything here is a real result, pulled back from Kaggle with `kaggle kernels output`.

## Dataset (V.1 + V.2): kernel `mibrahimsalman022/manzil-yolo-data`

Built by `kaggle/yolo_data/prepare_yolo_data.py` from two attached Kaggle datasets:
`bratjay/ua-detrac-orig` and `awsaf49/coco-2017-dataset`. The images stay on Kaggle; the
kernel output (`manzil_yolo/`) is attached to the training kernel through `kernel_sources`.
Label checksum (sha256 over all label files): `dataset_stats.json` → `labels_sha256`.

Classes: `0 car, 1 bus, 2 truck, 3 motorcycle`.
UA-DETRAC mapping (confirmed against the data, whose only types are car / van / bus / others):
car→car, van→car, bus→bus, others→truck. COCO: car, bus, truck, motorcycle as they are.

| Split | UA-DETRAC | COCO (images with a motorcycle) |
|---|---|---|
| train | 7,365 frames, 54 sequences | 3,202 images (train2017) |
| val | 867 frames, 6 whole sequences | 300 images (train2017, held out) |
| test | 5,625 frames, official 40 test sequences | — |
| test_motorcycle | — | 159 images (COCO val2017) |

- Every 10th frame (2.5 fps) to drop near-duplicates; val is split by whole sequence, so frames of a sequence never appear in both train and val.
- DETRAC ignored regions (unlabelled vehicles) are filled grey, and boxes centred in them are dropped.
- Class imbalance: DETRAC "others" (→ truck) is rare, with 274 boxes in train against 48,463 cars.

## Training (V.3): kernel `mibrahimsalman022/manzil-yolo-train`

`kaggle/yolo_train/train_yolo.py`: YOLO11s (COCO-pretrained) fine-tuned with Ultralytics 8.4.210, PyTorch 2.11 + CUDA, on 2× Tesla T4 (DDP). Settings: 50 epochs, image size 640, batch 32, seed 0, patience 15. It took 6,371 s (1.8 h); the best epoch on val was **40** (val mAP50-95 0.590). Training curve: `results.png`, `results.csv`.

Weights: `models/yolo/manzil_yolo11s_best.pt` (19.2 MB), sha256 `0022c8a0394bf8a583ef0d21e324853a73251ca86a3ac6caab656fd65ae8dc2f`.

## Test results (held-out, never used for training or model selection)

Baseline = the same COCO-pretrained yolo11s.pt **without** fine-tuning, restricted to the four classes and scored on the same labels.

**UA-DETRAC test split (5,625 frames, 63,377 boxes):**

| Model | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| Pretrained (no fine-tuning) | 0.748 | 0.769 | 0.752 | 0.530 |
| **Fine-tuned** | **0.889** | 0.729 | **0.799** | **0.586** |

| Class (fine-tuned vs pretrained) | mAP50 | mAP50-95 | Recall |
|---|---|---|---|
| car | 0.924 vs 0.875 | 0.671 vs 0.605 | 0.861 vs 0.807 |
| bus | 0.918 vs 0.859 | 0.659 vs 0.593 | 0.863 vs 0.843 |
| truck | 0.555 vs 0.522 | 0.427 vs 0.391 | **0.463 vs 0.655** |

**COCO val2017 motorcycle images (159 images, 367 motorcycles):**

| Class | mAP50 | mAP50-95 | Precision | Recall |
|---|---|---|---|---|
| motorcycle, fine-tuned | 0.749 | 0.479 | 0.682 | 0.708 |
| motorcycle, pretrained | 0.761 | 0.509 | 0.826 | 0.658 |

Inference speed on a T4: about 6.8 ms per 640-px image (plus ~1.4 ms pre- and post-processing).

## What this means

- Fine-tuning helps on the target camera domain: +4.7 points mAP50 and +5.6 points mAP50-95 on UA-DETRAC test, with large precision gains for car and bus.
- **Truck is the weak class.** "others" has only 274 training boxes. Recall fell from 0.655 to 0.463, although mAP still rose slightly. More truck data or class weighting is the next fix.
- **Motorcycles were kept, but not improved:** mAP50 0.749 vs 0.761 for the pretrained model (−1.2 points, mAP50-95 −3.0). The COCO mix prevented forgetting (UA-DETRAC alone has no motorcycles), but it is still a small drop. On these COCO images, car/bus/truck scores also fell, because the model has shifted towards the fixed-camera DETRAC view. That is expected and is not the target domain.
- Caveats: DETRAC "others" is not exactly COCO "truck", and the baseline may call some DETRAC vans "truck", which slightly disadvantages the baseline on truck. There was one training seed, and Lahore footage has not been tested yet (V.6).

Plots: `finetuned_test_BoxPR_curve.png`, `finetuned_test_confusion_matrix_normalized.png`, `baseline_test_*`, `finetuned_test_motorcycle_*`; sample predictions are in `*_val_batch0_pred.jpg`. Full numbers: `metrics.json`.
