"""Read-only Phase 29 four-item study. Run from the project with python -m scripts.compare_fc27_provider_sample."""
import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from backend.ingestion.fc27_source_evidence import (
    CARD_ATTRS, OCTOBER_ATTRS, PLAYER_FIELDS, SOURCES, name_key, normalize_item,
    number, read_snapshot,
)
from backend.services.demand_composition import compose_demand
from backend.services.engine_config import PRICE_FRESH_DAYS
from backend.services.formations import PROFILE_DIMENSIONS
from backend.services.v3_config import DEFAULT_V3_CONFIG

# Explicit study selection. The second ID is a candidate base for comparison only.
CASES = {192119: 192119, 231747: 231747, 67386507: 277643, 84163723: 277643}
FUT_GROUPS = {
    "paceAttributes": "acceleration sprint_speed",
    "shootingAttributes": "positioning finishing shot_power long_shots volleys penalties",
    "passingAttributes": "vision crossing free_kick_accuracy short_passing long_passing curve",
    "dribblingAttributes": "agility balance reactions ball_control dribbling_detail composure",
    "defendingAttributes": "interceptions heading_accuracy standing_tackle sliding_tackle defensive_awareness",
    "physicalityAttributes": "jumping stamina strength aggression",
    "goalkeeperAttributes": "gk_diving gk_handling gk_kicking gk_positioning gk_reflexes",
}
FACE = dict(pace="pac", shooting="sho", passing="pas", dribbling="dri", defending="def", physicality="phy")


def fut_paths():
    paths = {key: key for key in FACE}
    for group, fields in FUT_GROUPS.items():
        for key in fields.split():
            head, *rest = key.removeprefix("gk_").split("_")
            leaf = head + "".join(part.title() for part in rest)
            leaf = {"dribbling_detail": "dribbling", "defensive_awareness": "defenseAwareness"}.get(key, leaf)
            paths[key] = f"{group}.{leaf}"
    return paths


def demanded(position):
    return sorted({field for profile in PROFILE_DIMENSIONS for field, weight in compose_demand(
        position=position, tactical_profile=profile, lam=DEFAULT_V3_CONFIG.lam_default.value,
    ).vector.items() if weight > 0})


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def observed_stat(record, path):
    if record is None or not path:
        return None
    value = record
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if type(value) is int and 1 <= value <= 99 else None


def timestamp(value):
    try:
        time = datetime.fromisoformat(value)
        return time if time.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def quote_checks(quote, card, as_of, sandbox):
    reasons = []
    if sandbox:
        reasons.append("ILLUSTRATIVE_SANDBOX")
    for field, actual in (("name", card["player_name"]), ("club", card["club"]),
                          ("position", card["positions"].split(",")[0])):
        if name_key(quote.get(field) or "") != name_key(actual):
            reasons.append(field.upper() + "_MISMATCH")
    if quote.get("game") != "fc27" or quote.get("ea_id") != int(card["eaId"]):
        reasons.append("GAME_OR_ITEM_MISMATCH")
    if quote.get("rating") != int(card["overall"]):
        reasons.append("RATING_MISMATCH")
    market = quote.get("market")
    platforms = {"console": ("ps", "xbox", "console"), "pc": ("pc",)}
    if quote.get("platform") not in platforms.get(market, ()):
        reasons.append("PLATFORM_MISMATCH")
    if type(quote.get("price")) is not int or quote["price"] <= 0 or quote.get("availability") != "listed":
        reasons.append("NO_LISTED_PRICE")
    observed = timestamp(quote.get("observed_at"))
    checked = timestamp(quote.get("checked_at"))
    if not observed or not checked or not observed <= checked <= as_of:
        reasons.append("INVALID_TIME")
    elif as_of - observed > timedelta(days=PRICE_FRESH_DAYS) or quote.get("stale") is True:
        reasons.append("OUTSIDE_FRESHNESS_WINDOW")
    source_time = quote.get("futbin_updated_at") or quote.get("source_updated_at")
    if source_time is not None:
        upstream = timestamp(source_time)
        if not upstream or not checked or upstream > checked or as_of - upstream > timedelta(days=PRICE_FRESH_DAYS):
            reasons.append("SOURCE_TIMESTAMP_UNUSABLE")
    if quote.get("pending") is not False or quote.get("exact") is not True:
        reasons.append("PENDING_OR_INEXACT")
    return reasons


