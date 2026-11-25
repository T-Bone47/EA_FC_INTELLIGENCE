# Phase 39: Research Source Verification & Adaptation Report

All Stage 8 research sources were verified via live web lookup for licensing compatibility, availability, and domain applicability to EA SPORTS FC 26/27 prior to implementation.

---

## 1. Pitch Control & Spatial Intelligence Sources

| Source | Verification Status | License | Decision & Adaptation for EA FC |
| :--- | :--- | :--- | :--- |
| **Friends of Tracking** (`Friends-of-Tracking-Data-FoTD`) & Spearman Physics Pitch Control | Verified available on GitHub (`LaurieOnTracking`) | MIT / Educational Open-Source | **Adapted cleanly**: Implemented Spearman-inspired time-to-intercept / anisotropic Gaussian influence oriented along velocity vectors in `spatial_intelligence.py`, labeled explicitly `HEURISTIC_GAUSSIAN_INFLUENCE` rather than claiming real broadcast match empirical probability calibration. |
| **Metrica Sports Sample Data** (`metrica-sports/sample-data`) | Verified available on GitHub | Open Research Sample | **Adopted format contract**: Normalized `[0..1] x [0..1]` player + ball frame schema modeled inside `real_match_trace_importer.py` (`IMPORTED_MATCH_TRACE`). |
| **SoccerAction** (`ML-KULeuven/socceraction`) | Verified available on GitHub | MIT License | **Conceptual alignment**: Separated ball actions/progression valuation (`Expected Threat`) without requiring raw SPADL match logs where CV produces spatial states rather than Opta event feeds. |
| **Expected Threat (`xT`)** (`karun.in/blog/expected-threat.html`) | Verified seminal Markov surface publication | Open Methodology | **Adopted 12×8 positional value matrix** in `expected_threat_at()` to quantify progressive pass/carry threat gains across EA FC pitch corridors. |

---

## 2. Computer Vision, Calibration & Multi-Object Tracking Sources

| Source | Verification Status | License | Decision & Adaptation for EA FC |
| :--- | :--- | :--- | :--- |
| **SoccerNet GSR** (`SoccerNet/sn-gamestate`) | Verified CVPR 2024 GSR repository | **GPL-3.0** | **Reference methodology ONLY (no code copied)** due to GPL-3.0 copyleft restrictions. Adapted GS-HOTA concepts, broadcast+minimap tracking separation, and coordinate provenance independently in MIT/Apache-safe code. |
| **SoccerNet Calibration** (`SoccerNet/sn-calibration`) | Verified camera calibration challenge suite | GPL / Academic Research | **Methodology adapted**: Implemented geometric line extraction (`HoughLinesP`), DLT SVD, RANSAC inliers, and explicit rejection (`GOOD`/`COARSE`/`REJECTED`) in `homography_dlt.py`. |
| **ByteTrack** (`FoundationVision/ByteTrack`) | Verified on GitHub | **MIT License** | **Adopted core algorithm**: Pure Python/NumPy + SciPy `linear_sum_assignment` two-stage association (`bytetrack_adapter.py`) with high/low confidence matching. |
| **BoT-SORT** (`NirAharon/BoT-SORT`) | Verified on GitHub | **MIT License** | **Adopted CMC component**: Implemented sparse Lucas-Kanade optical-flow background camera pan offset `(dx, dy)` in `homography_dlt.py` to stabilize virtual EA FC Tele Broadcast panning. |
| **TrackEval** (`JonathonLuiten/TrackEval`) | Verified on GitHub | **MIT License** | **Adopted standard metrics formulas**: Preserved HOTA/IDF1 separation and explicit ID-switch accountability. |

---

## 3. EA FC-Specific Vision & Simulation Sources

| Source | Verification Status | License | Decision & Adaptation for EA FC |
| :--- | :--- | :--- | :--- |
| **`maxtiandi`** (`Computer-Vision-System-for-Gameplay-Analysis-and-Tactical-Recommendations-in-Football-Simulator`) | Verified HSE Master's thesis repo on GitHub | Open Research Repo | **Adapted key EA FC simulator insights**: Jersey HSV clustering, referee/player visual filtering, and ball proximity possession assignment tailored to simulated stadium lighting and cast shadows. |
| **FUT HyperVision** (`futevolution.com/hypervision`, `omardoucoure.com/posts/how-hypervision-works`) | Verified architectural breakdown of 7-stage EA FC pipeline | Proprietary Architecture Article (Conceptual Reference Only) | **Architecture aligned cleanly**: Adopted the 7-stage logical breakdown (player/ball detection -> pitch registration -> camera motion compensation -> defensive & attacking choice diagnostics -> Stadium-style visual presentation) without copying proprietary weights or scraping content. |

---

## 4. Video Processing, Inference & Calibration Libraries

| Library / Reference | Installed Version | License | Verification & Licensing Posture |
| :--- | :--- | :--- | :--- |
| **PyAV (`av`)** | `19.0.2` (`cp312-abi3-win_amd64`) | BSD-3-Clause (FFmpeg libs LGPL/GPL bundled wheel) | Installed and benchmarked at **392.8 fps** decode speed across MP4/MOV/WebM. Note: binary distribution involving FFmpeg libraries requires preserving LGPL/GPL attribution notices in any external release. |
| **OpenCV Headless (`opencv-python-headless`)** | `5.1.0.95` | **Apache 2.0 License** | Installed; OpenCL RTX 3050 GPU path verified (`OPENCL_GPU`). Note OpenCV 5 returns 2D `(N, 4)` from `HoughLinesP`; handled defensively with `.reshape(-1, 4)`. |
| **SciPy (`scipy`)** | `1.18.1` (`cp315-win_amd64`) | BSD-3-Clause | Installed; `scipy.optimize.linear_sum_assignment` powers exact Hungarian track association. |
| **scikit-learn (`scikit-learn`)** | `1.9.1` (`cp315-win_amd64`) | BSD-3-Clause | Installed; `KMeans` powers jersey team separation (`multi_channel_perception.py`), supporting Stage 8 calibration docs (`sklearn.calibration`). |
| **ONNX Runtime (`onnxruntime` / `onnxruntime-directml`)** | Checked via PyPI `index versions` | MIT | **Unavailable as cp315 wheel on PyPI as of install check.** Handled cleanly via `cv2.dnn.readNetFromONNX` (OpenCL GPU/CPU) slot at `backend/models/fc_detector.onnx` without requiring failing packages. |
| **Google Research Football (`google-research/football`)** | Verified Apache 2.0 repo | Apache 2.0 | Referenced as future synthetic ground-truth benchmark option; clean local encoded test clips utilized immediately without external Linux Build deps. |
