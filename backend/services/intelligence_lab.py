"""Intelligence Evaluation Lab (Phase 23).

A repeatable, versioned measurement harness for the V3 engine. It runs the
UNCHANGED production engine (baseline V3.1) and candidate variants against
real datasets and reports the same metric set for each, so a candidate is
adopted only on evidence and the baseline is never overwritten.

Metric set (every one measured, none assumed):
  counts / kappa / score distributions      what the engine actually sees
  tactical discrimination                   mean pairwise top-10 overlap across profiles
  opposed-tactic separation                 HIGH_PRESS vs LOW_BLOCK, POSSESSION vs COUNTER_ATTACK
  OVR dependence                            Spearman rho(R, OVR) (reported, not optimised)
  OVR independence                          shuffle OVR -> R must be bit-identical
  monotonicity                              +1 on a demanded attribute never lowers C_lo
  Pareto dominance                          uniformly weaker copy never outscores
  irrelevance                               changing a non-demanded attribute never moves C_lo
  missing-data invariant                    hiding a published value never raises C_lo
  pool independence                         a player's R is identical alone and in the pool
  determinism                               same inputs (any pool order) -> identical ranking
  stability                                 small lambda change -> top-10 overlap
  near ties                                 adjacent top-10 pairs within noise or overlapping intervals
  archetype separability                    do archetype demand vectors pick distinct players

Variants are post-engine transforms of ScoringContexts (or alternative
missing-value charges in the capability probe), so the production engine
code path is untouched while measuring.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, replace

from backend.domain.card_model import Candidate, PlayerAttributes
from backend.domain.user_model import UserRequirements
from backend.services.capability_model import compute_capability, saturate
from backend.services.demand_composition import compose_demand
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import (
    POSITION_GROUPS,
    ReferenceDistribution,
    position_group_for,
)
from backend.services.v3_config import (
    DEFAULT_V3_CONFIG,
    V3_1_CONFIG,
    V3_2_CONFIG,
    CalibratedValue,
    CalibrationStatus,
    V3Config,
)

LAB_VERSION = "lab-2026-09-30-r2"   # r2 (Phase 24): variants carry a pinned config
POSITIONS = ("CM", "CDM", "CAM", "CB", "LB", "ST", "LW", "GK")
PROFILES = ("BALANCED", "POSSESSION", "HIGH_PRESS", "LOW_BLOCK", "COUNTER_ATTACK", "DIRECT_PLAY")
OPPOSED = (("HIGH_PRESS", "LOW_BLOCK"), ("POSSESSION", "COUNTER_ATTACK"))


# ---------------------------------------------------------------------- stats
def spearman(xs: list[float], ys: list[float]) -> float:
    """Average-rank (tie-correct) Spearman, same estimator as the RD tests."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r
    n = len(xs)
    if n < 3:
        return 0.0
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def pct(values: list[float], ps=(0.01, 0.10, 0.50, 0.90, 0.99)) -> dict:
    if not values:
        return {}
    v = sorted(values)
    return {f"p{int(p * 100):02d}": round(v[min(len(v) - 1, int(p * (len(v) - 1)))], 6) for p in ps}


def ranking_hash(rows: list[tuple]) -> str:
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------- variants
@dataclass(frozen=True)
class Variant:
    """A candidate engine behaviour. `rescore(ctx, candidate)` returns the
    variant's ranking score from the baseline ScoringContext (post-engine
    transform); None means 'same as baseline'. `missing_charge` swaps the
    charge for unpublished demanded attributes in the capability probes."""
    name: str
    hypothesis: str
    rescore: Callable | None = None
    lam: float | None = None
    missing_charge: str | None = None     # None/'p10' (baseline) | 'zero' | 'p01'
    notes: str = ""
    # Engine config the variant runs on. Phase-23 experiments were defined against V3.1 and
    # stay PINNED to it so their recorded results reproduce after V3.2 became the default.
    # New experiments must pass config=... explicitly.
    config: V3Config = V3_1_CONFIG


BASELINE = Variant("V3.1-baseline", "production engine, unchanged (lambda 0.7, Model A, "
                   "interaction disabled, confidence reporting-only)")

# V3.2 (Phase 24): V3.1 + missing_value_charge ZERO. The production engine since Phase 24.
V3_2_DEFAULT = Variant("V3.2-default", "production engine since Phase 24: V3.1 + missing_value_charge "
                       "ZERO (lambda 0.7, Model A, interaction disabled, confidence reporting-only)",
                       missing_charge="zero", config=V3_2_CONFIG)
