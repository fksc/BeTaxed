# KB/00_mother_doc.md — Mother Document
**This document is always loaded alongside any KB child doc.**
**It provides global context, rules, and the index of all child docs.**
**It never goes deep — details live in child docs.**

---

## What This Platform Is

BeTaxed is a **B2B Social Security savings product** for Portuguese companies. The company gives us the extract they can generate from their Segurança Social account. We find **unrealized hiring-benefit savings** and, if they become a client, we run the application and bill a **success fee** on realized savings.

**Product line (now):** employer TSU reduction for hiring young people on a first permanent contract. Other saving types may be added later on the same company / employee / declaration spine.

**Not a DIY tax calculator.** The in-app teaser must not teach the recipe (rates, named eligible people, remaining months, “convert this contract”). If we show how, they file themselves and the success fee is pointless. The client deck in `.KB/Samples/` is for **controlled** sales conversations, not the self-serve result screen.

---

## Actors (Summary)

| Actor | Role |
|---|---|
| BeTaxed Admin / Ops | Platform staff. Full access with explicit `company_id` (or intake) in the request. Never “belongs” to a client company. |
| Company Admin | Workspace owner. Billing, members, continue/decline intake. |
| Company HR | Employees, contracts, status overrides, monthly SS uploads. |
| Company Finance | Invoices, payments, invoicing method. |

There is no talent/employee login in v1. Employees are **data**, not actors.

---

## Core Domain Objects (Summary)

| Object | Description |
|---|---|
| UserBase | Every human actor. Maps Firebase UID to internal UUID. |
| Intake | Two-pass pre-workspace: SS upload + teaser. Convert → company, or decline → **purge**. |
| Company | Client tenant / workspace. Created only when they continue. |
| CompanyMembership | User ↔ company with role. |
| Employee | Person in a tenant. Internal UUID; NISS is encrypted + HMAC, never the PK. |
| Employment | One vínculo. Rehire = new row, same employee. |
| CompensationPeriod | Salary / rendimento period on an employment. |
| EmploymentEvent | Hire, fire, leave, raise, conversion, rate change, user override. |
| SsBatch | One SS declaration upload (one xlsx or two files). |
| StoredFile | GCS object (SS export, contract, certificate, proforma). |
| IncentiveRegime | Versioned legal/commercial parameters (internal). |
| BenefitCase | Per-employee 5-year file for a regime (**internal**). |
| SavingMonth | Per employee per month saving + fee (**internal**, billing fuel). |
| Invoice / Payment | What the company sees and pays. |

→ Tables: `KB/01`–`KB/06`. Encryption: `KB/07`. Flow: `KB/10`. Regime: `KB/20`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.136.1 (Python 3.13) |
| Auth | Firebase Auth |
| Frontend | Next.js 16 App Router + shadcn/ui (Node 24) |
| Database | PostgreSQL 18 (local compose / Cloud SQL) |
| Cache | Redis 8 (local compose, host 6380) |
| File storage | GCS (paths in DB, never blobs; signed URLs on demand) |
| Deployment | Google Cloud Run (backend + frontend, independent) |
| Payments | Stripe (SEPA Direct Debit intended); certified PT invoicing software as alternate path |
| i18n | UI strings in the app; `preferred_language` / `company.locale` (`pt`, `en`, …) |

Same shape as other DEV repos: GCP, Cloud Run, Firebase, Postgres, FastAPI, Next.js.

---

## Repository Structure

```
BeTaxed/                    ← monorepo
  .KB/                      ← knowledge base (this folder)
  backend/                  ← FastAPI (`app/`, Alembic)
  frontend/                 ← Next.js + shadcn (`app/`, `components/`, `lib/`)
  infra/                    ← Cloud Run placeholders
  docs/                     ← setup notes
  scripts/                  ← local / CI helpers
  docker-compose.yml        ← local Postgres 18 + Redis 8
```

---

## Global Rules (Apply Everywhere — No Exceptions)

**1. Context-based permissions.**
Every company-scoped write carries explicit `company_id`. BeTaxed staff do not inherit a home company. Intake-scoped writes carry `intake_id` until conversion.

**2. Tenant isolation.**
No query without `company_id` (or `intake_id` pre-convert). HMAC of NISS is per-tenant unique.

**3. No JSON blobs for queryable data.**
Filterable / billable / event fields are typed columns. JSONB only for parser leftovers, Stripe webhook payloads, and certified-software payloads.

**4. Soft deletes for workspace data; hard purge for declined intake.**
Company/employee records: `deleted_at` / `is_active`. Declined pass-1 intake: **hard delete** files + parsed rows + teaser run (`KB/10_product_flow.md#wipe-on-decline`).

**5. Recipe stays internal.**
`benefit_case`, `saving_month`, regime parameters, and per-employee eligibility are **not** on company-facing APIs. Invoices show fee totals, not how savings were computed.

**6. NISS is never the primary key.**
Internal UUID everywhere. Join uploads with `niss_hash`.

**7. Files live in GCS.**
DB stores object refs only.

**8. Side effects via domain events.**
SS diffs emit `employment_event` rows (and a domain event) in the same transaction as canonical updates. Billing status changes append `invoice_status_event`.

**9. Preserve ledgers.**
Invoiced `saving_month` rows are locked. Corrections are new months or credit notes, not silent rewrites.

**10. HRMS-ready spine.**
Employee / employment / compensation / events have `source` (`SS` \| `USER` \| `HRMS` \| `CONTRACT` \| `ADMIN`). Do not design vendor-specific HRMS tables now.

---

## Open Decisions

Leave these open until explicitly locked. Do not implement a silent default in product copy as if it were decided.

| ID | Topic | Options | Notes |
|---|---|---|---|
| OD-1 | **When identity happens** | (A) Account (even thin) → upload → teaser → continue or wipe. (B) Upload → teaser → account or wipe. | Prefer (A) for GDPR/ToS; (B) converts more. Schema supports both (`intake.user_id` nullable). |
| OD-2 | Teaser payload | One aggregate number vs vaguer “opportunity found” | Lean one number, no breakdown. |
| OD-3 | Salary at rest | NUMERIC in CMEK Cloud SQL vs app-level encrypt | Lean NUMERIC so invoicing can `SUM`. Identifiers still app-encrypted. |
| OD-4 | Regime edge cases | Age at **sem termo** vs first hire; leave vs billable; fee %; certified vendor | Working assumptions in `KB/20`; hammer later. |

---

## KB Document Index

| Doc | Contents |
|---|---|
| `KB/00_mother_doc.md` | This file. |
| `KB/10_product_flow.md` | Two-pass intake, teaser vs workspace. |
| `KB/20_regime_ss_hiring_benefit.md` | SS hiring benefit rules (current product line). |
| `KB/01_schema_core.md` | Users, company, membership, intake. |
| `KB/02_schema_employment.md` | People, jobs, pay, events. |
| `KB/03_schema_ss_ingest.md` | Declarations, raw sheets, diffs, headcount. |
| `KB/04_schema_documents.md` | Files and contracts. |
| `KB/05_schema_benefit.md` | Internal eligibility and savings ledger. |
| `KB/06_schema_billing.md` | Invoices and payments. |
| `KB/07_security_encryption.md` | Encryption and isolation. |
| `KB/40_permissions.md` | Permission matrix. |
| `KB/GIT_STRATEGY.md` | `main` / `dev`, Linear `DEV-`. |
| `KB/kb_document_plan.md` | Doc plan. |
| `.KB/Samples/` | Local PII samples — not in git. |
