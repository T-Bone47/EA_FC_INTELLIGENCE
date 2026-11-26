# Phase 43 Computer Vision Training, Evaluation & Calibration Report

## 1. Local Hardware & Runtime Inventory (Verified Observed)
From `C:\Python315\python.exe -m backend.cv_training.benchmark_cv`:
- `opencv`: `5.1.0` (`onnx_inference_ready_via_opencv_dnn = true`)
- `pyav`: `19.0.2`
- `scipy`: `1.18.1`
- `scikit_learn`: `1.9.1`
- `opencl_available`: `true` (`NVIDIA GeForce RTX 3050 Laptop GPU`)
- `torch` / `torchvision` / `onnxruntime` / `ultralytics`: `null` (`training_ready_for_pytorch_gradient_descent = false`)
- **ONNX Weights Status:** `NO_TRAINED_WEIGHTS_PRESENT` (`weights_present = []`). The runtime explicitly reports fallback to `CV_CLASSICAL_HSV_CONTOUR` + ByteTrack tracking — zero trained neural weights are fabricated or claimed.

## 2. Dual-Stream Separation (`BROADCAST` vs `MINIMAP_ROI`) & Training Protocol
Implemented in `backend/cv_training/config_generator.py` (`TrainingRecipeSpec`) and `backend/cv_training/dataset_tools.py` (`get_cv_pipeline_status`):
- **`broadcast` stream:** `[640, 640]` (players) / `[960, 960]` (ball), target `backend/models/fc_detector.onnx`, Apache-2.0 YOLOX recipe (`batch_size=4`, `grad_accumulation_steps=4`, `fp16=True`).
- **`minimap_roi` stream:** `[320, 320]`, target `backend/models/fc_minimap_detector.onnx`, dedicated radar-crop evaluation resolving broadcast off-screen compactness blindness.
- **Early Stopping & Resume Controls:** `early_stopping_patience_epochs = 8`, `early_stopping_min_delta = 0.003`, `resume_checkpoint_path` parameter, and strict AGPL-3.0 opt-in guard for Ultralytics (`accept_agpl_copyleft=True`).
- **Anti-Leakage Split:** Enforces match-level/video-level disjoint splits (`manifest_valid = true`, `leakage_free_verified = true`).

## 3. Strictly Separated Evaluation Results (Observed Run)
### A. Synthetic Calibrated Geometry Proxy (`SYNTHETIC_CALIBRATED_GEOMETRY_PROXY`)
- `evaluation_scope`: `SYNTHETIC_CALIBRATED_GEOMETRY_PROXY` (`12` frames, `32.48 FPS`):
  - `mAP@50`: `0.7712` (`player_ap50 = 0.8758`, `ball_ap50 = 0.6667`)
  - `macro_precision`: `0.8287`, `macro_recall`: `0.775`
  - `MOTA`: `0.875`, `IDF1`: `0.9339`, `HOTA`: `0.936`, `id_switches = 0`
  - `pitch_localization_rmse_m`: `0.331 m`, `median`: `0.336 m`
  - **Confidence Calibration (`FC_TACTICAL_EXPERIMENT_BENCH_V1` Category G):** `ECE = 0.0643`, `Brier = 0.0042` (labeled strictly synthetic proxy).

### B. Real Uploaded Gameplay Clips
- `total_files`: `29` scanned in workspace storage
- `processed_ok`: `2` valid gameplay videos (`c2eb123f-..._78e44f.mp4` at `79.5%` coverage / `6.47 FPS`, `eda57480-..._f9868b.mp4` at `80.3%` coverage / `14.57 FPS`, both `12/12` calibrated frames via `CV_CLASSICAL_HSV_CONTOUR`)
- `corrupt_stub_count`: `27` corrupt/test stub clips reported accurately without inflation.
