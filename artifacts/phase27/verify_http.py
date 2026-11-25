"""Exercise the isolated research and production-like servers without exporting dataset rows."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

RESEARCH = "http://127.0.0.1:35428"
PRODUCTION = "http://127.0.0.1:35430"


def call(server, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(server + path, data=body, headers={
        "Content-Type": "application/json", "Accept-Encoding": "gzip"})
    started = perf_counter()
    try:
        response = urlopen(request, timeout=40)
    except HTTPError as error:
        response = error
    with response:
        wire = response.read()
        encoded = response.headers.get("Content-Encoding") == "gzip"
        decoded = gzip.decompress(wire) if encoded else wire
        return response.status, json.loads(decoded), {
            "ms": round((perf_counter() - started) * 1000, 2),
            "wire_bytes": len(wire), "json_bytes": len(decoded), "gzip": encoded,
        }


def main():
    record = {"production_denials": [], "research_http": {}, "warm_sequential": [], "concurrent": []}
    entity = uuid.uuid4()
    for game in ("FC26", "FC27"):
        for route in ("/players", "/players/facets", "/players/" + str(entity),
                      "/cards", "/cards/" + str(entity),
                      *("/cards/" + str(entity) + "/" + x for x in ("versions", "value", "prices")),
                      "/card-data-status", "/meta/reference"):
            status, response, _ = call(PRODUCTION, "/api" + route + "?game_version=" + game)
            assert status == 403 and response["detail"]["error"] == "DATA_LICENSE_GATE_FAILED"
            record["production_denials"].append({"path": route, "version": game, "status": status})
        status, response, _ = call(PRODUCTION, "/api/v3/recommendations", {
            "game_version": game, "position": "CM", "include_research_data": game == "FC27"})
        assert status == 403 and response["detail"]["error"] in {
            "DATA_LICENSE_GATE_FAILED", "RESEARCH_DATA_REFUSED_IN_PRODUCTION"}
        record["production_denials"].append({"path": "/v3/recommendations", "version": game, "status": status})
    assert call(PRODUCTION, "/api/health/ready")[1] == {"status": "ready", "database": "up"}
    requests = [
        {"game_version": "FC26", "position": "CM", "tactical_profile": "BALANCED", "limit": 10},
        {"game_version": "FC27", "division": "Men's Football", "position": "CM",
         "tactical_profile": "HIGH_PRESS", "include_research_data": True, "limit": 10},
    ]

    def recommend(request):
        status, result, measurement = call(RESEARCH, "/api/v3/recommendations", request)
        assert status == 200 and result["ranked"]
        assert result["dataset"]["game_version"] == request["game_version"]
        assert result["division"]["requested"] == request.get("division")
        assert result["request"]["tactical_profile"] == request["tactical_profile"]
        assert result["entity_scope"] == "game_player"
        return result, measurement

    wanted = {}
    for request in requests:
        result, measurement = recommend(request)
        game = request["game_version"]
        wanted[game] = [(r["entity_id"], r["rank"], r["score"]) for r in result["ranked"]]
        entity_ids = [row[0] for row in wanted[game][:2]]
        status, compared, _ = call(RESEARCH, "/api/v3/compare", {"request": request, "entity_ids": entity_ids})
        assert status == 200 and len(compared["players"]) == 2
        status, variants, _ = call(RESEARCH, "/api/v3/what-if", {
            "base": request, "variants": [{"label": "low block", "tactical_profile": "LOW_BLOCK"}], "track_top": 2})
        assert status == 200 and variants["variants"][0]["parent_request_id"] == variants["request_id"]
        record["research_http"][game] = {
            "request": request, "candidate_count": result["counts"]["candidates"],
            "reference": result["reference_distribution_version"],
            "recommend_compare_what_if": "PASS", "recommendation": measurement,
        }
    for _ in range(6):
        for request in requests:
            result, measurement = recommend(request)
            assert [(r["entity_id"], r["rank"], r["score"]) for r in result["ranked"]] == wanted[request["game_version"]]
            record["warm_sequential"].append({"version": request["game_version"], **measurement})
    with ThreadPoolExecutor(4) as workers:
        samples = requests * 4
        for request, (result, measurement) in zip(samples, workers.map(recommend, samples)):
            game = request["game_version"]
            assert [(r["entity_id"], r["rank"], r["score"]) for r in result["ranked"]] == wanted[game]
            record["concurrent"].append({"version": game, **measurement})
    record["warm_median_ms"] = {game: median(x["ms"] for x in record["warm_sequential"] if x["version"] == game) for game in wanted}
    record["status"] = "PASS"
    Path(__file__).with_name("HTTP_RESULTS.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("PASS", len(record["production_denials"]), "production denials,", len(record["concurrent"]), "concurrent research requests")


if __name__ == "__main__":
    main()
