"""Pydantic request/response schemas — the API validation boundary (§26).

All free-text inputs are length-bounded; enums are validated against
version-aware reference data at the service layer. Unknown fields are ignored
(extra='forbid' on mutation endpoints to catch client bugs early).
"""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ------------------------------------------------------------------ auth
class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=80)

    @field_validator("password")
    @classmethod
    def password_sane(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("password must not start/end with whitespace")
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=300)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: dict


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Optional[str] = Field(default=None, max_length=80)
    preferred_game_version: Optional[str] = Field(default=None, max_length=10)
    preferences: Optional[dict[str, Any]] = None


# ------------------------------------------------------------------ recommendations
class AttributePreferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute: str = Field(max_length=40)
    min_value: Optional[int] = Field(default=None, ge=1, le=99)
    target_value: Optional[int] = Field(default=None, ge=1, le=99)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)


class AttributeBandIn(BaseModel):
    """§11 qualitative band -> configured soft target (never a hard floor)."""
    model_config = ConfigDict(extra="forbid")
    attribute: str = Field(max_length=40)
    band: Literal["elite", "excellent", "very_good", "good", "average", "weak"]


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_version: str = Field(min_length=2, max_length=10)
    position: Optional[str] = Field(default=None, max_length=5)
    formation: Optional[str] = Field(default=None, max_length=12)
    tactical_profile: str = Field(default="BALANCED", max_length=30)
    custom_tactics: dict[str, float] = Field(default_factory=dict)
    role: Optional[str] = Field(default=None, max_length=60)
    attribute_preferences: list[AttributePreferenceIn] = Field(
        default_factory=list, max_length=20)
    desired_playstyles: list[str] = Field(default_factory=list, max_length=10)
    desired_playstyles_plus: list[str] = Field(default_factory=list, max_length=5)
    budget_coins: Optional[int] = Field(default=None, ge=0, le=10_000_000_000)
    min_overall: Optional[int] = Field(default=None, ge=1, le=99)
    max_overall: Optional[int] = Field(default=None, ge=1, le=99)
    squad_id: Optional[uuid.UUID] = None
    entity_scope: Literal["auto", "game_player", "ut_card"] = "auto"
    strict_tactics: bool = False
    limit: int = Field(default=10, ge=1, le=50)
    # ---- v2.1 intelligence inputs (optional; absent => exact legacy behavior) ----
    archetype: Optional[str] = Field(default=None, max_length=40)
    slot: Optional[str] = Field(default=None, max_length=8)
    secondary_tactical_profile: Optional[str] = Field(default=None, max_length=30)
    attribute_bands: list[AttributeBandIn] = Field(default_factory=list, max_length=20)
    enable_interactions: bool = False
    enable_saturation: bool = False
    enable_playstyle_context: bool = False
    required_playstyles: list[str] = Field(default_factory=list, max_length=5)
    required_league: Optional[str] = Field(default=None, max_length=120)
    required_club: Optional[str] = Field(default=None, max_length=120)
    required_nation: Optional[str] = Field(default=None, max_length=120)
    replacement_for: Optional[uuid.UUID] = None
    overall_quality_bias: Optional[Literal["low", "normal", "high"]] = None
    complement_hint: Optional[dict[str, Any]] = None
    disable_counterfactuals: bool = False

    @field_validator("position")
    @classmethod
    def upper_pos(cls, v):
        return v.strip().upper() if v else v

    @field_validator("game_version")
    @classmethod
    def upper_gv(cls, v):
        return v.strip().upper()

    @field_validator("secondary_tactical_profile")
    @classmethod
    def upper_sec(cls, v):
        return v.strip().upper() if v else v

    @field_validator("archetype")
    @classmethod
    def upper_arch(cls, v):
        return v.strip().upper() if v else v

    @field_validator("complement_hint")
    @classmethod
    def hint_shape(cls, v):
        if v is None:
            return v
        if not isinstance(v, dict) or len(v) > 4:
            raise ValueError("complement_hint must be a small object")
        if v.get("bias") not in (None, "ATTACKING", "DEFENSIVE", "FAST", "PHYSICAL", "BALANCED"):
            raise ValueError("complement_hint.bias must be one of "
                             "ATTACKING/DEFENSIVE/FAST/PHYSICAL/BALANCED")
        return v

    @field_validator("custom_tactics")
    @classmethod
    def tactic_weights(cls, v):
        if len(v) > 30:
            raise ValueError("custom_tactics too large")
        for k, w in v.items():
            if w < 0 or w > 100:
                raise ValueError(f"invalid weight for {k}")
        return v

    def to_requirements(self):
        from backend.domain.user_model import (
            AttributeBand, AttributePreference, UserRequirements,
        )
        return UserRequirements(
            game_version=self.game_version,
            position=self.position,
            formation=self.formation,
            tactical_profile=self.tactical_profile.upper(),
            custom_tactics=dict(self.custom_tactics),
            role=self.role,
            attribute_preferences=[
                AttributePreference(p.attribute, p.min_value, p.target_value, p.weight)
                for p in self.attribute_preferences],
            desired_playstyles=list(self.desired_playstyles),
            desired_playstyles_plus=list(self.desired_playstyles_plus),
            budget_coins=self.budget_coins,
            min_overall=self.min_overall,
            max_overall=self.max_overall,
            squad_id=self.squad_id,
            entity_scope=self.entity_scope,
            strict_tactics=self.strict_tactics,
            limit=self.limit,
            archetype=self.archetype,
            slot=self.slot,
            secondary_tactical_profile=self.secondary_tactical_profile,
            attribute_bands=[AttributeBand(p.attribute, p.band)
                             for p in self.attribute_bands],
            enable_interactions=self.enable_interactions,
            enable_saturation=self.enable_saturation,
            enable_playstyle_context=self.enable_playstyle_context,
            required_playstyles=list(self.required_playstyles),
            required_league=self.required_league,
            required_club=self.required_club,
            required_nation=self.required_nation,
            replacement_for=self.replacement_for,
            overall_quality_bias=self.overall_quality_bias,
            complement_hint=self.complement_hint,
            disable_counterfactuals=self.disable_counterfactuals,
        )


