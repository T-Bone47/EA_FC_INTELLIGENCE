"""Local shortlist benchmark. Run from the project root with python -m verification.phase30_benchmark."""
import json
import math
import os
import platform
import statistics
import sys
import time
import tracemalloc
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener
from unittest.mock import patch

from backend.core.config import get_settings
from backend.services import card_squad_lab as lab
from backend.services.fc27_card_research import RELEASE, ResearchCards, local_release, staged_cards


def distribution(values):
    ordered = sorted(values)
    return {"n": len(values), "p50_ms": round(statistics.median(values),3),
            "p95_ms": round(ordered[math.ceil(len(values)*.95)-1],3),
            **({"p99_ms":round(ordered[math.ceil(len(values)*.99)-1],3)} if len(values)>=100 else {})}


def main(base, destination):
    settings = get_settings()
    if (urlparse(base).hostname != "127.0.0.1" or urlparse(settings.database_url).hostname != "127.0.0.1"
            or settings.environment.lower() != "test" or not settings.fc27_card_research_enabled):
        raise SystemExit("Use the opted-in loopback test instance.")
    start=time.perf_counter()
    rows=staged_cards()
    query_ms=(time.perf_counter()-start)*1000
    del rows
    start=time.perf_counter()
    ref,pool=local_release(settings.database_url)
    cold_ms=(time.perf_counter()-start)*1000
    eligible=[c for c in pool if c.extra["identity_status"]!="CONFLICTED"]
    ordered=sorted(eligible,key=lambda c:str(c.entity_id))
    positions=["GK","LB","CB","RB","CM","LW","ST","RW","CDM","CAM"]
    selected=[c for pos in positions for c in [i for i in ordered if i.position_primary==pos][:5]]
    plan=lab.SquadPlan(game_version="FC27",entity_scope="ut_card",release_id=RELEASE,include_research_data=True,
                       formation="4-3-3",candidate_ids=[c.entity_id for c in selected],
                       alternatives=["POSSESSION","HIGH_PRESS","COUNTER_ATTACK","LOW_BLOCK"])
    service=ResearchCards(ref,pool)
    label_times=defaultdict(list)
    payload=json.dumps(plan.model_dump(mode="json")).encode()
    def post():
        op=build_opener(ProxyHandler({}))
        start=time.perf_counter()
        with op.open(Request(base.rstrip("/")+"/api/research/fc27/cards/squad/preview",data=payload,
                             headers={"Content-Type":"application/json"}),timeout=60) as response:
            raw=response.read()
        duration=(time.perf_counter()-start)*1000
        result=json.loads(raw)
        assert result["solver_status"]=="EXACT_OPTIMAL" and result["optimized"]["scored"]>0
        return duration,len(raw),result["receipt"]
    post()
    timings=[post() for _ in range(25)]
    with ThreadPoolExecutor(4) as executor:
        concurrent=list(executor.map(lambda _:post(),range(12)))
    def timed(label,fn):
        def wrapped(*args,**kwargs):
            start=time.perf_counter()
            value=fn(*args,**kwargs)
            label_times[label].append((time.perf_counter()-start)*1000)
            return value
        return wrapped
    with patch.object(lab,"score_slots",timed("score_all_slots_one_tactic",lab.score_slots)), patch.object(
            lab,"optimal_assignments",timed("solver_one_tactic",lab.optimal_assignments)):
        for _ in range(10):
            start=time.perf_counter()
            out=lab.evaluate(service,plan)
            label_times["complete_evaluation"].append((time.perf_counter()-start)*1000)
            start=time.perf_counter()
            json.dumps(out)
            label_times["json_dumps"].append((time.perf_counter()-start)*1000)
    tracemalloc.start()
    lab.evaluate(service,plan)
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len({r[2] for r in timings+concurrent})==1
    data={"system":platform.platform(),"processor":platform.processor(),"python":platform.python_version(),
          "logical_cpus":os.cpu_count(),"release":RELEASE,"release_items":len(pool),"selected_items":len(selected),
          "formation":plan.formation,"tactics":[plan.tactical_profile,*plan.alternatives],"scored_slots":out["optimized"]["scored"],
          "database_fetch_all_ms":round(query_ms,3),"cold_release_fetch_verify_construct_ms":round(cold_ms,3),
          "warm_http":distribution([v[0] for v in timings]),"four_concurrent_http":distribution([v[0] for v in concurrent]),
          "body_bytes":timings[0][1],"request_python_peak_bytes_excluding_loaded_release":peak,
          "in_process":{k:distribution(v) for k,v in label_times.items()},
          "tactical_matrix":[{k:v for k,v in m.items() if k!="assignment"} for m in out["matrix"]],
          "non_dominated_generated":out["nondominated_generated_profiles"]}
    Path(destination).write_text(json.dumps(data,indent=2),encoding="utf-8")


if __name__=="__main__":
    main(*sys.argv[1:])
