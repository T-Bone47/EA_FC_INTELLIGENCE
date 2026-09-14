"""Role fit service.

Real Role data (FC Roles + familiarity) is NOT ingested for any version yet
(see docs: card-layer investigation blocked). Until legitimate Role data
exists, role_fit returns INSUFFICIENT_EVIDENCE — explicitly NOT a penalty and
NOT a fabricated incompatibility (§19: missing Role != incompatible Role).

When role familiarity data becomes available it is loaded here (from
game_player_role_familiarity) and scored without touching engine semantics.
"""
from __future__ import annotations

from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import UserRequirements
from backend.services.fit_value import FitValue
from backend.services.scoring_config import ScoringConfig


class RoleFitService:
    def __init__(self, config: ScoringConfig,
                 familiarity_lookup: Optional[dict] = None):
        """familiarity_lookup: {(entity_id_str, role_code): 0..1} — empty until
        legitimate Role data is ingested."""
        self.config = config
        self.familiarity_lookup = familiarity_lookup or {}

    def evaluate(self, candidate: Candidate, req: UserRequirements) -> FitValue:
        if not req.role:
            return FitValue.unknown("no Role requirement specified")
        # §9 card roles: when the CARD itself publishes role familiarity
        # (ut_card_role rows loaded into candidate.extra['roles']), it is the
        # authority for this candidate — Roles and archetypes stay distinct
        # concepts and no generic "has roles" bonus is ever applied.
        if candidate.entity_type == "ut_card":
            from backend.services import engine_config as ec
            wanted = (req.role or "").strip().lower()
            roles = (candidate.extra or {}).get("roles") or []
            for r in roles:
                if str(r.get("role") or "").strip().lower() != wanted:
                    continue
                label = str(r.get("familiarity") or "").strip().upper()
                fam_score = ec.CARD_ROLE_FAMILIARITY_SCORES.get(label)
                if fam_score is None:
                    return FitValue.insufficient(
                        f"card role {r.get('role')!r} has unmapped familiarity "
                        f"label {label!r} — withheld, not guessed")
                return FitValue.known(
                    float(fam_score),
                    evidence=(f"card-published role data: {r.get('role')} "
                              f"familiarity={label or 'UNSPECIFIED'} "
                              f"(reference mapping {fam_score:.2f})",))
            if roles:
                published = ", ".join(sorted(str(r.get("role")) for r in roles))
                return FitValue.insufficient(
                    f"card publishes Roles ({published}) but not {req.role!r} — "
                    "withheld, not counted as incompatibility")

        vc = self.config.version(candidate.game_version.value)
        if not vc.roles_available:
            return FitValue.insufficient(
                f"Role data is not available for {candidate.game_version.value}; "
                f"cannot verify fit for requested Role {req.role!r}. Withheld — "
                "not counted as incompatibility.")
        fam = self.familiarity_lookup.get((str(candidate.entity_id), req.role))
        if fam is None:
            return FitValue.insufficient(
                f"no familiarity record for this candidate and Role {req.role!r}")
        return FitValue.known(
            float(fam),
            evidence=(f"role familiarity {fam:.2f} for {req.role} (ingested data)",))
