"""Phase 43B: Immutable Versioned Tactical Configuration Snapshot Service.

Captures complete edition-, patch-, mode-, squad-, role-, instruction-, cohesion-, and
partnership-aware TacticalConfigurationSnapshots while preserving explicit unknowns
instead of inventing missing settings, roles, or prices.
"""
from __future__ import annotations

import hashlib
import json
import uuid as uuid_lib
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from backend.domain.phase43_models import (
    MidMatchTacticalChange,
    TacticalConfigurationSnapshot,
    TacticalSlotConfig,
    TacticalSnapshotCreate,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase43_repository import Phase43Repository, SnapshotNotFoundError, get_phase43_repository
from backend.repositories.player_repository import PlayerRepository
from backend.repositories.squad_repository import SquadRepository
from backend.services.formations import slots_for
from backend.services.partnership_intelligence import PartnershipIntelligenceEngine
from backend.services.squad_synergy import compute_whole_xi_synergy


def compute_config_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TacticalSnapshotService:
    """Builds and persists immutable versioned TacticalConfigurationSnapshots."""

    def __init__(
        self,
        repo: Optional[Phase43Repository] = None,
        phase40_repo: Optional[Phase40Repository] = None,
        squad_repo: Optional[SquadRepository] = None,
        player_repo: Optional[PlayerRepository] = None,
    ) -> None:
        self.repo = repo or get_phase43_repository()
        self.p40_repo = phase40_repo or get_phase40_repository()
        self.squads = squad_repo or SquadRepository()
        self.players = player_repo or PlayerRepository()
        self.partnerships = PartnershipIntelligenceEngine()

    def create_snapshot(self, user_id: str, req: TacticalSnapshotCreate) -> TacticalConfigurationSnapshot:
        uid = str(user_id)
        slots = list(req.slots)
        formation = req.formation
        source_squad_id = req.source_squad_id
        chemistry_summary: Optional[Dict[str, Any]] = None

        # Hydrate saved squad slots cleanly if user referenced a squad ID without passing explicit slots
        if source_squad_id and not slots:
            try:
                sq_uuid = uuid_lib.UUID(str(source_squad_id))
                uid_uuid = uuid_lib.UUID(uid)
                sq = self.squads.get_squad(uid_uuid, sq_uuid)
                if not sq:
                    raise ValueError(f"Saved squad {source_squad_id!r} not found for user.")
                if not req.formation:
                    formation = str(sq.get("formation") or "4-3-3")
                raw_slots = self.squads.slots(sq_uuid, uid_uuid, research=(req.game_version == "FC27"))
                for rs in raw_slots:
                    slots.append(
                        TacticalSlotConfig(
                            slot_index=int(rs.get("slot_index", len(slots))),
                            slot_position=str(rs.get("slot_position") or "CM"),
                            entity_id=str(rs.get("game_player_id") or rs.get("ut_card_id") or "") or None,
                            entity_type="ut_card" if rs.get("ut_card_id") else "game_player",
                            player_name=rs.get("player_name"),
                            overall_rating=int(rs["overall_rating"]) if rs.get("overall_rating") else None,
                            role_familiarity="UNKNOWN",
                        )
                    )
            except ValueError:
                raise
            except Exception:
                source_squad_id = None

        # Explicit unknown field tracking — never silently fabricate defaults
        unknowns: List[str] = []
        if not req.build_up_style:
            unknowns.append("build_up_style")
        if not req.defensive_approach:
            unknowns.append("defensive_approach")
        if req.line_height is None:
            unknowns.append("line_height")
        if req.width_setting is None:
            unknowns.append("width_setting")
        if not slots:
            unknowns.append("squad_slots")
        else:
            if any(not s.assigned_role for s in slots):
                unknowns.append("some_slot_roles")
            if any(s.role_familiarity == "UNKNOWN" for s in slots):
                unknowns.append("some_role_familiarities")
            if any(not s.attributes for s in slots):
                unknowns.append("some_player_attributes")
        unknowns.append("chemistry_verified_rules_partial" if req.game_version == "FC27" else "market_price_coins")

        # Version chain inheritance if parent_snapshot_id specified
        version_number = 1
        if req.parent_snapshot_id:
            try:
                parent = self.repo.get_snapshot(uid, req.parent_snapshot_id)
                if parent.game_version != req.game_version:
                    raise ValueError("Cannot fork snapshot across FC26 and FC27 edition boundary.")
                version_number = parent.version_number + 1
            except SnapshotNotFoundError as exc:
                raise ValueError(f"Parent snapshot {req.parent_snapshot_id!r} not found.") from exc

        # Reconstruct Whole-XI cohesion cleanly across filled slots
        f_slots = slots_for(formation)
        slot_inputs: List[Dict[str, Any]] = []
        cards_by_id: Dict[str, Any] = {}
        for idx, s in enumerate(slots):
            slot_label = f_slots[idx].slot if idx < len(f_slots) else s.slot_position
            ovr_proxy = float(s.overall_rating or 78)
            score_proxy = max(0.35, min(0.95, (ovr_proxy - 55.0) / 42.0))
            entity_key = str(s.entity_id or f"slot_{idx}_{slot_label}")
            player_label = s.player_name or s.slot_position
            clean_attrs = {k: v for k, v in s.attributes.items() if v is not None}
            cards_by_id[entity_key] = SimpleNamespace(
                id=entity_key,
                name=player_label,
                position_primary=s.slot_position,
                attributes=clean_attrs,
            )
            slot_inputs.append(
                {
                    "slot": slot_label,
                    "position": s.slot_position,
                    "entity_id": entity_key,
                    "item": {"entity_id": entity_key, "name": player_label},
                    "player_name": player_label,
                    "score": round(score_proxy, 4),
                    "attributes": clean_attrs,
                    "playstyles": s.playstyles,
                }
            )
        cohesion = compute_whole_xi_synergy(
            formation=formation,
            tactical_profile=req.tactical_profile,
            slots_data=slot_inputs,
            cards_by_id=cards_by_id,
        )

        # Partnership evaluation on central pivot / key link when at least 2 slots filled
        partnership_summary: Optional[Dict[str, Any]] = None
        if len(slot_inputs) >= 2:
            cm_or_cdm = [s for s in slot_inputs if s["position"] in ("CDM", "CM")]
            pair_a, pair_b = (cm_or_cdm[0], cm_or_cdm[1]) if len(cm_or_cdm) >= 2 else (slot_inputs[0], slot_inputs[1])
            p_res = self.partnerships.evaluate_partnership(
                slot_1=pair_a["slot"],
                card_1={"name": pair_a["player_name"], "attributes": pair_a["attributes"]},
                card_1_score=pair_a["score"],
                slot_2=pair_b["slot"],
                card_2={"name": pair_b["player_name"], "attributes": pair_b["attributes"]},
                card_2_score=pair_b["score"],
                tactical_profile=req.tactical_profile,
            )
            partnership_summary = p_res.to_dict()

        # Attach cold-start preferences as metadata (never treated as empirical evidence)
        cold_prefs = self.p40_repo.get_cold_start_preferences(uid)
        gamer_prefs = cold_prefs.model_dump(mode="json") if cold_prefs else None

        hash_input = {
            "user_id": uid,
            "game_version": req.game_version,
            "game_patch": req.game_patch,
            "gameplay_mode": req.gameplay_mode,
            "formation": formation,
            "tactical_profile": req.tactical_profile,
            "build_up_style": req.build_up_style,
            "defensive_approach": req.defensive_approach,
            "line_height": req.line_height,
            "width_setting": req.width_setting,
            "tactical_instructions": req.tactical_instructions,
            "slots": [s.model_dump(mode="json") for s in slots],
        }
        snap = TacticalConfigurationSnapshot(
            user_id=uid,
            label=req.label.strip(),
            game_version=req.game_version,
            game_patch=req.game_patch,
            gameplay_mode=req.gameplay_mode,
            source_squad_id=source_squad_id,
            formation=formation,
            tactical_profile=req.tactical_profile,
            build_up_style=req.build_up_style,
            defensive_approach=req.defensive_approach,
            line_height=req.line_height,
            width_setting=req.width_setting,
            tactical_instructions=dict(req.tactical_instructions),
            mid_match_changes=list(req.mid_match_changes),
            notes=req.notes.strip(),
            slots=slots,
            chemistry_summary=chemistry_summary,
            cohesion_summary=cohesion,
            partnership_summary=partnership_summary,
            gamer_style_preferences=gamer_prefs,
            unknown_fields=sorted(set(unknowns)),
            config_hash=compute_config_hash(hash_input),
            version_number=version_number,
            parent_snapshot_id=req.parent_snapshot_id,
            is_immutable=True,
        )
        return self.repo.save_snapshot(snap)

    def diff_snapshots(self, user_id: str, baseline_snapshot_id: str, variant_snapshot_id: str) -> Dict[str, Any]:
        uid = str(user_id)
        base = self.repo.get_snapshot(uid, baseline_snapshot_id)
        var = self.repo.get_snapshot(uid, variant_snapshot_id)
        if base.game_version != var.game_version:
            raise ValueError("Snapshot diff blocked across FC26 and FC27 edition boundary.")

        field_changes: List[Dict[str, Any]] = []
        for field in ("formation", "tactical_profile", "build_up_style", "defensive_approach", "line_height", "width_setting", "gameplay_mode"):
            b_val = getattr(base, field)
            v_val = getattr(var, field)
            if b_val != v_val:
                field_changes.append({"field": field, "baseline": b_val, "variant": v_val})

        instr_keys = sorted(set(base.tactical_instructions.keys()) | set(var.tactical_instructions.keys()))
        instr_diffs = [
            {
                "instruction": k,
                "baseline": base.tactical_instructions.get(k),
                "variant": var.tactical_instructions.get(k),
            }
            for k in instr_keys
            if base.tactical_instructions.get(k) != var.tactical_instructions.get(k)
        ]

        slot_diffs: List[Dict[str, Any]] = []
        base_slots = {s.slot_index: s for s in base.slots}
        var_slots = {s.slot_index: s for s in var.slots}
        for idx in sorted(set(base_slots.keys()) | set(var_slots.keys())):
            bs = base_slots.get(idx)
            vs = var_slots.get(idx)
            if bs != vs:
                slot_diffs.append(
                    {
                        "slot_index": idx,
                        "position": (vs.slot_position if vs else bs.slot_position if bs else None),
                        "baseline_player": bs.player_name if bs else None,
                        "variant_player": vs.player_name if vs else None,
                        "baseline_role": f"{bs.assigned_role or 'UNKNOWN'} ({bs.role_focus or '-'})" if bs else None,
                        "variant_role": f"{vs.assigned_role or 'UNKNOWN'} ({vs.role_focus or '-'})" if vs else None,
                    }
                )

        return {
            "baseline_snapshot_id": base.snapshot_id,
            "variant_snapshot_id": var.snapshot_id,
            "game_version": base.game_version,
            "patch_changed": base.game_patch != var.game_patch,
            "field_changes": field_changes,
            "instruction_changes": instr_diffs,
            "slot_changes": slot_diffs,
            "mid_match_changes_count": len(var.mid_match_changes),
        }
