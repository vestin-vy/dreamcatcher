"""Marketing consent service (GDPR/ePrivacy, Task 3).

Consent is stored per email in its own table (MarketingConsent), independent of orders.
We record the exact wording shown (consent_text), the language, the source, and a random
unsubscribe token for one-click, login-free withdrawal.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlmodel import Session, select

from app import i18n
from app.models import MarketingConsent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def build_consent_text(lang: str) -> str:
    """The EXACT marketing body shown at capture, with {privacy_policy} resolved to a
    label + URL so the stored consent_text mirrors what the user read."""
    body = i18n.t(lang, "marketing.body")
    label = i18n.t(lang, "marketing.privacy_link")
    return body.replace("{privacy_policy}", f"{label} (/{lang}/privacy)")


def record_consent(session: Session, email: str, lang: str,
                   source: str = "checkout_confirmation") -> MarketingConsent:
    """Upsert an affirmative subscription for `email`. Re-subscribing clears withdrawal."""
    email = (email or "").strip().lower()
    consent = session.exec(
        select(MarketingConsent).where(MarketingConsent.email == email)
    ).first()
    text = build_consent_text(lang)
    if consent is None:
        consent = MarketingConsent(email=email, unsubscribe_token=_new_token())
    consent.status = "subscribed"
    consent.consented_at = _utcnow()
    consent.withdrawn_at = None
    consent.lang = lang
    consent.consent_text = text
    consent.source = source
    if not consent.unsubscribe_token:
        consent.unsubscribe_token = _new_token()
    session.add(consent)
    session.commit()
    session.refresh(consent)
    return consent


def withdraw_by_token(session: Session, token: str) -> MarketingConsent | None:
    """One-click unsubscribe. Idempotent: returns the consent (already-withdrawn is fine),
    or None if the token is unknown."""
    if not token:
        return None
    consent = session.exec(
        select(MarketingConsent).where(MarketingConsent.unsubscribe_token == token)
    ).first()
    if consent is None:
        return None
    if consent.status != "withdrawn":
        consent.status = "withdrawn"
        consent.withdrawn_at = _utcnow()
        session.add(consent)
        session.commit()
        session.refresh(consent)
    return consent


def subscribed(session: Session) -> list[MarketingConsent]:
    """Currently-subscribed contacts, newest first (for the admin list / CSV)."""
    return session.exec(
        select(MarketingConsent)
        .where(MarketingConsent.status == "subscribed")
        .order_by(MarketingConsent.consented_at.desc())
    ).all()
