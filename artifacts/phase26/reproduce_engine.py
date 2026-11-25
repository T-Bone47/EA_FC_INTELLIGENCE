"""Offline Phase 26 checks. No API credentials or database needed. Python 3.12+."""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import sys
from time import perf_counter
import uuid

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[1]))
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.domain.card_model import ALL_ATTRS, DataStatus, IdentityStatus
from backend.services.explanation_service_v3 import explain
from backend.services.recommendation_engine_v3 import RecommendationEngineV3, UnsupportedEntityScopeError
from backend.services.reference_distribution import load_reference_for, ReferenceDistributionMismatch
from backend.services.scoring_config import POSITION_ATTRIBUTE_WEIGHTS, TACTICAL_ATTRIBUTE_WEIGHTS
from backend.services.v3_config import DEFAULT_V3_CONFIG
from backend.tests.helpers import make_req, make_candidate, make_attrs

REF = "fc26-players-2026-09-r1"


def engine():
    return RecommendationEngineV3(reference=load_reference_for("FC26"), data_version=REF)


def signature(result):
    return [(str(r.context.candidate_entity_id), r.context.r, r.rank) for r in result.ranked]


def json_out(name, payload):
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def latency(xs):
    ordered = sorted(xs)
    return {"n":len(xs), "p50_ms":statistics.median(xs), "p95_ms":ordered[(95*len(xs)-1)//100] if len(xs)>=20 else None,
            "p99_ms":ordered[(99*len(xs)-1)//100] if len(xs)>=100 else None, "max_ms":max(xs)}


def play(case):
    e, candidates, position, tactic = case
    request = make_req(game_version="FC26", entity_scope="game_player", position=position, tactical_profile=tactic)
    return signature(e.recommend(candidates, request))


def main():
    e = engine()
    started = perf_counter()
    pool = load_foundation_candidates()
    csv_ms = 1000*(perf_counter()-started)
    seed = random.Random(26)
    rows, engine_ms, explain_ms, cases = [], [], [], []
    for position in POSITION_ATTRIBUTE_WEIGHTS:
        matched = [c for c in pool if c.position_primary == position or position in c.secondary_positions]
        sample = seed.sample(matched, min(24,len(matched)))
        for tactic in TACTICAL_ATTRIBUTE_WEIGHTS:
            request = make_req(position=position,tactical_profile=tactic,entity_scope="game_player")
            started = perf_counter()
            a=e.recommend(sample,request)
            engine_ms.append(1000*(perf_counter()-started))
            original=signature(a)
            repeated=signature(e.recommend(sample,request))
            reversed_ids=signature(e.recommend(list(reversed(sample)),request))
            no_ovr=signature(e.recommend([replace(c,overall_rating=0) for c in sample],request))
            started = perf_counter()
            explanations = [explain(r.context) for r in a.ranked]
            explain_ms.append(1000*(perf_counter()-started))
            rows.append({"position":position,"tactic":tactic,"pool":len(sample),"ranked":len(original),
                         "repeat_equal":repeated==original, "reverse_equal":reversed_ids==original,
                         "ovr_equal":no_ovr==original, "explanations_exact":bool(explanations) and all(x.matches_ranking_score for x in explanations),
                         "modifier_in_bounds":all(DEFAULT_V3_CONFIG.modifier_min.value<=r.context.modifier_total<=DEFAULT_V3_CONFIG.modifier_max.value for r in a.ranked),
                         "top_id":original[0][0] if original else None})
            if tactic in {"HIGH_PRESS","POSSESSION"} and position in {"CM","CB","ST","GK"}:
                cases.append((e,sample,position,tactic))
    checks={}
    def check(name, passed, evidence=None):
        checks[name]={"status":"PASS" if passed else "FAIL", "evidence":evidence}
    for key in ["repeat_equal","reverse_equal","ovr_equal","explanations_exact","modifier_in_bounds"]:
        failures=[(row["position"],row["tactic"]) for row in rows if not row[key] or not row["ranked"]]
        check(key,not failures,failures)
    tactical={p:len({r["top_id"] for r in rows if r["position"]==p}) for p in POSITION_ATTRIBUTE_WEIGHTS}
    check("tactical_discrimination_in_sample",max(tactical.values())>1,tactical)
    # Explicit engineering fixtures. The fixture domain status is canonical only in process memory.
    req=make_req(position="CM",tactical_profile="POSSESSION",entity_scope="game_player")
    base=make_candidate(position="CM",entity_id=uuid.UUID(int=1),attrs=make_attrs(**dict.fromkeys(ALL_ATTRS,65)))
    def run(c, request=req):
        return e.recommend([c],request)
    def ctx(c, request=req):
        return run(c,request).ranked[0].context
    baseline=ctx(base)
    attr=max(baseline.demand_vector,key=baseline.demand_vector.get)
    def with_attr(key,value):
        return replace(base,attributes=make_attrs(**{**base.attributes.values,key:value}))
    raised=ctx(with_attr(attr,75))
    check("attribute_relevance",raised.r>baseline.r,{"attribute":attr,"baseline":baseline.r,"raised":raised.r})
    irrelevant=next(a for a in ALL_ATTRS if a not in baseline.demand_vector)
    check("attribute_irrelevance",ctx(with_attr(irrelevant,90)).r==baseline.r,irrelevant)
    missing=ctx(with_attr(attr,None))
    check("missingness",missing.r<=baseline.r and attr in missing.missing_attributes)
    thin=run(replace(base,attributes=make_attrs()))
    check("coverage_floor",not thin.ranked and len(thin.not_evaluable)==1)
    check("position_gate",not run(replace(base,position_primary="ST")).ranked)
    check("gk_gate_both_directions",not run(replace(base,position_primary="GK")).ranked and not run(base,replace(req,position="GK")).ranked)
    twin=replace(base,entity_id=uuid.UUID(int=2),overall_rating=95)
    joint=signature(e.recommend([twin,base],req))
    check("ties", [x[0] for x in joint]==[str(base.entity_id),str(twin.entity_id)] and joint[0][1]==joint[1][1])
    check("pool_independence", len(joint)==2 and all(t[1]==baseline.r for t in joint))
    preference=replace(req,desired_playstyles=["Tiki Taka"])
    mods=[ctx(replace(base,playstyles_base=lst,playstyles_plus=[]),preference).modifier_total for lst in [[],["irrelevant"],["Tiki Taka"]]]
    check("playstyle_evidence_and_monotonicity",mods[0]==mods[1]==1 and mods[0]<=mods[2]<=DEFAULT_V3_CONFIG.modifier_max.value,mods)
    base.identity_status=IdentityStatus.RESOLVED
    confident=ctx(base)
    base.identity_status=IdentityStatus.UNRESOLVED
    uncertain=ctx(base)
    check("confidence_reporting_only",confident.r==uncertain.r and confident.confidence!=uncertain.confidence)
    check("fc27_candidate_excluded",not run(make_candidate(version="FC27")).ranked)
    try:
        run(base,replace(req,game_version="FC27"))
        incompatible=False
    except ReferenceDistributionMismatch:
        incompatible=True
    check("incompatible_reference",incompatible)
    for label,c in [("synthetic_flag",replace(base,is_synthetic=True)),("synthetic_status",replace(base,data_status=DataStatus.SYNTHETIC_TEST)),
                    ("card_candidate_in_player_pool",replace(base,entity_type="ut_card")),
                    ("research_status_with_fc26_reference",replace(base,data_status=DataStatus.RESEARCH_ONLY))]:
        check(label,not run(c).ranked)
    for scope in ["ut_card","unsupported"]:
        try:
            run(base,replace(req,entity_scope=scope))
            refused=False
        except UnsupportedEntityScopeError:
            refused=True
        check("request_scope_"+scope,refused)
    check("empty_pool",not e.recommend([],req).ranked)
    status="FAIL" if any(v["status"]=="FAIL" for v in checks.values()) else "PASS"
    json_out("INTELLIGENCE_INVARIANT_RESULTS.json",{"status":status,"scope":"offline V3.2 FC26 research + tagged in-memory engineering checks","command":"python -B artifacts/phase26/reproduce_engine.py",
             "reference":REF,"seed":26,"pool_total":len(pool),"checks":checks,"matrix":rows})
    serial=[play(case) for case in cases]
    parallel={}
    for label,executor in [("threads",ThreadPoolExecutor),("processes",ProcessPoolExecutor)]:
        with executor(max_workers=4) as workers:
            got=list(workers.map(play,cases))
        parallel[label]={"workers":4,"requests":len(cases),"matches_sequential":got==serial}
    json_out("CONCURRENCY_RESULTS.json",{"scope":"FC26 in-process scoring and worker isolation only",
             "reference":REF,"comparisons":parallel,"cases":[[p,t] for _,_,p,t in cases],
             "http_multiworker_version_division_reference_isolation":"BLOCKED","database_recovery":"BLOCKED"})
    large=[]
    for i in range(3):
        started=perf_counter()
        r=e.recommend(pool,req)
        large.append(1000*(perf_counter()-started))
    hw={"python":sys.version.split()[0],"os":platform.platform(),"processor":platform.processor(),"logical_cpus":os.cpu_count()}
    json_out("PERFORMANCE_RESULTS.json",{"scope":"local offline FC26 V3.2 player scoring","hardware":hw,"sla":"owner decision pending",
             "csv_load_ms":csv_ms,"request_concurrency":1,"reference":"preloaded","engine_24_candidate_ms":latency(engine_ms),
             "explain_top_10_ms":latency(explain_ms),"engine_16228_candidate_ms":latency(large),
             "large_counts":{"ranked":len(r.ranked),"excluded":len(r.excluded),"not_evaluable":len(r.not_evaluable)},
             "notes":"192 distinct tactical workloads; percentiles across workloads. Full-pool p95/p99 withheld for n=3. No compression or network in this check.",
             "blocked_stages":["HTTP","database","API response serialization/compression","browser render","transfer"]})
    print(status,[k for k,v in checks.items() if v["status"]=="FAIL"])
    return int(status=="FAIL" or any(not v["matches_sequential"] for v in parallel.values()))


if __name__ == "__main__":
    raise SystemExit(main())

