"""Generates RECOMMENDATION_STABILITY_RESULTS.json by running systematic perturbations on FC27 cohort."""
import csv
import json
from pathlib import Path
from uuid import UUID

from backend.domain.card_model import Candidate, DataStatus, GameVersionCode, PlayerAttributes
from backend.services.fc27_card_research import ResearchCards, _card_reference
from backend.services.recommendation_stability import RecommendationStabilityEngine

ROOT = Path(__file__).resolve().parents[1]
COHORT_CSV = ROOT / "artifacts/phase31/TOP_100_BASE_CARDS.csv"
OUT_FILE = ROOT / "artifacts/phase35/RECOMMENDATION_STABILITY_RESULTS.json"


def load_cohort():
    with COHORT_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cards = []
    for r in rows:
        item_id = UUID(r["card_item_id"])
        styles = json.loads(r["playstyles"])
        cards.append(Candidate(
            entity_type="ut_card",
            entity_id=item_id,
            game_version=GameVersionCode.FC27,
            name=r["name"],
            position_primary=r["primary_position"],
            secondary_positions=json.loads(r["positions"])[1:],
            attributes=PlayerAttributes(json.loads(r["attributes"])),
            overall_rating=int(r["overall"]),
            rarity=r["rarity"],
            playstyles_base=styles["base"],
            playstyles_plus=styles["plus"],
            playstyle_data_published=bool(styles["base"] or styles["plus"]),
            data_status=DataStatus.RESEARCH_ONLY,
            extra={
                "source_item_id": r.get("source_item_id"),
                "identity_status": r.get("identity_status"),
                "confirmed_base_id": r.get("confirmed_base_id") or r.get("candidate_base_player_id") or None,
                "editorial_role_fit": r.get("editorial_role_fit") or None,
                "position_issues": json.loads(r["position_issues"]) if r.get("position_issues") and r["position_issues"].startswith("[") else [],
            },
        ))
    return cards


def main():
    cards = load_cohort()
    ref = _card_reference()
    service = ResearchCards(ref, cards)
    engine = RecommendationStabilityEngine(service)
    
    # Run stability analysis for key positions: ST and CB
    st_results = engine.evaluate_position_stability(
        position="ST",
        formation="4-3-3",
        test_formations=["4-3-3", "4-4-2", "3-5-2"],
    )
    cb_results = engine.evaluate_position_stability(
        position="CB",
        formation="4-3-3",
        test_formations=["4-3-3", "3-5-2", "5-3-2"],
    )
    
    full_report = {
        "report_title": "EA FC Intelligence Recommendation Stability Lab Results",
        "phase": "Phase 35",
        "engine_version": "V3.2.1",
        "dataset_release": "fc27-card-items-local-r1",
        "positions_analyzed": {
            "ST": st_results,
            "CB": cb_results,
        },
    }
    
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
    print(f"Stability results successfully written to {OUT_FILE}")


if __name__ == "__main__":
    main()
