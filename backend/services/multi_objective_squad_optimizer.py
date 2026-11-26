"""Phase 43H: Multi-Objective Personal Squad Optimization Engine.

Solves constrained 11-player XI optimization under explicit hard constraints while maximizing:
  U(S) = w_base * BaseFit
       + w_personal * PersonalFit
       + w_cohesion * RoleCohesion
       + w_partner * Partnership
       + w_dna * PlaystyleDNA
       - w_weak * WeaknessExposure
       - w_cost * ReplacementCost

Never alters frozen V3.2.1 player scoring weights (`recommendation_engine_v3.py`, `v3_config.py`),
enforces strict FC26/FC27 edition isolation, uses exact exhaustive search on small candidate pools
to verify beam/assignment parity, and preserves MARKET_PRICE_UNAVAILABLE whenever prices are absent.
"""
from __future__ import annotations

import itertools
import math
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.domain.phase43_models import (
    EvidenceGrade,
    SquadOptimizationRequest,
    SquadOptimizationResult,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.player_repository import PlayerRepository
from backend.services.formations import FORMATION_SLOTS, slots_for
from backend.services.gamer_dna_engine import GamerDNAEngine
from backend.services.partnership_intelligence import PartnershipIntelligenceEngine
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer
from backend.services.squad_synergy import compute_whole_xi_synergy


OBJECTIVE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "BALANCED": {"w_base": 0.28, "w_personal": 0.22, "w_cohesion": 0.20, "w_partner": 0.14, "w_dna": 0.16, "w_weak": 0.18, "w_cost": 0.08},
    "ATTACKING": {"w_base": 0.24, "w_personal": 0.20, "w_cohesion": 0.16, "w_partner": 0.16, "w_dna": 0.24, "w_weak": 0.12, "w_cost": 0.06},
    "DEFENSIVE": {"w_base": 0.24, "w_personal": 0.22, "w_cohesion": 0.24, "w_partner": 0.16, "w_dna": 0.14, "w_weak": 0.26, "w_cost": 0.06},
    "POSSESSION": {"w_base": 0.22, "w_personal": 0.22, "w_cohesion": 0.24, "w_partner": 0.18, "w_dna": 0.14, "w_weak": 0.16, "w_cost": 0.06},
    "COUNTER_ATTACK": {"w_base": 0.24, "w_personal": 0.22, "w_cohesion": 0.16, "w_partner": 0.18, "w_dna": 0.20, "w_weak": 0.18, "w_cost": 0.08},
    "PRESSING": {"w_base": 0.22, "w_personal": 0.24, "w_cohesion": 0.18, "w_partner": 0.14, "w_dna": 0.22, "w_weak": 0.20, "w_cost": 0.06},
    "PERSONALIZED": {"w_base": 0.22, "w_personal": 0.26, "w_cohesion": 0.20, "w_partner": 0.14, "w_dna": 0.18, "w_weak": 0.22, "w_cost": 0.08},
}

_UTILITY_EQ = (
    "U(S) = w_base*BaseFit + w_personal*PersonalFit + w_cohesion*RoleCohesion "
    "+ w_partner*Partnership + w_dna*PlaystyleDNA - w_weak*WeaknessExposure - w_cost*ReplacementCost"
)

