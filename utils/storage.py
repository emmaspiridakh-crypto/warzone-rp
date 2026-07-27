"""
utils/storage.py
------------------
Πολύ απλό persistence layer με JSON αρχεία μέσα στο data/.
Δεν είναι "βαρύ" database, αλλά αρκεί για: suggestion votes, staff activity
χρόνους, και mapping temp-voice-channel -> owner.

ΠΡΟΣΟΧΗ στο Render: το filesystem ΔΕΝ είναι persistent ανάμεσα σε deploys
(κάθε redeploy το μηδενίζει). Αν θες μόνιμη αποθήκευση staff activity κλπ
μακροπρόθεσμα, θα χρειαστείς πραγματική βάση (π.χ. Render Postgres free tier).
Για τώρα αυτό αρκεί για να δουλέψει το σύστημα.
"""

import json
import os
import threading

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_lock = threading.Lock()


def _path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.json")


def load(name: str, default=None):
    if default is None:
        default = {}
    path = _path(name)
    if not os.path.exists(path):
        return default
    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return default


def save(name: str, data) -> None:
    path = _path(name)
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- Συγκεκριμένα helpers ----------

def get_store(name: str, default=None) -> dict:
    return load(name, default or {})


def update_store(name: str, key: str, value) -> None:
    data = load(name, {})
    data[key] = value
    save(name, data)