def identity_checks(card, base, details, entry, illustrative):
    """Corroborate candidate identifiers. Provider club/rarity IDs are namespace-specific."""
    reasons = []
    if details is None:
        reasons.append("FUTDB_SAMPLE_MISSING")
    if entry is None:
        reasons.append("FLUX_CATALOGUE_SAMPLE_MISSING")
    if illustrative:
        reasons.append("ILLUSTRATIVE_CATALOGUE")
    if details is not None and entry is not None:
        if not details.get("futBinId") or details["futBinId"] != entry.get("futbin_id"):
            reasons.append("SECOND_ITEM_CROSSWALK_UNVERIFIED")
    if details is not None:
        if details.get("resourceBaseId") != base or details.get("resourceId") != int(card["eaId"]):
            reasons.append("FUTDB_ID_CONFLICT")
        if str(details.get("version")) not in ("27", "FC27"):
            reasons.append("FUTDB_VERSION_UNVERIFIED")
        if details.get("rating") != int(card["overall"]) or details.get("position") != card["positions"].split(",")[0]:
            reasons.append("FUTDB_CARD_METADATA_CONFLICT")
    if entry is not None:
        if entry.get("player_id") != base or entry.get("ea_id") != int(card["eaId"]):
            reasons.append("FLUX_ID_CONFLICT")
        expected = (("club", "club"), ("league", "league"), ("nation", "nation"))
        if any(name_key(entry.get(k) or "") != name_key(card[v]) for k, v in expected):
            reasons.append("FLUX_AFFILIATION_CONFLICT")
        if entry.get("rating") != int(card["overall"]) or entry.get("position") != card["positions"].split(",")[0]:
            reasons.append("FLUX_CARD_METADATA_CONFLICT")
        rarities = {name_key(entry.get(k) or "") for k in ("rarity", "rarity_name")}
        accepted = {name_key(card["rarity"])}
        if card["rarity"] == "Rare":
            accepted.add("goldrare")
        if rarities.isdisjoint(accepted):
            reasons.append("RARITY_UNVERIFIED")
    for label, record, keys in (("FUTDB", details, ("name", "commonName")),
                                ("FLUX", entry, ("name",))):
        if record is not None and not any(name_key(record.get(k) or "") in
                {name_key(card["player_name"]), name_key(card["full_name"])} - {""} for k in keys):
            reasons.append(label + "_NAME_UNVERIFIED")
    return reasons


