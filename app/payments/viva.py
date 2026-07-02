"""Viva.com payment provider (SPEC-BILLING §3).

Two modes:
  * demo  — internal stub flow, no keys required. `create_checkout` redirects to an
            in-app demo payment page; that page POSTs the SAME webhook endpoint the real
            gateway would, so the "webhook is the source of truth" path is exercised.
  * live  — real Viva Smart Checkout (skeleton; activate when keys are provisioned).

The live branch is intentionally left with clearly-marked TODOs: confirm the exact Viva
API shapes against the official docs (https://developer.viva.com) before going live.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import Request

from app.config import settings
from app.models import Order
from app.payments.base import CheckoutResult, PaymentProvider, PaymentResult


class VivaProvider(PaymentProvider):
    def __init__(self, mode: str = "demo") -> None:
        self.mode = (mode or "demo").lower()

    # --- checkout -----------------------------------------------------------

    def create_checkout(self, order: Order, *, lang: str) -> CheckoutResult:
        if self.mode == "live":
            return self._create_checkout_live(order, lang=lang)
        return self._create_checkout_demo(order, lang=lang)

    def _create_checkout_demo(self, order: Order, *, lang: str) -> CheckoutResult:
        # In demo the provider "order code" is just our order number.
        order.viva_order_code = order.number
        return CheckoutResult(
            redirect_url=f"/{lang}/checkout/pay/{order.number}",
            provider_ref=order.number,
        )

    def _create_checkout_live(self, order: Order, *, lang: str) -> CheckoutResult:
        # TODO(live): implement against Viva Smart Checkout.
        #   1. OAuth2 client-credentials token from accounts.vivapayments.com
        #      using VIVA_CLIENT_ID / VIVA_CLIENT_SECRET.
        #   2. POST /checkout/v2/orders with amount (in cents), customer, sourceCode,
        #      and merchantTrns=order.number -> returns orderCode.
        #   3. redirect_url = https://www.vivapayments.com/web/checkout?ref={orderCode}
        # Uses httpx (already a dependency). Verify field names against current docs.
        raise NotImplementedError(
            "VIVA_MODE=live is not wired yet. Use VIVA_MODE=demo, or implement "
            "_create_checkout_live against the current Viva API."
        )

    # --- webhook ------------------------------------------------------------

    async def verify_webhook(self, request: Request, raw_body: bytes) -> PaymentResult | None:
        if self.mode == "live":
            return self._verify_webhook_live(request, raw_body)
        return self._verify_webhook_demo(request, raw_body)

    def _parse_body(self, raw_body: bytes) -> dict:
        if not raw_body:
            return {}
        try:
            return json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            # Demo pay page submits a form; fall back to urlencoded parsing.
            from urllib.parse import parse_qs

            parsed = parse_qs(raw_body.decode("utf-8", "ignore"))
            return {k: v[0] for k, v in parsed.items()}

    def _verify_webhook_demo(self, request: Request, raw_body: bytes) -> PaymentResult | None:
        data = self._parse_body(raw_body)
        order_ref = data.get("order_code") or data.get("order_ref") or data.get("number")
        if not order_ref:
            return None
        status = (data.get("status") or "paid").lower()
        txn = data.get("transaction_id") or f"demo-{order_ref}"
        return PaymentResult(
            order_ref=str(order_ref),
            status="paid" if status in {"paid", "success"} else status,
            transaction_id=str(txn),
        )

    def _verify_webhook_live(self, request: Request, raw_body: bytes) -> PaymentResult | None:
        # Optional HMAC signature check (configure the header name per Viva docs).
        secret = settings.VIVA_WEBHOOK_SECRET
        if secret:
            sent = request.headers.get("x-viva-signature", "")
            expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sent, expected):
                return None
        data = self._parse_body(raw_body)
        # TODO(live): map Viva's webhook payload (EventData.OrderCode,
        # EventData.TransactionId, EventTypeId) to the fields below. Confirm against docs.
        event = data.get("EventData") or {}
        order_ref = event.get("MerchantTrns") or event.get("OrderCode")
        if not order_ref:
            return None
        # Viva EventTypeId 1796 = "Transaction Payment Created" (successful charge).
        is_paid = str(data.get("EventTypeId")) == "1796"
        return PaymentResult(
            order_ref=str(order_ref),
            status="paid" if is_paid else "pending",
            transaction_id=str(event.get("TransactionId") or "") or None,
        )
