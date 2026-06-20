# DreamCatcher — project memory

Jewelry **showcase** site (not a shop): catalog + contact, CRUD admin, i18n (el default).
**`SPEC.md` is the source of truth** — read it before implementing. Design tokens live in
`design-system/dreamcatcher/MASTER.md`.

## Environment (hard constraints)
- **Python 3.12 only.** No node / npm / docker on this machine.
- Interpreter command is **`python`** (a `python3` shim also works).
- Stack: FastAPI + Uvicorn + Jinja2 + SQLModel + SQLite. Server-side rendering only.

## Locked decisions
- **CSS: hand-written plain CSS, NO Tailwind, NO build step.** Author from
  `static/css/tokens.css` (CSS variables out of MASTER.md). Do not add a Tailwind binary,
  PostCSS, or Play CDN.
- **Fonts/map (MVP):** Google Fonts `@import` + Leaflet via CDN. Local `.woff2` / offline
  Leaflet are an optional later hardening step (SPEC §9), not required for MVP.
- **Auth:** `passlib[bcrypt]` with **`bcrypt<4.1`** (4.1+ breaks passlib's version probe on 3.12).
- Pin versions in `requirements.txt`.

## Design rules (enforced — see MASTER.md checklist)
- SVG icons only (Heroicons/Lucide), **never emoji as icons**.
- `cursor:pointer` on clickables; hover transitions 150–300ms; visible focus; contrast ≥ 4.5:1.
- Respect `prefers-reduced-motion`. Responsive at 375 / 768 / 1024 / 1440.

## Run & verify
```powershell
cd D:\DreamCatcher
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # set SECRET_KEY + ADMIN_PASSWORD_HASH
python -m app.seed            # optional demo data
python -m uvicorn app.main:app --reload   # http://127.0.0.1:8000 -> /el/
```
- **Verification path:** `python -m pytest -q` (see `tests/test_smoke.py`, the route contract),
  then walk the manual DoD in SPEC §10 and screenshot 375/768/1024/1440.
