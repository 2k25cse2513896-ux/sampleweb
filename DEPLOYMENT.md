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
5. Wait for the deploy, then open:
   - `https://YOUR-API.onrender.com/api/health`
   - `https://YOUR-API.onrender.com/api/ready`
6. Both endpoints must respond successfully before deploying the frontend.

The Render start command runs Alembic migrations before Uvicorn starts. `DEMO_MODE=false` prevents demo users and demo data from being created in production.

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
