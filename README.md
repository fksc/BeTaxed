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
| **PostgreSQL** | 18.x | Host port **5434** (Talent Journey uses 5432; tests use 5433) |
| **Redis** | 8.x | Host port **6381** (container 6379; Talent Journey uses 6380) |

## Local development

From the **repository root**:

```bash
docker compose up -d postgres redis firebase-auth
```

To wipe local Postgres + Auth emulator volumes, migrate, and seed BeTaxed ops staff (`ops@betaxed.local` / `betaxed-dev`):

```bash
./scripts/reset-local-dev.sh
```

Then sign in at `/en/login` and open `/en/admins`. Re-seed without wiping: `cd backend && PYTHONPATH=. python scripts/seed_betaxed_staff.py`. Override `SEED_STAFF_EMAIL` / `SEED_STAFF_PASSWORD`. Seed refuses unless `ENV=DEV` and the Auth emulator host is set.

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
- `/` — pass 1 teaser (upload SS, four figures, continue or decline)

Firebase Auth is the **emulator** in local/DEV (`FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`, UI at http://127.0.0.1:4000). Users are stored in the `betaxed_firebase_auth_data` volume (`--export-on-exit`); `docker compose down -v` wipes them. Cloud agents can run the same Compose stack. Unset the emulator host only for staging/prod.

Do not commit `.KB/Samples/` (PII) or `.env` files. Git: `main` production, `dev` integration — `.KB/GIT_STRATEGY.md`.
