"""Shared FastAPI dependencies: locale, DB session, admin guard, site settings."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request, status
from sqlmodel import Session, select

from app.db import get_session
from app.i18n import LANGS
from app.models import Setting

# Default site settings (used when a key is absent from the DB).
DEFAULT_SETTINGS: dict[str, str] = {
    "site_title": "DreamCatcher",
    "phone": "+30 210 000 0000",
    "email": "hello@dreamcatcher.example",
    "address": "Ermou 1, Athens 105 63, Greece",
    "whatsapp": "302100000000",
    "instagram": "dreamcatcher.jewelry",
    "map_lat": "37.9755",
    "map_lng": "23.7348",
    "default_lang": "el",
    "show_prices": "1",
    "about_text": "DreamCatcher creates handcrafted jewelry inspired by timeless elegance.",
    # Billing (SPEC-BILLING §4). settings_save picks these up automatically.
    "vat_rate": "24",
    # One shipping method per line: slug|Greek label|English label|cost
    "shipping_methods": (
        "courier|Ταχυμεταφορά|Courier|5\n"
        "pickup|Παραλαβή από το κατάστημα|Store pickup|0"
    ),
    "notify_email": "",
}


def get_lang(lang: str = Path(...)) -> str:
    """Validate the `{lang}` path param against the supported languages."""
    if lang not in LANGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown language")
    return lang


def get_site_settings(session: Session = Depends(get_session)) -> dict[str, str]:
    """Load all site settings, layering DB values over defaults."""
    merged = dict(DEFAULT_SETTINGS)
    for row in session.exec(select(Setting)).all():
        merged[row.key] = row.value
    return merged


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin"))


def current_admin(request: Request) -> bool:
    """Guard dependency for admin routes; redirects handled by the route layer."""
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return True
