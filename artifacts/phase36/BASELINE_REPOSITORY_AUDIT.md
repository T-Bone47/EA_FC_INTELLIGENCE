# Phase 36 Baseline Repository Audit
**Project:** EA FC Intelligence — Stadium 3.0  
**Phase:** 36 — Video Gameplay Intelligence & Empirical Validation  
**Date:** November 24, 2026  
**Auditor:** Principal AI/ML Research Scientist & Architecture Team  

---

## 1. Executive Summary

Phase 35 concluded with a certified, zero-regression mathematical engine and Stadium 3.0 UI:
- **Frozen Baseline:** V3.2.1 deterministic core intact, bit-exact reproduction across `v3_1_golden_fixtures.json` and `v3_2_golden_fixtures.json`.
- **Backend Certification:** 109 passed, 4 skipped across 10 certified modules in 4.80s.
- **Frontend Certification:** 92 passed, 3 skipped in 6.83s; clean production build in 1.45s.
- **Hardware Profile:** Local Windows dev machine with NVIDIA RTX 3050 (4 GB VRAM), 16 GB RAM, Intel Core i5.
- **External Financial Budget:** ₹0.00 consumed.

However, the baseline audit reveals an inescapable epistemic reality:
> **`fc27_staging` contains exactly ZERO (0) accepted live match gameplay records.**

All current recommendations, whole-XI synergy scores, tactical friction penalties, and partnership dynamics remain formally classified as `MODELED_HEURISTIC`. Phase 36 must bridge this gap by establishing a video gameplay research infrastructure connecting observable gameplay events to model hypotheses without corrupting the frozen deterministic core.

---

## 2. Inventory of Inherited Subsystems

| Module / System | File Path | Phase 35 Status | Role in Phase 36 |
|---|---|---|---|
| **V3.2.1 Recommendation Core** | `backend/services/card_squad_lab.py` | FROZEN (Production) | Benchmark target for prediction challenges |
| **Tactical Synergy Engine** | `backend/services/squad_synergy.py` | FROZEN (Production) | Supplies Whole-XI alignment formula ($I_{\text{align}}$) & friction rules |
| **Partnership Intelligence V2** | `backend/services/partnership_intelligence.py` | FROZEN (Production) | Target hypotheses for 5 tactical pairings |
| **Stability Lab Engine** | `backend/services/recommendation_stability.py` | FROZEN (Production) | Context sensitivity baseline across 14 perturbations |
| **Empirical Observation Schema** | `backend/domain/empirical_observation.py` | EXTENSIBLE | Extended for video gameplay metadata & event taxonomy |
| **Empirical Evaluator** | `backend/services/empirical_evaluator.py` | EXTENSIBLE | Statistical testing ($t$-test & Wilcoxon) for video observations |
| **Stadium 3.0 UI** | `frontend/src/pages/CardSquadLab.tsx` | PRODUCTION | Host platform for new Gameplay Intelligence Studio |
| **Performance Evidence Lab** | `frontend/src/pages/PerformanceEvidenceLab.tsx` | PRODUCTION | Displays Staging Evidence Status and Quality Checklist |

---

## 3. The Core Epistemic Limitation

While Phase 34B and Phase 35 provided rigorous mathematical reconstruction (e.g., LCB dispersion term $0.5\sigma_r$, double-precision unrounded delta policy $\Delta I$), the underlying attribute-based weights have never been validated against direct video-gameplay observations. 

For instance:
- `RULE-HP-FWD-DEF`: Forward defending $< 40.0$ triggers a $-0.025$ friction deduction. Heuristically, this penalizes Kylian Mbappé ($29$ defending) in High Press. 
- *The Unanswered Question:* Does Mbappé's in-game virtual avatar actually win fewer turnovers per 90 in a high press, or does his $97$ pace and acceleration close down passing lanes faster than Dembélé's $55$ defending?
- *The Solution:* Direct video event capture of pressing attempts, pressure sequences, and turnovers.

---

## 4. Legal, Architectural, and Resource Boundary Constraints

1. **YouTube Terms of Service Compliance:**
   - Under no circumstances will unauthorized automated scraping, downloading, or frame extraction of YouTube streams take place.
   - Public videos are ingested via **Path A (YouTube Reference Mode)**: authorized iframe embeds, timestamp metadata, human-reviewed annotations, and observer notes.
   - Computer vision and frame-level tracking are strictly limited to **Path B (Authorized Video Analysis)** and **Path C (Controlled Gameplay Recordings)**.
2. **GPU & Memory Constraints (4 GB VRAM Budget):**
   - The local NVIDIA RTX 3050 has 4 GB VRAM. Large transformer-based video models (e.g. Video-LLaVA or heavy ViT backbones) would cause Out-Of-Memory (OOM) fatal crashes.
   - The CV architecture must rely on lightweight, edge-optimized modules: OpenCV background subtraction, MobileNet/YOLOv8-Nano/ONNX models, ByteTrack/Kalman filtering, and pitch homography via planar landmark correspondence.
   - An asynchronous CPU fallback must ensure the system operates gracefully even without GPU acceleration.
3. **Data Integrity Invariant:**
   - Zero synthetic video tracks will be falsely tagged as "real gameplay". Unpopulated or unreviewed data will be transparently labeled as `DRAFT` or `UNREVIEWED`.
