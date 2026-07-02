"""FastAPI application factory: middleware, static mount, routers, root redirect.

The smoke-test contract imports `from app.main import app` (tests/test_smoke.py).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import init_db
from app.i18n import LANGS
from app.routes.admin import router as admin_router
from app.routes.cart import router as cart_router
from app.routes.checkout import router as checkout_router
from app.routes.payments import router as payments_router
from app.routes.marketing import router as marketing_router
from app.routes.media import router as media_router
from app.routes.public import router as public_router
from app.routes.wholesale import router as wholesale_router


# The insecure fallback from app/config.py — never acceptable outside local dev.
_INSECURE_DEFAULT_KEY = "dev-insecure-change-me"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.DEBUG and settings.SECRET_KEY in ("", _INSECURE_DEFAULT_KEY):
        raise RuntimeError(
            "SECRET_KEY is unset (or the insecure dev default) while DEBUG is off. "
            "Set a strong SECRET_KEY in the environment before starting."
        )
    settings.ensure_dirs()
    init_db()
    if settings.FORCE_RESEED:
        # Destructive one-shot: drop + recreate + reseed (see Settings.FORCE_RESEED).
        import logging
        logging.getLogger("seed").warning(
            "FORCE_RESEED is set -> dropping and reseeding the database. "
            "Remove this env var after this deploy."
        )
        from app.seed import run
        run()
    elif settings.AUTO_SEED:
        from app.seed import seed_if_empty
        seed_if_empty()
    yield


app = FastAPI(title="DreamCatcher", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE,
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.SESSION_HTTPS_ONLY,
)

# Security headers on every response. The CSP allow-list mirrors the only external
# origins the templates use: Google Fonts (@import in app.css), Leaflet from unpkg,
# and OpenStreetMap tiles (contact map). The sha256 source is the one inline
# bootstrap script in templates/base.html — if that script changes, recompute:
#   python -c "import hashlib,base64;print(base64.b64encode(hashlib.sha256(b\"<script body>\").digest()).decode())"
_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com "
    "'sha256-Du+OJKJSbdUgz5nrHeWWINvez6XKDDU/tyj/5c2uvwo='; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://unpkg.com https://*.tile.openstreetmap.org; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' mailto:; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", _CSP)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.SESSION_HTTPS_ONLY:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


# Static assets (css/js/img/uploads). Directory is created by ensure_dirs() too.
settings.ensure_dirs()
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root(request: Request) -> RedirectResponse:
    """Redirect `/` to the language prefix (cookie choice if valid, else default)."""
    lang = request.cookies.get("lang")
    if lang not in LANGS:
        lang = settings.DEFAULT_LANG
    return RedirectResponse(url=f"/{lang}/", status_code=307)


# Routers. Admin first; then the specific /{lang}/cart|checkout and /payments routers;
# public last (its routes are explicit paths, but keep ordering predictable).
app.include_router(admin_router)
app.include_router(media_router)
app.include_router(payments_router)
app.include_router(cart_router)
app.include_router(checkout_router)
app.include_router(wholesale_router)
app.include_router(marketing_router)
app.include_router(public_router)
