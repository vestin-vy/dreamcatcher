"""Marketing consent routes (GDPR/ePrivacy, Task 3), under the `/{lang}` prefix.

Capture happens via an inline block on the order confirmation page (not a modal).
Withdrawal is a one-click, login-free link carried by every marketing email.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app import marketing
from app.deps import get_lang, get_session, get_site_settings
from app.security import verify_csrf
from app.templating import render

router = APIRouter()


@router.post("/{lang}/marketing/consent")
async def marketing_consent(request: Request, lang: str = Depends(get_lang),
                            session: Session = Depends(get_session)):
    form = await request.form()
    order_number = (form.get("order") or "").strip()
    success = f"/{lang}/checkout/success?order={order_number}"
    if not verify_csrf(request, form.get("csrf_token")):
        return RedirectResponse(url=success, status_code=status.HTTP_303_SEE_OTHER)

    choice = (form.get("choice") or "").strip()
    email = (form.get("email") or "").strip()
    if choice == "accept" and email:
        marketing.record_consent(session, email, lang, source="checkout_confirmation")
        flag = "yes"
    else:
        flag = "no"  # decline records nothing — no consent given
    return RedirectResponse(url=f"{success}&m={flag}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{lang}/unsubscribe/{token}", name="unsubscribe")
def unsubscribe(token: str, request: Request, lang: str = Depends(get_lang),
                session: Session = Depends(get_session), site: dict = Depends(get_site_settings)):
    marketing.withdraw_by_token(session, token)  # idempotent; unknown token -> generic page
    return render(request, "public/unsubscribe.html", lang=lang, site=site)
