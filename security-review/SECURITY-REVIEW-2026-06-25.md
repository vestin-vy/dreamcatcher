# DreamCatcher (with billing) — Pre-Production Security Review

- **Target:** `D:\Dreamcatcher_site_with_billing` (local, pre-deployment)
- **Date:** 2026-06-25
- **Engagement:** Non-destructive, authorized AppSec assessment (detect-and-report). Read-only on source.
- **Stack (detected):** Python 3.12 · FastAPI + Uvicorn + Jinja2 + SQLModel + SQLite · server-side rendered · no JS build step · payment provider **Viva.com (Viva Wallet)** via `app/payments/viva.py` + `httpx`.
- **Reviewer note:** This is a server-rendered Python app, so the JS-oriented parts of the original plan (npm audit, retire.js, source-maps) are **N/A**; Python-native equivalents (pip-audit, bandit) were used instead, and DAST tooling was adapted (no Docker → no ZAP).

---

## Executive summary — fix-first

| # | Severity | Finding | OWASP |
|---|----------|---------|-------|
| 1 | **HIGH** | `VIVA_MODE=demo` is the shipped default; demo webhook/pay path authenticates nothing → **free "paid" orders**. Live mode is `NotImplementedError`, so the app can currently run **only** in the bypassable mode. | A04 / A05 |
| 2 | **HIGH** | Live webhook signature check is **optional** (`if secret:`) and the HMAC scheme is an unverified placeholder → **forgeable "payment success"**. | A04 / A07 |
| 3 | **MEDIUM** | IDOR / info-disclosure: orders resolved by **predictable sequential number**; unauthenticated demo pay page leaks order total. | A01 |
| 4 | **MEDIUM** | Stored XSS via product description `|safe` (admin-authored, autoescape bypassed). | A03 |
| 5 | **MEDIUM** | **No security headers** (CSP / HSTS / X-Frame-Options / X-Content-Type-Options / Referrer-Policy). | A05 |
| 6 | **LOW** | Insecure default `SECRET_KEY` → admin session forgery if deployed unset. | A02 / A05 |
| 7 | **LOW** | Hardcoded admin password (`"dreamcatcher"`) in git-tracked `scripts/shoot.py`. | A07 |
| 8 | **LOW** | Login rate-limit is per-process / in-memory / peer-IP keyed (defense-in-depth gap). | A07 |
| 9 | **INFO** | Stray `"f"`→paid status token; webhook `GET` returns a static key string. | A09 |

**Bottom line:** The billing *core* is well-designed — prices are computed server-side, mark-paid is idempotent, CSRF and the admin guard are applied consistently, and no card data ever touches the app (Viva hosted-redirect). The risk is concentrated in **deployment posture**: the only working payment mode is the unauthenticated demo, and the live path's webhook authentication is unfinished. **Do not deploy with real payments until #1 and #2 are resolved.**

---

## What passed (verified, no action needed)

