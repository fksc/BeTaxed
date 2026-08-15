# BeTaxed API

FastAPI service. Layout matches Talent Journey: `app/{routers,models,schemas,services,deps}`, Alembic, `/health` + `/ready`.

```bash
# from repo root
docker compose up -d postgres redis

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.dev.example .env
alembic upgrade head   # no revisions yet
uvicorn app.main:app --reload --port 8080
```

- `GET /health` — process liveness (no DB)
- `GET /ready` — PostgreSQL `SELECT 1`
- Tests: `PYTHONPATH=. pytest`
