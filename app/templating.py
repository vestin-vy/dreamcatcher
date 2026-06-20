"""Jinja2 templates configured with i18n + design helpers and a render helper."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import i18n
from app.cart import cart_count
from app.config import settings
from app.deps import DEFAULT_SETTINGS, is_authenticated
from app.security import get_csrf_token

templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

# Globals available in every template.
templates.env.globals["LANGS"] = i18n.LANGS
templates.env.globals["LANG_NAMES"] = i18n.LANG_NAMES
templates.env.globals["DEFAULT_LANG"] = settings.DEFAULT_LANG
templates.env.globals["format_price"] = i18n.format_price
templates.env.globals["hreflang_alternates"] = i18n.hreflang_alternates


def render(
    request: Request,
    template: str,
    *,
    lang: str | None = None,
    site: dict[str, str] | None = None,
    **context,
):
    """Render a template with the standard context (translator, lang, settings).

    `lang` defaults to the app default; `site` defaults to the static defaults so
    even error/login pages have contact info available.
    """
    lang = lang or settings.DEFAULT_LANG
    # Path with the language prefix stripped, for the language switcher links.
    path = request.url.path
    path_no_lang = path
    if path.startswith(f"/{lang}"):
        path_no_lang = path[len(lang) + 1:] or "/"
    if path_no_lang == "/":
        path_no_lang = ""
    ctx = {
        "request": request,
        "lang": lang,
        "_": i18n.make_translator(lang),
        "site": site or dict(DEFAULT_SETTINGS),
        "is_admin": is_authenticated(request),
        "current_path": request.url.path,
        "path_no_lang": path_no_lang,
        "year": datetime.now(timezone.utc).year,
        # Available on every page: CSRF token (for public cart/checkout forms) and
        # the header cart badge count. Explicit context values still override these.
        "csrf_token": get_csrf_token(request),
        "cart_count": cart_count(request),
        **context,
    }
    return templates.TemplateResponse(request, template, ctx)