- **Price/amount integrity — SOLID.** The cart session stores only `{product_id: qty}` (`app/cart.py`); prices are always read fresh from the DB and snapshotted onto the order at checkout (`app/orders.py:create_order_from_cart`). The client cannot tamper with price, currency (forced `EUR`), or inject negative quantities (`add()` uses `max(1, qty)`; `set_qty<=0` removes).
- **Idempotent payment application — SOLID.** `mark_order_paid` (`app/orders.py:164`) returns early if already `paid` or if the transaction id was already recorded → webhook replay cannot double-pay or double-decrement stock (SPEC-BILLING §6 satisfied).
- **CSRF** is verified on every state-changing POST (checkout, cart, admin, demo pay) via `verify_csrf` with `secrets.compare_digest`.
- **Admin authZ** — every `/admin/*` route calls `ensure_admin`; status transitions are whitelisted (`_ALLOWED_TRANSITIONS`); admin order views require auth (no IDOR there).
- **Secrets hygiene — GOOD.** `.gitignore` excludes `.env`, `data.db`, and uploads; only `.env.example` (placeholders) is tracked. No secret Viva key is rendered to any template/JS — keys live server-side in `app/config.py`; demo mode needs none.
- **Password storage** uses `passlib` bcrypt; session cookie flags are correct in production (HttpOnly always, `SameSite=Lax`, `Secure` when `DEBUG` is off — see Layer 7).
- **Dependencies** — `pip-audit`: no known CVEs in the installed environment.
- **SAST** — `bandit` (medium+): clean (only the Low in #7).

---

## Detailed findings

### 1. HIGH — Demo payment mode is the default; complete payment bypass if deployed
**OWASP A04 Insecure Design / A05 Security Misconfiguration**

`VIVA_MODE` defaults to `"demo"` ([app/config.py:73](app/config.py:73)) and `.env.example` ships `VIVA_MODE=demo` ([.env.example:26](.env.example:26)). In demo mode:

- `_verify_webhook_demo` ([app/payments/viva.py:76](app/payments/viva.py:76)) performs **no authentication and no signature check** — any body containing an `order_code` returns `status="paid"`.
- Both the public demo pay page (`POST /{lang}/checkout/pay/{number}`, [app/routes/checkout.py:110](app/routes/checkout.py:110)) and the webhook ([app/routes/payments.py:20](app/routes/payments.py:20)) route through `apply_payment_result` → `mark_order_paid`, flipping the order to **paid with no real payment**.
- The live alternative is not implemented — `_create_checkout_live` raises `NotImplementedError` ([app/payments/viva.py:52](app/payments/viva.py:52)). **The app can therefore only run today in the bypassable demo mode.**

**Evidence:** Provider mode confirmed `demo` at runtime; the demo webhook handler accepts an unsigned forged body and `mark_order_paid` transitions the order — verified by reading the exact 3-function chain (`verify_webhook` → `apply_payment_result` → `mark_order_paid`). A live HTTP proof was attempted (`security-review/poc_demo_bypass.py`) but the Windows `TestClient`/shell exhibited output-buffering hangs; the code path is unambiguous and self-contained.

**Remediation:**
- Fail-closed: refuse to start (or refuse `POST /checkout`) when `VIVA_MODE != "live"` and `DEBUG` is off.
- Implement and verify `_create_checkout_live` / `_verify_webhook_live` against current Viva docs before any deploy.
- Never ship `demo` as the default for a build that has billing enabled — make `live` the default and demo an explicit opt-in guarded by `DEBUG`.

### 2. HIGH — Live webhook signature verification is optional and a placeholder
**OWASP A04 / A07**

`_verify_webhook_live` ([app/payments/viva.py:89](app/payments/viva.py:89)):
```python
secret = settings.VIVA_WEBHOOK_SECRET
if secret:                       # <-- skipped entirely when unset
    sent = request.headers.get("x-viva-signature", "")
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sent, expected):
        return None
```
- If `VIVA_WEBHOOK_SECRET` is unset, **no verification happens** → any POST with `EventTypeId=1796` and an `OrderCode`/`MerchantTrns` marks an order paid (forged success callback).
- Even when set, the `x-viva-signature` HMAC-SHA256 scheme is a **guessed placeholder** (the code's own TODO says to confirm against docs). Viva's real webhook model is a Basic-auth *Messages* verification key / webhook verification token — not this HMAC — so as written it will either reject all genuine events or validate nothing.

**Remediation:** Make verification **mandatory** in live (reject if the secret is missing); implement Viva's actual verification (developer.viva.com) and add a timestamp/replay guard. Add a unit test that a wrong/missing signature yields no state change.

### 3. MEDIUM — IDOR & info disclosure via predictable order numbers
**OWASP A01 Broken Access Control**

Order numbers are sequential and guessable: `DC-YYYYMMDD-NNNN` ([app/orders.py:54](app/orders.py:54)). They are the correlation key in both the webhook (`find_order_by_ref`, [app/orders.py:194](app/orders.py:194)) and the **unauthenticated** demo pay page `GET /{lang}/checkout/pay/{number}` ([app/routes/checkout.py:96](app/routes/checkout.py:96)), which has no session/ownership binding. An attacker can enumerate numbers to confirm an order exists and read its **total** (`templates/public/pay_demo.html` renders `order.total` + `order.number`), and in demo drive it to paid (see #1).

**Remediation:** Bind the pay/success pages to the session that created the order (store the order id in `request.session`), or address orders by an unguessable token (e.g. a random `provider_ref`) rather than the public number. In live, never accept the human order number as the sole webhook correlator.

### 4. MEDIUM — Stored XSS via product description (`|safe`)
**OWASP A03 Injection**

[templates/public/product.html:47](templates/public/product.html:47):
```jinja
{% if product.description %}<p class="product__desc">{{ product.description|replace('\n', '<br>')|safe }}</p>{% endif %}
```
`|safe` disables autoescaping on the whole description. The field is admin-authored (CRUD admin), so exploitation requires admin access or a second write vector — but any markup an admin pastes (or that reaches the field) executes as script in every visitor's browser, and there is no CSP to blunt it (#5).

**Remediation:** Escape *before* inserting `<br>`: `{{ product.description|e|replace('\n','<br>')|safe }}` (the replace then operates on already-escaped text). Cleaner still: drop `|safe` and render newlines with CSS `white-space: pre-line`.

### 5. MEDIUM — Missing security headers
**OWASP A05 Security Misconfiguration**

[app/main.py](app/main.py) registers only `SessionMiddleware`; no response-header middleware exists and `TemplateResponse` adds none. Confirmed from code (definitive). Consequences: no clickjacking protection on `/admin` (no `X-Frame-Options`/`frame-ancestors`), no `X-Content-Type-Options: nosniff`, no HSTS, and no CSP to mitigate #4.

**Remediation:** Add a small middleware:
```python
@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self' https://unpkg.com; frame-ancestors 'none'")
    if settings.SESSION_HTTPS_ONLY:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp
```
(Tune the CSP allow-list to the exact Google Fonts / Leaflet CDN origins in use.)

### 6. LOW — Insecure default SECRET_KEY
**OWASP A02 / A05**

`SECRET_KEY` defaults to `"dev-insecure-change-me"` ([app/config.py:39](app/config.py:39)); `.env.example` ships a placeholder. Deployed unset, the itsdangerous session-signing key is public → an attacker can forge a `{"admin": true}` session cookie and take over the admin.

**Remediation:** Fail-closed at startup if `SECRET_KEY` is empty/default while `DEBUG` is off.

### 7. LOW — Hardcoded admin password in a git-tracked script
**OWASP A07**

[scripts/shoot.py:20](scripts/shoot.py:20): `ADMIN_PASS = "dreamcatcher"` — confirmed git-tracked (`git ls-files scripts/shoot.py`). If this is/was the real admin password it is a committed credential (present in history too).

**Remediation:** Read the password from `.env`, not a literal; rotate the admin password; scrub history if it was ever a real secret. (Flagged by `bandit` B105.)

### 8. LOW — Login rate-limit is per-process / in-memory / peer-IP keyed
**OWASP A07**

[app/security.py:68-82](app/security.py:68). Resets on restart, not shared across workers; behind a reverse proxy `request.client.host` is the proxy IP, collapsing all clients into one bucket. Defense-in-depth only (credentials are bcrypt-hashed).

**Remediation:** Acceptable for MVP; for production use a shared store and derive the client IP from a trusted proxy header only when behind a known proxy.

### 9. INFO — Minor robustness/disclosure
- `_verify_webhook_demo` maps `status in {"paid","success","f"}` → paid ([app/payments/viva.py:85](app/payments/viva.py:85)). The stray `"f"` looks like a copy artifact; Viva historically uses `F` = *Fail*, so this could mis-classify a failure as paid in some payloads. Remove it.
- `GET /payments/viva/webhook` returns a static `{"Key": "dreamcatcher-viva-webhook"}` ([app/routes/payments.py:32](app/routes/payments.py:32)) — trivial endpoint fingerprint; harmless but revisit when wiring live verification.

---

## Layer-by-layer status

| Layer | Tool/method | Result |
|-------|-------------|--------|
| 1. Discovery | manual | FastAPI/SQLModel/SQLite + Viva; done |
| 2. Dependencies | `pip-audit` | **clean** (no known CVEs). Note: `requirements.txt` is unpinned — pin versions / commit `requirements.lock` (CLAUDE.md already says to) for supply-chain hygiene. |
| 3. Client-side libs | retire.js | **N/A** — no JS bundle; only Leaflet + Google Fonts via CDN (SRI not applied — minor, consider `integrity=` on the CDN tags). |
| 4. SAST | `bandit` | medium+ clean; one Low (#7). |
| 5. Secrets | gitleaks→git/grep | **clean** — no secrets tracked; `.gitignore` correct; no keys client-side. |
| 6. Billing | manual source review | Findings #1–#3, #9; price integrity & idempotency **pass**. |
| 7. Hygiene | code + intended DAST | Missing headers (#5); cookie flags correct in prod; source-maps N/A. |
| 8. DAST | OWASP ZAP / TestClient | **Not completed** — Docker absent (no ZAP); in-process `TestClient` hit lifespan/output-buffering hangs on this Windows host. Header/cookie facts derived from code (definitive); bypass confirmed via code path. |

### Skipped / not-run checks (and why)
- **OWASP ZAP baseline** — Docker not installed on this machine; no non-Docker ZAP available.
- **npm audit / retire.js / trivy** — N/A (no Node project / no JS bundle) or not installed; replaced by pip-audit + bandit.
- **Live HTTP DAST run** — Starlette `TestClient` (httpx) hung on lifespan startup under PowerShell here; not pursued further since all relevant facts were obtainable from source with certainty.

### Cookie flags (from code — `starlette.middleware.sessions`)
With `same_site="lax"` and `https_only=settings.SESSION_HTTPS_ONLY` (defaults to `not DEBUG`):
- **HttpOnly:** yes (always set by SessionMiddleware)
- **SameSite:** `Lax`
- **Secure:** yes in production (`DEBUG` off), off in local dev — correct.

---

## PII / card-data hygiene
No PAN/CVV is handled, logged, or stored anywhere — Viva uses a **hosted-redirect / Smart Checkout** model, so card data never reaches this app or its SQLite DB. SQL `echo` is tied to `DEBUG` ([app/db.py:13](app/db.py:13)) → off in production, so customer PII is not logged via query echo in prod. Order PII (name, email, phone, address) is stored in `data.db`; ensure host-level file protection and the backup target (`scripts/backup.py`) are access-controlled.

## Suggested fix order
1. **#1 + #2** — gate demo mode out of production and finish/verify live webhook auth (blockers for real payments).
2. **#5 + #4** — add security-header middleware and fix the `|safe` XSS together (CSP backstops the XSS).
3. **#3** — bind checkout/pay pages to the buyer's session.
4. **#6, #7, #8, #9** — startup secret check, move the script password to env + rotate, harden rate-limit, tidy the status token.