def sample_index(rows, key):
    index = {}
    for row in rows:
        item = row[key]
        if item in index:
            raise ValueError(f"Duplicate sample identity {item}")
        index[item] = row
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=timestamp, required=True)
    parser.add_argument("--futdb-dir", type=Path, help="Evaluation PlayerResponse files named <EA item ID>.json")
    parser.add_argument("--catalogue", type=Path, help="DataFluxor card search response")
    parser.add_argument("--prices", type=Path, nargs="+", default=[], help="DataFluxor price responses by market")
    args = parser.parse_args()
    if args.as_of is None:
        parser.error("--as-of needs an ISO timestamp with UTC offset")
    tables = [sample_index(read_snapshot(args.archives, spec)[1], spec.key)
              for spec in (SOURCES[0], SOURCES[2], SOURCES[3])]
    players, october, cards = tables
    catalogue = load_json(args.catalogue) if args.catalogue else {}
    if args.catalogue and (catalogue.get("success") is not True or not isinstance(catalogue.get("data", {}).get("cards"), list)):
        raise ValueError("Expected a successful DataFluxor catalogue response")
    samples = sample_index(catalogue.get("data", {}).get("cards", []), "ea_id")
    prices = [load_json(path) for path in args.prices]
    if any(p.get("success") is not True or not isinstance(p.get("data", {}).get("items"), list) for p in prices):
        raise ValueError("Expected a successful DataFluxor price response")
    paths = fut_paths()
    rows, cases = [], []
    for item, base in CASES.items():
        card = cards[str(item)]
        canonical = normalize_item(card, october=False)
        position = canonical["position_primary"]
        needed = demanded(position)
        alt = october.get(str(item))
        alt_attrs = normalize_item(alt, october=True)["attributes"] if alt else {}
        player = players[str(base)]
        details = None
        if args.futdb_dir and (file := args.futdb_dir / f"{item}.json").is_file():
            details = load_json(file)["player"]
            if details is not None and details.get("resourceId") != item:
                raise ValueError(f"FUT-DB file {item} returned a different resourceId")
        entry = samples.get(item)
        identity_issues = identity_checks(card, base, details, entry, catalogue.get("sandbox") is True and entry is not None)
        for key in needed:
            source_field = next((k for k, v in PLAYER_FIELDS.items() if v == key), None)
            baseline_value = player.get(source_field)
            flux_path = "stats." + FACE[key] if key in FACE else None
            rows.append(dict(item=item, primary_position=position, attribute=key,
                             game_player_context=number(baseline_value, 1, 99) if baseline_value else None,
                             october_field=next((k for k,v in OCTOBER_ATTRS.items() if v == key), None),
                             october_exact_item=alt_attrs.get(key),
                             card_field=next((k for k,v in CARD_ATTRS.items() if v == key), None),
                             card_observation=canonical["attributes"].get(key),
                             futdb_schema_path=paths.get(key), futdb_returned=observed_stat(details, paths.get(key)),
                             flux_sample_path=flux_path, flux_returned=observed_stat(entry, flux_path)))
        subset = rows[-len(needed):]
        card_quotes = []
        for envelope in prices:
            for q in envelope["data"]["items"]:
                if q.get("ea_id") == item:
                    issues = quote_checks(q, card, args.as_of, envelope.get("sandbox") is True)
                    if entry is not None and (not q.get("rarity_id") or q.get("rarity_id") != entry.get("rarity_id")):
                        issues.append("PRICE_CATALOGUE_RARITY_UNVERIFIED")
                    card_quotes.append(dict(platform=q.get("platform"), market=q.get("market"),
                        observed_at=q.get("observed_at"), checked_at=q.get("checked_at"),
                        rarity=q.get("rarity"), price_source=q.get("price_source"),
                        issues=issues, independently_corroborated=not (issues or identity_issues)))
        cases.append(dict(item=item, candidate_base=base, name=card["player_name"], rarity=card["rarity"],
                          rating=canonical["overall_rating"], positions_raw=card["positions"],
                          eligible_local=canonical["observed_positions"], issues=canonical["issues"],
                          base_club_matches=name_key(player["club"]) == name_key(card["club"]),
                          provider_identity_issues=identity_issues,
                          october_exact_base=alt["base_id"] if alt else None,
                          styles=canonical["playstyles"], role_kind=canonical["role_observation_kind"],
                          official_role_eligibility=None, demanded=len(needed),
                          counts={col: sum(row[col] is not None for row in subset) if available else None
                                  for col, available in (("card_observation", True), ("october_exact_item", alt is not None),
                                      ("game_player_context", True), ("futdb_returned", details is not None),
                                      ("flux_returned", entry is not None), ("futdb_schema_path", True),
                                      ("flux_sample_path", True))},
                          futdb_identity_and_metadata={k: details.get(k) for k in (
                              "resourceBaseId", "version", "name", "rating", "club", "rarity", "position",
                              "positionAlternatives", "roles", "rolesPlusPlus", "playStyles", "playStylesPlus"
                          )} if details is not None else None,
                          datafluxor_catalogue_base=entry.get("player_id") if entry else None,
                          datafluxor_catalogue_sandbox=catalogue.get("sandbox") if entry else None,
                          price_candidates=card_quotes))
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "field_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    report = dict(as_of=args.as_of.isoformat(), config=DEFAULT_V3_CONFIG.config_version,
                  scope="FOUR_ITEM_RESEARCH_ONLY", profiles=list(PROFILE_DIMENSIONS),
                  source_csv_sha256={s.archive: s.sha for s in (SOURCES[0], SOURCES[2], SOURCES[3])},
                  cases=cases, public_release=False, price_reconciliation="REQUIRES_VERIFIED_CROSS_PROVIDER_IDENTITY")
    (args.output / "observations.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
