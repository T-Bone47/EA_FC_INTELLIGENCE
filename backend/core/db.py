"""Database connection pool management (psycopg3)."""
from __future__ import annotations

import atexit
import json
import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.core.config import get_settings
from backend.services.data_license_gate import Environment, catalogue_releases, environment_from_settings

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ConnectionPool(
                conninfo=get_settings().database_url,
                min_size=1,
                max_size=8,
                kwargs={"row_factory": dict_row},
                open=True,
            )
        return _pool


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with get_pool().connection() as conn:
        yield conn


def catalogue_access() -> tuple[Environment, dict[str, dict[str, str]]]:
    environment = environment_from_settings(get_settings().environment)
    return environment, catalogue_releases(environment)


@contextmanager
def get_catalogue_conn(*, local_fc27_research: bool = False, verified_only: bool = False) -> Iterator[psycopg.Connection]:
    """Confine customer-facing catalogue reads to one snapshot of reviewed membership."""
    environment, releases = catalogue_access()
    if environment == Environment.LOCAL and local_fc27_research:
        environment = Environment.RESEARCH
        releases = {"FC27": catalogue_releases(environment).get("FC27", {})}
    if verified_only:
        environment = Environment.PRODUCTION
        releases = catalogue_releases(environment)
    with get_conn() as conn:
        if environment != Environment.LOCAL:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL search_path TO pg_catalog, catalogue_serving, public, pg_temp")
            required = ["game_player", "ut_card", "card_price", "card_version", "source_observation"]
            visible = conn.execute(
                """SELECT bool_and(coalesce(to_regclass(rel) =
                           to_regclass('catalogue_serving.' || rel), false)) AS present
                   FROM unnest(%s::text[]) AS scoped(rel)""", (required,)).fetchone()
            if not visible["present"]:
                raise RuntimeError("Catalogue serving views are unavailable. Apply migration 011.")
            conn.execute(
                "SELECT set_config('eafc.catalogue_releases', %s, true), "
                "set_config('eafc.catalogue_mode', %s, true)",
                (json.dumps(releases, sort_keys=True), environment.value))
        yield conn


def catalogue_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with get_catalogue_conn() as conn:
        return conn.execute(sql, params).fetchall()


def query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None


atexit.register(close_pool)
