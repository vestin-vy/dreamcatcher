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


@asynccontextmanager
async def lifespan(app: FastAPI):
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
