"""Recompute single, paired and minimum-change replacements on the real pinned card release."""
import json
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


def main(base, destination):
    if urlsplit(base).hostname != "127.0.0.1":
        raise SystemExit("Use the loopback research application.")
    root=base.rstrip("/")+"/api/research/fc27/cards"
    http=build_opener(ProxyHandler({}))
    def post(path,data):
        with http.open(Request(root+path,data=json.dumps(data).encode(),headers={"Content-Type":"application/json"})) as r:
            return json.load(r)
    cards={}
    assigned={}
    for slot,name in [("RW","Yamal"),("ST","Mbapp")]:
        with http.open(root+"?"+urlencode({"q":name,"include_research_data":"true"})) as response:
            items=[i for i in json.load(response)["items"] if slot in i["positions"] and i["base_identity_status"]!="CONFLICTED"][:5]
        request={"game_version":"FC27","entity_scope":"ut_card","include_research_data":True,"formation":"4-3-3","slot":slot,"position":slot}
        assert len(items)>=2
        scores=post("/compare",{"request":request,"card_ids":[i["entity_id"] for i in items]})["players"]
        assert len(scores)>=2
        assigned[slot]=scores[-1]["entity_id"]
        cards.update({r["entity_id"]:r["card"]["source_item_id"] for r in scores})
    plan={"game_version":"FC27","entity_scope":"ut_card","release_id":"fc27-card-items-local-r1","include_research_data":True,
          "formation":"4-3-3","assigned":assigned,"candidate_ids":list(cards)}
    results={}
    for mode in ("one","two","minimum"):
        gain=results["one"]["gain"]+1e-8 if mode=="minimum" else 0
        out=post("/squad/preview",{**plan,"upgrade":mode,"minimum_gain":gain})
        assert out["upgrade_status"]=="EXACT_OPTIMAL"
        changes=[{"slot":u["slot"],"old_source_item":u["before"]["source_item_id"],"new_source_item":u["after"]["source_item_id"],
                  "before_score":u["before_score"],"after_score":u["after_score"],"delta":u["delta"],
                  "coverage_before":u["coverage_before"],"coverage_after":u["coverage_after"]} for u in out["upgrades"]]
        assert len(changes)==(1 if mode=="one" else 2) and abs(sum(c["delta"] for c in changes)-out["upgrade_gain"])<1e-9
        results[mode]={"gain":out["upgrade_gain"],"minimum_requested_gain":gain,"changes":changes}
    Path(destination).write_text(json.dumps({"release":plan["release_id"],"formation":plan["formation"],
        "profile":"BALANCED","pool_items":len(cards),"results":results},indent=2),encoding="utf-8")


if __name__=="__main__":
    main(*sys.argv[1:])
