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

Then use **Connection string** → **URI** on the same page: it will show `postgresql://postgres.[ref]:[YOUR-PASSWORD]@...` or `postgresql://postgres:[YOUR-PASSWORD]@db.<ref>.supabase.co:5432/postgres` — paste your real password in place of the placeholder. If the password contains `@`, `#`, `/`, or `%`, [URL-encode](https://developer.mozilla.org/en-US/docs/Glossary/Percent-encoding) those characters in the URI or use a password without them.

**Correct database name in the path is `postgres` (full word),** not `postgre`:

`postgresql://postgres:YOUR_DB_PASSWORD@db.alknctbyuwwhgejvjyvw.supabase.co:5432/postgres`

### Finish the connection URI

1. On the same **Database** settings page, under **Connection string**, choose **URI** and **Direct connection** (or **Session** mode if offered). Copy the string that starts with **`postgresql://`** or **`postgres://`**, and substitute your real database password for the placeholder.
2. **Render (long‑running Uvicorn):** port **5432** / host `db.<project-ref>.supabase.co` is appropriate for an always-on service. For **serverless** or many short-lived workers, prefer **pooling** on port **6543** (Transaction mode).
3. If the URI has no `sslmode`, append **`?sslmode=require`** (the app also forces TLS for `*.supabase.co` when `sslmode` is missing).

Paste that full URI into Render → **Environment** → `DATABASE_URL` (and into local `backend/.env` if you use Postgres locally).

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
| **Pre-Deploy Command** | *(leave empty)* — migrations already run in the start command below |
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

1. **GitHub is behind your laptop** — `backend/requirements.txt` on `main` must include `alembic` and `psycopg2-binary`. Commit and push, then redeploy.
2. **Wrong Root Directory** — Build must run from `backend` so it reads `backend/requirements.txt` (the file that lists Alembic). If the root `requirements.txt` is a stub (`-r backend/requirements.txt`), either use **Root Directory** `backend` or install from the repo root with `pip install -r backend/requirements.txt`.

Use **`python -m alembic upgrade head`** instead of **`alembic upgrade head`** in the start command (avoids rare `PATH` issues). Adding `&& python -c "import alembic, psycopg2"` to the **build command** makes the build fail early if those packages are missing.

### Supabase CLI (`supabase link`, `migration new`, `db push`) vs this repo

This backend’s schema is managed with **Alembic** (`backend/alembic/`). There is **no** `supabase/migrations` folder in the repo yet.

| Approach | Use when |
|----------|----------|
| **Alembic only** (recommended for this app) | You deploy FastAPI on Render. Run `alembic upgrade head` on deploy. Set `DATABASE_URL` to the Supabase Postgres URI. You do **not** need `supabase db push` for the Python app’s tables. |
| **Supabase CLI migrations** | You maintain SQL migrations under `supabase/migrations/` and apply with `supabase db push`. That is a **second** migration track. Avoid running **both** Alembic and Supabase migrations against the same tables unless you carefully avoid duplicate DDL. |

**Vercel integrated with Supabase** usually supplies env vars to **frontend** (e.g. anon key, URL). The **FastAPI** service on Render still needs **`DATABASE_URL`** (the `postgresql://…` URI) set separately in Render — it does not use the Supabase REST URL for SQLAlchemy.

**CLI tip:** `supabase link --project-ref alknctbyuwwhgejvjyvw` ties your local Supabase CLI to this project; use it if you add Edge Functions, RLS policies as SQL, or storage — not required for Render + Alembic alone.

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

- `GET /health-check` — `dependencies.database` should be `true` after Postgres is correct.
- Place a test call after removing `SKIP_TWILIO_SIGNATURE`.
