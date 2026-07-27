"""
utils/turso.py
----------------
Κεντρική σύνδεση με Turso (hosted libSQL) ώστε ΟΛΑ τα δεδομένα του bot
(giveaways, invites, bot status, κτλ) να επιβιώνουν σε redeploy / reset
στο Render — δεν χάνεται τίποτα, δεν χρειάζεται να ξαναστείλεις κανένα panel.

Env vars (Render -> Environment, ή .env local):
    TURSO_DATABASE_URL   π.χ. libsql://warzone-rp-<org>.turso.io
    TURSO_AUTH_TOKEN     το token από `turso db tokens create <db-name>`

Αν λείπουν (π.χ. τρέχεις local χωρίς Turso account), το bot πέφτει
αυτόματα σε τοπικό αρχείο SQLite (data/local.db) — δουλεύει κανονικά,
απλά δεν είναι persistent σε redeploy.

Χρήση:
    from utils.turso import async_execute, sync_execute

    rows = await async_execute("SELECT * FROM giveaways WHERE id = ?", [gw_id])
    rows = sync_execute("SELECT value FROM kv_store WHERE store = ?", ["invite_stats"])

Κάθε "rows" είναι list[dict] (κάθε dict = μία γραμμή, κλειδιά = ονόματα στηλών).
"""

from __future__ import annotations

import os
from typing import Any, Optional

import libsql_client

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)
_LOCAL_PATH = os.path.join(_DATA_DIR, "local.db")


def is_configured() -> bool:
    """True αν έχουν μπει τα Turso env vars (αλλιώς χρησιμοποιούμε local sqlite fallback)."""
    return bool(TURSO_URL)


def _client_kwargs() -> dict:
    if TURSO_URL:
        return {"url": TURSO_URL, "auth_token": TURSO_TOKEN or None}
    return {"url": f"file:{_LOCAL_PATH}"}


_async_client: Optional[libsql_client.Client] = None
_sync_client: Optional[libsql_client.ClientSync] = None


def get_async_client() -> libsql_client.Client:
    global _async_client
    if _async_client is None:
        _async_client = libsql_client.create_client(**_client_kwargs())
    return _async_client


def get_sync_client() -> libsql_client.ClientSync:
    global _sync_client
    if _sync_client is None:
        _sync_client = libsql_client.create_client_sync(**_client_kwargs())
    return _sync_client


async def async_execute(sql: str, args: Optional[list] = None) -> list[dict]:
    client = get_async_client()
    rs = await client.execute(sql, args or [])
    return [row.asdict() for row in rs.rows]


def sync_execute(sql: str, args: Optional[list] = None) -> list[dict]:
    client = get_sync_client()
    rs = client.execute(sql, args or [])
    return [row.asdict() for row in rs.rows]


async def async_close():
    global _async_client
    if _async_client is not None:
        try:
            await _async_client.close()
        except Exception:
            pass
        _async_client = None
