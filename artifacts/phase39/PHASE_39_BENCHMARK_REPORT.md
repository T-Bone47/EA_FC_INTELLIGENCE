# Phase 39: Empirical Benchmark Report

All timing measurements below were executed directly on the target workstation running Windows 11, Python 3.15.1, PyAV 19.0.2, OpenCV 5.1.0, SciPy 1.18.1, scikit-learn 1.9.1, and NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB VRAM).

---

## 1. Hardware & Acceleration Verification (`GET /api/research/system-capabilities`)

- **GPU Device Detected:** `NVIDIA GeForce RTX 3050 Laptop GPU` (4096 MiB VRAM total)
- **Active OpenCV Compute Backend:** `OPENCL_GPU` (live `cv2.UMat` kernel smoke test verified)
- **CPU Fallback:** Clean `CPU_SIMD` / `CPU_NUMPY_FALLBACK` paths verified when OpenCL is disabled
- **Video Decoder:** `PyAV 19.0.2` (FFmpeg shared libraries in wheel)

---

## 2. Measured Pipeline Throughput (720p Compressed Bitstream)

Input clip: `1280×720` `mpeg4` `.mp4` (`60 frames @ 20 fps`, `HIGH_ACCURACY` 10 Hz sampling -> `30 sampled active gameplay frames`).

| Benchmark Metric | Baseline Before Optimization | Post-Optimization Measured | Notes |
| :--- | :--- | :--- | :--- |
| **Pure Video Frame Decode (`iter_adaptive_frames`)** | 369.91 fps (`0.0811s` for 30 frames) | **392.8 fps** (`0.0764s`) | PyAV `thread_type=AUTO` streaming decode |
| **Full E2E Pipeline (`process_video_file`)** | 3.55 fps (`8.4568s`) | **12.02 fps (`2.4968s` total)** | Scene classification, LK optical flow CMC, Hough/RANSAC DLT, HSV+KMeans CV, SciPy Hungarian ByteTrack, 10 Hz fusion |
| **DLT Pitch Calibration Success Rate** | 30/30 frames | **30/30 frames (`GOOD`)** | Early RANSAC convergence on clean pitch lines |
| **Spatial Intelligence (`analyze_timeline`)** | 0.074 ms / frame | **0.062 ms / frame** | Vectorized 21×14 Gaussian influence + xT + overloads + lanes |
| **Tactical Coaching (`TacticalCoachingEngine`)** | 0.029 ms total | **0.020 ms total** | All 12 diagnostic scanners |

> **Result:** Post-optimization end-to-end 720p real video vision processes at **12.02 fps**, exceeding the 10 Hz `HIGH_ACCURACY` sampling target in real time on local laptop hardware with ₹0 external cost.

---

## 3. WebM & MOV Container Probe Timing

- `640×360` VP8 WebM (`matroska,webm`, `24 frames @ 12 fps`): `probe_video_container` verified duration `2.0s`, dimensions `640×360`, codec `vp8` cleanly via `PyAV/19.0.2`.
- `640×360` MPEG-4 QuickTime `.mov`: probed and decoded cleanly.
