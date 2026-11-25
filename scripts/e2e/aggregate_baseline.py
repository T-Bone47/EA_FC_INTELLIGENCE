import csv, glob, os, re, sys, platform, subprocess
D = "reports/e2e/evidence/baseline_chunks"
CLS = {  # test-name fragment -> (classification, affects_production_contract, evidence/next step)
 "test_engine_adversarial_phase7": ("POLICY_REQUIRED", "YES while v2 /api/recommendations is mounted", "Legacy V2 engine ranks a generic high-OVR player above a specialist (the OVR-channel defect V3 was built to fix). Decide: retire/disable v2 recommend in production or label it legacy."),
 "test_engine_v3_real_data": ("POLICY_REQUIRED", "NO (V3 contract)", "rho(R,OVR)=0.86-0.91 exceeds the stale [0.35,0.85] band. Phase 23: OVR-shuffle ranking identical => structural correlation, not a channel. Revise the spec threshold with evidence; do not tune the engine."),
 "test_why_this_matches_scoring": ("PRE_EXISTING", "NO for v3; v2 explanations UNVERIFIED", "AttributeError: RecommendationResult has no attribute 'explanations' - stale test against a refactored v2 result object."),
 "test_why_not_alternatives_differentials": ("PRE_EXISTING", "NO for v3; v2 explanations UNVERIFIED", "Same stale-attribute cause as test_why_this_matches_scoring."),
 "test_confidence_v2_additive": ("UNCLASSIFIED", "UNKNOWN", "Assertion False on confidence_v2 composition; root cause not investigated."),
 "test_formation": ("UNCLASSIFIED", "UNKNOWN (v2 formations only; v3 has none)", "Expected slots LCM/RCM/LDM... but code returns CM/CDM...; slot-naming drift vs product decision not determined."),
 "test_outfield_combo_pressing_fast_build_up": ("UNCLASSIFIED", "UNKNOWN (v2)", "Expected evidence status KNOWN, got INSUFFICIENT_EVIDENCE; root cause not investigated."),
 "test_version_mismatch_rejected": ("PRE_EXISTING", "NO (v3 version wall covered by passing tests)", "TypeError: test helper cand() no longer accepts game_version - stale test code."),
 "test_budget_unverified_not_enforced": ("UNCLASSIFIED", "UNKNOWN (v2 budget)", "result.budget_decision is None (AttributeError); budget is unsupported in v3; v2 behavior not determined."),
 "test_sql_injection_inert": ("PRE_EXISTING", "NO", "Test asserts REJECTION (422/400) but the API treats input as data. Dynamic probes (7 payloads) -> 200, 0 rows, no SQL leak, table intact. Property that matters (inert) holds."),
 "test_rate_limiting": ("PRE_EXISTING", "NO", "conftest autouse relaxes limits to 1,000,000 and this test does not request strict_rate_limits. Direct repro with defaults: 10x401 then 5x429 (10/min enforced)."),
}
tot = dict(passed=0, failed=0, skipped=0); rows = []; n_mod = 0
for f in sorted(glob.glob(D + "/test_*.txt")):
    if "CONTAMINATED" in f: continue
    n_mod += 1; t = open(f, encoding="utf-8", errors="replace").read()
    for n, k in re.findall(r"(\d+) (passed|failed|skipped)", t.strip().splitlines()[-1]): tot[k] += int(n)
    for l in t.splitlines():
        if l.startswith("FAILED "):
            tid = l[7:].split(" - ")[0].strip().replace("\\", "/"); cls = next((v for k, v in CLS.items() if k in tid), ("UNCLASSIFIED", "UNKNOWN", ""))
            rows.append((tid, *cls))
with open("reports/e2e/BASELINE_FAILURES.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["test_id", "classification", "affects_production_contract", "evidence_or_next_step"]); w.writerows(rows)
by = {}
for r in rows: by[r[1]] = by.get(r[1], 0) + 1
print("TOTALS", tot, "modules", n_mod, "| classification counts", by)
open("reports/e2e/_baseline_totals.txt", "w").write(f"{tot['passed']} {tot['failed']} {tot['skipped']} {n_mod} {by}")
