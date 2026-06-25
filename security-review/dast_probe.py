"""Non-destructive DAST probe via Starlette TestClient (full middleware stack).

Throwaway temp SQLite DB so the real data.db is untouched. NO seeding (slow image gen).
Checks: (1) security response headers, (2) session cookie flags under prod config,
(3) minimal proof that VIVA_MODE=demo lets an UNAUTHENTICATED webhook POST mark an
order 'paid' with no real payment.
"""
import os
import pathlib
import tempfile

_OUT = open(pathlib.Path(__file__).with_name("dast_results.txt"), "w", encoding="utf-8")
_b = __import__("builtins").print
def print(*a, **k):  # noqa: A001
    _b(*a, **k); _b(*a, **k, file=_OUT); _OUT.flush()

tmpdb = pathlib.Path(tempfile.gettempdir()) / "dc_dast_probe.db"
if tmpdb.exists():
    tmpdb.unlink()
os.environ["DB_URL"] = f"sqlite:///{tmpdb.as_posix()}"
os.environ["VIVA_MODE"] = "demo"
os.environ["DEBUG"] = "false"        # -> SESSION_HTTPS_ONLY defaults True (prod-like cookies)
os.environ["SECRET_KEY"] = "dast-test-only"
os.environ["AUTO_SEED"] = "false"

from fastapi.testclient import TestClient            # noqa: E402
from sqlmodel import Session, select                 # noqa: E402
from app.main import app                             # noqa: E402
from app.db import engine, init_db                   # noqa: E402
from app.models import Order                         # noqa: E402

init_db()

with TestClient(app, base_url="http://testserver") as c:  # `with` drives lifespan
    print("=" * 60)
    print("[3] DEMO PAYMENT BYPASS  (unauthenticated webhook -> order 'paid')")
    print("=" * 60)
    with Session(engine) as s:
        o = Order(number="DC-DAST-0001", status="pending", customer_name="PoC",
                  customer_email="poc@example.com", subtotal=100.0, total=100.0,
                  vat_amount=0.0, vat_rate=24.0, currency="EUR")
        s.add(o); s.commit(); s.refresh(o)
        onum = o.number
        print(f"  seeded pending order: {onum} status={o.status}")

    wh = c.post("/payments/viva/webhook", json={"order_code": onum, "status": "paid"},
                timeout=10)
    print(f"  forged POST /payments/viva/webhook -> HTTP {wh.status_code} body={wh.text}")
    with Session(engine) as s:
        o = s.exec(select(Order).where(Order.number == onum)).first()
        print(f"  order {onum} status AFTER forged webhook: ***{o.status}***  txn={o.viva_transaction_id}")
        print("  >>> RESULT:", "PAYMENT FORGED - order marked paid with NO payment"
              if o.status == "paid" else "not forged (order still pending)")

    print()
    print("=" * 60)
    print("[2] SESSION COOKIE FLAGS  (DEBUG=false -> prod-like)")
    print("=" * 60)
    r2 = c.get("/admin/login", timeout=10)  # light page; render() sets csrf -> Set-Cookie
    sc = r2.headers.get("set-cookie")
    print("status:", r2.status_code, "| raw Set-Cookie:", sc)
    if sc:
        low = sc.lower()
        print("  HttpOnly:", "YES" if "httponly" in low else "NO  (missing)")
        print("  Secure  :", "YES" if "secure" in low else "NO  (missing)")
        print("  SameSite:", "lax" if "samesite=lax" in low else ("present" if "samesite" in low else "NO"))

    print()
    print("=" * 60)
    print("[1] SECURITY RESPONSE HEADERS  (GET /admin/login)")
    print("=" * 60)
    print("status:", r2.status_code)
    for h in ["content-security-policy", "strict-transport-security", "x-frame-options",
              "x-content-type-options", "referrer-policy", "permissions-policy"]:
        print(f"  {h:28} {'PRESENT: ' + r2.headers[h] if h in r2.headers else 'MISSING'}")

try:
    if tmpdb.exists():
        tmpdb.unlink()
except OSError:
    pass
print("\n[done]")