PRODUCTION_VARIANTS = (BASELINE, V3_2_DEFAULT)

# Complementary pairs: football hypotheses, NOT verified EA mechanics.
COMPLEMENT_PAIRS = (
    ("acceleration", "sprint_speed"),
    ("short_passing", "vision"),
    ("ball_control", "dribbling_detail"),
    ("defensive_awareness", "standing_tackle"),
    ("reactions", "defensive_awareness"),
)


def complementarity_score(ctx, cap: float) -> float:
    """H-INT-1 transform. m = 1 + cap * sum_p d_p * min(s_a, s_b) / sum_p d_p
    over pairs whose attributes are both demanded (d_p = pair demand weight);
    a pair with an unpublished side contributes 0."""
    by = {a.attribute: a for a in ctx.per_attribute}
    num = den = 0.0
    for a, b in COMPLEMENT_PAIRS:
        pa, pb = by.get(a), by.get(b)
        if pa is None or pb is None:
            continue
        d = pa.weight + pb.weight
        den += d
        if pa.covered and pb.covered:
            num += d * min(pa.s_eff, pb.s_eff)
    return round(ctx.r * (1.0 + (cap * num / den if den > 0 else 0.0)), 10)


def complementarity_variant(cap: float = 0.05) -> Variant:
    return Variant(
        "V3.2-cand-complementarity",
        "H-INT-1: balanced complementary attribute pairs deserve bounded credit; "
        "min() is non-decreasing in each argument (monotone by construction), uses only "
        "the candidate's own values (pool independent), and an unpublished side earns 0",
        rescore=lambda ctx, _c: complementarity_score(ctx, cap),
        notes=f"cap={cap}; pairs={COMPLEMENT_PAIRS}")


# H-GK-1: signed two-pole GK tactical demand (ENGINE_DERIVED hypothesis, uses
# only the five GK attributes every version publishes). V3.1 GK demand is
# single-pole/magnitude-only over the same five collinear attributes, which
# the lab measured as tactically inert (HIGH_PRESS vs LOW_BLOCK top-10 10/10).
GK_HIGH_POLE: dict[str, dict[str, float]] = {
    "press_intensity": {"gk_positioning": 0.45, "gk_kicking": 0.35, "gk_reflexes": 0.20},
    "block_height": {"gk_positioning": 0.50, "gk_kicking": 0.30, "gk_reflexes": 0.20},
    "build_up_speed": {"gk_kicking": 0.60, "gk_positioning": 0.20, "gk_reflexes": 0.20},
    "directness": {"gk_kicking": 0.70, "gk_handling": 0.30},
    "tempo": {"gk_kicking": 0.40, "gk_reflexes": 0.40, "gk_positioning": 0.20},
    "width": {"gk_handling": 0.40, "gk_positioning": 0.30, "gk_diving": 0.30},
}
GK_LOW_POLE: dict[str, dict[str, float]] = {
    "press_intensity": {"gk_reflexes": 0.35, "gk_diving": 0.35, "gk_handling": 0.30},
    "block_height": {"gk_diving": 0.35, "gk_reflexes": 0.35, "gk_handling": 0.30},
    "build_up_speed": {"gk_kicking": 0.50, "gk_positioning": 0.30, "gk_handling": 0.20},
    "directness": {"gk_kicking": 0.50, "gk_positioning": 0.30, "gk_handling": 0.20},
    "tempo": {"gk_handling": 0.40, "gk_positioning": 0.30, "gk_diving": 0.30},
}


def gk_signed_demand(profile: str, lam: float) -> dict[str, float]:
    from backend.services.formations import dimension_vector
    from backend.services.scoring_config import ScoringConfig
    base = ScoringConfig().position_attribute_weights("GK")
    tot = sum(base.values())
    w0 = {a: v / tot for a, v in base.items()}
    tac: dict[str, float] = {}
    for dim, value in dimension_vector(profile, None, 0.65).items():
        shift = (value - 0.5) * 2.0
        if abs(shift) < 1e-9:
            continue
        pole = GK_HIGH_POLE if shift > 0 else GK_LOW_POLE
        for a, aff in pole.get(dim, {}).items():
            tac[a] = tac.get(a, 0.0) + aff * abs(shift)
    t = sum(tac.values())
    tac = {a: v / t for a, v in tac.items()} if t > 0 else {}
    keys = set(w0) | set(tac)
    w1 = {a: (1 - lam) * w0.get(a, 0.0) + lam * tac.get(a, 0.0) for a in keys}
    s = sum(w1.values())
    return {a: v / s for a, v in w1.items()}


