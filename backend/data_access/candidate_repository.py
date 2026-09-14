"""PRODUCTION candidate loading for the recommendation engine.

This module is the production-side replacement for the legacy test-side
candidate loader anti-pattern (§14): production code lives here; tests import
production code, never the reverse.

Loads Candidates from PostgreSQL (canonical store), game_version-scoped,
excluding SYNTHETIC_TEST data (firewall), with an in-process cache keyed by
(game_version, data watermark) so the 16K-candidate evaluation stays fast
without stale reads after re-ingestion.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Optional

from backend.core.db import get_conn
from backend.domain.card_model import (
    ALL_ATTRS, Candidate, DataStatus, GamePlayer, GameVersionCode,
    IdentityStatus, PlayerAttributes, UTCard,
)
from backend.services.scoring_config import compatible_positions

_CACHE_TTL_SECONDS = 120.0


class CandidateRepository:
    def __init__(self, cache_ttl: float = _CACHE_TTL_SECONDS):
        self._cache: dict[str, tuple[float, str, list[Candidate]]] = {}
        self._lock = threading.Lock()
        self.cache_ttl = cache_ttl
        # §59 telemetry: stats of the most recent load (hit/miss + data version)
        self.last_load_stats: dict = {}

    # ------------------------------------------------------------------ public
    def load_candidates(self, game_version: str,
                        positions: Optional[set[str]] = None,
                        include_synthetic: bool = False) -> list[Candidate]:
        """Load game_player-backed candidates.

        include_synthetic=True is for TEST/BENCHMARK code paths only; the API
        layer never sets it. Production reads always filter the firewall.
        """
        gv = GameVersionCode.parse(game_version)
        watermark = self._watermark(gv.value)
        key = f"{gv.value}|{include_synthetic}"
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and hit[1] == watermark and (now - hit[0]) < self.cache_ttl:
                all_c = hit[2]
                cache_hit = True
            else:
                all_c = self._load_all(gv, include_synthetic)
                self._cache[key] = (now, watermark, all_c)
                cache_hit = False
        self.last_load_stats = {"cache_hit": cache_hit, "data_version": watermark,
                                "loaded": len(all_c)}
        if positions:
            return [c for c in all_c if self._matches_positions(c, positions)]
        return list(all_c)

    def load_for_position(self, game_version: str, position: str,
                          include_adjacent: bool = True) -> list[Candidate]:
        positions = compatible_positions(position) if include_adjacent else {position}
        return self.load_candidates(game_version, positions=positions)

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()

    # ---------------------------------------------------------------- cards (§11)
    def load_cards(self, game_version: str,
                   positions: Optional[set[str]] = None,
                   include_synthetic: bool = False) -> list[Candidate]:
        """Load PRODUCTION UT cards as Candidates (entity_type='ut_card').

        Card attributes/PlayStyles/price come from the CARD — never from the
        base player (§5). The base GamePlayer contributes only link facts
        (nation/club/league/secondary positions). Synthetic cards stay
        firewalled unless include_synthetic=True (TEST paths only; the API
        layer never sets it).

        Cached under a card-specific namespace with its OWN watermark (§28):
        player ingests never invalidate the card cache and vice versa.
        """
        gv = GameVersionCode.parse(game_version)
        key = f"cards|{gv.value}|{include_synthetic}"
        watermark = self._card_watermark(gv.value)
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and hit[1] == watermark and (now - hit[0]) < self.cache_ttl:
                all_c, cache_hit = hit[2], True
            else:
                all_c = self._load_cards(gv, include_synthetic)
                self._cache[key] = (now, watermark, all_c)
                cache_hit = False
        self.last_load_stats = {"cache_hit": cache_hit, "scope": "ut_card",
                                "data_version": watermark, "loaded": len(all_c)}
        if positions:
            return [c for c in all_c if self._matches_positions(c, positions)]
        return list(all_c)

    # ------------------------------------------------------------------ internals
    def _card_watermark(self, game_version: str) -> str:
        """§28/§47: card data version — cards, versions, PRICES and chemistry
        rules each contribute, so a price update or rule ingest invalidates
        the card cache (no stale prices after updates, §31)."""
        with get_conn() as conn:
            row = conn.execute(
                """SELECT count(*) AS n,
                          coalesce(max(c.updated_at), 'epoch') AS mu,
                          coalesce(max(v.valid_from), 'epoch') AS mv,
                          coalesce(max(p.observed_at), 'epoch') AS mp,
                          count(DISTINCT p.id) AS np
                   FROM ut_card c
                   JOIN game_version g ON g.id = c.game_version_id AND g.code = %(code)s
                   LEFT JOIN card_version v ON v.ut_card_id = c.id AND v.is_current
                   LEFT JOIN card_price p ON p.ut_card_id = c.id
                   WHERE c.is_synthetic = FALSE""", {"code": game_version}).fetchone()
            chem = conn.execute(
                """SELECT count(*) AS n, coalesce(max(cr.id::text), '') AS h
                   FROM chemistry_rule cr
                   JOIN game_version g ON g.id = cr.game_version_id
                   WHERE g.code = %(code)s AND cr.verified = TRUE""",
                {"code": game_version}).fetchone()
        return (f"{row['n']}@{row['mu']}@{row['mv']}@{row['mp']}@{row['np']}"
                f"@chem{chem['n']}")

    def _load_cards(self, gv: GameVersionCode, include_synthetic: bool) -> list[Candidate]:
        synth = "" if include_synthetic else "AND c.is_synthetic = FALSE"
        sql = f"""
            SELECT c.id, c.card_name, c.position, c.overall_rating,
                   c.source_id, c.source_card_id, c.is_synthetic, c.data_status,
                   c.canonical_card_id, c.card_type, c.rarity_raw,
                   c.release_date, c.release_group, c.identity_status,
                   c.identity_rule, c.playstyle_data_published,
                   r.rarity_code,
                   v.attributes AS version_attributes,
                   v.playstyles AS version_playstyles,
                   v.overall_rating AS version_ovr,
                   p.price_coins, p.platform AS price_platform,
                   p.observed_at AS price_observed_at,
                   p.source_observation_id AS price_source_id,
                   p.confidence AS price_confidence,
                   gp.id AS gp_id, gp.nation, gp.display_name AS gp_name,
                   gp.position_primary AS gp_position,
                   gp.overall_rating AS gp_ovr, gp.source_player_id,
                   coalesce(sp.sec_positions, '{{}}') AS sec_positions,
                   cl.name AS club, cl.league_name AS league,
                   cl.nation AS club_nation
            FROM ut_card c
            JOIN game_version gvg ON gvg.id = c.game_version_id AND gvg.code = %(gv)s
            LEFT JOIN card_rarity r ON r.id = c.rarity_id
            LEFT JOIN LATERAL (
                SELECT cv.attributes, cv.playstyles, cv.overall_rating
                FROM card_version cv
                WHERE cv.ut_card_id = c.id AND cv.is_current = TRUE
                ORDER BY cv.version_number DESC LIMIT 1) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT cp.price_coins, cp.platform, cp.observed_at,
                       cp.source_observation_id, cp.confidence
                FROM card_price cp
                WHERE cp.ut_card_id = c.id AND cp.currency = 'COINS'
                ORDER BY cp.observed_at DESC LIMIT 1) p ON TRUE
            LEFT JOIN game_player gp ON gp.id = c.game_player_id
            LEFT JOIN club_affiliation ca ON ca.game_player_id = gp.id
                     AND ca.game_version_id = gp.game_version_id
            LEFT JOIN club cl ON cl.id = ca.club_id
            LEFT JOIN LATERAL (
                SELECT array_agg(sp0.position ORDER BY sp0.sort_order) AS sec_positions
                FROM game_player_position_secondary sp0
                WHERE sp0.game_player_id = gp.id) sp ON TRUE
            WHERE c.data_status <> 'SYNTHETIC_TEST' OR %(synth_flag)s
            {synth}
        """
        with get_conn() as conn:
            rows = conn.execute(sql, {"gv": gv.value,
                                      "synth_flag": bool(include_synthetic)}).fetchall()
            ids = [r["id"] for r in rows]
            ps_rows: dict = {i: ([], []) for i in ids}
            role_rows: dict = {i: [] for i in ids}
            if ids:
                for pr in conn.execute(
                        """SELECT ut_card_id, playstyle_name, tier
                           FROM ut_card_playstyle WHERE ut_card_id = ANY(%s)""",
                        (ids,)).fetchall():
                    ps_rows[pr["ut_card_id"]][0 if pr["tier"] == "base" else 1] \
                        .append(pr["playstyle_name"])
                for rr in conn.execute(
                        """SELECT ut_card_id, role_name, familiarity, is_primary,
                                  data_status
                           FROM ut_card_role WHERE ut_card_id = ANY(%s)""",
                        (ids,)).fetchall():
                    role_rows[rr["ut_card_id"]].append(
                        {"role": rr["role_name"], "familiarity": rr["familiarity"],
                         "is_primary": rr["is_primary"],
                         "data_status": rr["data_status"]})

        out: list[Candidate] = []
        for row in rows:
            attrs_raw = row["version_attributes"] or {}
            overrides = {k: v for k, v in attrs_raw.items()
                         if k in ALL_ATTRS and v is not None}
            vps = row["version_playstyles"] or {}
            ps_base = list(vps.get("base") or [])
            ps_plus = list(vps.get("plus") or [])
            if not (ps_base or ps_plus):
                ps_base, ps_plus = ps_rows.get(row["id"], ([], []))
            published = bool(row["playstyle_data_published"])
            card = UTCard(
                id=row["id"], game_version=gv, source_id=row["source_id"],
                source_card_id=str(row["source_card_id"]),
                card_name=row["card_name"], position=row["position"],
                overall_rating=(row["version_ovr"] if row["version_ovr"] is not None
                                else row["overall_rating"]),
                rarity=row["rarity_code"],
                game_player_id=row["gp_id"],
                attribute_overrides=overrides,
                playstyles_base=ps_base, playstyles_plus=ps_plus,
                playstyle_data_published=published,
                price_coins=row["price_coins"],
                price_platform=row["price_platform"],
                price_observed_at=(row["price_observed_at"].isoformat()
                                   if row["price_observed_at"] else None),
                price_source_id=(str(row["price_source_id"])
                                 if row["price_source_id"] else None),
                price_confidence=(float(row["price_confidence"])
                                  if row["price_confidence"] is not None else None),
                is_synthetic=bool(row["is_synthetic"]),
                data_status=DataStatus(row["data_status"] or "CANONICAL"),
                canonical_card_id=row["canonical_card_id"],
                card_type=row["card_type"], rarity_raw=row["rarity_raw"],
                release_date=row["release_date"],
                release_group=row["release_group"],
                identity_status=IdentityStatus(row["identity_status"] or "UNRESOLVED"),
                identity_rule=row["identity_rule"],
                roles=role_rows.get(row["id"], []),
            )
            gp = None
            if row["gp_id"] is not None:
                gp = GamePlayer(
                    id=row["gp_id"], game_version=gv,
                    source_id=row["source_id"],
                    source_player_id=row["source_player_id"],
                    display_name=row["gp_name"] or card.card_name,
                    position_primary=row["gp_position"] or card.position,
                    overall_rating=row["gp_ovr"],
                    nation=row["nation"],
                    club=row["club"], league=row["league"],
                    secondary_positions=list(row["sec_positions"] or []))
            out.append(Candidate.from_ut_card(card, gp))
        return out

    @staticmethod
    def _matches_positions(c: Candidate, positions: set[str]) -> bool:
        up = {p.upper() for p in positions}
        if c.position_primary.upper() in up:
            return True
        return bool(up & {s.upper() for s in c.secondary_positions})

    def _watermark(self, game_version: str) -> str:
        with get_conn() as conn:
            row = conn.execute(
                """SELECT count(*) AS n, coalesce(max(updated_at), 'epoch') AS wm
                   FROM game_player gp JOIN game_version gv ON gv.id = gp.game_version_id
                   WHERE gv.code = %s""", (game_version,)).fetchone()
        return f"{row['n']}@{row['wm']}"

    def _load_all(self, gv: GameVersionCode, include_synthetic: bool) -> list[Candidate]:
        status_filter = "" if include_synthetic else "AND gp.data_status <> 'SYNTHETIC_TEST'"
        attr_cols = ", ".join(f"a.{c}" for c in ALL_ATTRS)
        with get_conn() as conn:
            rows = conn.execute(f"""
                SELECT gp.id, gp.display_name, gp.position_primary, gp.overall_rating,
                       gp.nation, gp.data_status, gp.source_player_id, gp.position_type, gp.identity_status,
                       gp.preferred_foot, gp.weak_foot_stars, gp.skill_moves_stars,
                       c.name AS club, c.league_name AS league,
                       {attr_cols},
                       coalesce(ps.base_names, '{{}}')  AS ps_base,
                       coalesce(ps.plus_names, '{{}}')  AS ps_plus,
                       coalesce(sp.sec_positions, '{{}}') AS sec_positions,
                       (ps.published IS NOT NULL) AS ps_published
                FROM game_player gp
                JOIN game_version gvv ON gvv.id = gp.game_version_id AND gvv.code = %(code)s
                LEFT JOIN game_player_attributes a ON a.game_player_id = gp.id
                LEFT JOIN club_affiliation ca ON ca.game_player_id = gp.id
                         AND ca.game_version_id = gp.game_version_id
                LEFT JOIN club c ON c.id = ca.club_id
                LEFT JOIN LATERAL (
                    SELECT array_agg(pd.playstyle_name) FILTER (WHERE gpp.tier='base') AS base_names,
                           array_agg(pd.playstyle_name) FILTER (WHERE gpp.tier='plus') AS plus_names,
                           TRUE AS published
                    FROM game_player_playstyle gpp
                    JOIN playstyle_definition pd ON pd.id = gpp.playstyle_definition_id
                    WHERE gpp.game_player_id = gp.id
                ) ps ON TRUE
                LEFT JOIN LATERAL (
                    SELECT array_agg(sp0.position ORDER BY sp0.sort_order) AS sec_positions
                    FROM game_player_position_secondary sp0
                    WHERE sp0.game_player_id = gp.id
                ) sp ON TRUE
                WHERE TRUE {status_filter}
                ORDER BY gp.overall_rating DESC, gp.display_name""",
                {"code": gv.value}).fetchall()

        candidates: list[Candidate] = []
        for r in rows:
            attrs = PlayerAttributes()
            for c in ALL_ATTRS:
                attrs.set(c, r[c])
            candidates.append(Candidate(
                entity_type="game_player",
                entity_id=r["id"],
                game_version=gv,
                name=r["display_name"],
                position_primary=r["position_primary"],
                secondary_positions=list(r["sec_positions"] or []),
                overall_rating=r["overall_rating"],
                attributes=attrs,
                playstyles_base=list(r["ps_base"] or []),
                playstyles_plus=list(r["ps_plus"] or []),
                playstyle_data_published=bool(r["ps_published"]),
                nation=r["nation"], club=r["club"], league=r["league"],
                data_status=DataStatus(r["data_status"]),
                is_synthetic=(r["data_status"] == DataStatus.SYNTHETIC_TEST.value),
                extra={"position_type": r["position_type"],
                       "preferred_foot": r["preferred_foot"],
                       "weak_foot_stars": r["weak_foot_stars"],
                       "skill_moves_stars": r["skill_moves_stars"],
                       "source_player_id": r["source_player_id"],
                       "identity_status": r["identity_status"]},
            ))
        return candidates
