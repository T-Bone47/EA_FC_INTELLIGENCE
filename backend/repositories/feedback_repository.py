"""Recommendation feedback persistence — the future training-data pipeline (§34).

Every recommendation shown/selected/rejected is captured with its full request
context and game version, so a future learning-to-rank stage has real labels.
Deterministic engine first; ML only after enough high-quality labels exist.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from backend.core.db import execute, query, query_one


class FeedbackRepository:
    def record(self, user_id: Optional[uuid.UUID], game_version_id: Optional[uuid.UUID],
               action: str, entity_type: str, entity_id: Optional[uuid.UUID],
               request_context: dict, recommendation_id: Optional[str] = None,
               reason: Optional[str] = None) -> uuid.UUID:
        row = query_one(
            """INSERT INTO user_recommendation_feedback
                 (user_profile_id, game_version_id, request_context, recommendation_id,
                  entity_type, entity_id, action, reason)
               VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING id""",
            (str(user_id) if user_id else None,
             str(game_version_id) if game_version_id else None,
             json.dumps(request_context, default=str),
             recommendation_id, entity_type,
             str(entity_id) if entity_id else None, action, reason))
        return row["id"]  # type: ignore[return-value]

    def count_for_recommendation(self, recommendation_id: str) -> dict[str, int]:
        rows = query(
            """SELECT action, count(*)::int AS n
               FROM user_recommendation_feedback
               WHERE recommendation_id = %s GROUP BY action""", (recommendation_id,))
        return {r["action"]: r["n"] for r in rows}

    def label_stats(self) -> dict:
        """Readiness gauge for a future ML stage (never triggers ML by itself)."""
        row = query_one(
            """SELECT count(*)::int AS total,
                      count(*) FILTER (WHERE action IN ('SELECTED','REJECTED',
                                                        'ALTERNATIVE_SELECTED'))::int AS labeled
               FROM user_recommendation_feedback""")
        return dict(row) if row else {"total": 0, "labeled": 0}
