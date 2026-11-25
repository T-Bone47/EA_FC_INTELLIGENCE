"""Production read-side repository: search, player pages, card pages.

Catalogue record queries default to canonical rows and scope them by game
version. The API applies release permission separately. Local diagnostics can
count quarantined records or explicitly inspect synthetic fixtures.
"""
from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any, Optional

from backend.core.db import get_catalogue_conn as get_conn

# Allow-list, not deny-list: `<> 'SYNTHETIC_TEST'` (the pre-Phase-22 filter)
# would have served RESEARCH_ONLY and PENDING_REVIEW rows.
PROD_FILTER = "gp.data_status = 'CANONICAL'"
CARD_FILTER = "uc.data_status = 'CANONICAL' AND uc.is_synthetic = FALSE"

SORTABLE = {
    "overall_rating": "gp.overall_rating",
    "name": "gp.display_name",
    "pace": "a.pace", "shooting": "a.shooting", "passing": "a.passing",
    "dribbling": "a.dribbling", "defending": "a.defending", "physicality": "a.physicality",
    "source_rank": "gp.source_rank",
}


class PlayerRepository:
    # ------------------------------------------------------------------ search
    def search(self, game_version_id: uuid.UUID,
               q: Optional[str] = None,
               position: Optional[str] = None,
               positions: Optional[list[str]] = None,
               club: Optional[str] = None,
               nation: Optional[str] = None,
               league: Optional[str] = None,
               ovr_min: Optional[int] = None,
               ovr_max: Optional[int] = None,
               playstyle: Optional[str] = None,
               sort: str = "overall_rating",
               sort_dir: str = "desc",
               page: int = 1,
               page_size: int = 25, *, research: bool = False) -> dict[str, Any]:
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        player_status = "gp.data_status = 'RESEARCH_ONLY'" if research else PROD_FILTER
        where = ["gp.game_version_id = %(gv)s", player_status]
        params: dict[str, Any] = {"gv": game_version_id}

        if q:
            # '%%' -> psycopg unescapes to the pg_trgm similarity operator '%'
            where.append("(gp.display_name ILIKE %(like)s OR gp.normalized_name "
                         "%% %(like)s OR gp.nation ILIKE %(like)s "
                         "OR c.name ILIKE %(like)s)")
            params["like"] = f"%{q}%"
        if position:
            positions = [position]
        if positions:
            where.append("""(gp.position_primary = ANY(%(pos)s) OR EXISTS (
                SELECT 1 FROM game_player_position_secondary sp
                WHERE sp.game_player_id = gp.id AND sp.position = ANY(%(pos)s)))""")
            params["pos"] = [p.upper() for p in positions]
        if club:
            where.append("c.name ILIKE %(club)s")
            params["club"] = f"%{club}%"
        if nation:
            where.append("gp.nation ILIKE %(nation)s")
            params["nation"] = f"%{nation}%"
        if league:
            where.append("c.league_name ILIKE %(league)s")
            params["league"] = f"%{league}%"
        if ovr_min is not None:
            where.append("gp.overall_rating >= %(ovr_min)s")
            params["ovr_min"] = ovr_min
        if ovr_max is not None:
            where.append("gp.overall_rating <= %(ovr_max)s")
            params["ovr_max"] = ovr_max
        if playstyle:
            where.append("""EXISTS (SELECT 1 FROM game_player_playstyle gpp
                JOIN playstyle_definition pd ON pd.id = gpp.playstyle_definition_id
                WHERE gpp.game_player_id = gp.id
                  AND pd.game_version_id = gp.game_version_id AND pd.data_status = gp.data_status
                  AND pd.normalized_name = lower(regexp_replace(%(ps)s, '[^A-Za-z0-9 ]','','g')))""")
            params["ps"] = playstyle

        where_sql = " AND ".join(where)
        sort_col = SORTABLE.get(sort, SORTABLE["overall_rating"])
        direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
        nulls = "NULLS LAST"

        from_sql = """
            FROM game_player gp
            LEFT JOIN game_player_attributes a ON a.game_player_id = gp.id
            LEFT JOIN club_affiliation ca ON ca.game_player_id = gp.id
                     AND ca.game_version_id = gp.game_version_id
            LEFT JOIN club c ON c.id = ca.club_id"""

        with get_conn(local_fc27_research=research) as conn:
            total = conn.execute(
                f"SELECT count(*) AS n {from_sql} WHERE {where_sql}",
                params).fetchone()["n"]
            rows = conn.execute(f"""
                SELECT gp.id, gp.source_player_id, gp.display_name, gp.first_name,
                       gp.last_name, gp.common_name, gp.nation, c.name AS club,
                       c.league_name AS league, gp.position_primary, gp.position_type,
                       gp.overall_rating, gp.source_rank, gp.data_status,
                       gp.identity_status, gp.preferred_foot, gp.weak_foot_stars,
                       gp.skill_moves_stars, gp.date_of_birth, gp.height_cm, gp.weight_kg,
                       a.pace, a.shooting, a.passing, a.dribbling, a.defending, a.physicality,
                       ARRAY(SELECT DISTINCT sp.position FROM game_player_position_secondary sp
                             WHERE sp.game_player_id = gp.id ORDER BY sp.position) AS secondary_positions
                {from_sql}
                WHERE {where_sql}
                ORDER BY {sort_col} {direction} {nulls}, gp.display_name ASC
                LIMIT %(limit)s OFFSET %(offset)s""",
                {**params, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
        return {"total": total, "page": page, "page_size": page_size,
                "items": [dict(r) for r in rows]}

    # ------------------------------------------------------------------ player page
    def player_page(self, game_version_id: uuid.UUID,
                    player_id: uuid.UUID, *, include_cards: bool = True,
                    include_other_versions: bool = True, research: bool = False) -> Optional[dict]:
        """Full RealPlayer -> GamePlayer -> UTCard aggregate with provenance."""
        player_status = "gp.data_status = 'RESEARCH_ONLY'" if research else PROD_FILTER
        with get_conn(local_fc27_research=research) as conn:
            gp = conn.execute(f"""
                SELECT gp.*, c.name AS club, c.league_name AS league,
                       rp.full_name AS real_player_name,
                       rp.identity_status AS real_identity_status
                FROM game_player gp
                LEFT JOIN club_affiliation ca ON ca.game_player_id = gp.id
                         AND ca.game_version_id = gp.game_version_id
                LEFT JOIN club c ON c.id = ca.club_id
                LEFT JOIN real_player rp ON rp.id = gp.real_player_id AND rp.data_status = 'CANONICAL'
                WHERE gp.id = %(id)s AND gp.game_version_id = %(gv)s AND {player_status}""",
                {"id": player_id, "gv": game_version_id}).fetchone()
            if gp is None:
                return None
            attrs = conn.execute(
                "SELECT * FROM game_player_attributes WHERE game_player_id=%s",
                (player_id,)).fetchone()
            secondary = conn.execute(
                """SELECT position FROM game_player_position_secondary
                   WHERE game_player_id=%s ORDER BY sort_order""",
                (player_id,)).fetchall()
            playstyles = conn.execute(
                """SELECT pd.playstyle_name, gpp.tier
                   FROM game_player_playstyle gpp
                   JOIN playstyle_definition pd ON pd.id = gpp.playstyle_definition_id
                   WHERE gpp.game_player_id=%s AND pd.game_version_id=%s
                     AND pd.data_status = %s
                   ORDER BY gpp.tier, pd.playstyle_name""",
                (player_id, game_version_id, gp["data_status"])).fetchall()
            cards = conn.execute(
                f"""SELECT uc.id, uc.card_name, uc.position, uc.overall_rating,
                          uc.data_status, uc.source_card_id, cr.rarity_code,
                          uc.created_at
                   FROM ut_card uc
                   LEFT JOIN card_rarity cr ON cr.id = uc.rarity_id
                   WHERE uc.game_player_id=%s AND uc.game_version_id=%s AND {CARD_FILTER}
                   ORDER BY uc.overall_rating DESC NULLS LAST, uc.card_name""",
                (player_id, game_version_id)).fetchall() if include_cards else []
            versions = conn.execute(
                """SELECT gv.code FROM game_version gv WHERE gv.id=%s""",
                (game_version_id,)).fetchone()
            provenance = conn.execute(
                """SELECT sr.source_id, sr.name, sr.authority_tier, sr.usage_status,
                          sr.license, sr.url
                   FROM game_player gp JOIN source_registry sr ON sr.source_id = gp.source_id
                   WHERE gp.id=%s""", (player_id,)).fetchone()
            freshness = conn.execute(
                """SELECT max(so.observed_at) AS last_observed
                   FROM source_observation so
                   WHERE so.source_id = (SELECT source_id FROM game_player WHERE id=%s)
                     AND so.game_version_id = %s""",
                (player_id, game_version_id)).fetchone()
            # sibling game versions of the same real player (never mixed, listed only)
            siblings = []
            if include_other_versions and gp.get("real_player_id"):
                siblings = conn.execute(
                    """SELECT g2.id, g2.display_name, gv2.code AS game_version
                       FROM game_player g2 JOIN game_version gv2 ON gv2.id = g2.game_version_id
                       WHERE g2.real_player_id=%s AND g2.id <> %s
                         AND g2.data_status = 'CANONICAL'""",
                    (gp["real_player_id"], player_id)).fetchall()

        return {
            "game_version": versions["code"] if versions else None,
            "game_player": dict(gp),
            "attributes": dict(attrs) if attrs else None,
            "secondary_positions": [r["position"] for r in secondary],
            "playstyles": [{"name": r["playstyle_name"], "tier": r["tier"]} for r in playstyles],
            "playstyle_data_published": bool(playstyles),
            "cards": [dict(r) for r in cards],
            "other_game_versions": [dict(r) for r in siblings],
            "provenance": dict(provenance) if provenance else None,
            "freshness": {"last_observed": freshness["last_observed"].isoformat()
                          if freshness and freshness["last_observed"] else None},
        }

    # ------------------------------------------------------------------ card page
    def card_page(self, game_version_id: uuid.UUID, card_id: uuid.UUID, *,
                  include_player: bool = True, include_synthetic: bool = False, connection=None) -> Optional[dict]:
        visible = CARD_FILTER
        if include_synthetic:
            visible = f"({CARD_FILTER} OR (uc.data_status = 'SYNTHETIC_TEST' AND uc.is_synthetic))"
        with (get_conn() if connection is None else nullcontext(connection)) as conn:
            card = conn.execute(
                f"""SELECT uc.*, cr.rarity_code, cr.rarity_name
                   FROM ut_card uc LEFT JOIN card_rarity cr ON cr.id = uc.rarity_id
                   WHERE uc.id=%s AND uc.game_version_id=%s AND {visible}""",
                (card_id, game_version_id)).fetchone()
            if card is None:
                return None
            overrides = conn.execute(
                "SELECT attribute_code, value FROM ut_card_attribute_override WHERE ut_card_id=%s",
                (card_id,)).fetchall()
            playstyles = conn.execute(
                "SELECT playstyle_name, tier FROM ut_card_playstyle WHERE ut_card_id=%s",
                (card_id,)).fetchall()
            versions = conn.execute(
                """SELECT version_number, content_hash, overall_rating, valid_from,
                          is_current
                   FROM card_version WHERE ut_card_id=%s ORDER BY version_number""",
                (card_id,)).fetchall()
            price = conn.execute(
                """SELECT price_coins, platform, observed_at, confidence
                   FROM card_price WHERE ut_card_id=%s
                   ORDER BY observed_at DESC LIMIT 1""", (card_id,)).fetchone()
            player = None
            if include_player and card.get("game_player_id"):
                player = conn.execute(
                    f"""SELECT id, display_name, position_primary, overall_rating
                        FROM game_player gp WHERE id=%s AND game_version_id=%s AND {PROD_FILTER}""",
                    (card["game_player_id"], game_version_id)).fetchone()
            card = dict(card)
            if player is None:
                card["game_player_id"] = None
        return {
            "card": dict(card),
            "attribute_overrides": {r["attribute_code"]: r["value"] for r in overrides},
            "playstyles": [dict(r) for r in playstyles],
            "versions": [dict(r) for r in versions],
            "price": dict(price) if price else None,   # None => UNKNOWN, never 0
            "game_player": dict(player) if player else None,
        }

    def card_pair(self, game_version_id: uuid.UUID, ids: tuple[uuid.UUID, uuid.UUID]) -> list[dict | None]:
        with get_conn() as conn:
            return [self.card_page(game_version_id, card_id, include_player=False, connection=conn)
                    for card_id in ids]

    # ------------------------------------------------------------------ card search (§49)
    _CARD_SORTS = {
        "overall_rating": "uc.overall_rating",
        "card_name": "uc.card_name",
        "price": "latest_price.price_coins",
        "updated_at": "uc.updated_at",
    }

    def card_search(self, game_version_id: uuid.UUID, *,
                    include_player: bool = True,
                    q: Optional[str] = None,
                    position: Optional[str] = None,
                    rarity: Optional[str] = None,
                    card_type: Optional[str] = None,
                    playstyle: Optional[str] = None,
                    ovr_min: Optional[int] = None, ovr_max: Optional[int] = None,
                    price_max: Optional[int] = None,
                    sort: str = "overall_rating", sort_dir: str = "desc",
                    page: int = 1, page_size: int = 25) -> dict:
        """Server-side card discovery. Production cards only (synthetic
        firewall). Unknown filters match nothing — never everything."""
        sort_col = self._CARD_SORTS.get(sort, "uc.overall_rating")
        direction = "ASC" if sort_dir == "asc" else "DESC"
        where = ["uc.game_version_id = %(gv)s", CARD_FILTER]
        params: dict = {"gv": game_version_id, "include_player": include_player}
        if q:
            where.append("uc.card_name ILIKE %(q)s")
            params["q"] = f"%{q}%"
        if position:
            where.append("upper(uc.position) = %(pos)s")
            params["pos"] = position.upper()
        if rarity:
            where.append("lower(cr.rarity_code) = lower(%(rarity)s)")
            params["rarity"] = rarity
        if card_type:
            where.append("lower(uc.card_type) = lower(%(ctype)s)")
            params["ctype"] = card_type
        if playstyle:
            where.append("""EXISTS (SELECT 1 FROM ut_card_playstyle ucp
                            WHERE ucp.ut_card_id = uc.id
                              AND ucp.playstyle_name ILIKE %(ps)s)""")
            params["ps"] = f"%{playstyle}%"
        if ovr_min is not None:
            where.append("uc.overall_rating >= %(ovrmin)s")
            params["ovrmin"] = ovr_min
        if ovr_max is not None:
            where.append("uc.overall_rating <= %(ovrmax)s")
            params["ovrmax"] = ovr_max
        if price_max is not None:
            where.append("latest_price.price_coins IS NOT NULL")
            where.append("latest_price.price_coins <= %(pmax)s")
            params["pmax"] = price_max
        where_sql = " AND ".join(where)
        with get_conn() as conn:
            total = conn.execute(
                f"""SELECT count(*) AS n FROM ut_card uc
                    LEFT JOIN card_rarity cr ON cr.id = uc.rarity_id
                    LEFT JOIN LATERAL (
                        SELECT cp.price_coins FROM card_price cp
                        WHERE cp.ut_card_id = uc.id AND cp.currency = 'COINS'
                        ORDER BY cp.observed_at DESC LIMIT 1) latest_price ON TRUE
                    WHERE {where_sql}""", params).fetchone()["n"]
            rows = conn.execute(
                f"""SELECT uc.id, uc.card_name, uc.position, uc.overall_rating,
                           uc.card_type, uc.rarity_raw, uc.release_group,
                           uc.identity_status, uc.playstyle_data_published,
                           uc.updated_at, cr.rarity_code, cr.rarity_name,
                           gp.display_name AS player_name,
                           latest_price.price_coins,
                           latest_price.observed_at AS price_observed_at
                    FROM ut_card uc
                    LEFT JOIN card_rarity cr ON cr.id = uc.rarity_id
                    LEFT JOIN game_player gp ON gp.id = uc.game_player_id
                        AND gp.game_version_id = uc.game_version_id
                        AND %(include_player)s AND {PROD_FILTER}
                    LEFT JOIN LATERAL (
                        SELECT cp.price_coins, cp.observed_at FROM card_price cp
                        WHERE cp.ut_card_id = uc.id AND cp.currency = 'COINS'
                        ORDER BY cp.observed_at DESC LIMIT 1) latest_price ON TRUE
                    WHERE {where_sql}
                    ORDER BY {sort_col} {direction} NULLS LAST, uc.card_name
                    LIMIT %(limit)s OFFSET %(offset)s""",
                {**params, "limit": page_size,
                 "offset": (page - 1) * page_size}).fetchall()
        return {"total": total, "page": page, "page_size": page_size,
                "items": [dict(r) for r in rows]}

    def scoped_card_status(self, game_version_id: uuid.UUID) -> dict:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE EXISTS (
                           SELECT 1 FROM ut_card_attribute_override a
                           WHERE a.ut_card_id = uc.id AND a.value IS NOT NULL
                       )) AS with_attributes
                FROM ut_card uc
                WHERE uc.game_version_id = %s
                """,
                (game_version_id,),
            ).fetchone()
        total, count = row["total"], row["with_attributes"]
        status = "NO_DATA" if not count else "PARTIAL" if count < total else "AVAILABLE"
        return {
            "production_cards": total,
            "cards_with_attributes": count,
            "availability": {"card_attributes": status},
        }

    def card_data_status(self, game_version_id: uuid.UUID) -> dict:
        """§44 data-quality surface: what card data exists, and what does not."""
        with get_conn() as conn:
            cards = conn.execute(
                """SELECT count(*) FILTER (WHERE data_status = 'CANONICAL' AND NOT is_synthetic) AS production,
                          count(*) FILTER (WHERE is_synthetic) AS synthetic,
                          count(*) FILTER (WHERE data_status = 'CANONICAL' AND NOT is_synthetic
                                           AND playstyle_data_published) AS ps_published,
                          count(*) FILTER (WHERE data_status = 'CANONICAL' AND NOT is_synthetic
                                                 AND identity_status = 'RESOLVED') AS resolved,
                          max(updated_at) FILTER (WHERE data_status = 'CANONICAL' AND NOT is_synthetic) AS last_update
                   FROM ut_card WHERE game_version_id = %s""",
                (game_version_id,)).fetchone()
            prices = conn.execute(
                """SELECT count(DISTINCT cp.ut_card_id) AS priced
                   FROM card_price cp JOIN ut_card uc ON uc.id = cp.ut_card_id
                   WHERE uc.game_version_id = %s AND uc.data_status = 'CANONICAL' AND NOT uc.is_synthetic""",
                (game_version_id,)).fetchone()
            roles = conn.execute(
                """SELECT count(*) AS n FROM ut_card_role ucr
                   JOIN ut_card uc ON uc.id = ucr.ut_card_id
                   WHERE uc.game_version_id = %s AND uc.data_status = 'CANONICAL' AND NOT uc.is_synthetic""",
                (game_version_id,)).fetchone()
            chem = conn.execute(
                """SELECT count(*) AS n FROM chemistry_rule cr
                   WHERE cr.game_version_id = %s AND cr.verified = TRUE""",
                (game_version_id,)).fetchone()
            evos = conn.execute(
                """SELECT count(*) AS n FROM card_evolution ce
                   WHERE ce.game_version_id = %s""", (game_version_id,)).fetchone()
            runs = conn.execute(
                """SELECT ir.stage, ir.activation_status, ir.rows_accepted,
                          ir.rows_rejected, ir.rows_quarantined, ir.started_at,
                          ir.finished_at, ir.source_id
                   FROM ingestion_run ir
                   WHERE ir.game_version_id = %s
                   ORDER BY ir.started_at DESC LIMIT 5""",
                (game_version_id,)).fetchall()
            quarantined = conn.execute(
                """SELECT count(*) AS n FROM ingestion_quarantine iq
                   WHERE upper(iq.game_version) = (SELECT code FROM game_version
                                                   WHERE id = %s)""",
                (game_version_id,)).fetchone()
        prod = int(cards["production"] or 0)
        return {
            "production_cards": prod,
            "synthetic_cards_firewalled": int(cards["synthetic"] or 0),
            "playstyle_published_cards": int(cards["ps_published"] or 0),
            "identity_resolved_cards": int(cards["resolved"] or 0),
            "cards_with_price": int(prices["priced"] or 0),
            "card_roles_rows": int(roles["n"] or 0),
            "verified_chemistry_rules": int(chem["n"] or 0),
            "evolution_rows": int(evos["n"] or 0),
            "quarantined_rows": int(quarantined["n"] or 0),
            "last_card_update": cards["last_update"],
            "recent_ingestion_runs": [dict(r) for r in runs],
            "availability": {
                "card_attributes": "AVAILABLE" if prod else "NO_DATA",
                "card_prices": ("PARTIAL" if 0 < int(prices["priced"] or 0) < prod
                                else "AVAILABLE" if prod else "NO_DATA"),
                "card_roles": "AVAILABLE" if int(roles["n"] or 0) else "NO_DATA",
                "chemistry_rules": ("AVAILABLE" if int(chem["n"] or 0)
                                    else "NO_VERIFIED_RULES"),
                "evolutions": "AVAILABLE" if int(evos["n"] or 0) else "NO_DATA",
            },
        }

    # ------------------------------------------------------------------ lookups
    def by_source_player_id(self, game_version_id: uuid.UUID,
                            source_player_id: int) -> Optional[dict]:
        with get_conn() as conn:
            row = conn.execute(
                f"""SELECT gp.id FROM game_player gp
                    WHERE gp.game_version_id=%s AND gp.source_player_id=%s AND {PROD_FILTER}""",
                (game_version_id, source_player_id)).fetchone()
        return dict(row) if row else None

    def game_version_id(self, code: str) -> Optional[uuid.UUID]:
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM game_version WHERE code=%s",
                               (code.upper(),)).fetchone()
        return row["id"] if row else None

    def facets(self, game_version_id: uuid.UUID, *, research: bool = False) -> dict:
        player_status = "gp.data_status = 'RESEARCH_ONLY'" if research else PROD_FILTER
        with get_conn(local_fc27_research=research) as conn:
            nations = conn.execute(
                f"""SELECT nation, count(*) n FROM game_player gp
                    WHERE game_version_id=%s AND {player_status} AND nation IS NOT NULL
                    GROUP BY nation ORDER BY n DESC""", (game_version_id,)).fetchall()
            leagues = conn.execute(
                f"""SELECT c.league_name, count(*) n FROM club_affiliation ca
                   JOIN club c ON c.id = ca.club_id
                   JOIN game_player gp ON gp.id = ca.game_player_id
                   WHERE ca.game_version_id=%s AND gp.game_version_id=ca.game_version_id
                     AND c.league_name IS NOT NULL
                     AND {player_status}
                   GROUP BY c.league_name ORDER BY n DESC""", (game_version_id,)).fetchall()
            positions = conn.execute(
                f"""SELECT position_primary, count(*) n FROM game_player gp
                    WHERE game_version_id=%s AND {player_status}
                    GROUP BY position_primary ORDER BY n DESC""",
                (game_version_id,)).fetchall()
        return {"nations": [dict(r) for r in nations],
                "leagues": [dict(r) for r in leagues],
                "positions": [dict(r) for r in positions]}
