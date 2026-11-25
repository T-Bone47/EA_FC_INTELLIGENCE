"""V3 API schemas. Player-scope only.

entity_scope is a Literal["game_player"] here, not the auto/ut_card union v2
uses -- per the implementation mandate ("Entity scope must explicitly say
game_player, not UT card") this is enforced at the type level, not by a
runtime check that a future edit could accidentally skip.
"""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.api.schemas import AttributePreferenceIn
from backend.services.formations import require_formation_slot, validate_tactical_combination


class RecommendationRequestV3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_version: str = Field(min_length=2, max_length=10)
    position: str = Field(min_length=1, max_length=5)
    formation: str | None = Field(default=None, min_length=3, max_length=12)
    slot: str | None = Field(default=None, min_length=1, max_length=8)
    tactical_profile: str = Field(default="BALANCED", max_length=30)
    secondary_tactical_profile: Optional[str] = Field(default=None, max_length=30)
    attribute_preferences: list[AttributePreferenceIn] = Field(default_factory=list, max_length=20)
    desired_playstyles: list[str] = Field(default_factory=list, max_length=10)
    desired_playstyles_plus: list[str] = Field(default_factory=list, max_length=5)
    required_playstyles: list[str] = Field(default_factory=list, max_length=5)
    required_league: Optional[str] = Field(default=None, max_length=120)
    required_club: Optional[str] = Field(default=None, max_length=120)
    required_nation: Optional[str] = Field(default=None, max_length=120)
    squad_id: None = Field(default=None, description="Squad context is unsupported in V3.")
    entity_scope: Literal["game_player"] = "game_player"
    limit: int = Field(default=10, ge=1, le=50)
    lam: Optional[float] = Field(default=None, ge=0.0, le=1.0,
                                  description="Override the configured tactical-share "
                                  "default (see v3_config.lam_default). Advanced use only.")
    explain_top_n: int = Field(default=3, ge=0, le=20)
    provenance_detail: Literal["summary", "full"] = "summary"
    division: Optional[Literal["Men's Football", "Women's Football"]] = Field(
        default=None,
        description="Optional user filter on EA's division label. No default policy: "
                    "omitted = every published division of the requested version.")
    include_research_data: bool = Field(
        default=False,
        description="Opt in to RESEARCH_ONLY data (e.g. the FC27 non-commercial snapshot). "
                    "Refused in production deployments; responses are labelled research-only.")

    @field_validator("position")
    @classmethod
    def upper_pos(cls, v):
        return v.strip().upper()

    @field_validator("game_version")
    @classmethod
    def upper_gv(cls, v):
        return v.strip().upper()

    @field_validator("tactical_profile", "secondary_tactical_profile")
    @classmethod
    def upper_profile(cls, v):
        return v.strip().upper() if v else v


    @field_validator("formation", "slot")
    @classmethod
    def normalize_assignment(cls, value):
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def validate_assignment(self):
        require_formation_slot(self.formation, self.slot, self.position)
        validate_tactical_combination(self.tactical_profile, self.secondary_tactical_profile)
        return self


class CardRecommendationRequest(RecommendationRequestV3):
    entity_scope: Literal["ut_card"] = "ut_card"
    include_research_data: Literal[False] = False
    division: None = None


class CardCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_version: str = Field(min_length=2, max_length=10)
    card_ids: tuple[uuid.UUID, uuid.UUID]


class CompareRequestV3(BaseModel):
    """Compare chosen players under ONE tactical request."""
    model_config = ConfigDict(extra="forbid")
    request: RecommendationRequestV3
    entity_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)


    @field_validator("entity_ids")
    @classmethod
    def distinct_players(cls, ids):
        if len(ids) != len(set(ids)):
            raise ValueError("Choose distinct players to compare")
        return ids


class WhatIfChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=60)
    position: Optional[str] = Field(default=None, min_length=1, max_length=5)
    formation: Optional[str] = Field(default=None, min_length=3, max_length=12)
    slot: Optional[str] = Field(default=None, min_length=1, max_length=8)
    tactical_profile: Optional[str] = Field(default=None, max_length=30)
    secondary_tactical_profile: Optional[str] = Field(default=None, max_length=30)
    lam: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    division: Optional[Literal["Men's Football", "Women's Football"]] = None

    def changes(self) -> dict:
        out = {}
        if self.division:
            out["division"] = self.division
        if self.position:
            out["position"] = self.position.strip().upper()
        if self.formation:
            out["formation"] = self.formation.strip().upper()
        if self.slot:
            out["slot"] = self.slot.strip().upper()
        if self.tactical_profile:
            out["tactical_profile"] = self.tactical_profile.strip().upper()
        if self.secondary_tactical_profile:
            out["secondary_tactical_profile"] = self.secondary_tactical_profile.strip().upper()
        if self.lam is not None:
            out["lam"] = self.lam
        return out


class WhatIfRequestV3(BaseModel):
    """Recompute the deterministic engine for input variants."""
    model_config = ConfigDict(extra="forbid")
    base: RecommendationRequestV3
    variants: list[WhatIfChange] = Field(min_length=1, max_length=5)
    track_top: int = Field(default=10, ge=1, le=25)
