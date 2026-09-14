"""Squad, slot and saved-player persistence. Ownership checks live in the API
layer; this repository always scopes queries by user_profile_id so a missing
check cannot leak cross-user data by accident."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from backend.core.db import execute, get_conn, query, query_one
from backend.domain.user_model import SquadContext, SquadSlot


class SquadRepository:
    # ------------------------------------------------------------------ squads
    def create_squad(self, user_id: uuid.UUID, name: str, formation: str,
                     game_version_id: uuid.UUID, tactics: Optional[dict] = None) -> dict:
        row = query_one(
            """INSERT INTO user_squad (user_profile_id, name, formation,
                                       game_version_id, tactics)
               VALUES (%s,%s,%s,%s,%s)
               RETURNING id, name, formation, game_version_id, tactics, created_at""",
            (str(user_id), name.strip(), formation.upper(), str(game_version_id),
             json.dumps(tactics or {})))
        return dict(row)  # type: ignore[arg-type]

    def list_squads(self, user_id: uuid.UUID) -> list[dict]:
        rows = query(
            """SELECT s.id, s.name, s.formation, gv.code AS game_version,
                      s.tactics, s.created_at, s.updated_at,
                      (SELECT count(*) FROM user_squad_slot sl
                        WHERE sl.squad_id = s.id AND
                              (sl.game_player_id IS NOT NULL OR sl.ut_card_id IS NOT NULL)
                      ) AS filled_slots
               FROM user_squad s JOIN game_version gv ON gv.id = s.game_version_id
               WHERE s.user_profile_id = %s ORDER BY s.created_at""", (str(user_id),))
        return [dict(r) for r in rows]

    def get_squad(self, user_id: uuid.UUID, squad_id: uuid.UUID) -> Optional[dict]:
        row = query_one(
            """SELECT s.*, gv.code AS game_version_code, gv.id AS game_version_id
               FROM user_squad s JOIN game_version gv ON gv.id = s.game_version_id
               WHERE s.id = %s AND s.user_profile_id = %s""",
            (str(squad_id), str(user_id)))
        return dict(row) if row else None

    def delete_squad(self, user_id: uuid.UUID, squad_id: uuid.UUID) -> int:
        return execute("DELETE FROM user_squad WHERE id=%s AND user_profile_id=%s",
                       (str(squad_id), str(user_id)))

    def rename_squad(self, user_id: uuid.UUID, squad_id: uuid.UUID,
                     name: Optional[str] = None, formation: Optional[str] = None,
                     tactics: Optional[dict] = None) -> int:
        return execute(
            """UPDATE user_squad SET
                 name = COALESCE(%s, name),
                 formation = COALESCE(%s, formation),
                 tactics = COALESCE(%s::jsonb, tactics),
                 updated_at = now()
               WHERE id=%s AND user_profile_id=%s""",
            (name, formation.upper() if formation else None,
             json.dumps(tactics) if tactics is not None else None,
             str(squad_id), str(user_id)))

    # ------------------------------------------------------------------ slots
    def assign_slot(self, squad_id: uuid.UUID, user_id: uuid.UUID, slot_index: int,
                    slot_position: str,
                    game_player_id: Optional[uuid.UUID] = None,
                    ut_card_id: Optional[uuid.UUID] = None) -> None:
        execute(
            """INSERT INTO user_squad_slot (user_profile_id, squad_id, formation,
                                            slot_index, slot_position,
                                            game_player_id, ut_card_id)
               VALUES (%s,%s,(SELECT formation FROM user_squad WHERE id=%s),%s,%s,%s,%s)
               ON CONFLICT (squad_id, slot_index) DO UPDATE SET
                 slot_position = EXCLUDED.slot_position,
                 game_player_id = EXCLUDED.game_player_id,
                 ut_card_id = EXCLUDED.ut_card_id""",
            (str(user_id), str(squad_id), str(squad_id), slot_index,
             slot_position.upper(),
             str(game_player_id) if game_player_id else None,
             str(ut_card_id) if ut_card_id else None))

    def clear_slot(self, squad_id: uuid.UUID, user_id: uuid.UUID, slot_index: int) -> int:
        return execute(
            """DELETE FROM user_squad_slot WHERE squad_id=%s AND slot_index=%s
               AND user_profile_id=%s""", (str(squad_id), slot_index, str(user_id)))

    def slots(self, squad_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
        rows = query(
            """SELECT sl.id, sl.slot_index, sl.slot_position, sl.game_player_id,
                      sl.ut_card_id, gp.display_name AS player_name,
                      gp.overall_rating, gp.position_primary, gp.nation,
                      c.name AS club, c.league_name AS league
               FROM user_squad_slot sl
               LEFT JOIN game_player gp ON gp.id = sl.game_player_id
               LEFT JOIN club_affiliation ca ON ca.game_player_id = gp.id
                 AND ca.game_version_id = gp.game_version_id
               LEFT JOIN club c ON c.id = ca.club_id
               WHERE sl.squad_id=%s AND sl.user_profile_id=%s
               ORDER BY sl.slot_index""", (str(squad_id), str(user_id)))
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ context
    def squad_context(self, user_id: uuid.UUID, squad_id: uuid.UUID) -> Optional[SquadContext]:
        """Builds the engine SquadContext with VERIFIED link facts only."""
        squad = self.get_squad(user_id, squad_id)
        if squad is None:
            return None
        slots = []
        for s in self.slots(squad_id, user_id):
            slots.append(SquadSlot(
                slot_index=s["slot_index"], slot_position=s["slot_position"],
                game_player_id=s["game_player_id"], ut_card_id=s["ut_card_id"],
                club=s.get("club"), league=s.get("league"), nation=s.get("nation")))
        return SquadContext(squad_id=squad_id, formation=squad["formation"],
                            game_version=squad["game_version_code"], slots=slots)

    # ------------------------------------------------------------------ saved
    def save_player(self, user_id: uuid.UUID, game_version_id: uuid.UUID,
                    entity_type: str, entity_id: uuid.UUID,
                    note: Optional[str] = None) -> None:
        execute(
            """INSERT INTO user_saved_player (user_profile_id, game_version_id,
                                              entity_type, entity_id, note)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (user_profile_id, entity_type, entity_id)
               DO UPDATE SET note = COALESCE(EXCLUDED.note, user_saved_player.note)""",
            (str(user_id), str(game_version_id), entity_type, str(entity_id), note))

    def unsave_player(self, user_id: uuid.UUID, entity_type: str,
                      entity_id: uuid.UUID) -> int:
        return execute(
            """DELETE FROM user_saved_player
               WHERE user_profile_id=%s AND entity_type=%s AND entity_id=%s""",
            (str(user_id), entity_type, str(entity_id)))

    def saved_players(self, user_id: uuid.UUID,
                      game_version: Optional[str] = None) -> list[dict]:
        rows = query(
            """SELECT sp.id, sp.entity_type, sp.entity_id, sp.note, sp.created_at,
                      gv.code AS game_version,
                      gp.display_name, gp.overall_rating, gp.position_primary,
                      gp.nation
               FROM user_saved_player sp
               JOIN game_version gv ON gv.id = sp.game_version_id
               LEFT JOIN game_player gp ON gp.id = sp.entity_id
               WHERE sp.user_profile_id = %s
                 AND (%s::text IS NULL OR gv.code = %s)
               ORDER BY sp.created_at DESC""",
            (str(user_id), game_version, game_version))
        return [dict(r) for r in rows]
