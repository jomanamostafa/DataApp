"""
user_store.py
─────────────
Replaces the entire database layer.
Users are stored in  data/users.json  as a plain JSON list.
No MySQL, no SQLAlchemy, no migrations — just a file.
"""

import os
import json
import uuid
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

USERS_FILE = os.getenv("USERS_FILE", "data/users.json")


def _load() -> list[dict]:
    """Read users from JSON file. Returns empty list if file missing."""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def _save(users: list[dict]):
    """Write users back to JSON file."""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


# ── Flask-Login compatible User object ──────────────

class User(UserMixin):
    def __init__(self, data: dict):
        self.id       = data["id"]
        self.username = data["username"]
        self.role     = data.get("role", "user")
        self._pw_hash = data["password_hash"]

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self._pw_hash, password)

    # Flask-Login requires get_id() to return a string
    def get_id(self):
        return str(self.id)


# ── CRUD helpers ─────────────────────────────────────

def get_all_users() -> list[dict]:
    return _load()


def find_by_username(username: str) -> User | None:
    for u in _load():
        if u["username"].lower() == username.lower():
            return User(u)
    return None


def find_by_id(user_id: str) -> User | None:
    for u in _load():
        if str(u["id"]) == str(user_id):
            return User(u)
    return None


def create_user(username: str, password: str, role: str = "user") -> User | None:
    """
    Create and persist a new user.
    Returns None if the username is already taken.
    """
    users = _load()
    if any(u["username"].lower() == username.lower() for u in users):
        return None          # duplicate

    new_user = {
        "id":            str(uuid.uuid4()),
        "username":      username,
        "password_hash": bcrypt.generate_password_hash(password).decode("utf-8"),
        "role":          role,
        "uploads":       [],
    }
    users.append(new_user)
    _save(users)
    return User(new_user)


def add_upload_record(user_id: str, filename: str, original_name: str):
    """Append an upload entry to the user's record in the JSON store."""
    import datetime
    users = _load()
    for u in users:
        if str(u["id"]) == str(user_id):
            u.setdefault("uploads", []).append({
                "filename":      filename,
                "original_name": original_name,
                "date":          datetime.datetime.utcnow().isoformat(),
            })
    _save(users)


def get_user_uploads(user_id: str) -> list[dict]:
    for u in _load():
        if str(u["id"]) == str(user_id):
            return u.get("uploads", [])
    return []


def get_all_uploads() -> list[dict]:
    """Return every upload from every user (for admin view)."""
    result = []
    for u in _load():
        for up in u.get("uploads", []):
            result.append({**up, "owner": u["username"]})
    return sorted(result, key=lambda x: x["date"], reverse=True)
