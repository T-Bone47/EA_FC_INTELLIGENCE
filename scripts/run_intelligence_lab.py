#!/usr/bin/env python
"""Run the Intelligence Evaluation Lab against real data (Phase 23).

Datasets:
  FC26  data_status=CANONICAL      + frozen fc26-players-2026-09-r1
  FC27  data_status=RESEARCH_ONLY  + research fc27-players-2026-09-r1
        (research use only; results are labelled RESEARCH_ONLY)

Variants: V3.1 baseline (historical config, pinned), V3.2-default (production since
Phase 24) and the Phase-23 candidates defined in backend/services/intelligence_lab.py.
Each run writes <out-dir>/<variant>__<GV>.json (default artifacts/phase24/lab); the baseline files are never
overwritten by a candidate. A summary with the adoption decision rule is
written to artifacts/phase23/lab/summary.json.

Usage:
    python scripts/run_intelligence_lab.py [--datasets FC26,FC27] [--positions CM,CB]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.data_access.candidate_repository import CandidateRepository
from backend.services import intelligence_lab as L
from backend.services.reference_distribution import load_reference_for

# Phase 24: default is the phase24 lab dir. The Phase 23 lab outputs are a recorded baseline and
# are only ever rewritten by passing --out-dir artifacts/phase23/lab explicitly.
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "phase24" / "lab"


def load(gv: str):
    research = gv == "FC27"
    ref = load_reference_for(gv, allow_research_only=research)
    cands = CandidateRepository().load_candidates(gv, include_research_only=research)
    return ref, cands, ("RESEARCH_ONLY" if research else "CANONICAL")


def summarise(base: dict, cand: dict) -> dict:
    """Decision rule (fixed before running): a candidate is ADOPTABLE only if
    every invariant has zero violations at every position, missing-data
    violations do not increase, mean tactical discrimination does not
    regress (lower overlap is better) and the near-tie rate does not rise.
    Otherwise REJECTED, with the failing reasons."""
    reasons = []
    disc_delta = []
    for pos, e in cand["positions"].items():
        inv = e["invariants"]
        for k in ("monotonicity", "pareto", "irrelevance"):
            if inv[k]["violations"]:
                reasons.append(f"{pos}: {k} violations={inv[k]['violations']}")
        b_inv = base["positions"][pos]["invariants"]
        if inv["missing_data"]["violations_any_value"] > b_inv["missing_data"]["violations_any_value"]:
            reasons.append(f"{pos}: missing-data violations increased")
        b = base["positions"][pos]["discrimination"]
        c = e["discrimination"]
        disc_delta.append(c["mean_pairwise_top10_overlap"] - b["mean_pairwise_top10_overlap"])
        if (c["near_tie_rate_top10"] or 0) > (b["near_tie_rate_top10"] or 0) + 1e-9:
            reasons.append(f"{pos}: near-tie rate rose {b['near_tie_rate_top10']} -> "
                           f"{c['near_tie_rate_top10']}")
    mean_delta = round(sum(disc_delta) / len(disc_delta), 3) if disc_delta else 0.0
    if mean_delta > 0:
        reasons.append(f"tactical discrimination regressed (mean overlap +{mean_delta})")
    return {"variant": cand["variant"], "game_version": cand["game_version"],
            "mean_overlap_delta_vs_baseline": mean_delta,
            "decision": "ADOPTABLE" if not reasons else "REJECTED", "reasons": reasons}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="FC26,FC27")
    ap.add_argument("--positions", default=",".join(L.POSITIONS))
    ap.add_argument("--out-dir", default=None, help="output directory (default artifacts/phase24/lab)")
    args = ap.parse_args()
    global OUT
    if args.out_dir:
        OUT = Path(args.out_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    positions = tuple(p.strip().upper() for p in args.positions.split(","))
    variants = [L.BASELINE, L.V3_2_DEFAULT, L.complementarity_variant(0.05),
                L.missing_charge_variant("zero"), L.missing_charge_variant("p01")]
    summary = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "lab_version": L.LAB_VERSION, "datasets": {}, "decisions": []}
    for gv in [d.strip().upper() for d in args.datasets.split(",")]:
        ref, cands, status = load(gv)
        summary["datasets"][gv] = {"candidates": len(cands), "data_status": status,
                                   "reference": ref.version, "content_hash": ref.content_hash}
        results = {}
        for v in variants:
            t = time.monotonic()
            rep = L.run_variant(v, cands, gv, ref, positions)
            rep.update({"data_status": status, "candidates": len(cands),
                        "seconds": round(time.monotonic() - t, 1)})
            results[v.name] = rep
            (OUT / f"{v.name}__{gv}.json").write_text(json.dumps(rep, indent=2, default=str),
                                                      encoding="utf-8")
            print(f"{gv} {v.name}: {rep['seconds']}s", flush=True)
        arche = L.archetype_separability(cands, ref)
        (OUT / f"archetypes__{gv}.json").write_text(json.dumps(arche, indent=2), encoding="utf-8")
        summary["datasets"][gv]["archetype_mean_overlap"] = {p: a["mean_overlap"]
                                                             for p, a in arche.items()}
        base = results[L.BASELINE.name]
        for v in variants[1:]:
            summary["decisions"].append(summarise(base, results[v.name]))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["decisions"], indent=2))


if __name__ == "__main__":
    main()
