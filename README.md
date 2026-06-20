# DreamCatcher

A jewelry **showcase** site (catalog + contact, not a shop) with a CRUD admin and
four-language UI (Greek default, plus English, Russian, French). Server-rendered with
FastAPI + Jinja2 + SQLModel + SQLite. Hand-written plain CSS, no build step.

See [`SPEC.md`](SPEC.md) for the full specification and
[`design-system/dreamcatcher/MASTER.md`](design-system/dreamcatcher/MASTER.md) for design tokens.

## Requirements

- **Python 3.12** (no node / npm / docker needed).
- Interpreter command is `python`.

## Quick start (Windows / PowerShell)

```powershell
cd D:\DreamCatcher
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure environment
copy .env.example .env
#  -> set SECRET_KEY and ADMIN_PASSWORD_HASH (see below)

python -m app.seed                          # optional: demo data + images
python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000  ->  /el/
```

Or use the helper script: `.\run.ps1` (or `run.cmd`).

### Generate the admin password hash

```powershell
python -m app.security hash "your-password"
```
Copy the printed `$2b$...` hash into `ADMIN_PASSWORD_HASH` in `.env`.
Generate a `SECRET_KEY` with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

> Local dev `.env` is pre-seeded with password **`dreamcatcher`** for user **`admin`** —
> change both before any real deployment.

## Admin

- Login at `/admin/login`. The admin area lives under `/admin/*`.
- Manage products (with **per-language tabs** for title/description/material), multi-image
  upload (Pillow → resized WebP + thumbnails), categories with translations, and site
  settings (contacts, map coordinates, default language, show-prices toggle).
- All admin POSTs are CSRF-protected; login is rate-limited; uploads accept images only.

## Internationalization

- URL prefix per language: `/el`, `/en`, `/ru`, `/fr`. `/` redirects to the default
  (cookie choice if set, else `el`).
- UI strings live in `app/i18n.py`. Content (products/categories) comes from the DB with a
  fallback chain **el → en**.

## Project layout

```
app/        FastAPI app: config, db, models, i18n, deps, security, images, routes/, seed
templates/  Jinja2: base.html, _macros.html, public/*, admin/*
static/     css/ (tokens.css + app.css), js/, img/, uploads/ (+ thumbs/)
tests/      test_smoke.py — the route contract (SPEC §10 DoD)
```

## Verify

```powershell
python -m pytest -q          # route contract: redirects, 4 languages, admin guard, fallback
```

Manual DoD (SPEC §10): `/` → `/el/`; language switch stays on page; catalog + product
cards show price or "on request"; missing translation falls back to el; admin can add a
product with photo and 4 translations and it appears on the site; visibility toggle
hides/shows it; non-image uploads are rejected.

### Screenshots (responsive check)

```powershell
pip install playwright
python -m playwright install chromium
python scripts/shoot.py      # writes screenshots/ at 375/768/1024/1440
```
