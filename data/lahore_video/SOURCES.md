# Lahore video sources (W2)

The videos are **not** in git. They are stored in the private Kaggle dataset
`mibrahimsalman022/manzil-lahore-videos` (uploaded by Ibrahim on 15 Nov 2026).
Attach it to a Kaggle kernel with `"dataset_sources": ["mibrahimsalman022/manzil-lahore-videos"]`.

| File | Duration | Resolution, fps | sha256 | Location | Filmed | Source and permission |
|---|---|---|---|---|---|---|
| `manzil-lahore-video.mp4` | 125.6 s (3,765 frames) | 1280x720, 29.97 | `d6debb6a663b1f731ae3d81e74e2508c9d332ffe890e98c7e22f90517fa97d9c` | Ferozpur Road, Lahore (beside the elevated Metro Bus track) | date unknown, daytime | Given to the team by a friend of Ibrahim, who states that use in this project is allowed. Original filming details not recorded. |
| `manzil-lahore-video-2.mov` | 13.2 s (395 frames) | 3294x2058, 30.00 | `b7f4f90647f3c1fcc7580acae0533382cc6e6eb3ae3a4980891a8a08e78e08c9` | Lahore (given as Ferozpur Road; tree-lined road seen from an overpass) | date unknown, daytime, hazy | Same as above. |

Checksums and properties measured on 16 Nov 2026 with OpenCV on the downloaded files.

## Notes from a first look (16 Nov 2026)

- Video 1: steady high camera, very dense mixed traffic (many rickshaws, motorcycles, cars, vans,
  buses, loaders). It is edited: about 4-5 shots with different framings (one change near 64 s,
  a shot through a railing from about 100 s). Shot boundaries must be detected before splitting.
- Video 2: one continuous steady shot, light traffic (mostly cars, a few motorcycles and rickshaws).
- Faces and number plates are too far away to read at normal size; still check any frame before
  it goes into the repo or report.

## Use conditions

- Research use in this FYP only. Do not publish the videos or upload them to a public dataset.
- Frames in the repo or report: only small samples, blurred where a plate or face is readable.
- Results from these videos are reported as from "team-provided footage, one location".

## W2 additions (16 Nov 2026, cloud session)

- **Location of video 1:** its first ~6.5 s carry a burned-in caption "ICHHRA, FEROZEPUR ROAD, LAHORE",
  so the place is Ichhra on Ferozepur Road (beside the Metro Bus track). Frames under the caption
  are not used for labels (`unused` in the manifest).
- **Video 1 is edited:** one hard cut at 101.6 s (found automatically) and camera moves (zoom near
  15.5 s, tilt up 60-64 s, tilt down 84-87 s). Segments, frame counts and cut scores:
  `results/fyp2/vision_lahore/shots.json`, `cut_scores.csv`.
- **Frames:** 273 frames at ~2 fps (video 2 downscaled to 1920x1200) are the output of the private
  Kaggle kernel `mibrahimsalman022/manzil-lahore-frames` (sha256 per frame in
  `results/fyp2/vision_lahore/frames.csv`). The videos never left Kaggle.
- **Split manifest:** `data/lahore_video/split_manifest.csv` (split by segment, never by frame;
  2 s guard band at split boundaries; title-caption frames unused).
- **Labels:** private Kaggle dataset `mibrahimsalman022/manzil-lahore-labels`
  (labels sha256 in `results/fyp2/vision_lahore/README.md`).
- **Privacy:** number plates in video 2 are readable at full resolution when zoomed. Do not put
  video 2 frames into the repo or report unless plates are blurred. Video 1 frames are only used
  downscaled (plates and faces not readable).
