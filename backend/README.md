# BeTaxed API

FastAPI service. Layout matches Talent Journey: `app/{routers,models,schemas,services,deps}`, Alembic, `/health` + `/ready`.

```bash
# from repo root
docker compose up -d postgres redis firebase-auth

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.dev.example .env
alembic upgrade head   # … DEV-832 intake; DEV-834 employment apply/diff
uvicorn app.main:app --reload --port 8080
```

Mint a Bearer token against the Auth emulator (UI at http://127.0.0.1:4000):

```bash
# from repo root
./scripts/mint-firebase-emulator-token.sh hr@acme.example password
# then: curl -H "Authorization: Bearer <idToken>" http://localhost:8080/v1/me
```

- `GET /health` — process liveness (no DB)
- `GET /ready` — PostgreSQL `SELECT 1`; Redis ping when `REDIS_URL` is set
- `GET /v1/people` — company people (Admin/HR/staff). `X-Company-Id` required. No NISS, no recipe.
- `POST /v1/people/{employee_id}/contracts` — PDF upload; emits `CONTRACT_UPLOADED` then stub/Gemini review (`CONTRACT_LLM`).
- `GET /v1/notifications` / `POST …/read` / `GET …/stream` — in-app feed + Redis SSE wake-up (KB/08).
- `GET /v1/ops/contract-flags` — staff-only SS vs paper mismatches.
- `POST /v1/ops/employment-documents/{id}/apply` — staff copies paper fields onto employment (`source = CONTRACT`).
- `GET /v1/me` — Firebase Bearer token; upserts `user_base` (`COMPANY_STAFF` on first login; `BETAXED_STAFF` is a DB promotion)
- `GET /v1/me/company` — requires `X-Company-Id` (never inferred). Staff: any company, no membership. Company users: active member.
- `GET /v1/me/intake` — requires `X-Intake-Id`. Owner, staff, or matching `X-Intake-Session` (upload-first, OD-1). Unbound intake without a session is staff-only.
- `POST /v1/intakes` — open a pass 1 intake. Bearer binds `user_id` (account-first). No auth mints `session_token` once (upload-first).
- `POST /v1/intakes/{id}/uploads` — multipart SS extract (`files` + `period_year_month`; xlsx or csv). Parses then **applies** to `employee` / `employment` / pay / events when parse succeeds, then persists the four teaser figures (OD-2).
- `GET /v1/intakes/{id}` — status, four teaser figures (now vs potential × monthly vs window), parse summary. No names, rates, or remaining months unless `ENV=DEV` and `VERBOSE=TRUE`, which adds `verbose_people`.
- `POST /v1/intakes/{id}/convert` — Firebase required. Creates `company` + `ADMIN` membership; re-keys PII to company scope.
- `POST /v1/intakes/{id}/decline` — wipe files + raw + hashes; intake tombstone `PURGED` with no PII.
- Tests: `PYTHONPATH=. pytest`

DEV verifies tokens against the Auth emulator (`FIREBASE_AUTH_EMULATOR_HOST`). Tests mock the verifier. Staging/prod: unset the emulator host, set a real `FIREBASE_PROJECT_ID`, and use Application Default Credentials.
