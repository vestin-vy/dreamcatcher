# DreamCatcher — project memory

Handmade-jewelry **shop**: catalog + cart + checkout (Viva.com, сейчас выключено)
+ B2B-опт + CRUD-админка, i18n **el (default) + en**.
**`SPEC.md` + `SPEC-BILLING.md` — источники истины** — читать перед реализацией.
Дизайн-токены: `design-system/dreamcatcher/MASTER.md`.

## Production (с 2026-07-08 — VPS, НЕ Render)
- **https://dc.elina-ami.gr** — papaki VPS `136.144.213.92`, systemd `dreamcatcher`,
  порт 8002 за Caddy, PostgreSQL 16 локально. Полная схема: `DEPLOY.md`.
- **`git push` НЕ деплоит.** Деплой = `ssh -i ~/.ssh/id_ed25519_papaki deploy@136.144.213.92
  'cd /srv/dreamcatcher && git pull && sudo systemctl restart dreamcatcher'`.
- Текущее состояние: **каталог пуст** (одноразовый `CLEAR_CATALOG`, маркер в settings,
  категории сохранены), **`PAYMENTS_ENABLED=false`** до контракта Viva, **админка
  всегда на английском** (форс в `admin_render`), «Забыл пароль» шлёт новый пароль
  на elina@elina-ami.gr (хэш в БД `admin_password_hash` перекрывает env).
- render.yaml — легаси, оставлен как история.

## Environment (hard constraints)
- **Python 3.12 only.** No node / npm / docker on this machine.
- Interpreter command is **`python`** (a `python3` shim also works).
- Stack: FastAPI + Uvicorn + Jinja2 + SQLModel. SQLite в dev, PostgreSQL в prod
  (`DB_URL`/`DATABASE_URL`, psycopg v3). Server-side rendering only.

## Locked decisions
- **CSS: hand-written plain CSS, NO Tailwind, NO build step.** Author from
  `static/css/tokens.css` (CSS variables out of MASTER.md). Do not add a Tailwind binary,
  PostCSS, or Play CDN.
- **Auth:** `passlib[bcrypt]` with **`bcrypt<4.1`** (4.1+ breaks passlib's version probe on 3.12).
- Pin versions in `requirements.txt`.
- **Оплата подтверждается ТОЛЬКО вебхуком** `/payments/viva/webhook`; success-redirect
  ничего не подтверждает; mark-paid идемпотентен.

## Design rules (enforced — see MASTER.md checklist)
- SVG icons only (Heroicons/Lucide), **never emoji as icons**.
- `cursor:pointer` on clickables; hover transitions 150–300ms; visible focus; contrast ≥ 4.5:1.
- Respect `prefers-reduced-motion`. Responsive at 375 / 768 / 1024 / 1440.

## Run & verify
```powershell
cd D:\Dreamcatcher_site_with_billing
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # set SECRET_KEY + ADMIN_PASSWORD_HASH
python -m app.seed            # demo data (drop + recreate!)
python -m uvicorn app.main:app --reload   # http://127.0.0.1:8000 -> /el/
```
- **Verification path:** `python -m pytest -q` (smoke + billing + security + wholesale
  + marketing + media + anonymize; красный прогон — сначала пересеять), затем ручной
  DoD из SPEC §10, скриншоты 375/768/1024/1440.
- Перед правкой models/auth/payments/i18n — читать
  `~/.claude/skills/dreamcatcher-dev/references/lessons-learned.md` (bcrypt-пин,
  no-future-annotations в models.py, CSP без inline, WMI-зависание pytest и др.).
- `tests/conftest.py` + `.venv/.../sitecustomize.py` содержат обход зависшей WMI этой
  машины (2026-07-08); sitecustomize можно удалить после перезагрузки Windows.
