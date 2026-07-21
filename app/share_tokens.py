from __future__ import annotations

import hashlib
import secrets

from app.config import settings


def create_share_token() -> str:
    return secrets.token_urlsafe(32)


def hash_share_token(token: str) -> str:
    raw = f"{token}:{settings.share_token_salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