class NaturalLanguageRequest(BaseModel):
    """Free-text intent (e.g. '4-2-3-1 high press, need a right CM, 100k').

    The parse step produces a RecommendationRequest-shaped draft that the user
    confirms; factual fields are always validated against reference data and
    never invented by the parser (§16)."""
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=3, max_length=1000)
    game_version: str = Field(default="FC26", max_length=10)


# ------------------------------------------------------------------ compare
class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_version: str
    entity_ids: list[uuid.UUID] = Field(min_length=2, max_length=4)
    user_context: Optional[RecommendationRequest] = None


# ------------------------------------------------------------------ squads
class SquadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    formation: str = Field(min_length=3, max_length=12)
    game_version: str = Field(default="FC26", max_length=10)
    tactics: dict[str, Any] = Field(default_factory=dict)


class SquadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, max_length=60)
    formation: Optional[str] = Field(default=None, max_length=12)
    tactics: Optional[dict[str, Any]] = None


class SlotAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_index: int = Field(ge=0, le=30)
    slot_position: str = Field(max_length=5)
    game_player_id: Optional[uuid.UUID] = None
    ut_card_id: Optional[uuid.UUID] = None

    @field_validator("slot_position")
    @classmethod
    def up(cls, v):
        return v.strip().upper()


class SquadReplaceRequest(BaseModel):
    """Find recommended replacements for one slot, in squad context."""
    model_config = ConfigDict(extra="forbid")
    slot_index: int = Field(ge=0, le=30)
    recommendation: Optional[RecommendationRequest] = None


# ------------------------------------------------------------------ feedback
class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: str = Field(min_length=1, max_length=64)
    action: Literal["SHOWN", "SELECTED", "REJECTED", "ALTERNATIVE_SELECTED", "SAVED"]
    entity_type: Literal["game_player", "ut_card"]
    entity_id: Optional[uuid.UUID] = None
    game_version: str = Field(default="FC26", max_length=10)
    reason: Optional[str] = Field(default=None, max_length=500)
    request_context: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------ saved
class SavePlayerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["game_player", "ut_card"] = "game_player"
    entity_id: uuid.UUID
    game_version: str = Field(default="FC26", max_length=10)
    note: Optional[str] = Field(default=None, max_length=300)