def gk_signed_variant() -> Variant:
    lam = DEFAULT_V3_CONFIG.lam_default.value

    def rescore(ctx, _cand):
        if ctx.position != "GK":
            return ctx.r
        w = gk_signed_demand(ctx.tactical_profile, lam)
        # per-attribute effective saturated value, including the V3.1 P10 charge
        eff = {a.attribute: (a.contribution_lo / a.weight if a.weight > 0 else 0.0)
               for a in ctx.per_attribute}
        if not set(w) <= set(eff):
            return ctx.r
        return round(sum(w[a] * eff[a] for a in w) * ctx.modifier_total, 10)
    return Variant("V3.2-cand-gk-signed-poles",
                   "H-GK-1: signed two-pole GK tactical demand over the five GK attributes",
                   rescore=rescore, notes="outfield positions unchanged by construction")


def missing_charge_variant(mode: str) -> Variant:
    return Variant(f"V3.2-cand-missing-{mode}",
                   f"charge unpublished demanded attributes at {mode} instead of the frozen P10",
                   missing_charge=mode)


# ---------------------------------------------------------------------- core runs
def make_engine(reference: ReferenceDistribution, lam: float | None = None,
                config: V3Config | None = None) -> RecommendationEngineV3:
    base = DEFAULT_V3_CONFIG if config is None else config
    cfg = base
    if lam is not None:
        cfg = replace(base, lam_default=CalibratedValue(
            lam, CalibrationStatus.POLICY, "lab override"))
    return RecommendationEngineV3(config=cfg, reference=reference, data_version=reference.version)


def family_pool(cands: list[Candidate], position: str) -> list[Candidate]:
    group = position_group_for(position)
    fam = POSITION_GROUPS.get(group, {position})
    return [c for c in cands if c.position_primary in fam or (set(c.secondary_positions) & fam)]


def score_all(engine, pool, game_version, position, profile, variant: Variant = BASELINE):
    """-> list of (score, ctx, cand) sorted like the engine: (-score, -kappa, id)."""
    req = UserRequirements(game_version=game_version, position=position,
                           tactical_profile=profile, limit=max(1, len(pool)))
    res = engine.recommend(pool, req)
    by_id = {c.entity_id: c for c in pool}
    rows = []
    for rc in res.ranked:
        ctx = rc.context
        cand = by_id[ctx.candidate_entity_id]
        s = variant.rescore(ctx, cand) if variant.rescore else ctx.r
        rows.append((s, ctx, cand))
    rows.sort(key=lambda t: (-t[0], -t[1].coverage_kappa, str(t[1].candidate_entity_id)))
    return rows, res


# ---------------------------------------------------------------------- metrics
def discrimination(engine, cands, game_version, position, variant=BASELINE) -> dict:
    pool = family_pool(cands, position)
    tops, rhos, near_ties, counts = {}, {}, [], {}
    eps = DEFAULT_V3_CONFIG.tie_epsilon.value
    for prof in PROFILES:
        rows, res = score_all(engine, pool, game_version, position, prof, variant)
        tops[prof] = [str(ctx.candidate_entity_id) for _, ctx, _ in rows[:10]]
        rated = [(s, c.overall_rating) for s, _, c in rows if c.overall_rating]
        rhos[prof] = round(spearman([s for s, _ in rated], [o for _, o in rated]), 4)
        for (sa, ca, _), (sb, cb, _) in zip(rows[:10], rows[1:10]):
            near_ties.append(1 if (sa - sb) < eps or cb.r_hi > ca.r else 0)
        if prof == "BALANCED":
            counts = {"pool": len(pool), "ranked": len(res.ranked),
                      "excluded": len(res.excluded), "not_evaluable": len(res.not_evaluable),
                      "kappa": pct([ctx.coverage_kappa for _, ctx, _ in rows]),
                      "score": pct([s for s, _, _ in rows]),
                      "top10": [(ctx.candidate_name, round(s, 4), c.overall_rating)
                                for s, ctx, c in rows[:10]]}
    overlaps = [len(set(tops[a]) & set(tops[b])) for a, b in itertools.combinations(PROFILES, 2)]
    return {
        "counts_balanced": counts,
        "mean_pairwise_top10_overlap": round(sum(overlaps) / len(overlaps), 3),
        "opposed_overlap": {f"{a}|{b}": len(set(tops[a]) & set(tops[b])) for a, b in OPPOSED},
        "rho_R_OVR": rhos,
        "rho_spread": round(max(rhos.values()) - min(rhos.values()), 4),
        "near_tie_rate_top10": round(sum(near_ties) / len(near_ties), 4) if near_ties else None,
        "top10_by_profile": tops,
    }


