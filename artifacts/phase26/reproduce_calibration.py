"""Run from any directory with Python 3.12+. Writes Phase 26 evidence only."""
import itertools
import json
from pathlib import Path
import statistics
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[1]))
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.capability_model import compute_capability
from backend.services.demand_composition import compose_demand
from backend.services.reference_distribution import load_reference_for
from backend.services.v3_config import DEFAULT_V3_CONFIG
from scripts.build_golden_fixtures_v3_2 import (
    build_fixtures, leaves, OUT_DIR, V31_GOLDEN, V3_1_CONFIG, V3_2_CONFIG,
)


def compare_goldens():
    versions = {}
    for config, path in [(V3_1_CONFIG, V31_GOLDEN), (V3_2_CONFIG, OUT_DIR / "golden_fixtures.json")]:
        live = dict(leaves(build_fixtures(config)))
        expected = dict(leaves(json.loads(path.read_text(encoding="utf-8"))))
        versions[config.config_version] = {
            name: {"actual": live.get(name, {}).get("hash"), "expected": expected.get(name, {}).get("hash")}
            for name in sorted(expected.keys() | live.keys())
        }
    old, new = versions.values()
    drift = [(v, k) for v, cases in versions.items() for k, d in cases.items() if d["actual"] != d["expected"]]
    cross = [k for k in old if old[k]["actual"] != new[k]["actual"]]
    result = {"status": "FAIL" if drift else "PASS", "drift": drift, "profiles": versions,
              "changed_across_versions": cross, "historical_baselines_written": False}
    (OUT / "GOLDEN_FIXTURE_DIFF.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def reproduce_calibration():
    ref = load_reference_for("FC26")
    profiles = ["PRESSING", "POSSESSION", "LOW_BLOCK", "PACE_ABUSER", "DIRECT_PLAY"]
    lines = ["# FC26 calibration reproduction", "",
             "Command: `python artifacts/phase26/reproduce_calibration.py` (Python 3.12+).",
             "Input: local FC26 foundation CSV, frozen FC26 player reference, shipped default V3.2 policy. Dataset rights remain UNVERIFIED. "
             "Repeat the repository RD-3/RD-4 capability-only protocol with average-rank Spearman correlations using Python statistics. "
             "These correlations measure association with OVR, not a scoring input or a gameplay outcome.", "",
             "| Position | Pool | " + " | ".join(profiles) + " | Spread | Mean top-10 overlap¹ |",
             "|---|---:|" + "---:|" * 7]
    failures = []
    for pos, family in [("CB", {"CB","LB","RB"}), ("CM", {"CM","CDM","CAM"}), ("ST", {"ST","LW","RW"})]:
        pool = load_foundation_candidates("FC26", positions=family)
        rhos, tops = [], []
        for t in profiles:
            demand = compose_demand(position=pos, tactical_profile=t, lam=DEFAULT_V3_CONFIG.lam_default.value).vector
            scored = []
            for c in pool:
                cap = compute_capability(demand=demand, attributes={k:c.attributes.get(k) for k in demand},
                                         position=pos, reference=ref)
                if cap.kappa >= DEFAULT_V3_CONFIG.kappa_min.value:
                    scored.append((cap.c_lo, c))
            scored.sort(key=lambda row: (-row[0],str(row[1].entity_id)))
            tops.append({c.name for _,c in scored[:10]})
            rateable = [(s,c.overall_rating) for s,c in scored if c.overall_rating]
            rhos.append(statistics.correlation(*zip(*rateable), method="ranked"))
        spread = max(rhos)-min(rhos)
        overlap = statistics.mean(len(a & b) for a,b in itertools.combinations(tops,2))
        lines.append(f"| {pos} | {len(pool)} | " + " | ".join(f"{r:.6f}" for r in rhos)
                     + f" | {spread:.6f} | {overlap:.2f} |")
        if any(not 0.35 <= r <= 0.85 for r in rhos):
            failures.append(f"RD-3 {pos} exceeds the registered [0.35, 0.85] band.")
        if pos in {"CB","ST"} and spread < 0.10:
            failures.append(f"RD-4 {pos} spread {spread:.6f} is below 0.10.")
    lines.extend(["", "¹ Mean number of shared player names across ten pairs of top-ten lists, following the existing test.",
                  "", "## Outstanding policy findings", ""] + ["- "+f for f in failures] +
                 ["","No parameter or threshold changes. The release owner retains responsibility for RD-3 and CB responsiveness."])
    (OUT / "CALIBRATION_REPRODUCTION.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    compare_goldens()
    reproduce_calibration()

