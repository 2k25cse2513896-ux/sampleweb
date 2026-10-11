# Free deployment checklist

This project is prepared for a free hobby deployment with:

- Vercel for the React/Vite frontend.
- Render Free for the FastAPI backend.
- Neon Free for PostgreSQL.

The free backend sleeps after inactivity, so the first request can take about a minute. Render's free filesystem is temporary; files written to `backend/uploads` are lost after a restart or redeploy. Do not treat this setup as a backup or a high-traffic production plan.

## 1. Put the project on GitHub

Create a private GitHub repository, then from the project folder run:

```powershell
git init
git add .
git commit -m "Prepare TECH TOYS for deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Do not commit `.env`, database passwords, API keys, or customer data. The repository's `.gitignore` already excludes the local environment and SQLite database.

## 2. Create the free PostgreSQL database

1. Create a project at https://neon.tech.
2. Create a database named `shop`.
3. Copy the pooled or direct connection string.
4. If the string starts with `postgresql://` or `postgres://`, the backend now converts it automatically to the installed `psycopg` driver. You can also use `postgresql+psycopg://` directly.

## 3. Deploy the backend on Render

1. Open https://dashboard.render.com and choose **New > Blueprint**.
2. Connect the GitHub repository and select the branch.
3. Render will read `render.yaml` and create `tech-toys-api`.
4. When asked for secret values, enter:
   - `DATABASE_URL`: the Neon connection string.
   - `CORS_ORIGINS`: temporarily use `https://example.com`; replace it after the frontend URL is known.
   - `ADMIN_PASSWORD`: a new private password with at least 12 characters. This is used only when the empty production database receives its one-time seeded admin.
   - `SEED_TOKEN`: optional separate private token for the recovery endpoint. If omitted, the recovery endpoint accepts `ADMIN_PASSWORD` instead.
5. Keep `SEED_ON_STARTUP=true` for the first deploy. Set it to `false` only if you want to disable the empty-database seed completely.
6. Wait for the deploy, then open:
   - `https://YOUR-API.onrender.com/api/health`
   - `https://YOUR-API.onrender.com/api/ready`
7. Both endpoints must respond successfully before deploying the frontend.

The Render start command runs Alembic migrations before Uvicorn starts. With `SEED_ON_STARTUP=true`, the API starts its liveness endpoint immediately, then checks the `products` table after migrations and seeds only when it is empty. `/api/ready` returns 503 while this bounded background step is running and returns 200 when it is complete. A PostgreSQL advisory lock makes simultaneous instance starts safe; an existing catalogue is never wiped or overwritten. `DEMO_MODE=false` still prevents the old demo-only normalization path from changing existing production rows. Logs contain `seed: checking`, `seed: skipped because ...`, `seed: inserted N products`, or `seed: FAILED ...` without printing database URLs or passwords.

### Empty-database recovery

If a deployment is healthy but `/api/products` still reports `total: 0`, an admin can call the one-time recovery endpoint. It is protected by `SEED_TOKEN`, or by `ADMIN_PASSWORD` when no separate token is configured. It only inserts the catalogue when the `products` table is empty and never resets existing rows:

```powershell
curl.exe -X POST https://YOUR-API.onrender.com/api/admin/seed -H "X-Seed-Token: YOUR_PRIVATE_TOKEN"
```

Expected output is `{"status":"seeded","inserted_products":60}` on the first successful recovery and `{"status":"skipped","inserted_products":0}` afterwards.

## 4. Deploy the frontend on Vercel

1. Open https://vercel.com/new and import the same GitHub repository.
2. Framework preset: **Vite**.
3. Build command: `npm run build`.
4. Output directory: `dist`.
5. Add the environment variable `VITE_API_URL` with the Render URL, for example `https://YOUR-API.onrender.com`.
6. Deploy and copy the Vercel URL.

The existing `vercel.json` keeps React Router routes working on refresh.

## 5. Lock CORS to the real frontend URL

In Render, edit `CORS_ORIGINS` to the exact Vercel URL, without a trailing slash, for example:

```text
https://tech-toys.vercel.app
```

Save and redeploy the backend. Then test the frontend homepage, shop search, phone finder, cart, tracking, admin login, and `/api/health`.

## Product image warning

The current admin upload endpoint stores images on the backend filesystem. That is safe locally, but Render Free does not persist that filesystem. For permanent admin-uploaded images, create a Cloudinary or Cloudflare R2 account and explicitly configure a storage adapter before enabling production uploads. Until then, use the existing remote seed images/SVG illustrations and do not rely on newly uploaded files surviving a Render restart.

## Local production-like check

```powershell
Copy-Item .env.production.example .env
docker compose -f docker-compose.production.yml up -d --build
```

For a real public deployment, keep `DEMO_MODE=false`, use a long random `SECRET_KEY`, and never paste secrets into GitHub or chat.