def _probe_sample(pool: list[Candidate], n: int, seed: int) -> list[Candidate]:
    rng = random.Random(seed)
    idx = sorted(rng.sample(range(len(pool)), min(n, len(pool))))
    return [pool[i] for i in idx]


def _cap(demand, attrs, position, reference, missing_charge=None) -> float:
    if missing_charge in (None, "p10"):
        # explicit: the lab's 'p10' probe IS the historical V3.1 charge, independent of the default
        return compute_capability(demand=demand, attributes=attrs, position=position,
                                  reference=reference, missing_charge="P10").c_lo
    total = 0.0
    for a, w in demand.items():
        v = attrs.get(a)
        if v is not None:
            total += w * saturate(v, a)
        elif missing_charge == "zero":
            continue
        elif missing_charge == "p01":
            q = reference.quantiles(position, a)
            # normal-tail extrapolation from the frozen P10/P50 (z10=1.2816, z01=2.3263)
            if q:
                sigma = (q.p50 - q.p10) / 1.2816
                total += w * saturate(max(1.0, q.p50 - 2.3263 * sigma), a)
    return round(total, 10)


def invariants(cands, game_version, position, reference, profile="BALANCED",
               n=200, seed=7, variant=BASELINE) -> dict:
    """Probe-based invariants on REAL players (perturbed copies are probes,
    never stored or served)."""
    pool = family_pool(cands, position)
    demand = compose_demand(position=position, tactical_profile=profile,
                            lam=variant.lam or DEFAULT_V3_CONFIG.lam_default.value).vector
    sample = _probe_sample(pool, n, seed)
    mono_checks = mono_viol = pareto_checks = pareto_viol = 0
    irr_checks = irr_viol = 0
    miss_checks = miss_viol = miss_viol_high = miss_high_checks = 0
    max_miss_gain = 0.0
    non_demanded = [a for a in ("volleys", "penalties", "free_kick_accuracy", "curve", "gk_diving")
                    if a not in demand]
    for c in sample:
        attrs = {a: c.attributes.get(a) for a in demand}
        base = _cap(demand, attrs, position, reference, variant.missing_charge)
        for a in demand:
            v = attrs.get(a)
            if v is None:
                continue
            if v < 99:
                mono_checks += 1
                if _cap(demand, dict(attrs, **{a: v + 1}), position, reference,
                        variant.missing_charge) < base - 1e-12:
                    mono_viol += 1
            miss_checks += 1
            gain = _cap(demand, dict(attrs, **{a: None}), position, reference,
                        variant.missing_charge) - base
            if gain > 1e-12:
                miss_viol += 1
                max_miss_gain = max(max_miss_gain, gain)
            q = reference.quantiles(position, a)
            if q and v >= q.p50:
                miss_high_checks += 1
                if gain > 1e-12:
                    miss_viol_high += 1
        weaker = {a: (max(1, v - 3) if v is not None else None) for a, v in attrs.items()}
        pareto_checks += 1
        if _cap(demand, weaker, position, reference, variant.missing_charge) > base + 1e-12:
            pareto_viol += 1
        for a in non_demanded:
            irr_checks += 1
            changed = PlayerAttributes(values=dict(c.attributes.values))
            changed.set(a, 1 if (c.attributes.get(a) or 50) > 50 else 99)
            attrs2 = {x: changed.get(x) for x in demand}
            if abs(_cap(demand, attrs2, position, reference, variant.missing_charge) - base) > 1e-12:
                irr_viol += 1
    return {
        "probe_players": len(sample), "profile": profile,
        "monotonicity": {"checks": mono_checks, "violations": mono_viol},
        "pareto": {"checks": pareto_checks, "violations": pareto_viol},
        "irrelevance": {"checks": irr_checks, "violations": irr_viol,
                        "attributes_probed": non_demanded},
        "missing_data": {"checks": miss_checks, "violations_any_value": miss_viol,
                         "high_value_checks": miss_high_checks,
                         "violations_high_value": miss_viol_high,
                         "max_gain_when_hidden": round(max_miss_gain, 6),
                         "note": ("violation = hiding a published value RAISES C_lo; possible "
                                  "only when the published value is below the charged quantile")},
    }


