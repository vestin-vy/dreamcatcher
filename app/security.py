"""Auth helpers: password hashing/verify, session login, CSRF, login rate-limit.

CLI: generate an admin password hash for .env:
    python -m app.security hash "your-password"
"""
from __future__ import annotations

import secrets
import time

from fastapi import Request
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- password ---------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return pwd_context.verify(password, hashed)
    except ValueError:
        return False


def check_admin_credentials(username: str, password: str) -> bool:
    if username != settings.ADMIN_USERNAME:
        return False
    return verify_password(password, settings.ADMIN_PASSWORD_HASH)


# --- session ----------------------------------------------------------------

def login_admin(request: Request) -> None:
    request.session["admin"] = True
    request.session["csrf"] = secrets.token_urlsafe(32)


def logout_admin(request: Request) -> None:
    request.session.clear()


# --- CSRF -------------------------------------------------------------------

def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def verify_csrf(request: Request, submitted: str | None) -> bool:
    expected = request.session.get("csrf")
    return bool(expected) and bool(submitted) and secrets.compare_digest(expected, submitted)


# --- login rate-limit (in-memory, per-process) ------------------------------

_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW = 300.0  # seconds


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def too_many_attempts(request: Request) -> bool:
    key = _client_key(request)
    now = time.monotonic()
    recent = [t for t in _attempts.get(key, []) if now - t < _WINDOW]
    _attempts[key] = recent
    return len(recent) >= _MAX_ATTEMPTS


def record_attempt(request: Request) -> None:
    key = _client_key(request)
    _attempts.setdefault(key, []).append(time.monotonic())


def reset_attempts(request: Request) -> None:
    _attempts.pop(_client_key(request), None)


# --- CLI --------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "hash":
        print(hash_password(sys.argv[2]))
    else:
        print('Usage: python -m app.security hash "your-password"')
