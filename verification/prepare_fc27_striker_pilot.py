"""Freeze the FC27 high-press versus counterattack striker pilot from the Phase 31 export."""
import csv
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from backend.domain.card_model import Candidate, DataStatus, GameVersionCode, PlayerAttributes
from backend.domain.user_model import UserRequirements
from backend.services.fc27_card_research import SNAPSHOT, _card_reference, digest
from backend.services.performance_cohort import COHORT_DIGEST
from backend.services.recommendation_engine_v3 import ENGINE_VERSION, RecommendationEngineV3
from backend.services.v3_response_blocks import evidence_gap

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "artifacts/phase31"
OUT = ROOT / "artifacts/striker_pilot"
PILOT = "fc27-st-press-counter-r1"
PROFILES = ("HIGH_PRESS", "COUNTER_ATTACK")
METRICS = dict(zip(PROFILES, ("tackles_won", "shots_on_target")))


def predict():
    source = COHORT / "TOP_100_BASE_CARDS.csv"
    manifest = json.loads((COHORT / "TOP_100_COHORT_MANIFEST.json").read_text(encoding="utf-8"))
    reference = _card_reference()
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not (
        manifest["cohort_digest"] == COHORT_DIGEST and len(rows) == manifest["top_100"]
        and all((r["snapshot_id"], r["release_id"]) == (SNAPSHOT, reference.version) for r in rows)
    ):
        raise ValueError("Unexpected Phase 31 cohort export")
    cards = {}
    for row in rows:
        if row["primary_position"] != "ST":
            continue
        item = UUID(row["card_item_id"])
        styles = json.loads(row["playstyles"])
        cards[item] = Candidate(
            entity_type="ut_card", entity_id=item, game_version=GameVersionCode.FC27, name=row["name"],
            position_primary="ST", secondary_positions=json.loads(row["positions"])[1:],
            attributes=PlayerAttributes(json.loads(row["attributes"])), overall_rating=int(row["overall"]),
            rarity=row["rarity"], playstyles_base=styles["base"], playstyles_plus=styles["plus"],
            playstyle_data_published=bool(styles["base"] or styles["plus"]), data_status=DataStatus.RESEARCH_ONLY,
            extra={"source_item_id": row["source_item_id"]},
        )
    engine = RecommendationEngineV3(reference=reference)
    context = {"game_version": "FC27", "entity_scope": "ut_card", "formation": "4-3-3", "slot": "ST", "position": "ST"}
    outcomes = {}
    for profile in PROFILES:
        req = UserRequirements(**context, tactical_profile=profile, limit=len(cards))
        outcomes[profile] = engine.recommend(list(cards.values()), req)
    leaders = [outcomes[p].ranked[0].context.candidate_entity_id for p in PROFILES]
    if leaders[0] == leaders[1]:
        raise ValueError("No leader reversal in the frozen striker subgroup")
    selected = {}
    comparisons = {}
    for profile, expected in zip(PROFILES, leaders):
        result = outcomes[profile]
        contexts = {ranked.context.candidate_entity_id: (rank, ranked.context)
                    for rank, ranked in enumerate(result.ranked, start=1)}
        predicted = []
        for item in (expected, next(l for l in leaders if l != expected)):
            rank, scored = contexts[item]
            card = cards[item]
            label = "A" if item == leaders[0] else "B"
            selected[label] = {"name": card.name, "card_item_id": str(item),
                               "source_item_id": card.extra["source_item_id"],
                               "overall": card.overall_rating, "source_rarity": card.rarity}
            predicted.append((label, rank, scored))
        gap = evidence_gap(predicted[0][2], predicted[1][2], engine.config.tie_epsilon.value)
        if gap["status"] != "CLEAR_SEPARATION":
            raise ValueError("The top picks do not have clearly separated model scores")
        comparisons[profile] = {
            "primary_outcome_per_90": METRICS[profile],
            "hypothesis": f"{predicted[0][0]} has a higher observed rate than {predicted[1][0]}",
            "ranked_strikers": len(contexts),
            "predictions": [{"card": label, "cohort_striker_rank": rank, "score": s.r, "upper": s.r_hi,
                             "coverage": s.coverage_kappa} for label, rank, s in predicted],
            "decision_evidence": gap,
        }
    return {"protocol_key": PILOT, "engine": ENGINE_VERSION, "config": engine.config.config_version,
            "research_only": True, "reference": reference.version, "reference_sha256": reference.content_hash,
            "snapshot": SNAPSHOT, "cohort_digest": COHORT_DIGEST,
            "top_100_export_sha256": sha256(source.read_bytes()).hexdigest(), "context": context,
            "cards": selected, "tactics": comparisons, "match_observations": 0}


def schedule(report):
    for session, blocks in enumerate((
        (("HIGH_PRESS", "AB"), ("COUNTER_ATTACK", "BA")),
        (("COUNTER_ATTACK", "AB"), ("HIGH_PRESS", "BA")),
    ), start=1):
        for block, (profile, arms) in enumerate(blocks, start=1):
            for order, arm in enumerate(arms, start=1):
                match_key = f"{PILOT}-s{session}-b{block}-m{order}"
                card = report["cards"][arm]
                yield {"protocol_key": PILOT, "session_key": f"s{session}", "block_key": f"s{session}-b{block}",
                       "order": order, "match_key": match_key, "tactical_profile": profile, "card": arm,
                       "name": card["name"], "source_item_id": card["source_item_id"], "card_item_id": card["card_item_id"],
                       "formation": "4-3-3", "slot": "ST", "position": "ST", "controller": "HUMAN",
                       "match_date": "", "game_patch": "", "platform": "", "game_mode": "", "role": "",
                       "setup_key": "", "opponent_context": "", "skill_context": "", "minutes": "",
                       "tackles_won": "", "interceptions": "", "shots": "", "shots_on_target": "", "goals": "",
                       "evidence_locator": "", "deviation": ""}


def main():
    report = predict()
    report["prediction_sha256"] = digest(report)
    rows = list(schedule(report))
    OUT.mkdir(parents=True, exist_ok=True)
    prediction_path = OUT / "FROZEN_PREDICTIONS.json"
    prediction = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if prediction_path.exists() and prediction_path.read_text(encoding="utf-8") != prediction:
        raise ValueError("Frozen predictions differ. Create a new protocol version.")
    if not prediction_path.exists():
        prediction_path.write_text(prediction, encoding="utf-8")
    sheet = OUT / "MATCH_SHEET.csv"
    if not sheet.exists():
        with sheet.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
