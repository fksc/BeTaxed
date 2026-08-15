# BeTaxed

Application repository for the Linear project **BeTaxed**. Spec: [`.KB/00_mother_doc.md`](.KB/00_mother_doc.md).

## Repository layout

| Path | Purpose |
|------|---------|
| `.KB/` | Product and technical knowledge base (source of truth) |
| `backend/` | FastAPI API (`uvicorn`, port 8080) |
| `frontend/` | Next.js App Router UI (`next start` / standalone in Docker) |
| `infra/` | Cloud Run–style service manifests and ops notes |
| `docs/` | Setup notes (to grow) |
| `scripts/` | Local / CI helper scripts (to grow) |

## Pinned stack

| Layer | Version | Notes |
|-------|---------|--------|
| **Python** | 3.13 | Backend Docker image: `python:3.13-slim` |
| **FastAPI** | 0.136.1 | Pinned in `backend/requirements.txt` |
| **Uvicorn** | 0.46.0 | `[standard]` extras |
| **SQLAlchemy** | 2.0.41 | Async + Alembic |
| **Node.js** | 24.x (Active LTS) | Frontend `engines` + Docker: `node:24-alpine` |
| **Next.js** | 16.3.x | App Router; `output: "standalone"` for Cloud Run |
| **React** | 19.2.x | As resolved with Next 16 |
| **PostgreSQL** | 18.x | Root `docker-compose.yml` / Cloud SQL later |
| **Redis** | 8.x | Host port **6380** (container 6379) |

## Local development

From the **repository root**:

```bash
docker compose up -d postgres redis
```

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.dev.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

- `GET /health` — process liveness (no DB)
- `GET /ready` — PostgreSQL connectivity

```bash
cd frontend
nvm use 24
npm install
npm run dev
```

- `GET /api/health` — frontend liveness

Do not commit `.KB/Samples/` (PII) or `.env` files. Git: `main` production, `dev` integration — `.KB/GIT_STRATEGY.md`.
