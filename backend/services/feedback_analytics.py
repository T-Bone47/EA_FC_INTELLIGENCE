"""FEEDBACK ANALYTICS (§33) — deterministic, label-counting only.

This module measures whether enough labeled feedback exists to ever justify
machine learning. It NEVER trains, scores or tunes anything. The 6-phase
roadmap is explicit:

  1. CAPTURE      — feedback rows with full request context (implemented:
                    POST /api/recommendations/feedback stores context).
  2. MEASURE      — this module: volumes, acceptance rates, context coverage,
                    bias checks, label sufficiency.
  3. LABEL REVIEW — human inspection of captured labels (out of scope here).
  4. OFFLINE EXP  — only when sufficient labels exist, via the experiment
                    framework (backend/services/engine_experiments.py).
  5. SHADOW       — offline winner compared to production, never serving.
  6. GUARDED LIVE — explicit, reviewed, reversible config change.

Phases 4-6 are gated on MIN_LABELS_FOR_LEARNING and remain unreachable today:
the deterministic engine is the permanent fallback (§33).
"""
from __future__ import annotations

from typing import Optional

# Deliberately high: no ML experiment is justified below this many labeled
# selection decisions with usable request context.
MIN_LABELS_FOR_LEARNING = 500
MIN_CONTEXT_COVERAGE = 0.8


def summarize(game_version: Optional[str] = None,
              limit_top: int = 10) -> dict:
    """Deterministic analytics over user_recommendation_feedback.

    Missing data is reported as UNKNOWN — never as zero. All counts come from
    the canonical feedback table; nothing is inferred or fabricated.
    """
    try:
        from backend.core.db import query
    except Exception as exc:                          # pragma: no cover - safety
        return {"status": "UNAVAILABLE", "reason": f"feedback store unreachable: {exc}"}

    where = ""
    params: tuple = ()
    if game_version:
        where = ("JOIN game_version gv ON gv.id = f.game_version_id "
                 "WHERE gv.code = %s")
        params = (str(game_version).upper(),)

    try:
        by_action = query(
            f"""SELECT f.action, count(*)::int AS n
                FROM user_recommendation_feedback f {where}
                GROUP BY f.action ORDER BY n DESC""", params)
        total_rows = query(
            f"""SELECT count(*)::int AS n,
                       count(*) FILTER (WHERE f.request_context <> '{{}}'::jsonb)::int AS with_context,
                       count(*) FILTER (WHERE f.action IN ('SELECTED','REJECTED','ALTERNATIVE_SELECTED'))::int AS labeled
                FROM user_recommendation_feedback f {where}""", params)
        top_entities = query(
            f"""SELECT f.entity_type, f.entity_id::text AS entity_id, count(*)::int AS n
                FROM user_recommendation_feedback f {where}
                {"AND" if where else "WHERE"} f.action = 'SELECTED'
                GROUP BY f.entity_type, f.entity_id
                ORDER BY n DESC LIMIT %s""", params + (int(limit_top),))
        reasons = query(
            f"""SELECT f.reason, count(*)::int AS n
                FROM user_recommendation_feedback f {where}
                {"AND" if where else "WHERE"} f.reason IS NOT NULL
                GROUP BY f.reason ORDER BY n DESC LIMIT %s""", params + (int(limit_top),))
    except Exception as exc:
        return {"status": "UNAVAILABLE", "reason": f"feedback query failed: {exc}"}

    counts = {r["action"]: r["n"] for r in by_action}
    row = total_rows[0] if total_rows else {"n": 0, "with_context": 0, "labeled": 0}
    total = row["n"]
    with_context = row["with_context"]
    labeled = row["labeled"]

    selected = counts.get("SELECTED", 0)
    rejected = counts.get("REJECTED", 0)
    alternative = counts.get("ALTERNATIVE_SELECTED", 0)
    decisions = selected + rejected
    context_coverage = (with_context / total) if total else None

    if decisions == 0:
        acceptance_rate: object = "UNKNOWN (no SELECTED/REJECTED labels yet)"
    else:
        acceptance_rate = round(selected / decisions, 4)

    ready = (labeled >= MIN_LABELS_FOR_LEARNING
             and context_coverage is not None
             and context_coverage >= MIN_CONTEXT_COVERAGE)

    return {
        "status": "OK",
        "game_version": str(game_version).upper() if game_version else "ALL",
        "totals": {
            "feedback_rows": total,
            "with_request_context": with_context,
            "labeled_decisions": labeled,
            "by_action": counts,
        },
        "metrics": {
            "acceptance_rate": acceptance_rate,
            "alternative_selected": alternative,
            "context_coverage": round(context_coverage, 4) if context_coverage is not None
            else "UNKNOWN (no feedback rows)",
            "top_selected_entities": [dict(r) for r in top_entities],
            "rejection_reasons": [dict(r) for r in reasons],
        },
        "learning_readiness": {
            "phase": "1-CAPTURE/2-MEASURE" if not ready else "3-LABEL REVIEW",
            "min_labels_for_learning": MIN_LABELS_FOR_LEARNING,
            "min_context_coverage": MIN_CONTEXT_COVERAGE,
            "labels_have": labeled,
            "sufficient_for_ml_experiment": ready,
            "policy": ("NO ML until sufficient labels exist; the deterministic "
                       "engine is the permanent fallback (§33). Offline "
                       "experiments run through engine_experiments, never "
                       "against production config."),
        },
    }
