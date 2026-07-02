"""Checkout flow (SPEC-BILLING §3), under the `/{lang}` prefix.

Flow: GET /checkout (form) -> POST /checkout (create pending order + payment session ->
redirect to pay) -> success/cancel. In demo mode the pay page mirrors the webhook to mark
the order paid; a redirect to /success NEVER confirms payment on its own.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app import cart as cart_mod
from app import orders as orders_mod
from app.deps import get_lang, get_session, get_site_settings
from app.payments import get_provider
from app.security import verify_csrf
from app.templating import render

router = APIRouter()


def _vat_rate(site: dict) -> float:
    try:
        return float(site.get("vat_rate") or cart_mod.DEFAULT_VAT_RATE)
    except (TypeError, ValueError):
        return cart_mod.DEFAULT_VAT_RATE


@router.get("/{lang}/checkout", name="checkout")
def checkout_page(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    view = cart_mod.cart_view(request, session, lang, vat_rate=_vat_rate(site))
    if not view["lines"]:
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    methods = orders_mod.parse_shipping_methods(site, lang)
    return render(
        request, "public/checkout.html", lang=lang, site=site,
        cart=view, shipping_methods=methods,
    )


@router.post("/{lang}/checkout")
async def checkout_submit(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return RedirectResponse(url=f"/{lang}/checkout", status_code=status.HTTP_303_SEE_OTHER)

    order = orders_mod.create_order_from_cart(request, session, lang, form, site)
    if order is None:
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    # Bind the order to this session: the pay/success pages only open for its creator.
    orders_mod.remember_order(request, order.number)

    provider = get_provider()
    result = provider.create_checkout(order, lang=lang)
    session.add(order)  # provider may have set viva_order_code
    session.commit()
    return RedirectResponse(url=result.redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{lang}/checkout/success", name="checkout_success")
def checkout_success(
    request: Request,
    order: str = "",
    m: str = "",  # marketing consent outcome: "yes" | "no" | "" (not yet answered)
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    # The order was placed; clear the cart. Payment status comes only from the webhook.
    cart_mod.clear(request)
    # Only resolve the order for the session that created it — numbers are guessable.
    owned = orders_mod.session_owns_order(request, order)
    order_obj = orders_mod.find_order_by_ref(session, order) if owned else None
    return render(
        request, "public/checkout_success.html", lang=lang, site=site,
        order_number=order,
        consent_email=(order_obj.customer_email if order_obj else ""),
        consent_done=m,
    )


@router.get("/{lang}/checkout/cancel", name="checkout_cancel")
def checkout_cancel(
    request: Request,
    order: str = "",
    lang: str = Depends(get_lang),
    site: dict = Depends(get_site_settings),
):
    # Cancelled: keep the cart so the buyer can retry.
    return render(request, "public/checkout_cancel.html", lang=lang, site=site, order_number=order)


# --- demo payment page (VIVA_MODE=demo only) --------------------------------

@router.get("/{lang}/checkout/pay/{number}", name="checkout_pay_demo")
def checkout_pay_demo(
    number: str,
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    if not orders_mod.session_owns_order(request, number):
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    order = orders_mod.find_order_by_ref(session, number)
    if not order:
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "public/pay_demo.html", lang=lang, site=site, order=order)


@router.post("/{lang}/checkout/pay/{number}")
async def checkout_pay_demo_submit(
    number: str,
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return RedirectResponse(url=f"/{lang}/checkout/pay/{number}", status_code=status.HTTP_303_SEE_OTHER)
    if not orders_mod.session_owns_order(request, number):
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)

    # Mirror the real webhook: build a demo payload, verify it, mark the order paid.
    payload = json.dumps({
        "order_code": number,
        "status": "paid",
        "transaction_id": f"demo-{number}",
    }).encode()
    provider = get_provider()
    result = await provider.verify_webhook(request, payload)
    orders_mod.apply_payment_result(session, result)
    return RedirectResponse(
        url=f"/{lang}/checkout/success?order={number}", status_code=status.HTTP_303_SEE_OTHER
    )
