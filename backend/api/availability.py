"""Availability derived from the same release scopes the serving paths use."""
from fastapi import Request
import psycopg
from psycopg_pool import PoolTimeout

from backend.api.deps import local_card_research_allowed
from backend.core import db
from backend.core.config import get_settings
from backend.services.data_license_gate import (
    DataLicenseGateFailure, Environment, ProductionOverrideForbidden, catalogue_releases, environment_from_settings,
)
from backend.services.fc27_card_research import (
    RELEASE, SNAPSHOT, local_release, validate_cached_membership,
)
from backend.services.reference_distribution import (
    ReferenceDistributionMismatch, ReferenceDistributionUnavailable, resolve_serving_reference,
)

_SCOPES = {"game_player": "data_status = 'CANONICAL'",
           "ut_card": "data_status = 'CANONICAL' AND NOT is_synthetic"}
_REFERENCE_ERRORS = (ReferenceDistributionMismatch, ReferenceDistributionUnavailable,
                     DataLicenseGateFailure, ProductionOverrideForbidden)


def _release(status, count=None, release_id=None, reference_ready=None):
    return {"status": status, "record_count": count, "release_id": release_id,
            "reference_ready": reference_ready}


def _count(conn, version, scope, condition):
    # Table and condition are internal constants, never request input.
    return conn.execute(f"""
        SELECT count(*) AS n FROM {scope}
        WHERE game_version_id = (SELECT id FROM public.game_version WHERE code = %s)
          AND {condition}
    """, (version,)).fetchone()["n"]


def _reference(version, scope, research, environment, release_id=None):
    try:
        ref, _ = resolve_serving_reference(version, scope, research, environment, release_id)
    except _REFERENCE_ERRORS:
        return None
    return ref


def _player_research(version):
    release_id = catalogue_releases(Environment.RESEARCH).get(version, {}).get("game_player")
    if not release_id:
        return _release("RELEASE_VALIDATION_FAILED")
    with db.get_catalogue_conn(local_fc27_research=True) as conn:
        count = _count(conn, version, "game_player", "data_status = 'RESEARCH_ONLY'")
    if not count:
        raw = db.query_one("""SELECT EXISTS (
            SELECT 1 FROM public.game_player p JOIN public.game_version g ON g.id = p.game_version_id
            WHERE g.code = %s AND p.data_status = 'RESEARCH_ONLY') AS present""", (version,))
        return _release("RELEASE_VALIDATION_FAILED" if raw["present"] else "DATA_NOT_INGESTED", 0, release_id, False)
    ref = _reference(version, "game_player", True, Environment.LOCAL, release_id)
    return _release("RESEARCH_RELEASE_AVAILABLE" if ref else "REFERENCE_UNAVAILABLE", count, release_id, bool(ref))


def _card_research():
    snapshot = db.query_one("SELECT 1 FROM fc27_staging.snapshot WHERE snapshot_id = %s", (SNAPSHOT,))
    if not snapshot:
        return _release("DATA_NOT_INGESTED", 0, RELEASE, False)
    try:
        count = validate_cached_membership()
        ref, pool = local_release(get_settings().database_url)
    except (ReferenceDistributionMismatch, ReferenceDistributionUnavailable):
        return _release("REFERENCE_UNAVAILABLE", count, RELEASE, False)
    except (ValueError, KeyError):
        return _release("RELEASE_VALIDATION_FAILED", release_id=RELEASE, reference_ready=False)
    result = _release("RESEARCH_RELEASE_AVAILABLE", len(pool), RELEASE, True)
    result["goalkeeper_reference_ready"] = bool(ref.groups.get("GK"))
    return result


def availability(request: Request) -> dict:
    settings = get_settings()
    env = environment_from_settings(settings.environment)
    versions = settings.supported_versions()
    data = {version: {} for version in versions}
    try:
        # Bound the connection probe even if the configured server is down.
        with db.get_pool().connection(timeout=2) as conn:
            conn.execute("SELECT 1")
        approved = catalogue_releases(Environment.PRODUCTION)
        for version in versions:
            for scope, predicate in _SCOPES.items():
                release_id = approved.get(version, {}).get(scope)
                production = _release("PRODUCTION_NOT_APPROVED", 0, reference_ready=False)
                if release_id:
                    with db.get_catalogue_conn(verified_only=True) as conn:
                        count = _count(conn, version, scope, predicate)
                    ref = _reference(version, scope, False, Environment.PRODUCTION, release_id) if count else None
                    state = ("PRODUCTION_RELEASE_AVAILABLE" if ref else "REFERENCE_UNAVAILABLE") if count else "DATA_NOT_INGESTED"
                    production = _release(state, count, release_id, bool(ref))
                local = None
                if env == Environment.LOCAL:
                    with db.get_conn() as conn:
                        count = _count(conn, version, scope, predicate)
                    ref = _reference(version, scope, False, env) if count else None
                    local = _release("LOCAL_CATALOGUE_AVAILABLE" if count else "DATA_NOT_INGESTED",
                                     count, ref.version if ref else None, bool(ref))
                research = None
                if version == "FC27":
                    research = _release("RESEARCH_ACCESS_DISABLED")
                    if env == Environment.LOCAL and scope == "game_player":
                        research = _player_research(version)
                    if scope == "ut_card" and local_card_research_allowed(request, settings):
                        try:
                            research = _card_research()
                        except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName):
                            research = _release("DATA_NOT_INGESTED", 0, reference_ready=False)
                data[version][scope] = {"production": production, "local": local, "research": research}
    except (psycopg.OperationalError, PoolTimeout):
        return {"environment": env.value, "database_status": "DATABASE_NOT_CONNECTED", "versions": {}}
    return {"environment": env.value, "database_status": "CONNECTED", "versions": data}