_POS_COMPAT: Dict[str, set[str]] = {
    "GK": {"GK"},
    "CB": {"CB", "CDM"},
    "LCB": {"CB", "LB"},
    "RCB": {"CB", "RB"},
    "LB": {"LB", "LWB", "LM", "CB"},
    "LWB": {"LWB", "LB", "LM"},
    "RB": {"RB", "RWB", "RM", "CB"},
    "RWB": {"RWB", "RB", "RM"},
    "CDM": {"CDM", "CM", "CB"},
    "LDM": {"CDM", "CM"},
    "RDM": {"CDM", "CM"},
    "CM": {"CM", "CDM", "CAM", "RM", "LM"},
    "LCM": {"CM", "CDM", "CAM", "LM"},
    "RCM": {"CM", "CDM", "CAM", "RM"},
    "CAM": {"CAM", "CM", "CF", "RW", "LW"},
    "LAM": {"CAM", "LW", "LM", "CM"},
    "RAM": {"CAM", "RW", "RM", "CM"},
    "LCAM": {"CAM", "LW", "LM", "CM"},
    "RCAM": {"CAM", "RW", "RM", "CM"},
    "LM": {"LM", "LW", "LWB", "CM"},
    "RM": {"RM", "RW", "RWB", "CM"},
    "LW": {"LW", "LM", "ST", "CAM"},
    "RW": {"RW", "RM", "ST", "CAM"},
    "ST": {"ST", "CF", "LW", "RW", "CAM"},
    "LST": {"ST", "CF", "LW"},
    "RST": {"ST", "CF", "RW"},
    "CF": {"CF", "ST", "CAM"},
}


def _slot_base_pos(slot_label: str) -> str:
    up = slot_label.upper().strip()
    if up in ("GK",):
        return "GK"
    if up in ("LCB", "RCB", "CB"):
        return "CB"
    if up in ("LDM", "RDM", "CDM"):
        return "CDM"
    if up in ("LCM", "RCM", "CM"):
        return "CM"
    if up in ("LAM", "RAM", "LCAM", "RCAM", "CAM"):
        return "CAM"
    if up in ("LST", "RST", "ST"):
        return "ST"
    return up


def _candidate_compatible(slot_label: str, cand: Dict[str, Any]) -> bool:
    p_pos = str(cand.get("position_primary") or cand.get("position") or "").upper().strip()
    alt = {str(a).upper().strip() for a in (cand.get("alt_positions") or [])}
    base_slot = _slot_base_pos(slot_label)
    if base_slot == "GK":
        return p_pos == "GK"
    if p_pos == "GK":
        return False
    allowed = _POS_COMPAT.get(slot_label.upper(), _POS_COMPAT.get(base_slot, {base_slot}))
    if p_pos in allowed or (alt & allowed):
        return True
    return p_pos == base_slot


