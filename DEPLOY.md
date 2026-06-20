# Deploy to Render (free)

This repo ships a Render Blueprint ([render.yaml](render.yaml)) — a free web service that
serves the shop over HTTPS. The free tier has an ephemeral filesystem and sleeps when idle;
`AUTO_SEED=true` re-creates the demo catalog on each cold start, so the demo always works
(orders placed on it are not durable — fine for showing the site).

## 1. Put the code on GitHub
Create a new **empty** repo on github.com (no README/.gitignore), then from this folder:

```bash
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```
(First push asks you to log in to GitHub in the browser / via a token.)

## 2. Create the service on Render
1. Sign up at https://render.com (use **"Sign in with GitHub"**).
2. **New +** → **Blueprint**.
3. Pick the repo you just pushed. Render reads `render.yaml` and shows one web service.
4. **Apply** / **Create**. First build takes ~2–4 min.
5. You get a public URL like `https://dreamcatcher-shop.onrender.com`.

That URL is permanent and works even when your PC is off. (First hit after idle is slow —
the free instance cold-starts.)

## Demo credentials
- Storefront: just browse → cart → checkout → demo payment.
- Admin: `/admin/login`, user `admin`, password `dreamcatcher`.

## Change the admin password (recommended for a public link)
```bash
python -m app.security hash "your-new-password"
```
Copy the hash → Render dashboard → your service → **Environment** → edit
`ADMIN_PASSWORD_HASH` → save (auto-redeploys).

## Going live with Viva (later)
Set in Render **Environment**: `VIVA_MODE=live` + `VIVA_CLIENT_ID`, `VIVA_CLIENT_SECRET`,
`VIVA_SOURCE_CODE`, `VIVA_WEBHOOK_SECRET`, and point Viva's webhook at
`https://<your-app>.onrender.com/payments/viva/webhook`. Finish the `live` methods in
[app/payments/viva.py](app/payments/viva.py) against the current Viva API first.

## Updating the deployed site
Render auto-deploys on every push to `main`:
```bash
git add -A && git commit -m "..." && git push
```