def engine_properties(engine, cands, game_version, position, profile="BALANCED", seed=11) -> dict:
    """Pool independence, determinism, OVR independence, lambda stability --
    run through the real engine."""
    pool = family_pool(cands, position)
    req = UserRequirements(game_version=game_version, position=position,
                           tactical_profile=profile, limit=max(1, len(pool)))
    full = engine.recommend(pool, req)
    r_full = {rc.context.candidate_entity_id: rc.context.r for rc in full.ranked}
    rng = random.Random(seed)
    probe = rng.sample(sorted(r_full, key=str), min(25, len(r_full)))
    by_id = {c.entity_id: c for c in pool}
    alone_diff = 0
    for eid in probe:
        solo = engine.recommend([by_id[eid]], replace(req, limit=1))
        if not solo.ranked or abs(solo.ranked[0].context.r - r_full[eid]) > 1e-12:
            alone_diff += 1
    shuffled = pool[:]
    rng.shuffle(shuffled)
    again = engine.recommend(list(reversed(shuffled)), req)

    def h(res):
        return ranking_hash([(str(rc.context.candidate_entity_id), rc.context.r)
                             for rc in res.ranked])
    ovrs = [c.overall_rating for c in pool]
    rng.shuffle(ovrs)
    shuf = engine.recommend([replace(c, overall_rating=o) for c, o in zip(pool, ovrs)], req)
    top10 = [rc.context.candidate_entity_id for rc in full.ranked[:10]]
    lam_top = [rc.context.candidate_entity_id
               for rc in make_engine(engine.reference, lam=0.65, config=engine.config).recommend(pool, req).ranked[:10]]
    return {
        "pool_independence": {"probes": len(probe), "score_differs_alone_vs_pool": alone_diff},
        "determinism": {"same_ranking_under_reordered_pool": h(full) == h(again), "hash": h(full)},
        "ovr_independence": {"ranking_identical_after_ovr_shuffle": h(full) == h(shuf)},
        "stability": {"top10_overlap_lambda_0.70_vs_0.65": len(set(top10) & set(lam_top))},
    }


def archetype_separability(cands, reference) -> dict:
    """Do the (v2-era, engine-derived) archetype attribute vectors select
    genuinely different players in the real data? Uses the V3 capability
    function with the archetype vector as demand -- a measurement, not a
    scoring path."""
    from backend.services.archetypes import ARCHETYPE_DEFINITIONS
    by_pos: dict[str, list[str]] = {}
    for name, d in ARCHETYPE_DEFINITIONS.items():
        for p in d["positions"]:
            by_pos.setdefault(p, []).append(name)
    out = {}
    for pos, names in sorted(by_pos.items()):
        if len(names) < 2:
            continue
        pool = [c for c in cands if c.position_primary == pos]
        tops = {}
        for name in names:
            w = ARCHETYPE_DEFINITIONS[name]["attributes"]
            tot = sum(w.values())
            demand = {a: v / tot for a, v in w.items()}
            scored = sorted(((compute_capability(
                demand=demand, attributes={a: c.attributes.get(a) for a in demand},
                position=pos, reference=reference).c_lo, str(c.entity_id)) for c in pool),
                key=lambda t: (-t[0], t[1]))
            tops[name] = [cid for _, cid in scored[:10]]
        pairs = {f"{a}|{b}": len(set(tops[a]) & set(tops[b]))
                 for a, b in itertools.combinations(names, 2)}
        out[pos] = {"pool": len(pool), "archetypes": names, "top10_overlap": pairs,
                    "mean_overlap": round(sum(pairs.values()) / len(pairs), 2)}
    return out


def run_variant(variant: Variant, cands, game_version, reference,
                positions=POSITIONS) -> dict:
    engine = make_engine(reference, lam=variant.lam, config=variant.config)
    report = {"variant": variant.name, "hypothesis": variant.hypothesis, "notes": variant.notes,
              "game_version": game_version, "reference_distribution": reference.version,
              "config_version": variant.config.config_version,
              "missing_value_charge": variant.config.missing_value_charge, "lab_version": LAB_VERSION, "positions": {}}
    for pos in positions:
        entry = {"discrimination": discrimination(engine, cands, game_version, pos, variant),
                 "invariants": invariants(cands, game_version, pos, reference, variant=variant)}
        if variant in PRODUCTION_VARIANTS:
            entry["engine_properties"] = engine_properties(engine, cands, game_version, pos)
        report["positions"][pos] = entry
    return report
