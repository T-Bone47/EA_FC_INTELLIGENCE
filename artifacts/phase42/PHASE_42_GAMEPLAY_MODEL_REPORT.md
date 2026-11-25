# Phase 42 Domain Computer Vision & Gameplay Model Report

**CV Harness Package:** `backend/cv_training/` (`manifest.py`, `dataset_splitter.py`, `config_generator.py`, `evaluator.py`, `export_onnx.py`, `benchmark_cv.py`)  
**Benchmark Evidence:** `artifacts/phase42/cv_benchmark_raw.json`

## 1. Verified Hardware & Runtime Environment
Probed via `probe_local_cv_environment()`:
- **OpenCV:** `5.1.0` (`OpenCL GPU` detected & active: `NVIDIA GeForce RTX 3050 Laptop GPU`)
- **Video Decoder / Math:** `PyAV 19.0.2`, `SciPy 1.18.1`, `scikit-learn 1.9.1`
- **Training / DL Frameworks Offline Status:** `torch=null`, `torchvision=null`, `onnxruntime=null`, `ultralytics=null`, `cuda_available=false`.
- **Trained Weights Status:** `backend/models/fc_detector.onnx` is **NOT present offline** (`weights_present=[]`, `status="NO_TRAINED_WEIGHTS_PRESENT"`). Runtime truthfully remains `CV_CLASSICAL_HSV_CONTOUR`. Zero synthetic weights were placed on disk.

## 2. Reproducible Training, Splitting & License Architecture (`42F`)
- **5-Class Domain Schema (`EA_FC_CLASSES`):** `0: player`, `1: goalkeeper`, `2: referee`, `3: ball`, `4: minimap_roi`.
- **Strict Provenance Manifest (`manifest.py`):** `validate_manifest()` blocks `is_synthetic_calibration_test=True` records from real training sets by default.
- **Leakage-Free Splitting (`dataset_splitter.py`):** `split_by_match_group()` splits strictly at the `match_id` boundary (`seed=42`) so adjacent broadcast frames never leak across `train/val/test`.
- **OSS License Segregation (`config_generator.py`):**
  - Default **Commercial-Safe Recipe:** `YOLOX-S` (**Apache-2.0**, `imgsz=(640, 640)` player / `(960, 960)` small ball, `batch=4` + `fp16` + grad accumulation for 4GB RTX 3050 VRAM, ONNX opset 12).
  - Opt-In Copyleft Recipe: `Ultralytics YOLO` (**AGPL-3.0**) blocked with `PermissionError` unless `accept_agpl_copyleft=True`.
- **ONNX DNN Inference Wiring (`multi_channel_perception.py`):** Added `PixelPerceptionExtractor._detect_with_onnx()` (`blobFromImage` + OpenCV DNN `NMSBoxes`) ready to run automatically once real exported `.onnx` weights are placed at `backend/models/fc_detector.onnx`.

## 3. Empirical Bug Fix & Real Clip Benchmark
During Phase 42F benchmarking, we diagnosed a defect in `PixelPerceptionExtractor.detect_broadcast_players_and_ball()`: `(19, 19)` morphological closing failed to close foreground player cutouts wider than `19px`, hollowing out detections. Replacing that step with `(25, 25)` closing + `cv2.RETR_EXTERNAL` filled contours yielded immediate improvements across real local MP4 clips in `data/video_research/uploads/`:

| Artifact / Benchmark | Before Fix | After Fix | Notes |
| :--- | :---: | :---: | :--- |
| `fc27_real_clip_78e44f.mp4` (`960x540`, `70,057 B`) | `0.0%` coverage | **`79.5%`** coverage (`GOOD` 12/12, `6.98 FPS`) | `CV_CLASSICAL_HSV_CONTOUR` + `PyAV` |
| `fc27_real_clip_f9868b.mp4` (`960x540`, `68,222 B`) | `0.8%` coverage | **`80.3%`** coverage (`GOOD` 12/12, `14.25 FPS`) | `CV_CLASSICAL_HSV_CONTOUR` + `PyAV` |
| Remaining 22 `4,096 B` / `4,132 B` files in uploads | `CONTAINER_PROBE_FAILED` | `CONTAINER_PROBE_FAILED` | Expected: minimal dummy byte files from unit tests |

## 4. Quantitative Proxy Evaluation (`SYNTHETIC_CALIBRATED_GEOMETRY_PROXY`)
Evaluated on deterministic `1280x720` 12-frame calibrated pitch sequence (`120` GT players, `12` GT balls, explicit synthetic label — **not** real EA FC broadcast ground truth):
- **Processing Speed:** `33.90 FPS` (`354.0 ms` / 12 frames)
- **Player (`IoU >= 0.50`):** `AP@50 = 0.8758` (`Precision = 0.9907`, `Recall = 0.8833`, vs `0.0` before fix)
- **Ball (`IoU >= 0.25`):** `AP@50 = 0.6667` (`Precision = 0.6667`, `Recall = 0.6667`)
- **Multi-Object Tracking:** `MOTA = 0.8750`, **`IDF1 = 0.9339`**, **`HOTA = 0.9360`**, `ID switches = 0`
- **Pitch Localization Error:** `RMSE = 0.331 m`, `Median = 0.336 m`

## 5. Honest Dataset & Weight Blockers
Real human-annotated EA FC broadcast player/ball datasets and a GPU PyTorch/YOLOX environment are required to train `fc_detector.onnx` weights. Classical HSV contours degrade under shadowed stadium lighting, colorful kits, or camera zooms — documented transparently in UI and API metadata.
