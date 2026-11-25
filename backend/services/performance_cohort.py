"""Selection and provenance for the pinned FC27 base-item research cohort."""
from collections import Counter
from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

from backend.domain.card_model import ALL_ATTRS
from backend.ingestion.fc27_source_evidence import SOURCES
from backend.services.fc27_card_research import MEMBERS_DIGEST, RELEASE, SNAPSHOT, SOURCE, digest, staged_cards
from backend.services.scoring_config import POSITION_ATTRIBUTE_WEIGHTS


COHORT_VERSION = "fc27-base-performance-r1"
COHORT_DIGEST = "2e35cec585bf2b896660f65213090128a5ca044374d059ba0cab6c41d46b7d63"


def build_cohort(rows):
    eligible = []
    for row in rows:
        item, link = row["normalized"], row["identity_review"]
        source_id = row["record_id"]
        if (item["rarity"] == "Rare" and source_id.isdecimal()
                and item["position_primary"] in POSITION_ATTRIBUTE_WEIGHTS
                and item["overall_rating"] is not None
                and link["status"] != "CONFLICTED"
                and link["direct_rating"] == item["overall_rating"]
                and link["candidate_base_id"] in (None, source_id)):
            eligible.append(row)
    eligible.sort(key=lambda row: (-row["normalized"]["overall_rating"], int(row["record_id"]), row["record_id"]))
    top = eligible[:100]
    if len(top) != 100:
        raise ValueError("Fewer than 100 eligible base-item candidates")
    # Independent control: take the best three outside the top 100 per primary position.
    controls = []
    for position in sorted(POSITION_ATTRIBUTE_WEIGHTS):
        controls.extend([row for row in eligible[100:] if row["normalized"]["position_primary"] == position][:3])

    def entry(row, group, rank):
        item, link = row["normalized"], row["identity_review"]
        source_id = row["record_id"]
        attributes = {field: item["attributes"].get(field) for field in ALL_ATTRS}
        return {
            "cohort": group, "rank": rank, "name": item["player_name"] or item["full_name"],
            "card_item_id": str(uuid5(NAMESPACE_URL, SNAPSHOT + "/" + source_id)),
            "source_item_id": source_id,
            "base_player_id": link["candidate_base_id"] if link["status"] == "RESOLVED" else None,
            "candidate_base_player_id": source_id,
            "identity_status": link["status"], "identity_conflict": link["direct_player_id_rating_conflict"],
            "game_version": "FC27", "release_id": RELEASE, "snapshot_id": SNAPSHOT,
            "snapshot_date": SOURCE.claimed, "source_id": SOURCE.source_id,
            "candidate_player_snapshot_date": SOURCES[0].claimed,
            "rarity": item["rarity"], "official_rarity": None, "overall": item["overall_rating"],
            "primary_position": item["position_primary"], "positions": item["observed_positions"],
            "attributes": attributes, "missing_attributes": [field for field, value in attributes.items() if value is None],
            "playstyles": item["playstyles"] if any(item["playstyles"].values()) else None,
            "official_roles": item.get("official_role_eligibility"),
            "editorial_role_fit": item.get("unverified_editorial_role_fit"), "position_issues": item["issues"],
        }

    cohorts = [entry(row, group, rank) for group, members in (("TOP_100", top), ("POSITION_CONTROL", controls))
               for rank, row in enumerate(members, 1)]
    manifest = {
        "version": COHORT_VERSION, "release_id": RELEASE, "snapshot_id": SNAPSHOT,
        "source_snapshot_date": SOURCE.claimed, "source_members_digest": MEMBERS_DIGEST,
        "eligible_items": len(eligible), "top_100": len(top), "position_control": len(controls),
        "top_100_positions": dict(Counter(row["normalized"]["position_primary"] for row in top)),
        "control_positions": dict(Counter(row["normalized"]["position_primary"] for row in controls)),
        "confirmed_base_links": sum(item["base_player_id"] is not None for item in cohorts),
        "minimum_top_100_overall": top[-1]["normalized"]["overall_rating"],
        "cohort_digest": digest(cohorts),
        "selection": "Source Rare, known primary position, same exact item ID and OVR in ratings snapshot, no identity conflict or different candidate base ID. Order by OVR descending, numeric item ID ascending, literal item ID ascending. Control takes top three remaining per primary position.",
    }
    return manifest, cohorts


@lru_cache(maxsize=1)
def load_cohort(database_url):
    rows = staged_cards()
    if len(rows) != SOURCE.rows or digest(rows) != MEMBERS_DIGEST:
        raise ValueError("Pinned card observations have changed")
    manifest, items = build_cohort(rows)
    if manifest["cohort_digest"] != COHORT_DIGEST:
        raise ValueError("Frozen performance cohort has changed")
    return manifest, items
