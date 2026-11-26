# Phase 43I Computer Vision Dataset Pipeline, Calibration & Benchmark Report

## 1. Local Hardware & Runtime Stack Verification
Measured via `python -m backend.cv_training.benchmark_cv`:
- **Installed Libraries:** `OpenCV 5.1.0`, `PyAV 19.0.2`, `SciPy 1.18.1`, `scikit-learn 1.9.1`.
- **Hardware Acceleration:** OpenCL available on `NVIDIA GeForce RTX 3050 Laptop GPU`; PyTorch CUDA (`torch`, `torchvision`, `onnxruntime`, `ultralytics`) is **not** installed locally (`training_ready_for_pytorch_gradient_descent: false`), whereas OpenCV DNN inference is ready (`onnx_inference_ready_via_opencv_dnn: true`).
- **ONNX Weights Status:** `backend/models/fc_detector.onnx` is absent (`weights_present: false`, `status: "NO_TRAINED_WEIGHTS_PRESENT"`). Active runtime operates honestly via `CV_CLASSICAL_HSV_CONTOUR`.
- **Commercial License Separation:** Default training pipeline specifies Apache-2.0 `YOLOX_APACHE2` (`input_size_player=[640, 640]`, `input_size_small_ball=[960, 960]`, `batch_size_4gb_vram=4`); Ultralytics `AGPL-3.0` stays segregated behind explicit opt-in.

## 2. Phase 43 Dataset Export, Calibration & Registry (`backend/cv_training/dataset_tools.py`)
- **YOLO / CVAT Dataset Export (`export_manifest_to_yolo_dataset`):**
  - Validates frames against `EA_FC_CLASSES` (`validate_manifest(manifest, allow_synthetic=False)`), splits strictly by match group via `split_by_match_group` (`leakage_free_verified: true`), writes `images/{train,val,test}`, `labels/{train,val,test}/*.txt`, `data.yaml`, and `cvat_labels.json`.
  - `parse_yolo_label_lines` ingests normalized bounding boxes (`class_id cx cy w h [track_id]`) cleanly back into typed `BoundingBoxLabel` records.
- **Expected Calibration Error (ECE) & Brier Score (`compute_detector_ece_and_brier`):**
  - Evaluates IoU-matched confidence calibration across 10 uniform bins (IoU thresholds: `0.50` players, `0.25` ball), always annotating explicit `evaluation_scope`.
  - Unit test verified (`test_phase43i_cv_yolo_exporter_and_ece_calibration`) on `LABELED_VALIDATION_SET` prediction confidence `0.85` -> `ECE = 0.15`, `Brier = 0.0225`.
- **Fail-Closed Checkpoint Registry (`register_cv_checkpoint_record`):**
  - Persists benchmark telemetry into `public.phase42_cv_checkpoint`, explicitly raising `FileNotFoundError` if supplied a non-existent `onnx_path` so fabricated ONNX weights can never be registered.

## 3. Verified Live Benchmark Measurements
### Real Uploaded Video Clips (`real_uploaded_clips`, 2 valid + 26 corrupt stubs)
1. `c2eb123f-..._fc27_real_clip_78e44f.mp4` (`70,057` bytes, `960x540`, `12/12` active frames): **`79.5%` tracking coverage**, `GOOD`, `CV_CLASSICAL_HSV_CONTOUR`, `908.46 ms` (`13.21 fps`).
2. `eda57480-..._fc27_real_clip_f9868b.mp4` (`68,222` bytes, `960x540`, `12/12` active frames): **`80.3%` tracking coverage**, `GOOD`, `CV_CLASSICAL_HSV_CONTOUR`, `523.14 ms` (`22.94 fps`).

### `SYNTHETIC_CALIBRATED_GEOMETRY_PROXY` (`12` frames, `50.6 fps`, `237.18 ms`)
- `map50 = 0.7712` (`player AP50 = 0.8758`, `ball AP50 = 0.6667`, `ball_recall = 0.6667`), `macro_precision = 0.8287`, `macro_recall = 0.775`.
- Multi-object tracking: `MOTA = 0.875`, `IDF1 = 0.9339`, `HOTA = 0.936`, `id_switches = 0`, `pitch_localization_rmse_m = 0.331`.
- Calibration probe (`benchmark_phase43_tactical_lab.py` & `/api/phase43/cv/benchmark-calibration`): `ECE = 0.0817`, `Brier = 0.0178`.
- **Disclosure:** Proxy metrics reflect calibrated synthetic geometry only; genuine broadcast validation requires human-annotated real match frames.
