"""Evaluate explicit FC27 item shortlists using the pinned card reference and existing V3.2 contexts."""
from collections import Counter
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.schemas import AttributePreferenceIn
from backend.domain.card_model import ALL_ATTRS, FACADE_ATTRS
from backend.services.explanation_service_v3 import why_not
from backend.api.schemas_v3 import CardRecommendationRequest
from backend.services.fc27_card_research import RELEASE, ResearchCards, card_facts, digest
from backend.services.formation_optimizer import SCALE, assignment_frontier, optimal_assignments
from backend.services.formations import slots_for
from backend.services.recommendation_engine_v3 import ENGINE_VERSION
from backend.services.squad_synergy import compute_whole_xi_synergy
from backend.services.v3_config import DEFAULT_V3_CONFIG

Profile = Literal["BALANCED", "HIGH_PRESS", "POSSESSION", "COUNTER_ATTACK", "LOW_BLOCK", "DIRECT_PLAY"]


class SlotRequest(CardRecommendationRequest):
    game_version: Literal["FC27"] = "FC27"
    include_research_data: Literal[True] = True


class SquadPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_version: Literal["FC27"]
    entity_scope: Literal["ut_card"]
    release_id: Literal["fc27-card-items-local-r1"]
    include_research_data: Literal[True]
    formation: str = Field(max_length=12)
    tactical_profile: Profile = "BALANCED"
    alternatives: list[Profile] = Field(default_factory=list, max_length=5)
    candidate_ids: list[UUID] = Field(max_length=50)
    assigned: dict[str, UUID] = Field(default_factory=dict, max_length=11)
    locked_slots: list[str] = Field(default_factory=list, max_length=11)
    excluded: list[UUID] = Field(default_factory=list, max_length=50)
    confirmed_only: bool = False
    continuity: bool = True
    desired_playstyles: list[str] = Field(default_factory=list, max_length=10)
    desired_playstyles_plus: list[str] = Field(default_factory=list, max_length=5)
    attribute_preferences: list[AttributePreferenceIn] = Field(default_factory=list, max_length=20)
    upgrade: Literal["one", "two", "minimum"] | None = None
    minimum_gain: float = Field(default=0, ge=0, le=11)

    @model_validator(mode="after")
    def check(self):
        slots = {s.slot for s in slots_for(self.formation)}
        if not slots or not self.assigned.keys() <= slots:
            raise ValueError("Choose a supported formation and valid slots.")
        for group in [self.candidate_ids, list(self.assigned.values()), self.excluded, self.locked_slots, self.alternatives]:
            if len(group) != len(set(group)):
                raise ValueError("Duplicate items, slots or tactical profiles.")
        pool = set(self.candidate_ids)
        if not set(self.assigned.values()) <= pool or not set(self.excluded) <= pool:
            raise ValueError("Assigned and excluded items must belong to the selected shortlist.")
        if set(self.locked_slots) - self.assigned.keys() or set(self.excluded) & set(self.assigned.values()):
            raise ValueError("Review your locks and exclusions.")
        if any(pref.attribute not in ALL_ATTRS for pref in self.attribute_preferences):
            raise ValueError("Choose a published scoring attribute.")
        return self


def identity_group(card):
    base = card.extra.get("confirmed_base_id")
    return "base:" + str(base) if base and card.extra["identity_status"] == "RESOLVED" else "item:" + str(card.entity_id)


def score_slots(service, plan, slots, profile):
    result = {}
    for slot in slots:
        req = SlotRequest(position=slot.position, formation=plan.formation, slot=slot.slot,
                          tactical_profile=profile, limit=50, desired_playstyles=plan.desired_playstyles,
                          desired_playstyles_plus=plan.desired_playstyles_plus,
                          attribute_preferences=plan.attribute_preferences)
        scored, _, _, _ = service.run(req)
        result[slot.slot] = {str(rc.context.candidate_entity_id): rc.context for rc in scored.ranked}
    return result


def nondominated(vectors):
    """Indices of non-dominated generated alternatives, all objectives maximized."""
    return [i for i, v in enumerate(vectors) if not any(
        all(a >= b for a, b in zip(w, v)) and any(a > b for a, b in zip(w, v)) for w in vectors)]


