"""Payment provider abstraction (SPEC-BILLING §3).

The order/checkout/webhook code depends ONLY on this interface, so swapping or adding a
gateway (Stripe, etc.) later means writing one new `PaymentProvider` — no changes to how
orders are created or marked paid.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import Request

from app.config import settings
from app.models import Order


@dataclass
class CheckoutResult:
    """Outcome of starting a payment: where to send the customer next."""
    redirect_url: str
    provider_ref: str  # provider's order code (stored as Order.viva_order_code)


@dataclass
class PaymentResult:
    """Normalised result parsed from a provider webhook."""
    order_ref: str           # provider order code / our order number
    status: str              # "paid" | "failed" | "pending"
    transaction_id: str | None = None

    @property
    def is_paid(self) -> bool:
        return self.status == "paid"


class PaymentProvider(ABC):
    """Interface every payment gateway implements."""

    @abstractmethod
    def create_checkout(self, order: Order, *, lang: str) -> CheckoutResult:
        """Create a payment session for `order` and return where to redirect the buyer.

        May mutate `order` (e.g. set the provider order code); the caller commits.
        """

    @abstractmethod
    async def verify_webhook(self, request: Request, raw_body: bytes) -> PaymentResult | None:
        """Validate an incoming webhook and return a normalised result.

        Returns None if the request is not a valid/recognised payment event. This is the
        ONLY trusted signal that a payment succeeded (SPEC-BILLING §3).
        """


def get_provider() -> PaymentProvider:
    """Return the configured provider (currently only Viva; demo or live by VIVA_MODE)."""
    from app.payments.viva import VivaProvider

    return VivaProvider(mode=settings.VIVA_MODE)
