# PHASE 40: Performance & Evaluation Benchmark Report

**Runner:** `verification/run_phase40_benchmarks.py`  
**Artifact:** `artifacts/phase40/PHASE_40_BENCHMARK_METRICS.json`  
**Environment:** Windows 11 · Intel Core i5 12th Gen · 16 GB RAM · NVIDIA RTX 3050 (4 GB VRAM)

## 1. Curated Coaching & Agent Security Benchmark (`N = 110`)

| Metric | Target Gate | Measured Result | Gate Status |
| :--- | :--- | :--- | :--- |
| Schema-Valid Structured Responses | `>= 95%` | **100.0%** (`110 / 110`) | **PASS** |
| Bounded Tool Selection Accuracy | `>= 90%` | **100.0%** (`110 / 110`) | **PASS** |
| Evidence-Reference Resolution (`deep_link`) | `>= 95%` | **100.0%** (`70 / 70` grounded cases) | **PASS** |
| Unsupported / Synthetic Abstention Rate | `100%` target | **100.0%** (`10 / 10` cold-start/synthetic cases) | **PASS** |
| Prompt Injection & Auth-Bypass Block Rate | `100%` target | **100.0%** (`10 / 10` adversarial probes) | **PASS** |

## 2. Latency Distribution (Local Deterministic Core, External API Cost = ₹0)
- **Mean:** `105.12 ms`
- **Median (p50):** `0.93 ms`
- **p95:** `236.29 ms`
- **Max:** `277.19 ms`

Because previously analyzed match telemetry and Gamer DNA aggregates are cached incrementally rather than re-running OpenCV/PyAV computer vision during coaching chat turns, typical Q&A turnaround stays well below `280 ms` on local 16 GB RAM hardware with `0` paid LLM tokens consumed.
