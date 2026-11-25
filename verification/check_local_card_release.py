"""Exercise the live zero-budget FC27 research API over loopback and report only aggregate evidence."""
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

POSITIONS = "GK CB LB RB CDM CM CAM LM RM LW RW ST".split()
TACTICS = "BALANCED POSSESSION HIGH_PRESS LOW_BLOCK COUNTER_ATTACK DIRECT_PLAY".split()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if urlsplit(args.origin).hostname not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("Expected a loopback research server")
    client = build_opener(ProxyHandler({}))
    rows = []
    for position in POSITIONS:
        for tactic in TACTICS:
            payload = {"position": position, "game_version": "FC27", "include_research_data": True,
                       "tactical_profile": tactic, "limit": 5}
            request = Request(args.origin.rstrip("/")+"/api/research/fc27/cards/recommendations",
                              data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
            start = perf_counter()
            with client.open(request, timeout=60) as response:
                body = response.read()
            elapsed = round((perf_counter()-start)*1000, 2)
            result = json.loads(body)
            assert result["dataset"]["research_only"] and result["entity_scope"] == "ut_card"
            assert result["reference_distribution_universe"] == "UT_CARDS"
            assert bool(result["ranked"]) == (position != "GK")
            assert all(r["card"]["market_price"] is None and r["explanation"]["reconstructed_score_matches_ranking"]
                       and 0 <= r["coverage"] <= 1 for r in result["ranked"])
            rows.append(dict(position=position, tactic=tactic, **result["counts"], elapsed_ms=elapsed,
                             response_bytes=len(body), config=result["config_version"], reference=result["data_version"]))
    times = sorted(r["elapsed_ms"] for r in rows)
    out = {"contexts": len(rows), "measurement": "local sequential HTTP, one request per context",
           "median_ms": median(times), "p95_ms_nearest_rank": times[(95*len(times)+99)//100-1], "rows": rows}
    args.output.write_text(json.dumps(out, indent=2)+"\n", encoding="utf-8")
    print({k:v for k,v in out.items() if k!="rows"})


if __name__ == "__main__":
    main()
