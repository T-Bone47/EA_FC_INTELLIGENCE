"""Team/squad context assembly.

Builds SquadContext from a persisted squad (via callback) using only verified
identity facts (club/league/nation from canonical data). Chemistry itself is
scored in fit_components.team_fit under the version's chemistry_rules_verified
gate — this module never fabricates chemistry values.
"""
from __future__ import annotations

from typing import Callable, Optional
import uuid

from backend.domain.user_model import SquadContext, SquadSlot


class TeamContextService:
    def __init__(self, squad_loader: Optional[Callable[[uuid.UUID], Optional[SquadContext]]] = None):
        self.squad_loader = squad_loader

    def context_for(self, squad_id: Optional[uuid.UUID]) -> Optional[SquadContext]:
        if squad_id is None or self.squad_loader is None:
            return None
        return self.squad_loader(squad_id)

    @staticmethod
    def link_summary(ctx: Optional[SquadContext]) -> dict:
        if ctx is None:
            return {"status": "NO_SQUAD_CONTEXT"}
        filled = ctx.filled_slots()
        return {
            "status": "OK",
            "formation": ctx.formation,
            "game_version": ctx.game_version,
            "filled_slots": len(filled),
            "total_slots": len(ctx.slots),
            "clubs": sorted({s.club for s in filled if s.club}),
            "leagues": sorted({s.league for s in filled if s.league}),
            "nations": sorted({s.nation for s in filled if s.nation}),
        }
