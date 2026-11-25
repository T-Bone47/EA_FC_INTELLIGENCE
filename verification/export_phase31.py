"""Export release membership, research coverage and real V3.2 responses. Local research only."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from backend.api.routes.performance_lab import reviewed_rows, view
from backend.core.config import get_settings
from backend.services.data_license_gate import Environment, environment_from_settings
from backend.services.fc27_card_research import validate_cached_membership
from backend.services.formations import FORMATION_SLOTS
from backend.services.performance_cohort import load_cohort
from backend.services.performance_evidence import official_rating_checks, opinion_summary, reported_matches


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict,list)) else value
                             for field, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:38533")
    parser.add_argument("--out", type=Path, default=Path("artifacts/phase31"))
    args = parser.parse_args()
    settings = get_settings()
    if (urlsplit(args.url).hostname != "127.0.0.1" or urlsplit(settings.database_url).hostname not in {"127.0.0.1","localhost","::1"}
            or environment_from_settings(settings.environment) != Environment.LOCAL or not settings.fc27_card_research_enabled):
        parser.error("Use explicit local FC27 research with a loopback server and database.")
    args.out.mkdir(parents=True, exist_ok=True)
    validate_cached_membership()
    manifest, items = load_cohort(settings.database_url)
    manifest["research_only"] = True
    manifest["selection_date"] = "2026-11-23"
    manifest["rating_references"] = len(official_rating_checks())
    (args.out/"TOP_100_COHORT_MANIFEST.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    for group, filename in (("TOP_100","TOP_100_BASE_CARDS.csv"),("POSITION_CONTROL","POSITION_CONTROL_COHORT.csv")):
        write_csv(args.out/filename, (item for item in items if item["cohort"]==group), list(items[0]))
    rows = reviewed_rows()
    eligible, disputes = reported_matches(rows)
    observations = [view(row) for row in eligible]
    write_csv(args.out/"PERFORMANCE_OBSERVATIONS.csv", observations,
              ["id","card_item_id","schema_version","observation_type","source_key","source_url","source_date",
               "provenance_status","review_status","context","match","data_completeness"])
    conflicts = [row for row in opinion_summary(rows) if row["status"]=="CONFLICTING"]+disputes
    write_csv(args.out/"CLAIM_CONFLICT_REPORT.csv", conflicts,
              ["card_item_id","topic","status","supporting_origins","contradicting_origins","context","records","observations"])
    coverage = Counter((str(row["card_item_id"]),row["payload"]["context"]["formation"],
                        row["payload"]["context"]["slot"],row["payload"]["context"]["role"]) for row in eligible)
    roles = []
    for item in items:
        for formation, slots in FORMATION_SLOTS.items():
            for slot in slots:
                if slot.position not in item["positions"] or (slot.position=="GK")!=(item["primary_position"]=="GK"):
                    continue
                counts = {role or "UNKNOWN":count for (card,shape,position,role), count in coverage.items()
                          if (card,shape,position)==(item["card_item_id"],formation,slot.slot)}
                roles.append({"card_item_id":item["card_item_id"],"source_item_id":item["source_item_id"],"cohort":item["cohort"],
                              "formation":formation,"slot":slot.slot,"position":slot.position,
                              "reviewed_matches":sum(counts.values()),"observed_roles":counts,
                              "official_role":item["official_roles"],
                              "coverage_status":"REVIEWED_MATCHES_AVAILABLE" if counts else "INSUFFICIENT_GAMEPLAY_EVIDENCE"})
    write_csv(args.out/"FORMATION_ROLE_COVERAGE.csv", roles, list(roles[0]))
    write_csv(args.out/"SOURCE_DISCOVERY_QUEUE.csv", (
        {"source_item_id":item["source_item_id"],"player":item["name"],"cohort":item["cohort"],
         "official_reference":official_rating_checks().get(item["source_item_id"],{}).get("source_url"),
         "queries":[f'FC27 "{item["name"]}" "{item["primary_position"]}" {term}'
                    for term in ("gold base item","role and PlayStyles","match review and patch","controlled card comparison")]}
        for item in items), ["source_item_id","player","cohort","official_reference","queries"])

    # Benchmark the normal HTTP entry point on two pinned base candidates.
    opener = build_opener(ProxyHandler({}))
    url = args.url.rstrip("/")+"/api/research/fc27/performance/compare"
    cards = [item["card_item_id"] for item in items if item["source_item_id"] in {"231747","239085"}]
    measured, results = [], {}
    for index in range(25):
        profile = ("BALANCED","HIGH_PRESS","POSSESSION","COUNTER_ATTACK","DIRECT_PLAY")[index%5]
        body = {"game_version":"FC27","include_research_data":True,"card_ids":cards,"metric":"goals","context":{
            "game_patch":"1.2.0","formation":"4-3-3","position":"ST","slot":"ST","role":"advanced forward",
            "game_mode":"friendly","controller":"HUMAN","tactical_profile":profile}}
        request = Request(url,data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
        start = perf_counter()
        with opener.open(request, timeout=30) as response:
            out = json.load(response)
        measured.append((perf_counter()-start)*1000)
        assert len(out["predictions"])==2
        results[profile] = out
    report = {"release":manifest["release_id"],"cohort_digest":manifest["cohort_digest"],
              "reviewed_match_count":len(observations),"formation_slots_enumerated":len(roles),"gameplay_holdout":None,
              "api_timing":{"n":len(measured),"cold_ms":round(measured[0],2),"warm_p50_ms":round(median(measured[1:]),2),
                            "warm_p95_ms":round(sorted(measured[1:])[22],2)},"profiles":results}
    (args.out/"ENGINE_COMPARISON_RESULTS.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print({key:value for key,value in report.items() if key!="profiles"})


if __name__ == "__main__":
    main()
