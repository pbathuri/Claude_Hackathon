# Production deployment (Render + Supabase + Twilio)

## 1. Supabase: correct `DATABASE_URL`

The value **`https://xxxx.supabase.co`** (for example `https://alknctbyuwwhgejvjyvw.supabase.co`) is the **REST API** base URL. It is **not** `DATABASE_URL`. The **project ref** (`alknctbyuwwhgejvjyvw`) is the same value you see in that hostname; it is not the database password.

### Where is the database password?

Supabase **does not show** your existing Postgres password again after creation (for security).

1. Open [Supabase Dashboard](https://supabase.com/dashboard) and select your project.
2. Click the **gear icon** → **Project Settings** (or **Settings** in the sidebar).
3. Open **Database**.
4. Scroll to **Database password** (sometimes under **Connection info**).
5. If you never saved the password from when the project was created, click **Reset database password**, choose a strong password, and **save it somewhere safe** (password manager). Updating the password applies immediately to Postgres; put the **new** value in `DATABASE_URL` everywhere (Render, local `.env`).

Then use **Connection string** → **URI** on the same page: it will show `postgresql://postgres.[ref]:[YOUR-PASSWORD]@...` or `postgresql://postgres:[YOUR-PASSWORD]@db.<ref>.supabase.co:5432/postgres` - paste your real password in place of the placeholder. If the password contains `@`, `#`, `/`, or `%`, [URL-encode](https://developer.mozilla.org/en-US/docs/Glossary/Percent-encoding) those characters in the URI or use a password without them.

**Correct database name in the path is `postgres` (full word),** not `postgre`.

### Use the **pooler** URI (not the direct connection)

The **direct** connection host (`db.<ref>.supabase.co`, port 5432) resolves to **IPv6 only**. Render's free tier does **not** have IPv6 connectivity, so you'll see:

> `connection to server at "db.alknctbyuwwhgejvjyvw.supabase.co" (2600:…) … failed: Network is unreachable`

**Fix:** use the Supabase **connection pooler** (Supavisor) instead. It resolves to **IPv4**.

1. Supabase Dashboard → **Settings** → **Database** → **Connection string** → **URI**.
2. Switch the mode dropdown from **Direct connection** to **Transaction** (recommended) or **Session**.
3. The URI changes to something like:

   `postgresql://postgres.alknctbyuwwhgejvjyvw:[YOUR-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres`

   Note the differences from direct:
   - **User** is `postgres.alknctbyuwwhgejvjyvw` (dot-separated, not colon-separated ref)
   - **Host** is `aws-0-<region>.pooler.supabase.com` (not `db.<ref>.supabase.co`)
   - **Port** is `6543` (not `5432`)

4. If the URI has no `sslmode`, append **`?sslmode=require`** (the app also forces TLS for `*.supabase.co` when `sslmode` is missing). The pooler hostname contains `supabase.com`, so also add this check - or just always append the param.

Paste that full pooler URI into Render → **Environment** → `DATABASE_URL` (and into local `backend/.env` if you use Postgres locally).

If `DATABASE_URL` is an `https://` URL, the app will **fail at startup** with a clear error in logs.

## 2. Render: build, migrations, start

### If you see `cd: ... pip install -r requirements.txt: No such file or directory`

**Root Directory** must be a **folder path** inside the repo (e.g. `backend`). It is **not** the build command. If you paste `pip install -r requirements.txt` there, Render tries to `cd` into a directory with that impossible name and fails.

**Clear these fields of junk** (remove stray `pip install.../ $` lines). Use **one** build line and **one** start line only.

### Recommended: Root Directory = `backend`

In the Render dashboard → your Web Service → **Settings**:

| Field | Value |
|--------|--------|
| **Root Directory** | `backend` |
| **Build Command** | `pip install -r requirements.txt && python -c "import alembic, psycopg2"` |
| **Pre-Deploy Command** | *(leave empty)* - migrations already run in the start command below |
| **Start Command** | `python -m alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT` |

Because the working directory is already `backend`, do **not** prefix with `cd backend &&`.

### Alternative: Root Directory empty (repo root)

| Field | Value |
|--------|--------|
| **Root Directory** | *(empty)* |
| **Build Command** | `pip install -r backend/requirements.txt` |
| **Start Command** | `cd backend && python -m alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT` |

Optional: set **Pre-Deploy Command** to `cd backend && python -m alembic upgrade head` and use `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` as start (no duplicate `alembic` in both unless you intend it).

### If you see `alembic: command not found`

That means **Alembic was not installed** in the build environment. Common causes:

1. **GitHub is behind your laptop** - `backend/requirements.txt` on `main` must include `alembic` and `psycopg2-binary`. Commit and push, then redeploy.
2. **Wrong Root Directory** - Build must run from `backend` so it reads `backend/requirements.txt` (the file that lists Alembic). If the root `requirements.txt` is a stub (`-r backend/requirements.txt`), either use **Root Directory** `backend` or install from the repo root with `pip install -r backend/requirements.txt`.

Use **`python -m alembic upgrade head`** instead of **`alembic upgrade head`** in the start command (avoids rare `PATH` issues). Adding `&& python -c "import alembic, psycopg2"` to the **build command** makes the build fail early if those packages are missing.

### Supabase CLI (`supabase link`, `migration new`, `db push`) vs this repo

This backend’s schema is managed with **Alembic** (`backend/alembic/`). There is **no** `supabase/migrations` folder in the repo yet.

| Approach | Use when |
|----------|----------|
| **Alembic only** (recommended for this app) | You deploy FastAPI on Render. Run `alembic upgrade head` on deploy. Set `DATABASE_URL` to the Supabase Postgres URI. You do **not** need `supabase db push` for the Python app’s tables. |
| **Supabase CLI migrations** | You maintain SQL migrations under `supabase/migrations/` and apply with `supabase db push`. That is a **second** migration track. Avoid running **both** Alembic and Supabase migrations against the same tables unless you carefully avoid duplicate DDL. |

**Vercel integrated with Supabase** usually supplies env vars to **frontend** (e.g. anon key, URL). The **FastAPI** service on Render still needs **`DATABASE_URL`** (the `postgresql://…` URI) set separately in Render - it does not use the Supabase REST URL for SQLAlchemy.

**CLI tip:** `supabase link --project-ref alknctbyuwwhgejvjyvw` ties your local Supabase CLI to this project; use it if you add Edge Functions, RLS policies as SQL, or storage - not required for Render + Alembic alone.

## 3. Twilio webhooks

- Voice webhook: `POST` `https://<your-service>.onrender.com/twilio/voice`
- **`PUBLIC_BASE_URL`**: `https://<your-service>.onrender.com` (scheme + host; no path). A host-only value like `hackathon-u86l.onrender.com` is auto-prefixed with `https://` for signature checks.
- **`SKIP_TWILIO_SIGNATURE=1`**: only for short debugging; remove for production.
- **`TWILIO_AUTH_TOKEN`**: required for signature validation (Auth Token from Twilio Console, not the API Key SID).

## 4. Environment variables (checklist)

| Variable | Notes |
|----------|--------|
| `DATABASE_URL` | Postgres URI only (`postgresql://...`) |
| `REDIS_URL` | Sessions / STT (Upstash or Render Redis) |
| `PUBLIC_BASE_URL` | Render service URL origin |
| `SKIP_TWILIO_SIGNATURE` | `0` or unset in production |
| `DEMO_MODE` | `0` when enforcing real auth |
| `SKIP_PIPELINE_ENRICHMENT` | `1` to skip heavy KG enrichment on boot (optional) |
| `SKIP_PIPELINE` | Legacy alias for `SKIP_PIPELINE_ENRICHMENT` |

## 5. Verify

- `GET /health-check` - `dependencies.database` should be `true` after Postgres is correct.
- Place a test call after removing `SKIP_TWILIO_SIGNATURE`.

## 6. Doctor portal on Render (Next.js)

The API already allows `http://localhost:3000` and common origins. For a **portal Web Service on Render**:

1. In [Render Dashboard](https://dashboard.render.com) choose **New** → **Blueprint**.
2. Connect the same GitHub repo and set the blueprint file path to **`doctor-portal/render.yaml`** (not the repo root).
3. Apply the blueprint; Render creates **`who-doctor-portal`** (Node): `npm install && npm run build`, then `next start` on `$PORT`.
4. When the deploy finishes, copy the portal URL (e.g. `https://who-doctor-portal.onrender.com`).
5. On the **backend** Web Service → **Environment**, add:
   - **`CORS_EXTRA_ORIGINS`** = that URL (no trailing slash). Use commas for multiple origins.
6. Redeploy the backend (or wait for auto-deploy) so CORS picks up the new variable.
7. Optional: change **`NEXT_PUBLIC_API_URL`** on the portal service if the API is not `https://claude-hackathon-u86l.onrender.com` - then trigger a **new deploy** of the portal so the client bundle is rebuilt with the correct API base URL.
