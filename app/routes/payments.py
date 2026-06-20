"""Payment webhooks (SPEC-BILLING §3). No language prefix, no CSRF — authenticity is
established by the provider's signature inside `verify_webhook`.

This endpoint is the ONLY trusted signal that a payment succeeded, and it is idempotent:
a redelivered event will not pay an order twice (see `orders.mark_order_paid`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app import orders as orders_mod
from app.db import get_session
from app.payments import get_provider

router = APIRouter(prefix="/payments")


@router.post("/viva/webhook")
async def viva_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    provider = get_provider()
    result = await provider.verify_webhook(request, raw)
    if result is None:
        # Not a recognised/valid event. 200 so the provider stops retrying a bad payload.
        return JSONResponse({"ok": False, "reason": "ignored"}, status_code=200)
    applied = orders_mod.apply_payment_result(session, result)
    return JSONResponse({"ok": True, "applied": applied}, status_code=200)


@router.get("/viva/webhook")
def viva_webhook_verify():
    """Some gateways GET the webhook URL to verify it. Return a simple 200."""
    return JSONResponse({"Key": "dreamcatcher-viva-webhook"}, status_code=200)
