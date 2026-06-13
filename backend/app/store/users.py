"""User CRUD — stored in storage/users.json.
A seed admin is created automatically if the file doesn't exist.
"""
import uuid
from pathlib import Path
from typing import Optional

from app.store._base import now_iso, read_json, write_json


def _users_path() -> Path:
    from app.config import settings
    p = Path(settings.STORAGE_PATH)
    p.mkdir(parents=True, exist_ok=True)
    return p / "users.json"


def _load() -> list:
    return read_json(_users_path(), [])


def _save(users: list) -> None:
    write_json(_users_path(), users)


def _seed_admin_if_empty() -> None:
    """Create a default admin account if no users exist."""
    if _load():
        return
    from app.core.security import get_password_hash
    from app.config import settings
    admin = {
        "id": str(uuid.uuid4()),
        "email": settings.DEFAULT_ADMIN_EMAIL,
        "name": "Admin",
        "hashed_password": get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
        "role": "admin",
        "is_active": True,
        "created_at": now_iso(),
    }
    _save([admin])


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_by_id(user_id: str) -> Optional[dict]:
    return next((u for u in _load() if u["id"] == user_id), None)


def get_user_by_email(email: str) -> Optional[dict]:
    _seed_admin_if_empty()
    return next((u for u in _load() if u["email"].lower() == email.lower()), None)


def list_users() -> list:
    _seed_admin_if_empty()
    return _load()


def create_user(
    email: str,
    name: str,
    hashed_password: str,
    role: str = "office",
) -> dict:
    users = _load()
    if any(u["email"].lower() == email.lower() for u in users):
        raise ValueError(f"Email already registered: {email}")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "hashed_password": hashed_password,
        "role": role,
        "is_active": True,
        "created_at": now_iso(),
    }
    users.append(user)
    _save(users)
    return user


def update_user(user_id: str, updates: dict) -> Optional[dict]:
    users = _load()
    for i, u in enumerate(users):
        if u["id"] == user_id:
            users[i] = {**u, **updates}
            _save(users)
            return users[i]
    return None
