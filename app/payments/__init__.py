"""Payment providers (SPEC-BILLING §3).

`get_provider()` returns the configured provider; routes depend on the abstract
`PaymentProvider` interface so a different gateway (e.g. Stripe) can be added later
without touching the order/checkout code.
"""
from app.payments.base import (
    CheckoutResult,
    PaymentProvider,
    PaymentResult,
    get_provider,
)

__all__ = ["CheckoutResult", "PaymentProvider", "PaymentResult", "get_provider"]
