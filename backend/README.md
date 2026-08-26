# BeTaxed API

FastAPI service. Layout matches Talent Journey: `app/{routers,models,schemas,services,deps}`, Alembic, `/health` + `/ready`.

```bash
# from repo root
docker compose up -d postgres redis firebase-auth

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.dev.example .env
alembic upgrade head   # … DEV-832 intake; DEV-834 employment apply/diff; DEV-835 headcount
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
- `GET /v1/people` — company people (any member/staff). `X-Company-Id` required. No NISS, no recipe. Includes `status`, `status_source`, `has_source_conflict`.
- `PATCH /v1/people/{employee_id}` — Admin/HR/staff set `ACTIVE` / `ON_LEAVE` / `TERMINATED`. Emits `STATUS_OVERRIDE` plus `LEAVE_STARTED`/`LEAVE_ENDED`. Sets `status_source` to `USER` (or `ADMIN` for staff). Finance 403. Does not invent a termination legal list.
- `POST /v1/ss-batches` — company monthly SS extract (`files` + `period_year_month`). Admin/HR/staff. Parses, fail-closed on employer NISS mismatch (409), then applies and upserts `company_headcount_month` (`SS_BATCH`). Optional remunerações leave sheet/file emits `LEAVE_*` (`source = SS_DIFF`); vínculos/contratos never invent leave.
- `GET /v1/ss-batches` — period, parse status, event **counts** only (no names, rates, or pay).
- `GET /v1/headcount-months` / `PUT /v1/headcount-months` — SS_BATCH and USER rows. USER does not overwrite SS_BATCH. Admin/HR/staff on PUT.
- `POST /v1/people/{employee_id}/contracts` — PDF upload; emits `CONTRACT_UPLOADED` then stub/Gemini review (`CONTRACT_LLM`).
- `GET /v1/notifications` / `POST …/read` / `GET …/stream` — in-app feed + Redis SSE wake-up (KB/08).
- `GET /v1/ops/contract-flags` — staff-only SS vs paper mismatches.
- `GET /v1/ops/benefit-cases` — staff-only internal cases (state, remaining months, monthly saving). Never on company APIs.
- `GET /v1/invoices` — Admin/Finance/staff. Totals and generic lines. No employee recipe. No `certified_external_id`.
- `POST /v1/invoices/{id}/proforma` / `legal-pdf` — Admin/Finance/staff attach PROFORMA and certified fatura PDF (`INVOICE_PDF`). Stores `legal_invoice_number` / `atcud`. Staff may set `certified_external_id`. No vendor API (choice still open).
- `POST /v1/ops/companies/{id}/invoicing` — staff set `CERTIFIED_SOFTWARE` or `STRIPE_SEPA` plus optional `certified_vendor_name`.
- `POST /v1/ops/companies/{id}/invoices` — staff draft from unlocked billable `saving_month` rows.
- `POST /v1/ops/invoices/{id}/issue` / `resolve` / `void` — status ledger. Manual resolve stores actor + reason.
- `GET /v1/billing` — Admin/Finance/staff. `invoicing_method` and `has_stripe_customer`. No Stripe ids.
- `POST /v1/invoices/sepa-checkout` — Admin/Finance/staff. Stripe Checkout setup mode for a SEPA mandate.
- `POST /v1/invoices/{id}/sepa-collect` / `POST /v1/ops/invoices/{id}/collect` — create a Stripe Invoice for collection.
- `POST /v1/webhooks/stripe` — HMAC (`Stripe-Signature`). `invoice.paid` → PAID; `invoice.payment_failed` → LATE (never silent PAID). Unknown Stripe ids return 200 ignored.
- `GET/POST /v1/ops/companies/{id}/commercial-terms` — staff fee % override. Convert seeds from `DEFAULT_FEE_PERCENT`.
- `POST /v1/ops/companies/{id}/applications` — snapshot headcount trailing-12, SS/AT cert caches, mark DETECTED cases SUBMITTED.
- `GET/POST /v1/certificates` — SS/AT no-debt PDFs. Admin/Finance/staff. HR 403.
- `POST /v1/ops/employment-documents/{id}/apply` — staff copies paper fields onto employment (`source = CONTRACT`).
- `GET /v1/me` — Firebase Bearer token; upserts `user_base` (`COMPANY_STAFF` on first login; `BETAXED_STAFF` is a DB promotion)
- `GET /v1/me/company` — requires `X-Company-Id` (never inferred). Staff: any company, no membership. Company users: active member.
- `GET /v1/me/intake` — requires `X-Intake-Id`. Owner, staff, or matching `X-Intake-Session` (upload-first, OD-1). Unbound intake without a session is staff-only.
- `POST /v1/intakes` — open a pass 1 intake. Bearer binds `user_id` (account-first). No auth mints `session_token` once (upload-first).
- `POST /v1/intakes/{id}/uploads` — multipart SS extract (`files` + `period_year_month`; xlsx or csv). Parses then **applies** to `employee` / `employment` / pay / events when parse succeeds, then persists the four teaser figures (OD-2).
- `GET /v1/intakes/{id}` — status, four teaser figures (now vs potential × monthly vs window), parse summary. No names, rates, or remaining months unless `ENV=DEV` and `VERBOSE=TRUE`, which adds `verbose_people`.
- `POST /v1/intakes/{id}/convert` — Firebase required. Creates `company` + `ADMIN` membership; re-keys PII and leftover JSONB NISS (`niss_enc` + tenant HMAC) to company scope.
- `POST /v1/intakes/{id}/decline` — wipe files + raw + hashes; intake tombstone `PURGED` with no PII.
- Tests: `PYTHONPATH=. pytest`

DEV verifies tokens against the Auth emulator (`FIREBASE_AUTH_EMULATOR_HOST`). Tests mock the verifier. Staging/prod: unset the emulator host, set a real `FIREBASE_PROJECT_ID`, and use Application Default Credentials.
