from __future__ import annotations

import hmac
import secrets

from config.settings import get_settings

_valid_tokens: set[str] = set()


def verify_password(password: str) -> bool:
    settings = get_settings()
    return hmac.compare_digest(password, settings.web_password)


def create_token() -> str:
    token = secrets.token_hex(32)
    _valid_tokens.add(token)
    return token


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    return token in _valid_tokens


def revoke_token(token: str) -> None:
    _valid_tokens.discard(token)
