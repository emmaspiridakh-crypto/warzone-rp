"""
utils/storage.py
------------------
Απλό key-value persistence layer. Η δημόσια συνάρτηση (load/save/get_store/
update_store) είναι ΙΔΙΑ όπως πριν, οπότε κανένα άλλο cog δεν χρειάζεται
αλλαγή — αλλά τώρα από κάτω αποθηκεύει σε Turso (hosted libSQL) αντί για
τοπικά .json αρχεία, ώστε να ΜΗΝ χάνεται τίποτα σε redeploy/reset στο Render.

Αν δεν έχουν μπει τα TURSO_DATABASE_URL / TURSO_AUTH_TOKEN env vars, πέφτει
αυτόματα σε τοπικά JSON αρχεία (ίδια συμπεριφορά με πριν) ώστε να δουλεύει
και local χωρίς Turso account.
"""

import json
import os
import threading

from utils import turso

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_lock = threading.Lock()
_schema_ready = False


def _ensure_schema():
    global _schema_ready
    if _schema_ready:
        return
    try:
        turso.sync_execute(
            "CREATE TABLE IF NOT EXISTS kv_store ("
            "store TEXT PRIMARY KEY, "
            "value TEXT NOT NULL"
            ")"
        )
        _schema_ready = True
    except Exception as e:
        print(f"[storage] Δεν μπόρεσα να φτιάξω το kv_store schema: {e}")


def _path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.json")


# ---------- Τοπικό JSON fallback (μόνο όταν δεν υπάρχει Turso config) ----------

def _local_load(name: str, default):
    path = _path(name)
    if not os.path.exists(path):
        return default
    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return default


def _local_save(name: str, data) -> None:
    path = _path(name)
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- Δημόσιο API ----------

def load(name: str, default=None):
    if default is None:
        default = {}

    if not turso.is_configured():
        return _local_load(name, default)

    _ensure_schema()
    try:
        rows = turso.sync_execute("SELECT value FROM kv_store WHERE store = ?", [name])
        if rows:
            return json.loads(rows[0]["value"])
    except Exception as e:
        print(f"[storage] Turso load απέτυχε για '{name}', fallback σε local: {e}")
        return _local_load(name, default)
    return default


def save(name: str, data) -> None:
    # Πάντα κρατάμε και τοπικό αντίγραφο σαν backup/cache — ελαφρύ, δεν πειράζει.
    _local_save(name, data)

    if not turso.is_configured():
        return

    _ensure_schema()
    payload = json.dumps(data, ensure_ascii=False)
    try:
        turso.sync_execute(
            "INSERT INTO kv_store (store, value) VALUES (?, ?) "
            "ON CONFLICT(store) DO UPDATE SET value = excluded.value",
            [name, payload],
        )
    except Exception as e:
        print(f"[storage] Turso save απέτυχε για '{name}' (έμεινε μόνο το local αντίγραφο): {e}")


# ---------- Συγκεκριμένα helpers ----------

def get_store(name: str, default=None) -> dict:
    return load(name, default or {})


def update_store(name: str, key: str, value) -> None:
    data = load(name, {})
    data[key] = value
    save(name, data)