def transform_formation(service, plan, target, use_shortlist):
    target_slots = {s.slot: s.position for s in slots_for(target)}
    if not target_slots or target == plan.formation:
        raise ValueError("Choose another supported formation.")
    before = evaluate(service, plan)["current"]
    target_assigned = {}
    roster_ids = set(plan.assigned.values())
    by_id = {str(c.entity_id): c for c in service.candidates if c.entity_id in roster_ids}
    for slot, item in plan.assigned.items():
        card = by_id[str(item)]
        position = target_slots.get(slot)
        if position in (card.position_primary,*card.secondary_positions) and (position == "GK") == (card.position_primary == "GK"):
            target_assigned[slot] = item
        elif slot in plan.locked_slots:
            raise ValueError(f"Locked slot {slot} is incompatible with the target formation.")
    pool = plan.candidate_ids if use_shortlist else list(plan.assigned.values())
    spec = plan.model_dump()
    spec.update(formation=target, candidate_ids=pool, assigned=target_assigned,
                excluded=[i for i in plan.excluded if i in pool], upgrade=None)
    target_plan = SquadPlan.model_validate(spec)
    after = evaluate(service, target_plan)["optimized"]
    old_slots = {str(i):s for s,i in plan.assigned.items()}
    new_slots = {s["item"]["entity_id"]:s["slot"] for s in after["slots"] if s["item"]}
    return {"current":before,"target":after,"formation":target,"pool":"SHORTLIST" if use_shortlist else "CURRENT_ROSTER",
            "assignments":{s:i for i,s in new_slots.items()},
            "changes":[{"entity_id":i,"from_slot":old_slots.get(i),"to_slot":new_slots.get(i)}
                       for i in sorted(old_slots.keys()|new_slots.keys()) if old_slots.get(i)!=new_slots.get(i)]}


