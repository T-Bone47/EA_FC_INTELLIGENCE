#!/usr/bin/env python
"""Generate the 15 immutable v3.1 golden response fixtures
(V3_1_CALIBRATION_REPORT.md Phase 18). Each fixture is a real engine
response, hashed, so a future change shows exactly which golden outputs
moved and by how much (drift monitor DR-6 in INTELLIGENCE_TEST_MATRIX.md).

Not a test file: this is a generator, run explicitly, whose output
(golden_fixtures.json) is committed and then checked against by
test_golden_fixtures.py.
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.data_access.foundation_loader import load_foundation_candidates  # noqa: E402
from backend.services.recommendation_engine_v3 import RecommendationEngineV3  # noqa: E402
from backend.services.reference_distribution import load_reference_distribution  # noqa: E402
from backend.services.v3_config import V3_1_CONFIG  # noqa: E402
from backend.tests.helpers import make_attrs, make_candidate, make_req  # noqa: E402

FIXED_REQUEST_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

FULL_CM = make_attrs(short_passing=85, vision=84, composure=82, ball_control=83,
                      long_passing=80, dribbling_detail=78, positioning=76,
                      curve=74, agility=75, reactions=80, stamina=82,
                      defensive_awareness=70, interceptions=65, standing_tackle=62,
                      strength=74, acceleration=76, pace=74, aggression=68,
                      long_shots=70, balance=76)


def _fingerprint(result) -> dict:
    rows = [(rc.context.candidate_name, rc.context.r, rc.context.c_lo,
             rc.context.c_hi, rc.context.coverage_kappa) for rc in result.ranked]
    blob = json.dumps(rows, sort_keys=True, default=str).encode()
    return {"top_names": [r[0] for r in rows[:10]], "hash": hashlib.sha256(blob).hexdigest(),
            # Phase 24: first rows kept for the V3.1->V3.2 diff report. NOT part of the hash.
            "rows": [list(r) for r in rows[:5]]}


def build_fixtures(config=None) -> dict:
    """Build the named scenarios. `config=None` pins the HISTORICAL V3.1 config so the
    committed V3.1 goldens stay reproducible after V3.2 became the default (Phase 24).
    Pass V3_2_CONFIG / DEFAULT_V3_CONFIG for the V3.2 goldens."""
    config = V3_1_CONFIG if config is None else config
    ref = load_reference_distribution("fc26-players-2026-09-r1")
    engine = RecommendationEngineV3(config=config, reference=ref, data_version="fc26-players-2026-09-r1")
    cm_pool = load_foundation_candidates("FC26", positions={"CM", "CDM", "CAM"})[:500]
    fixtures = {}

    for profile in ("LOW_BLOCK", "HIGH_PRESS", "POSSESSION", "BALANCED", "PACE_ABUSER", "DIRECT_PLAY"):
        req = make_req(position="CM", tactical_profile=profile, limit=10)
        res = engine.recommend(cm_pool, req, request_id=FIXED_REQUEST_ID)
        fixtures[f"tactical_{profile}"] = _fingerprint(res)

    thin = make_candidate(name="ThinEvidence", position="CM", ovr=82, attrs=make_attrs(short_passing=60))
    documented = make_candidate(name="Documented", position="CM", ovr=82, attrs=FULL_CM)
    res = engine.recommend([thin, documented], make_req(position="CM", tactical_profile="POSSESSION"),
                            request_id=FIXED_REQUEST_ID)
    fixtures["thin_evidence"] = _fingerprint(res)

    cb = make_candidate(name="RealCB", position="CB", ovr=85, attrs=make_attrs(
        defending=86, standing_tackle=85, interceptions=84, heading_accuracy=82,
        strength=86, defensive_awareness=85, jumping=80, reactions=82, pace=70))
    striker = make_candidate(name="MismatchedStriker", position="ST", ovr=91, attrs=make_attrs(
        finishing=92, positioning=90, shot_power=88, pace=90, defending=30,
        standing_tackle=25, interceptions=28, defensive_awareness=30))
    res = engine.recommend([cb, striker], make_req(position="CB", tactical_profile="LOW_BLOCK"),
                            request_id=FIXED_REQUEST_ID)
    fixtures["position_mismatch"] = _fingerprint(res)

    c_relevant = make_candidate(name="RelevantPS", position="CM", ovr=82, attrs=FULL_CM)
    c_relevant.playstyles_base = ["Tiki Taka"]
    c_relevant.playstyle_data_published = True
    c_none = make_candidate(name="NoPSEvidence", position="CM", ovr=82, attrs=FULL_CM)
    c_none.playstyle_data_published = False
    req_ps = make_req(position="CM", tactical_profile="POSSESSION", desired_playstyles=["Tiki Taka"])
    res = engine.recommend([c_relevant, c_none], req_ps, request_id=FIXED_REQUEST_ID)
    fixtures["playstyle_relevance"] = _fingerprint(res)
    res2 = engine.recommend([c_none], make_req(position="CM", tactical_profile="POSSESSION"),
                             request_id=FIXED_REQUEST_ID)
    fixtures["no_playstyle_evidence"] = _fingerprint(res2)

    same_attrs_low_ovr = make_candidate(name="SameAttrs", position="CM", ovr=65, attrs=FULL_CM)
    same_attrs_high_ovr = make_candidate(name="SameAttrs", position="CM", ovr=95, attrs=FULL_CM,
                                          entity_id=uuid.UUID(int=99))
    res = engine.recommend([same_attrs_low_ovr, same_attrs_high_ovr],
                            make_req(position="CM", tactical_profile="POSSESSION"),
                            request_id=FIXED_REQUEST_ID)
    fixtures["same_attributes_different_ovr"] = _fingerprint(res)

    diff_attrs_a = make_candidate(name="A", position="CM", ovr=84, attrs=FULL_CM)
    diff_vals = {k: max(1, v - 10) for k, v in FULL_CM.values.items()}
    diff_attrs_b = make_candidate(name="B", position="CM", ovr=84, attrs=make_attrs(**diff_vals))
    res = engine.recommend([diff_attrs_a, diff_attrs_b],
                            make_req(position="CM", tactical_profile="POSSESSION"),
                            request_id=FIXED_REQUEST_ID)
    fixtures["same_ovr_different_attributes"] = _fingerprint(res)

    single = make_candidate(name="SamePlayer", position="CM", ovr=84, attrs=FULL_CM)
    res_a = engine.recommend([single], make_req(position="CM", tactical_profile="LOW_BLOCK"),
                              request_id=FIXED_REQUEST_ID)
    res_b = engine.recommend([single], make_req(position="CM", tactical_profile="HIGH_PRESS"),
                              request_id=FIXED_REQUEST_ID)
    fixtures["same_player_two_tactics"] = {"low_block": _fingerprint(res_a), "high_press": _fingerprint(res_b)}

    pool_a = cm_pool[:50]
    pool_b = list(reversed(cm_pool[:50]))
    res_a = engine.recommend(pool_a, make_req(position="CM", tactical_profile="POSSESSION", limit=10),
                              request_id=FIXED_REQUEST_ID)
    res_b = engine.recommend(pool_b, make_req(position="CM", tactical_profile="POSSESSION", limit=10),
                              request_id=FIXED_REQUEST_ID)
    fp_a, fp_b = _fingerprint(res_a), _fingerprint(res_b)
    fixtures["pool_ordering_a"] = fp_a
    fixtures["pool_ordering_b"] = fp_b
    fixtures["pool_ordering_identical"] = fp_a["hash"] == fp_b["hash"]

    return fixtures


if __name__ == "__main__":
    fixtures = build_fixtures()
    out_path = Path(__file__).resolve().parents[1] / "artifacts" / "v3_1" / "calibration" / "golden_fixtures.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(fixtures, f, indent=2, sort_keys=True)
    print(f"Wrote {len(fixtures)} golden fixture entries to {out_path}")
    for k, v in fixtures.items():
        if isinstance(v, dict) and "hash" in v:
            print(f"  {k:40s} hash={v['hash'][:16]}  top={v.get('top_names', [])[:2]}")
