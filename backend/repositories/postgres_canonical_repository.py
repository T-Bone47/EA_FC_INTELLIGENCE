"""Canonical Postgres persistence for ingested data.

Write path used by the ingestion pipeline. Players are buffered and flushed
with COPY -> temp staging -> idempotent merge (fast for the 16K foundation,
safe for re-runs: deterministic UUIDs + ON CONFLICT upserts => no duplicates).

Synthetic firewall: rows carrying data_status=SYNTHETIC_TEST are persisted with
is_synthetic=TRUE / status flags so every production READ path can exclude them.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from backend.core.db import get_conn
from backend.domain.card_model import ALL_ATTRS, GamePlayer, UTCard
from backend.ingestion.normalizer import normalize_name

_STG_COLS = ("id,real_player_id,source_player_id,first_name,last_name,common_name,"
             "display_name,normalized_name,nation,position_primary,position_type,"
             "overall_rating,date_of_birth,height_cm,weight_kg,preferred_foot,"
             "weak_foot_stars,skill_moves_stars,gender,source_rank,identity_status,"
             "data_status,club_name,league_name,secondary_positions,playstyles_base,"
             "playstyles_plus,attrs")


def _d(v: Optional[str]) -> Optional[date]:
    return date.fromisoformat(str(v)[:10]) if v else None


class PostgresCanonicalRepository:
    """Implements ingestion.pipeline.CanonicalRepository."""

    def __init__(self, source_id: str, game_version: str):
        self.source_id = source_id
        self.game_version = game_version.upper()
        self._players: list[GamePlayer] = []
        self._cards: list[tuple[UTCard, dict]] = []

    # ------------------------------------------------------------------ buffering
    def upsert_game_player(self, gp: GamePlayer, playstyles_base: list[str],
                           playstyles_plus: list[str], playstyle_published: bool) -> None:
        if gp.game_version.value != self.game_version:
            raise ValueError("version contamination blocked at repository boundary")
        gp.playstyles_base = playstyles_base
        gp.playstyles_plus = playstyles_plus
        gp.playstyle_data_published = playstyle_published
        self._players.append(gp)

    def upsert_card(self, card: UTCard, version_payload: dict) -> None:
        if card.game_version.value != self.game_version:
            raise ValueError("version contamination blocked at repository boundary")
        self._cards.append((card, version_payload))

    # ------------------------------------------------------------------ flush
    def flush(self, observation_note: Optional[str] = None) -> dict:
        with get_conn() as conn:
            with conn.transaction():
                gv_id = self._game_version_id(conn)
                obs_id = self._record_observation(conn, gv_id, observation_note)
                counts = {"players": 0, "attributes": 0, "secondary": 0,
                          "playstyles": 0, "clubs": 0, "affiliations": 0,
                          "cards": 0, "card_versions": 0, "prices": 0}
                if self._players:
                    self._flush_players(conn, gv_id, counts)
                if self._cards:
                    self._flush_cards(conn, gv_id, obs_id, counts)
        n_players, n_cards = len(self._players), len(self._cards)
        self._players.clear()
        self._cards.clear()
        counts["players"] = n_players
        counts["cards"] = n_cards
        return counts

    # ------------------------------------------------------------------ internals
    def _game_version_id(self, conn) -> uuid.UUID:
        row = conn.execute("SELECT id FROM game_version WHERE code=%s",
                           (self.game_version,)).fetchone()
        if row is None:
            raise LookupError(f"game_version {self.game_version} not registered — "
                              "ingest refuses to run for unknown versions")
        return row["id"]

    def _record_observation(self, conn, gv_id, note) -> uuid.UUID:
        row = conn.execute(
            """INSERT INTO source_observation
                 (source_id, game_version_id, entity_type, entity_source_id,
                  snapshot_date, raw_payload, retrieval_context)
               VALUES (%s,%s,'snapshot',%s,%s,%s,'ingestion-pipeline') RETURNING id""",
            (self.source_id, gv_id, f"{self.source_id}:{self.game_version}",
             datetime.now(timezone.utc).date(),
             json.dumps({"players": len(self._players), "cards": len(self._cards),
                         "note": note or "pipeline flush"})),
        ).fetchone()
        return row["id"]

    def _flush_players(self, conn, gv_id, counts) -> None:
        conn.execute(f"""
            CREATE TEMP TABLE _stg_gp (
                id UUID, real_player_id UUID, source_player_id BIGINT,
                first_name TEXT, last_name TEXT, common_name TEXT,
                display_name TEXT, normalized_name TEXT, nation TEXT,
                position_primary TEXT, position_type TEXT, overall_rating INT,
                date_of_birth DATE, height_cm SMALLINT, weight_kg SMALLINT,
                preferred_foot TEXT, weak_foot_stars SMALLINT, skill_moves_stars SMALLINT,
                gender TEXT, source_rank INT, identity_status TEXT, data_status TEXT,
                club_name TEXT, league_name TEXT,
                secondary_positions TEXT, playstyles_base TEXT, playstyles_plus TEXT,
                attrs JSONB) ON COMMIT DROP""")

        rows = []
        for gp in self._players:
            rows.append((
                str(gp.id), str(gp.real_player_id) if gp.real_player_id else None,
                gp.source_player_id, gp.first_name, gp.last_name, gp.common_name,
                gp.display_name, normalize_name(gp.display_name), gp.nation,
                gp.position_primary, gp.position_type, gp.overall_rating,
                _d(gp.date_of_birth), gp.height_cm, gp.weight_kg,
                gp.preferred_foot, gp.weak_foot_stars, gp.skill_moves_stars,
                gp.gender, gp.source_rank, gp.identity_status.value,
                gp.data_status.value, gp.club, gp.league,
                ";".join(gp.secondary_positions),
                ";".join(gp.playstyles_base), ";".join(gp.playstyles_plus),
                json.dumps(gp.attributes.known()),
            ))
        with conn.cursor() as cur:
            with cur.copy(f"COPY _stg_gp ({_STG_COLS}) FROM STDIN") as copy:
                for r in rows:
                    copy.write_row(r)

        # ---- merge game_player
        conn.execute("""
            INSERT INTO game_player (id, game_version_id, real_player_id, source_id,
                source_player_id, first_name, last_name, common_name, display_name,
                normalized_name, nation, position_primary, position_type, overall_rating,
                date_of_birth, height_cm, weight_kg, preferred_foot, weak_foot_stars,
                skill_moves_stars, gender, source_rank, identity_status, data_status)
            SELECT s.id, %(gv)s, s.real_player_id, %(src)s, s.source_player_id,
                s.first_name, s.last_name, s.common_name, s.display_name,
                s.normalized_name, s.nation, s.position_primary, s.position_type,
                s.overall_rating, s.date_of_birth, s.height_cm, s.weight_kg,
                s.preferred_foot, s.weak_foot_stars, s.skill_moves_stars, s.gender,
                s.source_rank, s.identity_status, s.data_status
            FROM _stg_gp s
            ON CONFLICT (game_version_id, source_id, source_player_id) DO UPDATE SET
                real_player_id = COALESCE(EXCLUDED.real_player_id, game_player.real_player_id),
                first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name,
                common_name = EXCLUDED.common_name, display_name = EXCLUDED.display_name,
                normalized_name = EXCLUDED.normalized_name, nation = EXCLUDED.nation,
                position_primary = EXCLUDED.position_primary,
                position_type = EXCLUDED.position_type,
                overall_rating = EXCLUDED.overall_rating,
                date_of_birth = EXCLUDED.date_of_birth, height_cm = EXCLUDED.height_cm,
                weight_kg = EXCLUDED.weight_kg, preferred_foot = EXCLUDED.preferred_foot,
                weak_foot_stars = EXCLUDED.weak_foot_stars,
                skill_moves_stars = EXCLUDED.skill_moves_stars, gender = EXCLUDED.gender,
                source_rank = EXCLUDED.source_rank,
                identity_status = EXCLUDED.identity_status,
                data_status = EXCLUDED.data_status,
                updated_at = now()""", {"gv": gv_id, "src": self.source_id})

        # ---- re-point staging ids at the CANONICAL ids (an upsert may have hit
        # an existing row whose id differs from the freshly generated staging id;
        # every child insert below must use the persisted parent id)
        conn.execute("""
            UPDATE _stg_gp s SET id = gp.id
            FROM game_player gp
            WHERE gp.game_version_id = %(gv)s AND gp.source_id = %(src)s
              AND gp.source_player_id = s.source_player_id
              AND gp.id <> s.id""", {"gv": gv_id, "src": self.source_id})

        # ---- attributes (JSONB -> typed wide columns)
        attr_cols = ", ".join(ALL_ATTRS)
        sel = ", ".join(f"(a.{c})::SMALLINT" for c in ALL_ATTRS)
        upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in ALL_ATTRS)
        conn.execute(f"""
            INSERT INTO game_player_attributes (game_player_id, {attr_cols})
            SELECT s.id, {sel}
            FROM _stg_gp s
            CROSS JOIN LATERAL jsonb_populate_record(NULL::game_player_attributes,
                                                     s.attrs) AS a
            ON CONFLICT (game_player_id) DO UPDATE SET {upd}""")
        counts["attributes"] = len(self._players)

        # ---- secondary positions
        conn.execute("""
            INSERT INTO game_player_position_secondary (game_player_id, position, sort_order)
            SELECT s.id, upper(trim(t.pos)), t.ord
            FROM _stg_gp s
            CROSS JOIN LATERAL unnest(string_to_array(s.secondary_positions, ';'))
                 WITH ORDINALITY AS t(pos, ord)
            WHERE s.secondary_positions <> ''
            ON CONFLICT (game_player_id, position) DO NOTHING""")

        # ---- playstyle definitions + links
        conn.execute("""
            CREATE OR REPLACE FUNCTION normalize_ps(TEXT) RETURNS TEXT
            LANGUAGE sql IMMUTABLE AS $$
              SELECT lower(regexp_replace(coalesce($1,''), '[^A-Za-z0-9 ]', '', 'g'))
            $$""")
        conn.execute("""
            INSERT INTO playstyle_definition (game_version_id, playstyle_name,
                                              normalized_name, data_status)
            SELECT DISTINCT %(gv)s, trim(t.ps), normalize_ps(trim(t.ps)), 'CANONICAL'
            FROM _stg_gp s
            CROSS JOIN LATERAL unnest(string_to_array(
                s.playstyles_base || ';' || s.playstyles_plus, ';')) AS t(ps)
            WHERE trim(t.ps) <> ''
            ON CONFLICT (game_version_id, normalized_name) DO NOTHING""", {"gv": gv_id})
        conn.execute("""
            INSERT INTO game_player_playstyle (game_player_id, playstyle_definition_id, tier)
            SELECT s.id, d.id,
                   CASE WHEN trim(t.ps) = ANY(string_to_array(s.playstyles_plus, ';'))
                        THEN 'plus' ELSE 'base' END
            FROM _stg_gp s
            CROSS JOIN LATERAL unnest(string_to_array(
                s.playstyles_base || ';' || s.playstyles_plus, ';')) AS t(ps)
            JOIN playstyle_definition d
              ON d.game_version_id = %(gv)s AND d.normalized_name = normalize_ps(trim(t.ps))
            WHERE trim(t.ps) <> ''
            ON CONFLICT (game_player_id, playstyle_definition_id)
            DO UPDATE SET tier = EXCLUDED.tier""", {"gv": gv_id})

        # ---- clubs + affiliations
        conn.execute("""
            INSERT INTO club (name, normalized_name, league_name, nation)
            SELECT DISTINCT ON (lower(s.club_name), s.league_name)
                   s.club_name, lower(s.club_name), s.league_name, s.nation
            FROM _stg_gp s
            WHERE s.club_name IS NOT NULL AND s.club_name <> ''
            ORDER BY lower(s.club_name), s.league_name, s.club_name
            ON CONFLICT (normalized_name, league_name) DO NOTHING""")
        conn.execute("""
            INSERT INTO club_affiliation (club_id, game_version_id, game_player_id, source_id)
            SELECT c.id, %(gv)s, s.id, %(src)s
            FROM _stg_gp s
            JOIN club c ON c.normalized_name = lower(s.club_name)
                       AND c.league_name IS NOT DISTINCT FROM s.league_name
            WHERE s.club_name IS NOT NULL AND s.club_name <> ''
            ON CONFLICT (game_player_id, game_version_id)
            DO UPDATE SET club_id = EXCLUDED.club_id, source_id = EXCLUDED.source_id""",
            {"gv": gv_id, "src": self.source_id})

        counts["secondary"] = conn.execute(
            "SELECT count(*) c FROM game_player_position_secondary").fetchone()["c"]
        counts["playstyles"] = conn.execute(
            "SELECT count(*) c FROM game_player_playstyle").fetchone()["c"]
        counts["clubs"] = conn.execute("SELECT count(*) c FROM club").fetchone()["c"]
        counts["affiliations"] = conn.execute(
            "SELECT count(*) c FROM club_affiliation").fetchone()["c"]

    def _flush_cards(self, conn, gv_id, obs_id, counts) -> None:
        for card, vp in self._cards:
            rarity_id = None
            if card.rarity:
                row = conn.execute(
                    """SELECT id FROM card_rarity
                       WHERE game_version_id=%s AND lower(rarity_code)=lower(%s)""",
                    (gv_id, card.rarity)).fetchone()
                if row:
                    rarity_id = row["id"]
            conn.execute("""
                INSERT INTO ut_card (id, game_version_id, game_player_id, source_id,
                                     source_card_id, card_name, rarity_id, position,
                                     overall_rating, is_synthetic, data_status,
                                     canonical_card_id, card_type, rarity_raw,
                                     release_group, release_date, identity_status,
                                     identity_rule, playstyle_data_published)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_id, source_card_id, game_version_id) DO UPDATE SET
                    card_name = EXCLUDED.card_name, rarity_id = EXCLUDED.rarity_id,
                    position = EXCLUDED.position, overall_rating = EXCLUDED.overall_rating,
                    is_synthetic = EXCLUDED.is_synthetic, data_status = EXCLUDED.data_status,
                    canonical_card_id = coalesce(EXCLUDED.canonical_card_id,
                                                 ut_card.canonical_card_id),
                    card_type = coalesce(EXCLUDED.card_type, ut_card.card_type),
                    rarity_raw = coalesce(EXCLUDED.rarity_raw, ut_card.rarity_raw),
                    release_group = coalesce(EXCLUDED.release_group, ut_card.release_group),
                    release_date = coalesce(EXCLUDED.release_date, ut_card.release_date),
                    identity_status = CASE
                        WHEN EXCLUDED.identity_status = 'RESOLVED' THEN 'RESOLVED'
                        ELSE ut_card.identity_status END,
                    identity_rule = coalesce(EXCLUDED.identity_rule, ut_card.identity_rule),
                    playstyle_data_published = EXCLUDED.playstyle_data_published
                                               OR ut_card.playstyle_data_published,
                    updated_at = now()""",
                (str(card.id), gv_id, str(card.game_player_id) if card.game_player_id else None,
                 card.source_id, card.source_card_id, card.card_name, rarity_id,
                 card.position, card.overall_rating, card.is_synthetic,
                 card.data_status.value,
                 str(card.canonical_card_id) if card.canonical_card_id else None,
                 card.card_type, card.rarity_raw, card.release_group,
                 _d(card.release_date), card.identity_status.value,
                 card.identity_rule, card.playstyle_data_published))
            # resolve the CANONICAL card id (an upsert may have kept an
            # existing row with a different id than the one we generated)
            canonical_id = conn.execute(
                """SELECT id FROM ut_card
                   WHERE source_id=%s AND source_card_id=%s AND game_version_id=%s""",
                (card.source_id, card.source_card_id, gv_id)).fetchone()["id"]
            for code, val in card.attribute_overrides.items():
                if val is None:
                    continue
                conn.execute("""
                    INSERT INTO ut_card_attribute_override (ut_card_id, attribute_code, value)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (ut_card_id, attribute_code)
                    DO UPDATE SET value = EXCLUDED.value""",
                    (canonical_id, code, val))
            for ps in card.playstyles_base:
                conn.execute("""
                    INSERT INTO ut_card_playstyle (ut_card_id, playstyle_name, tier)
                    VALUES (%s,%s,'base')
                    ON CONFLICT (ut_card_id, playstyle_name, tier) DO NOTHING""",
                    (canonical_id, ps))
            for ps in card.playstyles_plus:
                conn.execute("""
                    INSERT INTO ut_card_playstyle (ut_card_id, playstyle_name, tier)
                    VALUES (%s,%s,'plus')
                    ON CONFLICT (ut_card_id, playstyle_name, tier) DO NOTHING""",
                    (canonical_id, ps))
            # card versions (§3): same content hash -> no-op (idempotent);
            # new content -> close the previous current version and append the
            # next version_number. Upgrades are history, never overwrites.
            existing = conn.execute(
                """SELECT id, version_number FROM card_version
                   WHERE ut_card_id=%s AND content_hash=%s""",
                (canonical_id, vp["content_hash"])).fetchone()
            if existing is None:
                conn.execute(
                    """UPDATE card_version SET is_current = FALSE,
                          valid_to = now()
                       WHERE ut_card_id=%s AND is_current = TRUE""",
                    (canonical_id,))
                maxv = conn.execute(
                    "SELECT coalesce(max(version_number), 0) AS n FROM card_version WHERE ut_card_id=%s",
                    (canonical_id,)).fetchone()["n"]
                conn.execute("""
                    INSERT INTO card_version (id, ut_card_id, version_number, content_hash,
                                              overall_rating, attributes, playstyles,
                                              source_observation_id, is_current)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)""",
                    (vp["version_id"], canonical_id, maxv + 1, vp["content_hash"],
                     card.overall_rating, json.dumps(vp["attributes"]),
                     json.dumps(vp["playstyles"]), obs_id))
                counts["card_versions"] += 1
            # price observation (§13): persisted ONLY when the source published
            # one; NULL/absent stays UNKNOWN and no row is written.
            if card.price_coins is not None:
                conn.execute("""
                    INSERT INTO card_price (ut_card_id, platform, price_coins,
                                            observed_at, source_observation_id,
                                            confidence, source_id, currency,
                                            valid_from, source_authority)
                    VALUES (%s,'UNKNOWN',%s,now(),%s,NULL,%s,'COINS',now(),NULL)""",
                    (canonical_id, card.price_coins, obs_id, card.source_id))
                counts.setdefault("prices", 0)
                counts["prices"] += 1