def evaluate(service, plan):
    slots = slots_for(plan.formation)
    current = {k: str(v) for k, v in plan.assigned.items()}
    wanted = set(plan.candidate_ids)
    cards = {str(c.entity_id): c for c in service.candidates if c.entity_id in wanted}
    if len(cards) != len(wanted):
        raise ValueError("An item is outside this card release.")
    excluded = {str(i) for i in plan.excluded}
    allowed = {k: c for k, c in cards.items() if k not in excluded and c.extra["identity_status"] != "CONFLICTED"
               and (not plan.confirmed_only or identity_group(c).startswith("base:"))}
    groups = set()
    for slot in slots:
        item = current.get(slot.slot)
        if not item:
            continue
        card = allowed.get(item)
        if not card or slot.position not in (card.position_primary, *card.secondary_positions):
            raise ValueError(f"Assigned item is ineligible for {slot.slot} or the identity policy.")
        if (slot.position == "GK") != (card.position_primary == "GK"):
            raise ValueError("Goalkeeper and outfield primary positions must be respected.")
        group = identity_group(card)
        if group in groups:
            raise ValueError("Two assignments represent the same confirmed footballer.")
        groups.add(group)

    profiles = list(dict.fromkeys([plan.tactical_profile, *plan.alternatives]))
    scoped = ResearchCards(service.reference, list(allowed.values()))
    contexts = {p: score_slots(scoped, plan, slots, p) for p in profiles}
    manual = {}
    for slot in slots:
        item = current.get(slot.slot)
        if item and item not in contexts[profiles[0]][slot.slot]:
            if slot.position == "GK" and slot.slot in plan.locked_slots:
                manual[slot.slot] = item
            else:
                raise ValueError(f"{slot.slot} has insufficient evidence. Only a locked primary goalkeeper may be unscored.")

    reserved = {identity_group(allowed[current[s]]) for s in plan.locked_slots}
    def options(profile):
        return [[{"entity_id": i, "score": c.r, "identity_group": identity_group(allowed[i])}
                 for i, c in contexts[profile][s.slot].items()
                 if (i == current[s.slot] if s.slot in plan.locked_slots else identity_group(allowed[i]) not in reserved)]
                for s in slots]

    def assignment(rows):
        return {**{s.slot: row["entity_id"] for s, row in zip(slots, rows) if row}, **manual}

    def summarize(lineup, profile):
        slot_rows = []
        contributions = Counter()
        evidence = []
        styles = Counter()
        face_values = {a: [] for a in FACADE_ATTRS}
        supported = {}
        unpublished_styles = 0
        for slot in slots:
            item = lineup.get(slot.slot)
            card = cards[item] if item else None
            ctx = contexts[profile][slot.slot].get(item)
            if ctx:
                evidence.append(ctx.coverage_kappa)
                for a in ctx.per_attribute:
                    if a.covered:
                        contributions[a.attribute] += a.contribution_lo * ctx.modifier_total
                        if a.s_eff is not None:
                            supported.setdefault(a.attribute, []).append(a.s_eff)
            if card:
                unpublished_styles += int(not card.playstyle_data_published)
                if card.position_primary != "GK":
                    for a in face_values:
                        value = card.attributes.get(a)
                        if value is not None:
                            face_values[a].append(value)
                styles.update(card.playstyles_base)
                styles.update(s + "+" for s in card.playstyles_plus)
            slot_rows.append({"slot": slot.slot, "position": slot.position, "item": card_facts(card) if card else None,
                              "score": ctx.r if ctx else None, "coverage": ctx.coverage_kappa if ctx else None,
                              "status": "SCORED" if ctx else "LOCKED_UNSCORED" if item else "UNFILLED",
                              "reason": None if ctx else "Insufficient goalkeeper item evidence" if slot.position == "GK"
                              else "No eligible item assigned"})
        scored = [s for s in slot_rows if s["score"] is not None]
        return {"slots": slot_rows, "filled": len(lineup), "scored": len(scored),
                "total_fit": round(sum(s["score"] for s in scored), 10) if scored else None,
                "mean_coverage_scored": sum(evidence)/len(evidence) if evidence else None,
                "weakest_scored_slots": [s["slot"] for s in sorted(scored, key=lambda r: (r["score"], r["slot"]))[:3]],
                "attribute_contributions": dict(contributions.most_common()), "observed_playstyles": dict(styles),
                "unknown_playstyle_lists": unpublished_styles, "official_role_distribution": None,
                "observed_outfield_attributes": {a: {"mean":sum(v)/len(v) if v else None,"published":len(v)}
                                                for a,v in face_values.items()},
                "attribute_suitability": sorted([{"attribute":a,"mean":sum(v)/len(v),"scored_slots":len(v)}
                                                 for a,v in supported.items()], key=lambda r:(-r["mean"],r["attribute"])),
                "fully_evaluated": len(scored) == len(slots),
                "footballer_uniqueness_verified": bool(lineup) and all(identity_group(cards[i]).startswith("base:") for i in lineup.values())}

    incumbents = [current.get(s.slot) for s in slots]
    primary = profiles[0]
    selection = assignment(optimal_assignments(options(primary), incumbents if plan.continuity else None))
    preview = summarize(selection, primary)
    matrix = []
    generated = []
    unavailable_profiles = {}
    for p in profiles:
        missing_locks = [s for s in plan.locked_slots if s not in manual and current[s] not in contexts[p][s]]
        if missing_locks:
            unavailable_profiles[p] = {"reason":"LOCKED_SLOT_INSUFFICIENT_EVIDENCE","slots":missing_locks}
            continue
        lineup = selection if p == primary else assignment(optimal_assignments(options(p), incumbents if plan.continuity else None))
        for name, arrangement in [(p, lineup), ("CURRENT", current)]:
            if name == "CURRENT" and p != primary or not arrangement:
                continue
            vector, counts = {}, {}
            for target in profiles:
                values = [contexts[target][slot].get(item) for slot, item in arrangement.items()]
                scores = [v.r for v in values if v]
                vector[target] = round(sum(scores), 10) if scores else None
                counts[target] = len(scores)
            matrix.append({"optimized_for": name, "assignment": arrangement, "scored_counts": counts, "scores": vector})
            if name != "CURRENT" and arrangement not in [m["assignment"] for m in generated]:
                generated.append(matrix[-1])
    # Compare vectors at equal coverage per tactic. Empty scored dimensions carry no preference.
    vectors = [tuple((m["scored_counts"][p], m["scores"][p] or 0) for p in profiles) for m in generated]
    frontier = [generated[i]["optimized_for"] for i in nondominated(vectors)]
    anchor = next((m for m in matrix if m["optimized_for"] == primary), None)
    for alternative in matrix:
        alternative["changed_slots"] = [s.slot for s in slots if alternative["assignment"].get(s.slot) != selection.get(s.slot)]
        alternative["fit_delta_vs_primary"] = {
            p: round(alternative["scores"][p] - anchor["scores"][p], 10)
            if anchor and alternative["scored_counts"][p] == anchor["scored_counts"][p]
            and alternative["scores"][p] is not None and anchor["scores"][p] is not None else None
            for p in profiles}

    changes = []
    gain = None
    upgrade_status = None
    if plan.upgrade:
        # Upgrade only currently occupied, scored slots. No credit for adding a new player.
        active = [i for i, s in enumerate(slots) if current.get(s.slot) and s.slot not in manual]
        opts = options(primary)
        roster = set(current.values())
        replacement_options = [[row for row in opts[i] if row["entity_id"] == incumbents[i]
                                or row["entity_id"] not in roster] for i in active]
        paths = assignment_frontier(replacement_options, [incumbents[i] for i in active], count_changes=True)
        baseline = sum(round(contexts[primary][slots[i].slot][incumbents[i]].r * SCALE) for i in active)
        upgrade_status = "NO_IMPROVING_SOLUTION"
        for edits, rows in sorted(paths.items()):
            if edits == 0 or (plan.upgrade != "minimum" and edits != {"one":1, "two":2}[plan.upgrade]):
                continue
            if any(row is None for row in rows):
                continue
            delta = sum(round(row["score"] * SCALE) for row in rows) - baseline
            if delta <= 0 or delta / SCALE < plan.minimum_gain:
                continue
            gain = delta / SCALE
            upgrade_status = "EXACT_OPTIMAL"
            for idx, row in zip(active, rows):
                s = slots[idx].slot
                old, new = current[s], row["entity_id"]
                if old != new:
                    left, right = contexts[primary][s][old], contexts[primary][s][new]
                    changes.append({"slot": s, "before": card_facts(cards[old]), "after": card_facts(cards[new]),
                                    "before_score": left.r, "after_score": right.r, "delta": round(right.r-left.r, 10),
                                    "coverage_before": left.coverage_kappa, "coverage_after": right.coverage_kappa,
                                    "why": list(why_not(right, left)) if right.r >= left.r else list(why_not(left, right)),
                                    "explanation_leader": new if right.r >= left.r else old})
            break

    current_summary = summarize(current, primary)
    optimized_synergy = compute_whole_xi_synergy(plan.formation, primary, preview["slots"], cards)
    current_synergy = compute_whole_xi_synergy(plan.formation, primary, current_summary["slots"], cards) if current else None

    result = {"release_id": RELEASE, "model_version": ENGINE_VERSION, "config_version": DEFAULT_V3_CONFIG.config_version,
              "solver_status": "EXACT_OPTIMAL" if preview["scored"] else "INSUFFICIENT_EVIDENCE",
              "pool_size": len(cards), "admissible_items": len(allowed), "scope": "SELECTED_RESEARCH_ITEMS",
              "research_only": True, "price": None, "chemistry": None, "current": current_summary,
              "optimized": preview, "tactical_synergy": {"optimized": optimized_synergy, "current": current_synergy},
              "matrix": matrix, "nondominated_generated_profiles": frontier,
              "unavailable_profiles":unavailable_profiles,
              "upgrade_status": upgrade_status, "upgrade_gain": gain, "upgrades": changes}
    result["receipt"] = digest([plan.model_dump(mode="json"), RELEASE, service.reference.content_hash,
                                ENGINE_VERSION, DEFAULT_V3_CONFIG.config_version, selection,
                                [(s["slot"], s["score"]) for s in preview["slots"]]])
    return result