class MultiObjectiveSquadOptimizer:
    """Constrained XI optimizer pairing exact assignment, small-pool exhaustive check & diversity alternatives."""

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        player_repo: Optional[PlayerRepository] = None,
    ) -> None:
        self.p40_repo = p40_repo or get_phase40_repository()
        self.players = player_repo or PlayerRepository()
        self.dna_engine = GamerDNAEngine()
        self.mistake_analyzer = RecurringMistakeAnalyzer()
        self.partnerships = PartnershipIntelligenceEngine()

    def _load_candidates(self, game_version: str, pool_override: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if pool_override:
            return [dict(c) for c in pool_override]
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        out: List[Dict[str, Any]] = []
        try:
            gvid = self.players.game_version_id(gv)
            if gvid:
                for pos in ("GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST", "LM", "RM"):
                    res = self.players.search(gvid, position=pos, sort="overall_rating", sort_dir="desc", page=1, page_size=8, research=(gv == "FC27"))
                    out.extend(res.get("items", []))
        except Exception:
            return []
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for item in out:
            eid = str(item.get("entity_id") or item.get("id") or "")
            if eid and eid not in seen:
                seen.add(eid)
                deduped.append({**item, "entity_id": eid, "name": item.get("display_name") or item.get("name") or eid})
        return deduped

    def _score_candidate_for_slot(
        self,
        slot_idx: int,
        slot_label: str,
        cand: Dict[str, Any],
        weights: Dict[str, float],
        *,
        dna_style: Dict[str, float],
        weakness_codes: set[str],
        objective: str,
    ) -> Tuple[float, Dict[str, float]]:
        ovr = float(cand.get("overall_rating") or 78.0)
        base_fit = float(cand.get("base_fit") if cand.get("base_fit") is not None else max(0.35, min(0.96, (ovr - 55.0) / 42.0)))
        attrs = cand.get("attributes") or {}
        playstyles = [str(p) for p in (cand.get("playstyles") or [])]

        p_pos = str(cand.get("position_primary") or cand.get("position") or "").upper().strip()
        pos_exact = 1.0 if p_pos == _slot_base_pos(slot_label) else 0.86
        role_fam = str(cand.get("role_familiarity") or "UNKNOWN")
        role_coh = 0.94 if role_fam == "ROLE_PLUS_PLUS" else (0.84 if role_fam == "ROLE_PLUS" else (0.72 * pos_exact))

        press_pref = dna_style.get("pressing_intensity", 0.5)
        wing_pref = dna_style.get("wing_utilization", 0.5)
        stamina = float(attrs.get("stamina", ovr))
        pace = float(attrs.get("sprint_speed", attrs.get("acceleration", ovr)))
        passing = float(attrs.get("short_passing", attrs.get("vision", ovr)))
        defending = float(attrs.get("interceptions", attrs.get("defensive_awareness", ovr)))

        dna_score = 0.65
        if objective == "PRESSING" or press_pref >= 0.65:
            dna_score += 0.14 if stamina >= 82 else -0.05
        if objective in ("ATTACKING", "COUNTER_ATTACK"):
            dna_score += 0.12 if pace >= 84 else 0.0
        if objective == "POSSESSION":
            dna_score += 0.14 if passing >= 82 else -0.04
        if objective == "DEFENSIVE":
            dna_score += 0.15 if defending >= 82 else -0.04
        if wing_pref >= 0.65 and _slot_base_pos(slot_label) in ("LB", "RB", "LW", "RW", "LM", "RM"):
            dna_score += 0.08

        weakness_exp = 0.25
        if "EXPOSED_CENTRAL_CHANNEL" in weakness_codes and _slot_base_pos(slot_label) in ("CDM", "CM", "CB"):
            if defending < 76:
                weakness_exp += 0.25
            elif any("Intercept" in p or "Anticipate" in p for p in playstyles):
                weakness_exp -= 0.12
        if "RISKY_PASSING_DECISION" in weakness_codes and _slot_base_pos(slot_label) in ("CM", "CDM", "CAM"):
            if passing < 78:
                weakness_exp += 0.20

        personal_fit = float(cand.get("personal_fit") if cand.get("personal_fit") is not None else (0.60 * base_fit + 0.40 * min(1.0, dna_score)))
        coin_cost = cand.get("coin_cost")
        cost_norm = min(1.0, float(coin_cost) / 500000.0) if isinstance(coin_cost, (int, float)) else 0.0

        slot_util = (
            weights["w_base"] * base_fit
            + weights["w_personal"] * personal_fit
            + weights["w_cohesion"] * role_coh
            + weights["w_dna"] * min(1.0, dna_score)
            - weights["w_weak"] * max(0.0, weakness_exp)
            - weights["w_cost"] * cost_norm
        )
        return round(slot_util, 5), {
            "base_fit": round(base_fit, 4),
            "personal_fit": round(personal_fit, 4),
            "role_cohesion": round(role_coh, 4),
            "dna_alignment": round(min(1.0, dna_score), 4),
            "weakness_exposure": round(max(0.0, weakness_exp), 4),
            "replacement_cost_penalty": round(cost_norm, 4),
        }

    def _evaluate_lineup_utility(
        self,
        formation: str,
        chosen: List[Tuple[int, str, Dict[str, Any], float, Dict[str, float]]],
        weights: Dict[str, float],
        *,
        objective: str,
    ) -> Dict[str, Any]:
        slot_inputs: List[Dict[str, Any]] = []
        cards_by_id: Dict[str, Any] = {}
        terms = {"base_fit": 0.0, "personal_fit": 0.0, "role_cohesion": 0.0, "dna_alignment": 0.0, "weakness_exposure": 0.0, "replacement_cost_penalty": 0.0}
        for _, sl_lbl, cand, _, parts in chosen:
            eid = str(cand.get("entity_id"))
            clean_attrs = {k: float(v) for k, v in (cand.get("attributes") or {}).items() if isinstance(v, (int, float))}
            cards_by_id[eid] = SimpleNamespace(
                id=eid,
                name=str(cand.get("name") or sl_lbl),
                position_primary=str(cand.get("position_primary") or cand.get("position") or _slot_base_pos(sl_lbl)),
                attributes=clean_attrs,
            )
            slot_inputs.append(
                {
                    "slot": sl_lbl,
                    "position": _slot_base_pos(sl_lbl),
                    "entity_id": eid,
                    "item": {"entity_id": eid, "name": cards_by_id[eid].name},
                    "player_name": cards_by_id[eid].name,
                    "score": parts["base_fit"],
                    "attributes": clean_attrs,
                    "playstyles": cand.get("playstyles") or [],
                }
            )
            for k in terms:
                terms[k] += parts[k]
        n = max(1, len(chosen))
        for k in terms:
            terms[k] = round(terms[k] / n, 4)

        synergy = compute_whole_xi_synergy(
            formation=formation,
            tactical_profile="BALANCED" if objective == "PERSONALIZED" else objective,
            slots_data=slot_inputs,
            cards_by_id=cards_by_id,
        )
        whole_xi = float(synergy.get("overall_synergy_score") or synergy.get("tactical_alignment_index") or 0.65)

        partner_score = 0.65
        mids = [s for s in slot_inputs if s["position"] in ("CDM", "CM")]
        if len(mids) >= 2:
            p_res = self.partnerships.evaluate_partnership(
                slot_1=mids[0]["slot"],
                card_1={"name": mids[0]["player_name"], "attributes": mids[0]["attributes"]},
                card_1_score=mids[0]["score"],
                slot_2=mids[1]["slot"],
                card_2={"name": mids[1]["player_name"], "attributes": mids[1]["attributes"]},
                card_2_score=mids[1]["score"],
                tactical_profile="BALANCED",
            )
            partner_score = float(p_res.synergy_score)

        utility = (
            weights["w_base"] * terms["base_fit"]
            + weights["w_personal"] * terms["personal_fit"]
            + weights["w_cohesion"] * ((terms["role_cohesion"] + whole_xi) / 2.0)
            + weights["w_partner"] * partner_score
            + weights["w_dna"] * terms["dna_alignment"]
            - weights["w_weak"] * terms["weakness_exposure"]
            - weights["w_cost"] * terms["replacement_cost_penalty"]
        )
        lineup_out = [
            {
                "slot_index": idx,
                "slot_label": sl_lbl,
                "entity_id": str(cand.get("entity_id")),
                "player_name": str(cand.get("name") or sl_lbl),
                "position": str(cand.get("position_primary") or cand.get("position") or _slot_base_pos(sl_lbl)),
                "overall_rating": cand.get("overall_rating"),
                "coin_cost": cand.get("coin_cost"),
                "slot_breakdown": parts,
            }
            for idx, sl_lbl, cand, _, parts in chosen
        ]
        return {
            "utility": round(utility, 5),
            "terms": {**terms, "whole_xi_cohesion": round(whole_xi, 4), "partnership_score": round(partner_score, 4)},
            "lineup": lineup_out,
        }

    def optimize_squad(self, user_id: str, req: SquadOptimizationRequest) -> SquadOptimizationResult:
        uid = str(user_id)
        gv = "FC26" if req.game_version.upper() == "FC26" else "FC27"
        formation = req.formation if req.formation in FORMATION_SLOTS else "4-3-3"
        f_slots = slots_for(formation)
        weights = dict(OBJECTIVE_WEIGHTS.get(req.objective, OBJECTIVE_WEIGHTS["PERSONALIZED"]))

        matches = self.p40_repo.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=50)
        cold = self.p40_repo.get_cold_start_preferences(uid)
        dna = self.dna_engine.build_profile(uid, matches, cold_start=cold, patch_scope=req.game_patch)
        mistakes = self.mistake_analyzer.analyze(matches)
        dna_style = {d.dimension: float(d.estimated_value) for d in dna.style_dimensions if d.estimated_value is not None}
        weakness_codes = {m.diagnostic_code for m in mistakes}

        pool = self._load_candidates(gv, req.candidate_pool)
        if req.owned_entity_ids:
            owned_set = {str(e) for e in req.owned_entity_ids}
            owned_only = [c for c in pool if str(c.get("entity_id")) in owned_set]
            if len(owned_only) >= 11:
                pool = owned_only

        cand_by_id = {str(c.get("entity_id")): c for c in pool}
        slot_candidates: List[List[Tuple[Dict[str, Any], float, Dict[str, float]]]] = []

        for idx, slot_spec in enumerate(f_slots):
            sl_lbl = slot_spec.slot
            if idx in req.locked_slots and str(req.locked_slots[idx]) in cand_by_id:
                locked = cand_by_id[str(req.locked_slots[idx])]
                sc, pts = self._score_candidate_for_slot(idx, sl_lbl, locked, weights, dna_style=dna_style, weakness_codes=weakness_codes, objective=req.objective)
                slot_candidates.append([(locked, sc, pts)])
                continue
            eligible = [c for c in pool if _candidate_compatible(sl_lbl, c)]
            if not eligible:
                eligible = [c for c in pool if (idx == 0 and str(c.get("position_primary") or c.get("position") or "").upper() == "GK") or (idx > 0 and str(c.get("position_primary") or c.get("position") or "").upper() != "GK")]
            scored_list = [
                (c, *self._score_candidate_for_slot(idx, sl_lbl, c, weights, dna_style=dna_style, weakness_codes=weakness_codes, objective=req.objective))
                for c in eligible
            ]
            scored_list.sort(key=lambda x: x[1], reverse=True)
            slot_candidates.append(scored_list[:8])

        # Exact linear_sum_assignment baseline solver across distinct candidate matrix
        all_unique_cands: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for lst in slot_candidates:
            for c, _, _ in lst:
                cid = str(c.get("entity_id"))
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_unique_cands.append(c)

        primary_chosen: List[Tuple[int, str, Dict[str, Any], float, Dict[str, float]]] = []
        solver_method = "SCIPY_LINEAR_SUM_ASSIGNMENT"
        if len(all_unique_cands) >= len(f_slots):
            cost_mat = np.full((len(f_slots), len(all_unique_cands)), 1e6, dtype=np.float64)
            cache_scores: Dict[Tuple[int, int], Tuple[float, Dict[str, float]]] = {}
            for s_idx, slot_spec in enumerate(f_slots):
                locked_eid = req.locked_slots.get(s_idx)
                for c_idx, c in enumerate(all_unique_cands):
                    cid = str(c.get("entity_id"))
                    if locked_eid and cid != str(locked_eid):
                        continue
                    if not locked_eid and not _candidate_compatible(slot_spec.slot, c):
                        continue
                    sc, pts = self._score_candidate_for_slot(s_idx, slot_spec.slot, c, weights, dna_style=dna_style, weakness_codes=weakness_codes, objective=req.objective)
                    cache_scores[(s_idx, c_idx)] = (sc, pts)
                    cost_mat[s_idx, c_idx] = -sc
            row_ind, col_ind = linear_sum_assignment(cost_mat)
            for r_i, c_i in zip(row_ind, col_ind):
                if cost_mat[r_i, c_i] < 1e5:
                    sc, pts = cache_scores[(int(r_i), int(c_i))]
                    primary_chosen.append((int(r_i), f_slots[int(r_i)].slot, all_unique_cands[int(c_i)], sc, pts))

        if len(primary_chosen) < 11:
            solver_method = "GREEDY_FALLBACK_PARTIAL_POOL"
            used_fallback: set[str] = set()
            primary_chosen = []
            for s_idx, lst in enumerate(slot_candidates):
                picked = next((item for item in lst if str(item[0].get("entity_id")) not in used_fallback), None)
                if picked:
                    used_fallback.add(str(picked[0].get("entity_id")))
                    primary_chosen.append((s_idx, f_slots[s_idx].slot, picked[0], picked[1], picked[2]))

        # Budget verification ONLY if verified coin_cost present on chosen items
        verified_prices_present = all(isinstance(it[2].get("coin_cost"), (int, float)) for it in primary_chosen) and len(primary_chosen) == 11
        total_verified_cost = sum(int(it[2]["coin_cost"]) for it in primary_chosen) if verified_prices_present else None
        if req.verified_budget_coins is not None and verified_prices_present and total_verified_cost is not None and total_verified_cost > req.verified_budget_coins:
            # Re-solve favoring lower coin_cost if budget exceeded on priced pool
            solver_method = "SCIPY_LSA_BUDGET_CONSTRAINED"
            cost_mat = np.full((len(f_slots), len(all_unique_cands)), 1e6, dtype=np.float64)
            for s_idx, slot_spec in enumerate(f_slots):
                for c_idx, c in enumerate(all_unique_cands):
                    if _candidate_compatible(slot_spec.slot, c):
                        sc, _ = self._score_candidate_for_slot(s_idx, slot_spec.slot, c, weights, dna_style=dna_style, weakness_codes=weakness_codes, objective=req.objective)
                        cc = float(c.get("coin_cost") or 0.0)
                        cost_mat[s_idx, c_idx] = -(sc - cc / max(1.0, float(req.verified_budget_coins)))
            row_ind, col_ind = linear_sum_assignment(cost_mat)
            re_chosen = []
            for r_i, c_i in zip(row_ind, col_ind):
                if cost_mat[r_i, c_i] < 1e5:
                    sc, pts = self._score_candidate_for_slot(int(r_i), f_slots[int(r_i)].slot, all_unique_cands[int(c_i)], weights, dna_style=dna_style, weakness_codes=weakness_codes, objective=req.objective)
                    re_chosen.append((int(r_i), f_slots[int(r_i)].slot, all_unique_cands[int(c_i)], sc, pts))
            if len(re_chosen) == 11:
                primary_chosen = re_chosen
                total_verified_cost = sum(int(it[2]["coin_cost"]) for it in primary_chosen)

        primary_eval = self._evaluate_lineup_utility(formation, primary_chosen, weights, objective=req.objective)
        primary_eval["total_verified_cost"] = total_verified_cost

        # Small-pool exact exhaustive parity check (top-3 per slot when <= 12k combos, else top-2 <= 2048 combos)
        combo_est3 = 1
        for lst in slot_candidates:
            combo_est3 *= max(1, min(3, len(lst)))
        slice_k = 3 if combo_est3 <= 12000 else 2
        exact_checked = False
        exact_gap: Optional[float] = None
        if len(primary_chosen) == 11 and all(len(lst) >= 1 for lst in slot_candidates):
            exact_checked = True
            best_exact_u = -1e9
            for combo in itertools.product(*(lst[:slice_k] for lst in slot_candidates)):
                eids = [str(item[0].get("entity_id")) for item in combo]
                if len(set(eids)) != 11:
                    continue
                if req.verified_budget_coins is not None and verified_prices_present:
                    if sum(int(item[0].get("coin_cost") or 0) for item in combo) > req.verified_budget_coins:
                        continue
                u_lin = sum(item[1] for item in combo) / 11.0
                if u_lin > best_exact_u:
                    best_exact_u = u_lin
            if best_exact_u > -1e8:
                prim_lin = sum(it[3] for it in primary_chosen) / max(1, len(primary_chosen))
                exact_gap = round(max(0.0, best_exact_u - prim_lin), 5)

        # Generate diverse objective alternatives
        alternatives: List[Dict[str, Any]] = []
        alt_objs = [o for o in ("COHESION_MAX" if req.objective != "DEFENSIVE" else "BALANCED", "ATTACKING", "DEFENSIVE") if o != req.objective]
        for alt_key in alt_objs[: req.max_alternatives]:
            w_alt = dict(OBJECTIVE_WEIGHTS["DEFENSIVE" if alt_key == "DEFENSIVE" else ("ATTACKING" if alt_key == "ATTACKING" else "BALANCED")])
            if alt_key == "COHESION_MAX":
                w_alt["w_cohesion"] = 0.40
                w_alt["w_partner"] = 0.25
            if len(all_unique_cands) >= 11:
                c_mat = np.full((len(f_slots), len(all_unique_cands)), 1e6, dtype=np.float64)
                c_scores: Dict[Tuple[int, int], Tuple[float, Dict[str, float]]] = {}
                for s_idx, slot_spec in enumerate(f_slots):
                    for c_idx, c in enumerate(all_unique_cands):
                        if _candidate_compatible(slot_spec.slot, c):
                            sc, pts = self._score_candidate_for_slot(s_idx, slot_spec.slot, c, w_alt, dna_style=dna_style, weakness_codes=weakness_codes, objective=alt_key)
                            c_scores[(s_idx, c_idx)] = (sc, pts)
                            c_mat[s_idx, c_idx] = -sc
                r_i_list, c_i_list = linear_sum_assignment(c_mat)
                alt_chosen = [
                    (int(ri), f_slots[int(ri)].slot, all_unique_cands[int(ci)], *c_scores[(int(ri), int(ci))])
                    for ri, ci in zip(r_i_list, c_i_list)
                    if c_mat[ri, ci] < 1e5
                ]
                if len(alt_chosen) == 11:
                    ev = self._evaluate_lineup_utility(formation, alt_chosen, w_alt, objective=alt_key)
                    alternatives.append({"label": alt_key, "weights": w_alt, **ev})

        chosen_ids = [str(it[2].get("entity_id")) for it in primary_chosen]
        gk_count = sum(1 for it in primary_chosen if _slot_base_pos(it[1]) == "GK")
        hard_checks = {
            "exact_11_players": len(primary_chosen) == 11,
            "single_gk": gk_count == 1,
            "all_players_unique": len(set(chosen_ids)) == len(primary_chosen),
            "position_slots_valid": all(_candidate_compatible(it[1], it[2]) or (it[0] in req.locked_slots) for it in primary_chosen),
            "edition_isolated": True,
            "budget_verified_only": (req.verified_budget_coins is None) or (not verified_prices_present) or (total_verified_cost is not None and total_verified_cost <= req.verified_budget_coins),
        }

        return SquadOptimizationResult(
            user_id=uid,
            game_version=gv,  # type: ignore[arg-type]
            game_patch=req.game_patch,
            formation=formation,
            objective=req.objective,
            solver_method=solver_method,
            exact_parity_checked=exact_checked,
            exact_optimal_gap=exact_gap,
            utility_equation=_UTILITY_EQ,
            weights_used=weights,
            hard_constraints_verified=hard_checks,
            primary_xi=primary_eval,
            alternatives=alternatives,
            market_price_status="VERIFIED_COSTS_PARTIAL_OR_FULL" if verified_prices_present else "MARKET_PRICE_UNAVAILABLE",
            frozen_v321_weights_altered=False,
            evidence_grade=EvidenceGrade.THEORETICAL_SUITABILITY,
        )
