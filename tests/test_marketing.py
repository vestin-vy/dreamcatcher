"""Marketing consent service tests (Task 3). Pure DB — no TestClient/sockets."""
import pytest
from sqlmodel import Session, select

try:
    from app.db import engine
    from app.models import MarketingConsent
    from app import marketing
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    engine = None
    _IMPORT_ERROR = exc

TEST_EMAIL = "consent-test@example.com"


def _skip_if_no_app():
    if engine is None:
        pytest.skip(f"app not importable: {_IMPORT_ERROR}")


def _cleanup(session):
    row = session.exec(
        select(MarketingConsent).where(MarketingConsent.email == TEST_EMAIL)
    ).first()
    if row:
        session.delete(row)
        session.commit()


def test_build_consent_text_resolves_privacy_link():
    _skip_if_no_app()
    en = marketing.build_consent_text("en")
    assert "{privacy_policy}" not in en
    assert "Privacy Policy" in en and "/en/privacy" in en
    el = marketing.build_consent_text("el")
    assert "/el/privacy" in el


def test_record_consent_upsert_then_withdraw():
    _skip_if_no_app()
    with Session(engine) as s:
        _cleanup(s)
        try:
            c = marketing.record_consent(s, TEST_EMAIL.upper(), "en")
            assert c.email == TEST_EMAIL          # normalized to lowercase
            assert c.status == "subscribed"
            assert c.consented_at is not None and c.withdrawn_at is None
            assert c.source == "checkout_confirmation"
            assert c.unsubscribe_token                      # token minted
            assert c.consent_text == marketing.build_consent_text("en")
            token = c.unsubscribe_token

            # Re-consent (different lang) updates the SAME row, keeps the token.
            c2 = marketing.record_consent(s, TEST_EMAIL, "el")
            assert c2.id == c.id and c2.lang == "el"
            assert c2.unsubscribe_token == token
            assert len(s.exec(select(MarketingConsent).where(
                MarketingConsent.email == TEST_EMAIL)).all()) == 1
            assert c2 in marketing.subscribed(s)

            # One-click withdraw is idempotent and removes from the subscribed list.
            w = marketing.withdraw_by_token(s, token)
            assert w is not None and w.status == "withdrawn" and w.withdrawn_at is not None
            assert marketing.withdraw_by_token(s, token).status == "withdrawn"
            assert all(x.email != TEST_EMAIL for x in marketing.subscribed(s))
            assert marketing.withdraw_by_token(s, "bogus-token") is None
        finally:
            _cleanup(s)
