# Database migrations

```bash
cd backend
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"  # or rely on .env
alembic upgrade head
```

Local SQLite (default in `.env.example`): tables are also created via `init_db()` on startup. For production, use PostgreSQL and run `alembic upgrade head` before or as part of deploy.
