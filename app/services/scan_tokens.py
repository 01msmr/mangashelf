"""
Short-lived tokens embedded in phone-scan QR codes.
Token → user_id, valid for 30 minutes, single-network use.
In-memory store is fine for a small library (resets on server restart).
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone, timedelta

_tokens: dict[str, tuple[int, str]] = {}  # token -> (user_id, expires_iso)

TTL = timedelta(minutes=30)


def make_token(user_id: int) -> str:
    token = secrets.token_urlsafe(16)
    expires = (datetime.now(timezone.utc) + TTL).isoformat()
    _tokens[token] = (user_id, expires)
    return token


def consume_token(token: str) -> int | None:
    """Validate and return user_id, or None if invalid/expired. Keeps token alive for TTL."""
    entry = _tokens.get(token)
    if not entry:
        return None
    user_id, expires_iso = entry
    if datetime.now(timezone.utc).isoformat() > expires_iso:
        _tokens.pop(token, None)
        return None
    return user_id
