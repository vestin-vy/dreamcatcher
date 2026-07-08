# Deploy — production on the papaki VPS

> **Current production**: https://dc.elina-ami.gr — a papaki VPS (Ubuntu 24.04,
> IP `136.144.213.92`) shared with the studying-greece site. Caddy terminates
> TLS (auto Let's Encrypt) and proxies `dc.elina-ami.gr` → `127.0.0.1:8002`.
> The old Render setup (render.yaml) is **legacy** — kept for reference only;
> pushing to GitHub does NOT deploy anymore.

## Server layout

| What | Where |
|---|---|
| App | `/srv/dreamcatcher` (git clone of this repo), venv in `.venv` |
| Service | systemd `dreamcatcher` → uvicorn on `127.0.0.1:8002` |
| DB | local PostgreSQL 16, database `dreamcatcher` (password: `/home/deploy/.db_pass_dreamcatcher`) |
| Env | `/srv/dreamcatcher/.env` (chmod 600): SECRET_KEY, ADMIN_PASSWORD_HASH, DB_URL, SESSION_HTTPS_ONLY=true, DEFAULT_LANG=el, VIVA_MODE=demo, **PAYMENTS_ENABLED=false**, AUTO_SEED=false, CLEAR_CATALOG=true (spent — marker-guarded), PUBLIC_BASE_URL, SMTP_* + NOTIFY_TO (password reset mail) |
| Reverse proxy | `/etc/caddy/Caddyfile` (also serves the root landing + study site) |
| Backups | cron 03:20 daily: `pg_dump` + uploads tar → `/home/deploy/backups` (30 days); papaki VPS snapshots every 12 h |
| SSH | `ssh -i ~/.ssh/id_ed25519_papaki deploy@136.144.213.92` (sudo NOPASSWD) |

## Deploying a change

```bash
# from the repo: verify -> commit -> push (push alone does NOT deploy)
python -m pytest -q
git add -A && git commit -m "..." && git push

# then pull + restart on the server:
ssh -i ~/.ssh/id_ed25519_papaki deploy@136.144.213.92 \
  'cd /srv/dreamcatcher && git pull && sudo systemctl restart dreamcatcher'
```

Static-only changes still need the restart (uvicorn serves /static).
Check health: `curl -s https://dc.elina-ami.gr/el/ -o /dev/null -w "%{http_code}"`.

## Current functional state (2026-07-08)

- **Catalog is empty on purpose** — demo products/orders were retired via the
  one-shot `CLEAR_CATALOG` (marker `catalog_cleared` in the settings table;
  categories kept). Real products go in via `/admin`.
- **Payments are OFF** (`PAYMENTS_ENABLED=false`): the checkout pay button is
  disabled and POST /checkout refuses orders, pending the Viva.com contract.
- **Admin UI is English** (forced in `admin_render`), public site el/en.
- **"Forgot password"** on `/admin/login` emails a fresh password to
  `NOTIFY_TO` (elina@elina-ami.gr) and stores its bcrypt hash in the settings
  table (key `admin_password_hash`; the .env hash remains as bootstrap).

## Admin password

Two ways to change it:
1. **Forgot password** button on `/admin/login` → new password lands in the
   owner's mailbox (needs SMTP_* env set — it is, on prod).
2. Manually: `python -m app.security hash "new-password"` → put the hash into
   `/srv/dreamcatcher/.env` (`ADMIN_PASSWORD_HASH=...`) **and** delete the
   `admin_password_hash` row from the settings table (it overrides env), then
   restart.

## Going live with Viva (when the contract lands)

1. Finish `_create_checkout_live` in [app/payments/viva.py](app/payments/viva.py)
   against current Viva docs (see SPEC-BILLING §3 and the skill's billing notes).
2. In `/srv/dreamcatcher/.env`: `VIVA_MODE=live`, `VIVA_CLIENT_ID/SECRET`,
   `VIVA_SOURCE_CODE`, `VIVA_WEBHOOK_SECRET`, and `PAYMENTS_ENABLED=true`.
3. Point Viva's webhook at `https://dc.elina-ami.gr/payments/viva/webhook`.
4. Restart the service; test a real transaction end to end.

## Legacy: Render (retired 2026-07-08)

`render.yaml` describes the old free-tier Render deployment (web service +
Postgres blueprint). The Render services/databases can be deleted; the file is
kept only as history. Reason for the move: free Postgres expires after 30 days,
services sleep when idle, uploads were ephemeral.
