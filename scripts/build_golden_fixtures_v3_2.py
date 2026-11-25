"""Phase 24 -- V3.2 golden fixtures + the deliberate V3.1 -> V3.2 change report.

Refuses to write anything unless the HISTORICAL V3.1 config still reproduces the
committed V3.1 goldens (proof that V3.1 is intact). Every changed fixture is
explained from data, and the explanation is ASSERTED, not narrated:
  * only candidates with partial evidence coverage (kappa < 1) may change,
  * a changed candidate's C_lo can only go DOWN (unpublished now earns 0, not P10).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_golden_fixtures_v3_1 import build_fixtures  # noqa: E402
from backend.services.recommendation_engine_v3 import ENGINE_VERSION  # noqa: E402
from backend.services.v3_config import V3_1_CONFIG, V3_2_CONFIG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V31_GOLDEN = ROOT / "artifacts" / "v3_1" / "calibration" / "golden_fixtures.json"
OUT_DIR = ROOT / "artifacts" / "v3_2" / "calibration"


def leaves(d, prefix=""):
    """Yield (path, fingerprint) for every dict that carries a 'hash'."""
    if isinstance(d, dict):
        if "hash" in d:
            yield prefix, d
        else:
            for k, v in d.items():
                if isinstance(v, dict):
                    yield from leaves(v, f"{prefix}.{k}" if prefix else k)


def strip_rows(d):
    if isinstance(d, dict):
        return {k: strip_rows(v) for k, v in d.items() if k != "rows"}
    return d


def main() -> int:
    v31 = build_fixtures(V3_1_CONFIG)
    v32 = build_fixtures(V3_2_CONFIG)
    committed = json.loads(V31_GOLDEN.read_text(encoding="utf-8"))
    cm = {p: f["hash"] for p, f in leaves(committed)}
    lv = {p: f["hash"] for p, f in leaves(v31)}
    assert cm == lv, f"V3.1 NOT reproducible: {sorted(k for k in cm if cm[k] != lv.get(k))}"

    l32 = dict(leaves(v32))
    report = {"from": V3_1_CONFIG.config_version, "to": V3_2_CONFIG.config_version,
              "engine_version": ENGINE_VERSION,
              "v3_1_reproduces_committed_goldens": True,
              "change": "missing_value_charge P10 -> ZERO", "fixtures": {}}
    for path, f1 in leaves(v31):
        f2 = l32[path]
        changed = f1["hash"] != f2["hash"]
        entry = {"changed": changed, "v3_1_hash": f1["hash"], "v3_2_hash": f2["hash"],
                 "v3_1_top": f1["top_names"][:3], "v3_2_top": f2["top_names"][:3]}
        if changed:
            by1 = {r[0]: r for r in f1["rows"]}
            deltas = []
            for r2 in f2["rows"]:
                r1 = by1.get(r2[0])
                if r1 is None:
                    continue
                name, kappa = r2[0], r2[4]
                d_clo = r2[2] - r1[2]
                if kappa == 1.0:
                    assert d_clo == 0.0 and r2[1] == r1[1], f"{path}/{name}: kappa=1 candidate moved"
                assert d_clo <= 1e-12, f"{path}/{name}: C_lo ROSE under ZERO ({d_clo})"
                deltas.append({"name": name, "kappa": kappa, "c_lo_v3_1": r1[2], "c_lo_v3_2": r2[2],
                               "delta_c_lo": d_clo, "r_v3_1": r1[1], "r_v3_2": r2[1],
                               "c_hi_changed": r2[3] != r1[3]})
            assert any(x["kappa"] < 1.0 for x in deltas), f"{path}: changed but no partial-coverage candidate"
            entry["rank_order_changed"] = f1["top_names"] != f2["top_names"]
            entry["candidate_deltas_first5"] = deltas
            entry["reason"] = ("Candidate(s) with partial evidence coverage (kappa<1): unpublished demanded "
                               "attributes now contribute 0 to C_lo instead of the frozen P10 charge, so C_lo "
                               "(and R = C_lo*M) can only fall. Fully covered candidates are bit-identical.")
        else:
            entry["reason"] = "No partial-coverage candidate affects this fixture; bit-identical."
        report["fixtures"][path] = entry
    report["changed"] = sorted(k for k, v in report["fixtures"].items() if v["changed"])
    report["n_changed"] = len(report["changed"])
    report["n_unchanged"] = len(report["fixtures"]) - report["n_changed"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    golden = {"_meta": {"config_version": V3_2_CONFIG.config_version, "engine_version": ENGINE_VERSION,
                        "missing_value_charge": V3_2_CONFIG.missing_value_charge,
                        "derived_from": "scripts/build_golden_fixtures_v3_2.py"}, **strip_rows(v32)}
    (OUT_DIR / "golden_fixtures.json").write_text(json.dumps(golden, indent=2, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "golden_diff_v3_1_to_v3_2.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"V3.1 reproduces its committed goldens: True ({len(cm)} fingerprints)")
    print(f"changed {report['n_changed']} / {len(report['fixtures'])}: {report['changed']}")
    for k in report["changed"]:
        e = report["fixtures"][k]
        print(f"  {k}: reorder={e['rank_order_changed']} top {e['v3_1_top']} -> {e['v3_2_top']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
