"""Passwords, JWTs and masking."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from .config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"uid": user_id, "role": role, "iat": int(now.timestamp()),
                       "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
                       "iss": "samanvay"}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer="samanvay")
    except jwt.PyJWTError:
        return None


def mask_name(name: str) -> str:
    """'Narmada Institute of Technology' -> 'Nar**** Ins****** of Tec*******'."""
    out = []
    for w in name.split():
        out.append(w if len(w) <= 3 else w[:3] + "*" * (len(w) - 3))
    return " ".join(out)


def sha256(data: str | bytes) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()
