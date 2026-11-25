# PHASE 41: Benchmark Report (220 Curated Tactical Decision Scenarios + Phase 40 Regression)

**Script:** `verification/run_phase41_benchmarks.py`  
**Metrics Artifact:** `artifacts/phase41/PHASE_41_BENCHMARK_METRICS.json`

## 1. Phase 41 Benchmark Results (220 Scenarios)

| Metric | Measured Result | Gate Requirement | Status |
| :--- | :---: | :---: | :---: |
| **Total Decision Scenarios** | `220` | `>= 200` | **PASS** |
| **Schema Validity Rate** | `100.0%` | `>= 95.0%` | **PASS** |
| **Evidence Reference Resolution** | `100.0%` | `>= 95.0%` | **PASS** |
| **Zero Hindsight Leakage Rate** | `100.0%` | `100.0%` | **PASS** |
| **Abstention Compliance Rate** | `100.0%` | Strict on `REJECTED` | **PASS** |
| **Coach Tool Routing Accuracy** | `100.0%` | `>= 90.0%` | **PASS** |
| **Evaluation Latency (Mean / p50 / p95 / Max)** | `4.711 ms` / `5.102 ms` / `7.065 ms` / `51.509 ms` | Low real-time latency | **PASS** |
| **Peak Traced Allocation Footprint** | `1.971 MB` | Fits 16 GB RAM budget | **PASS** |

## 2. Phase 40 Coaching Benchmark Non-Regression Check (`verification/run_phase40_benchmarks.py`)
Executed immediately after Phase 41 coach integration (`110` cases):
- Schema validity: `100.0%`
- Bounded tool selection accuracy: `100.0%`
- Evidence reference resolution: `100.0%`
- Unsupported evidence / synthetic abstention: `100.0%`
- Prompt injection block rate: `100.0%`
- Latency: `p50 = 1.78 ms`, `p95 = 366.88 ms` (`max = 429.09 ms`)
