#!/usr/bin/env python3
"""Ingest the FC27 card identity/reference package as RESEARCH_ONLY (migrations 009–010).

FAIL CLOSED:
  * refuses unless --approve-research-only-ingest AND --approved-by are given (the project registry
    lists `futgg` as NOT_PERMITTED); an independently reviewed permission
    record, evidence file and pinned package inventory are also required;
  * refuses if the package fails the integrity checks below (re-derived, not trusted from its self-report);
  * everything runs in ONE transaction; DB triggers enforce FC27-only + RESEARCH_ONLY + registered source;
  * nothing is resolved silently: package conflicts/duplicates and audit findings are stored as OPEN flags;
  * no price column exists; no per-card attribute/rarity/position is invented.
Idempotent (re-run inserts nothing new). Usage:
  python scripts/ingest_fc27_card_identity.py --package-dir <FC27_CARD_DATASET> --approve-research-only-ingest --approved-by "<name>"
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, hashlib, json, os, re, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_ID = "futgg_fc27_identity_research"
URL_RE = re.compile(r"^https://www\.fut\.gg/players/(\d+)-([^/]+)/(\d+)-(\d+)/$")


def die(msg: str) -> None:
    print(f"REFUSED: {msg}"); sys.exit(2)


def rd(p: Path):
    with open(p, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)) or not all(fields):
            die(f"invalid CSV header: {p.name}")
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            die(f"ragged CSV: {p.name}")
        return rows


def ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def log_window(log, needle):
    pts = []
    for r in log:
        if needle in r["saved_to"] or needle in r["url"]:
            d, rest = r["timestamp_utc"][:10], r["timestamp_utc"][11:]
            pts += [dt.datetime.fromisoformat(f"{d}T{hm}:00+00:00") for hm in re.findall(r"\d\d:\d\d", rest)]
    if not pts:
        die(f"no request-log row for {needle}")
    return min(pts), max(pts)


# Maintainer-reviewed evidence lives outside the supplied package. No approval ships today.
APPROVAL = ROOT / "data" / "approvals" / "fc27_card_identity.json"
REQUIRED = {
    "manifests/DATASET_MANIFEST.json", "provenance/raw_file_hashes.csv", "provenance/request_log.csv",
    "conflicts/CARD_DUPLICATES.csv", "conflicts/CONFLICT_QUEUE.csv",
    *("canonical/" + name + ".csv" for name in (
        "fc27_card_index", "fc27_game_players", "fc27_rarities", "fc27_roles_reference",
        "fc27_playstyles_reference", "fc27_ut_cards_observed_sample")),
}


def check_approval():
    if not APPROVAL.is_file():
        die("missing independently reviewed research permission record for futgg")
    record = json.loads(APPROVAL.read_text(encoding="utf-8"))
    today = dt.datetime.now(dt.timezone.utc).date()
    if (record.get("source") != "futgg" or record.get("scope") != "FC27_CARD_IDENTITY_RESEARCH_ONLY"
            or not record.get("reviewer") or not record.get("applicable_terms")
            or not dt.date.fromisoformat(record["review_date"]) <= today <= dt.date.fromisoformat(record["expires"])
            or not record.get("snapshot_id")):
        die("invalid or expired permission record")
    evidence = (APPROVAL.parent / record["permission_file"]).resolve()
    if (not evidence.is_relative_to(APPROVAL.parent.resolve()) or not evidence.is_file()
            or not evidence.stat().st_size or hashlib.sha256(evidence.read_bytes()).hexdigest() != record["permission_sha256"]):
        die("reviewed permission document unavailable or changed")
    return record


def verify_inventory(pkg, record):
    inventory = record["files"]
    if not REQUIRED <= inventory.keys() or not any(k.startswith("raw/") for k in inventory):
        die("approved inventory lacks required raw, canonical or provenance files")
    for name, meta in inventory.items():
        p = (pkg / name).resolve()
        if not p.is_relative_to(pkg.resolve()) or not p.is_file() or not p.stat().st_size:
            die(f"missing or invalid required file: {name}")
        if hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
            die(f"hash mismatch: {name}")
        if p.suffix.lower() == ".csv":
            rows = rd(p)
            if len(rows) != meta["rows"]:
                die(f"row count mismatch: {name}")
            if name.startswith("canonical/") and any(row.get("snapshot_id") != record["snapshot_id"] for row in rows):
                die(f"snapshot mismatch: {name}")
    man = json.loads((pkg / "manifests/DATASET_MANIFEST.json").read_text(encoding="utf-8-sig"))
    if (man["snapshot_id"] != record["snapshot_id"] or man["dataset_version"] not in ("0.1.0-research", "v0.1.0-research") or not man["dataset_name"]):
        die("unsupported package version or snapshot")
    return man


def verify_package(pkg: Path):
    idx = rd(pkg / "canonical/fc27_card_index.csv"); gp = rd(pkg / "canonical/fc27_game_players.csv")
    rar = rd(pkg / "canonical/fc27_rarities.csv"); ps = rd(pkg / "canonical/fc27_playstyles_reference.csv")
    roles = rd(pkg / "canonical/fc27_roles_reference.csv"); dups = rd(pkg / "conflicts/CARD_DUPLICATES.csv")
    if len(idx) != 20175 or len({r["card_id"] for r in idx}) != 20175: die("card index: expected 20,175 unique card_id")
    for r in idx:
        m = URL_RE.match(r["card_url"])
        if not m or m.group(3) != "27" or (m.group(1), m.group(2), m.group(4)) != (r["game_player_id"], r["player_slug"], r["card_id"]):
            die(f"card index row inconsistent / not FC27: {r['card_url']}")
    agg = collections.Counter(r["game_player_id"] for r in idx)
    if {r["game_player_id"]: int(r["fc27_card_count"]) for r in gp} != dict(agg): die("game_players is not a faithful aggregation of the card index")
    if len(rar) != 26 or sum(int(r["card_count"]) for r in rar) != 20189: die("rarities: expected 26 rows summing to 20,189")
    urls = {r["card_url"] for r in idx}
    if len(gp) != len(agg) or len(urls) != len(idx):
        die("duplicate player identity or canonical card URL")
    slugs = {row["game_player_id"]: row["player_slug"] for row in gp}
    if any(slugs[r["game_player_id"]] != r["player_slug"] for r in idx):
        die("contradictory source player slug")
    if any(d[k] not in urls for d in dups for k in ("record_a", "record_b")):
        die("duplicate references a URL absent from the index")
    raw = pkg / "raw"
    hashes = rd(pkg / "provenance/raw_file_hashes.csv")
    names = {r["file"] for r in hashes}
    if not raw.is_dir() or not hashes or len(names) != len(hashes) or names != {p.name for p in raw.iterdir() if p.is_file()}:
        die("raw files and hash inventory differ")
    for r in hashes:
        if hashlib.sha256((raw / r["file"]).read_bytes()).hexdigest() != r["sha256"]:
            die(f"raw hash mismatch: {r['file']}")
    raw_note = "raw sha256 verified"
    return idx, rar, ps, roles, dups, raw_note


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package-dir", required=True); ap.add_argument("--approve-research-only-ingest", action="store_true")
    ap.add_argument("--approved-by", default=""); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.approve_research_only_ingest or not a.approved_by.strip():
        die("owner approval required (--approve-research-only-ingest --approved-by NAME): registry lists futgg as NOT_PERMITTED")
    record = check_approval()
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        original = Path(a.package_dir).resolve()
        for name in record["files"]:
            source, dest = (original / name).resolve(), (pkg / name).resolve()
            if not source.is_relative_to(original) or not dest.is_relative_to(pkg) or not source.is_file():
                die(f"required file outside package or missing: {name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        man = verify_inventory(pkg, record)
        inventory_hash = hashlib.sha256(json.dumps(record["files"], sort_keys=True).encode()).hexdigest()
        return ingest(pkg, man, a, inventory_hash)


def ingest(pkg, man, a, inventory_hash):
    import psycopg
    idx, rar, ps, roles, dups, raw_note = verify_package(pkg)
    log = rd(pkg / "provenance/request_log.csv"); conflicts = rd(pkg / "conflicts/CONFLICT_QUEUE.csv")
    SNAP = man["snapshot_id"]
    w_rar, w_site, w_ps, w_roles = (log_window(log, n) for n in ("fut_gg_rarities", "sitemap27_p", "sitemap_playstyles", "fut_gg_roles_"))
    dup_extra = collections.Counter(d["record_a"] for d in dups)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return write_transaction(conn, a, inventory_hash, man, SNAP, idx, rar, ps, roles, dups, raw_note, conflicts, dup_extra, w_rar, w_site, w_ps, w_roles)


def write_transaction(conn, a, inventory_hash, man, SNAP, idx, rar, ps, roles, dups, raw_note, conflicts, dup_extra, w_rar, w_site, w_ps, w_roles):
    cur = conn.cursor(); S = {"raw": raw_note, "approved_by": a.approved_by}
    cur.execute("select id from game_version where code='FC27'"); r = cur.fetchone()
    if not r: die("game_version FC27 missing")
    GV = r[0]
    cur.execute("select usage_status, legal_gate from source_registry where source_id=%s", (SOURCE_ID,)); r = cur.fetchone()
    if not r or r[0] != "RESEARCH_ONLY": die(f"source {SOURCE_ID} not registered RESEARCH_ONLY (run migration 009)")
    cur.execute("select usage_status from source_registry where source_id='futgg'"); S["registry_futgg_usage_status_unchanged"] = (cur.fetchone() or [None])[0]
    cur.execute("LOCK TABLE card_source_snapshot IN SHARE ROW EXCLUSIVE MODE")
    cur.execute("SELECT snapshot_id, inventory_sha256 FROM card_source_snapshot WHERE game_version_id=%s", (GV,))
    if any(row != (SNAP, inventory_hash) for row in cur.fetchall()):
        die("existing FC27 snapshot differs or lacks a verified inventory; refusing to merge historical snapshots")
    cur.execute("""insert into card_source_snapshot(snapshot_id, inventory_sha256, game_version_id, source_id, package_name, package_version, declared_window_start, declared_window_end,
                   license_note, retrieved_at_semantics, audit_status) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""",
        (SNAP, inventory_hash, GV, SOURCE_ID, man["dataset_name"], man["dataset_version"], ts("2026-09-30T07:28:00Z"), ts("2026-09-30T08:10:00Z"),
         "RESEARCH-ONLY / NO REDISTRIBUTION / NO ML TRAINING (package LEGAL_ACCESS_REPORT); registry entry futgg is NOT_PERMITTED",
         "package retrieved_at values are build/processing times (08:31-08:56Z), AFTER the declared 07:28-08:10Z window; acquired_from/to are taken from provenance/request_log.csv",
         "INDEPENDENT_AUDIT_PARTIAL (Phase 24; see audit report)"))
    def ins(sql, rows): cur.executemany(sql, rows); return len(rows)
    ex = lambda w: (w[0], w[1])
    S["rarities"] = ins("""insert into fc27_rarity_catalogue(game_version_id,futgg_rarity_id,ea_rarity_id,rarity_name,slug,card_count,is_pseudo_rarity,source_id,snapshot_id,package_retrieved_at,acquired_from,acquired_to)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""",
        [(GV, int(r["futgg_rarity_id"]), int(r["ea_rarity_id"]), r["rarity_name"], r["slug"], int(r["card_count"]), int(r["ea_rarity_id"]) < 0, SOURCE_ID, SNAP, ts(r["retrieved_at"]), *ex(w_rar)) for r in rar])
    S["identity_rows_submitted"] = ins("""insert into fc27_card_identity(game_version_id,source_player_id,source_card_id,player_slug,card_url,is_base_style,sitemap_lastmod,sitemap_row_count,source_id,snapshot_id,package_retrieved_at,acquired_from,acquired_to)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""",
        [(GV, r["game_player_id"], r["card_id"], r["player_slug"], r["card_url"], r["card_id"] == r["game_player_id"], r["sitemap_lastmod"] or None, 1 + dup_extra.get(r["card_url"], 0), SOURCE_ID, SNAP, ts(r["retrieved_at"]), *ex(w_site)) for r in idx])
    S["roles"] = ins("""insert into fc27_role_reference(game_version_id,position_page,role_position_id,role_futgg_id,role_slug,role_name,role_plus_ea_id,role_plus_plus_ea_id,focus_name,source_id,snapshot_id,package_retrieved_at,acquired_from,acquired_to)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""",
        [(GV, r["position_page"], int(r["role_position_id"]), int(r["role_futgg_id"]), r["role_slug"], r["role_name"], int(r["role_plus_ea_id"]) if r["role_plus_ea_id"] else None,
          int(r["role_plus_plus_ea_id"]) if r["role_plus_plus_ea_id"] else None, r["focus_name"], SOURCE_ID, SNAP, ts(r["retrieved_at"]), *ex(w_roles)) for r in roles])
    pcount = collections.Counter(r["slug"] for r in ps); first = {}
    for r in ps: first.setdefault(r["slug"], r)
    S["playstyle_pages_unique"] = ins("""insert into fc27_playstyle_page_reference(game_version_id,slug,name_derived_from_slug,sitemap_row_count,source_id,snapshot_id,package_retrieved_at,acquired_from,acquired_to)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""", [(GV, s, first[s]["name_normalized"], n, SOURCE_ID, SNAP, ts(first[s]["retrieved_at"]), *ex(w_ps)) for s, n in pcount.items()])
    S["playstyle_sitemap_rows_collapsed"] = len(ps)
    # A provider ID alone is insufficient to establish a reviewed player link.
    S["identity_rows_resolved_to_game_player"] = 0
    # ---- open flags ----
    flags = []
    def flag(ft, ent, field=None, sa=None, va=None, sb=None, vb=None, status="OPEN", by="claude_audit", **details):
        flags.append((GV, SNAP, SOURCE_ID, ft, ent, field, sa, None if va is None else str(va), sb, None if vb is None else str(vb), status, by, json.dumps(details, default=str)))
    for d in dups: flag("DUPLICATE_SITEMAP_ROW", d["record_a"], None, by="glm_package", evidence=d["evidence"], package_resolution=d["resolution"])
    for c in conflicts: flag("PACKAGE_CONFLICT", c["entity"], c["field"], c["source_a"], c["value_a"], c["source_b"], c["value_b"], by="glm_package", authority=c["authority"], reason=c["reason"], package_resolution=c["resolution"])
    flag("STRUCTURAL_QUESTION", "rare_bucket_special_id_cards", "count", "package", 676, None, None, by="glm_package", note="special-ID cards inside the Rare bucket; composition unknown",
         claude_audit_note="19,514 (page Rare count) = 18,824 base-style + 676 + 14 = the 14 duplicate sitemap rows; consistent with duplicates being counted in the Rare bucket. INFERENCE ONLY, not resolved.")
    flag("AUDIT_FINDING", "fc27_playstyles_reference", "unique_pages", "package", "141 PlayStyle pages", "raw sitemap_playstyles.xml (re-derived)", "41 unique pages (141 <loc> rows incl. duplicates)", note="do not load 141 as definitions")
    flag("AUDIT_FINDING", "fc27_playstyles_reference", "version_scope", "package", "FC27 version wall enforced", "audit", "URLs carry no game-version marker; 5 slugs (aerial, flair, power header, quick reflexes, trivela) absent from our FC26 and FC27 playstyle vocab", note="FC27 membership unverified")
    flag("AUDIT_FINDING", "package_retrieved_at", "semantics", "package", "retrieved_at = fetch time in snapshot window 07:28-08:10Z", "audit", "canonical retrieved_at 08:31-08:56Z; 43/48 hash-table times outside window; 15 disagree with filename timestamps", note="treated as processing time; request log gives acquisition time")
    flag("REGISTRY_POLICY", "source_registry:futgg", "usage_status", "project registry", "NOT_PERMITTED", "package", "RESEARCH-ONLY (automated extraction PARTIAL)", note="owner decision required; futgg entry left unchanged; separate research source registered")
    flag("AUDIT_FINDING", "rarity_count_reconciliation", "independence", "package", "two independent surfaces agree on 20,189", "audit", "rarities page and sitemap are from the same operator; not independent", status="NOTED")
    flag("AUDIT_FINDING", "rarity:destined-for-glory", "card_count", "raw rarities page", "33 (2 fresh embedded copies + visible label)", "raw rarities page", "32 (1 stale embedded copy, older latestPlayerAt)", status="NOTED", note="package uses 33; counts drift")
    flag("AUDIT_FINDING", "fc27_game_players.first_card_url", "rule", "package", "first_card_url (rule undocumented)", "audit", "reproduces only as 'first row in sitemap file order'; lowest-card-id rule matches 19,525/19,620", status="NOTED", note="fc27_card_player_spine uses the explicit lowest-card-id rule")
    flag("AUDIT_FINDING", "package_claim:u+fffd_in_raw", "reproduction", "package", "U+FFFD in accented names in raw card pages", "audit", "0 U+FFFD bytes in all delivered raw/canonical files", status="NOTED")
    flag("AUDIT_FINDING", "canonical_schema", "source_id", "audit task (a)", "every row carries source_id", "audit", "fc27_playstyles_reference.csv and fc27_ut_cards_observed_sample.csv have NO source_id column (file-level attribution only, in provenance_map.json)", note="schema defect against the audit requirement")
    flag("AUDIT_FINDING", "package_premise", "raw_and_scripts", "audit prompt", "raw/ archive and pipeline scripts were not uploaded", "audit", "raw/ (48 files, sha256 verified) and processed/*.py WERE in the upload", status="NOTED")
    flag("AUDIT_FINDING", "request_log", "granularity", "package", "41 fut.gg requests at 1.5-2 s spacing", "audit", "41 reconcile only by expanding aggregated row 23 (sitemap pages 2-21); timestamps are minute-resolution so spacing is unverifiable; log not strictly chronological (rows 27, 47)", status="NOTED")
    # player-set decomposition + name disagreements (computed against our FC27 game_player rows)
    cur.execute("select gp.source_player_id::text, gp.normalized_name from game_player gp join game_version v on v.id=gp.game_version_id where v.code='FC27'"); db = dict(cur.fetchall())
    pk = {r["game_player_id"] for r in idx}; slug = {r["game_player_id"]: r["player_slug"] for r in idx}
    dbonly, pkonly = sorted(set(db) - pk, key=int), sorted(pk - set(db), key=int)
    flag("PLAYER_SET_DIFFERENCE", "fc27_game_player_dataset_minus_package", "count", "our FC27 game_player", len(db), "package", len(pk), count=len(dbonly), ids=dbonly, note="launch players with no fut.gg card page")
    flag("PLAYER_SET_DIFFERENCE", "package_minus_fc27_game_player_dataset", "count", "package", len(pk), "our FC27 game_player", len(db), count=len(pkonly), ids=pkonly, note="fut.gg players absent from launch list (sample: legends/icons)")
    dis = []
    for i in sorted(pk & set(db), key=int):
        a_, b_ = set(slug[i].replace("-", " ").split()), set((db[i] or "").lower().split())
        if not (a_ and b_ and (a_ & b_)): dis.append(i)
    for i in dis: flag("IDENTITY_NAME_DISAGREEMENT", f"player:{i}", "name", "package slug", slug[i], "our FC27 game_player", db[i], note="same EA id, names share no token; review before trusting the join")
    n0 = 0
    for f in flags:
        cur.execute("""insert into fc27_card_open_flag(game_version_id,snapshot_id,source_id,flag_type,entity,field,source_a,value_a,source_b,value_b,status,raised_by,details)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) on conflict do nothing""", f); n0 += cur.rowcount
    S["flags_inserted"] = n0; S["flags_submitted"] = len(flags); S["identity_name_disagreements"] = len(dis)
    expected_counts = {"fc27_card_identity": len(idx), "fc27_rarity_catalogue": len(rar),
                       "fc27_role_reference": len(roles), "fc27_playstyle_page_reference": len(first)}
    S["snapshot_counts"] = {}
    for table, expected in expected_counts.items():
        cur.execute(f"SELECT count(*) FROM {table} WHERE snapshot_id=%s AND source_id=%s", (SNAP, SOURCE_ID))
        actual = cur.fetchone()[0]
        if actual != expected:
            die(f"{table} snapshot count {actual} != expected {expected}")
        S["snapshot_counts"][table] = actual
    if a.dry_run: conn.rollback(); S["dry_run"] = "ROLLED BACK"
    else: conn.commit()
    out = ROOT / "artifacts" / "phase26" / "fc27_card_identity_ingest_report.json"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(S, indent=2, default=str), encoding="utf-8"); print(json.dumps(S, indent=2, default=str)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
