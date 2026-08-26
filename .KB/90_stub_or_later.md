# KB/90_stub_or_later.md — Parked slices and stubs
**Depends on:** `KB/00_mother_doc.md`
**How to use:** Append-only. Never delete an entry. Before starting a Linear issue, skim **open** rows. If this issue should close one, mark it resolved in place.

This is **not** a second backlog. Linear still owns tickets. This file records work we **cut from a change**, **left incomplete in code**, or **must not silently invent** on a later ticket.

---

## Entry format

Copy this block to the **bottom** of the file when parking something:

```markdown
### SL-NNN — short title
- **Opened:** YYYY-MM-DD
- **Status:** open
- **Resolved-date:** —
- **Related:** DEV-###, `KB/…`, code path
- **Context:** What exists today, what is missing, why a later reader would be confused.
- **Why later:** Which ticket or constraint parked it (do not invent a product default).
- **Pickup:** Concrete next step when someone takes it.
```

When done: set **Status** to `resolved`, set **Resolved-date** (ISO date), add **Resolution:** what shipped (PR/commit/ticket). Do not remove the original context.

---

## Index (open first)

| ID | Opened | Status | Resolved-date | Title |
|---|---|---|---|---|
| SL-001 | 2026-08-20 | open | — | Convert drops leftover JSONB `niss_hash` instead of re-HMAC |
| SL-002 | 2026-08-20 | resolved | 2026-08-26 | Company monthly SS upload API (workspace loop) |
| SL-003 | 2026-08-20 | resolved | 2026-08-26 | `company_headcount_month` write path |
| SL-004 | 2026-08-20 | open | — | Leave events from monthly remunerations files |
| SL-005 | 2026-08-20 | resolved | 2026-08-26 | Public employee status override (`PATCH`) |
| SL-006 | 2026-08-20 | open | — | Termination initiator/reason legal list |
| SL-007 | 2026-08-20 | resolved | 2026-08-21 | Pass 1 teaser figures stay null (engine) |
| SL-008 | 2026-08-21 | resolved | 2026-08-25 | Contract PDF vs SS row (override after teaser) |
| SL-009 | 2026-08-21 | resolved | 2026-08-25 | Gate (companies)/(admins) with Firebase + staff check |
| SL-010 | 2026-08-25 | open | — | Cloud Tasks for fanout + contract LLM review |

---

### SL-001 — Convert drops leftover JSONB `niss_hash` instead of re-HMAC
- **Opened:** 2026-08-20
- **Status:** open
- **Resolved-date:** —
- **Related:** DEV-832, DEV-848, `KB/07_security_encryption.md`, `app/services/intake.py` (`_drop_leftover_niss_hashes`), `app/services/ss_ingest.py` (`_leftover_for_storage`)
- **Context:** SS leftover columns that look like NISS are stored as `{ "niss_hash": ["…hex"] }` scoped to the **intake** HMAC key. On convert, HMAC tenant-scope becomes the **company** id, so those hashes would no longer match. Convert currently **deletes** leftover keys that contain `niss_hash` rather than re-hashing. Substitute-NISS extras on contratos are the usual case. Canonical `niss_enc` / `niss_hash` on raw rows **are** re-keyed.
- **Why later:** Leftover hashes have no plaintext in the DB. Re-HMAC would need decrypt-from-elsewhere or keeping leftover as opaque non-join data. 832 chose drop over a fake re-hash.
- **Pickup:** Either persist leftover NISS inside envelope encryption at ingest, or document leftover as non-join metadata and stop putting hashes there. Do not HMAC leftover with the wrong tenant-scope.

---

### SL-002 — Company monthly SS upload API (workspace loop)
- **Opened:** 2026-08-20
- **Status:** resolved
- **Resolved-date:** 2026-08-26
- **Related:** DEV-832, DEV-835, `KB/10_product_flow.md#after-the-workspace-exists`, `KB/03_schema_ss_ingest.md`, `POST /v1/intakes/{id}/uploads`
- **Context:** Pass 1 can upload SS files onto an **intake**. After convert, the product loop is monthly uploads onto a **company** (`X-Company-Id`, member Admin/HR or staff). There is no `POST /v1/companies/{id}/…` (or equivalent) SS upload yet. Ingest already accepts `company_id` XOR `intake_id` in the service; only the HTTP route is intake-scoped.
- **Why later:** 832 was two-pass intake (create / upload / convert / purge), not the workspace monthly loop. Apply/diff (DEV-834) can be a service without this route.
- **Pickup:** Add a company-scoped multipart upload that calls `ingest_ss_export(..., company_id=...)`, then `apply_ss_batch` once 834 exists. Fail closed if `employer_niss_hash` does not match `company.employer_niss_hash`.
- **Resolution:** DEV-835 `POST /v1/ss-batches` (`X-Company-Id`, Admin/HR/staff) ingest+apply; NISS mismatch is 409 FAILED not APPLIED. `GET /v1/ss-batches` returns event counts only. Workspace Declarations page.

---

### SL-003 — `company_headcount_month` write path
- **Opened:** 2026-08-20
- **Status:** resolved
- **Resolved-date:** 2026-08-26
- **Related:** DEV-834 (parked), DEV-835, DEV-838, `KB/03_schema_ss_ingest.md#table-company_headcount_month`, `KB/05_schema_benefit.md`, `KB/20_regime_ss_hiring_benefit.md` (application headcount test)
- **Context:** KB defines `company_headcount_month` (SS_BATCH or USER source, unique per company/month/source) for the “this month > average of previous 12” application gate. DEV-834’s table list is workplace / employee / employment / compensation_period / employment_event — **not** headcount. Until 12 months of batches exist, `source = USER` is allowed.
- **Why later:** Headcount is an application-time gate (benefit submit), not required to apply a declaration into employment rows.
- **Pickup:** Migration + write on apply (count active vínculos) and/or USER entry. Engine compares at `company_application` submit (DEV-838). Do not invent a headcount number in teaser.
- **Resolution:** DEV-835 table + SS_BATCH upsert on company-scoped apply and after convert. `PUT /v1/headcount-months` writes USER without clobbering SS_BATCH. Trailing-12 compare stays DEV-838.

---

### SL-004 — Leave events from monthly remunerations files
- **Opened:** 2026-08-20
- **Status:** open
- **Resolved-date:** —
- **Related:** DEV-834 (parked), DEV-849, DEV-837, DEV-838, `KB/03_schema_ss_ingest.md#apply-and-diff`, `KB/02_schema_employment.md` (`LEAVE_STARTED` / `LEAVE_ENDED`), OD-4 leave not billable
- **Context:** Sample SS extract (vínculos + contratos) does not carry parental/sickness leave. Event types exist in the KB enum. Until a monthly remunerations/DR raw table exists, leave is `USER` (or future file) as `source`. Apply/diff v1 must not fake `LEAVE_*` from the current xlsx.
- **Why later:** No source columns in the current parser. Billing must still treat leave months as not billable once we know them (OD-4) — that is ledger work, not this stub’s parser.
- **Pickup:** New raw table + parser when the file exists; emit `LEAVE_*` with `source = SS_DIFF`. Until then, a status override API (SL-005) is how `ON_LEAVE` gets onto `employee.status`.

---

### SL-005 — Public employee status override (`PATCH`)
- **Opened:** 2026-08-20
- **Status:** resolved
- **Resolved-date:** 2026-08-26
- **Related:** DEV-834 (parked), DEV-837, `KB/10_product_flow.md`, `KB/40_permissions.md` (Admin/HR override status), `employment_event` `STATUS_OVERRIDE` / `SOURCE_CONFLICT`
- **Context:** Company users may set `ACTIVE` / `ON_LEAVE` / `TERMINATED` until HRMS exists. If a later SS apply disagrees, emit `SOURCE_CONFLICT` and **do not** auto-overwrite `status` when `status_source` is `USER`/`ADMIN`. 834 should implement that apply rule; it does not need the HTTP override in the same PR.
- **Why later:** Apply/diff can be tested by writing `status_source` in the DB. Permissions matrix wants the company API separately.
- **Pickup:** `PATCH` (or equivalent) with explicit `X-Company-Id`, emit `STATUS_OVERRIDE`, set `status_source = USER`. Next SS apply must conflict rather than clobber.
- **Resolution:** DEV-837 `PATCH /v1/people/{id}` (Admin/HR/staff). `STATUS_OVERRIDE` + `LEAVE_STARTED`/`LEAVE_ENDED` for the ledger. `status_source = USER` (staff: `ADMIN`). Apply already emits `SOURCE_CONFLICT` and does not clobber. People UI status control; no initiator/reason legal list (SL-006 / DEV-851).

---

### SL-006 — Termination initiator/reason legal list
- **Opened:** 2026-08-20
- **Status:** open
- **Resolved-date:** —
- **Related:** DEV-851, DEV-837, `KB/02_schema_employment.md#table-employment_event`, `KB/20_regime_ss_hiring_benefit.md#cease-and-clawback`
- **Context:** Event columns `initiator` (EMPLOYER | EMPLOYEE | MUTUAL | OTHER) and `reason` (NO_FAIR_MOTIVE | COLLECTIVE | …) exist for clawback. KB says hammer the legal list later; keep the columns. SS extract does not populate them.
- **Why later:** Product/legal list is not locked. Do not treat the current enum as exhaustive law.
- **Pickup:** When ops UX or clawback (DEV-838) needs it, confirm the enum with the user, then map USER/ADMIN input. Do not infer initiator from the monthly xlsx.

---

### SL-007 — Pass 1 teaser figures stay null (engine)
- **Opened:** 2026-08-20
- **Status:** resolved
- **Resolved-date:** 2026-08-21
- **Related:** DEV-832, DEV-833, OD-2, `KB/10_product_flow.md`, `intake.teaser_*` columns (`KB/01_schema_core.md`)
- **Context:** GET/convert already expose four teaser amounts + currency. 832 leaves them **null**. Inventing 50% of 23.75% or per-person remaining months in 832/834 would leak the recipe. Canonical employment (834) is an input to the engine, not the engine itself.
- **Why later:** Teaser math is DEV-833. Persist what we **showed**; do not live-recompute a DIY calculator.
- **Pickup:** After apply/diff can describe current sem-termo vs term people, compute the four aggregates only. Never return names, rates, remaining months, or “convert this contract”.
- **Resolution:** DEV-833 `app/services/teaser.py` persists the four OD-2 aggregates after successful apply (and on convert if still null). API still omits names, rates, remaining months, and convert-this-contract. `teaser_regime_id` stays null until `incentive_regime` (DEV-838).

---

### SL-008 — Contract PDF vs SS row (override after teaser)
- **Opened:** 2026-08-21
- **Status:** resolved
- **Resolved-date:** 2026-08-25
- **Related:** `KB/10_product_flow.md` (educated guess), `KB/04_schema_documents.md` (`employment_document.matches_ss`), `KB/20_regime_ss_hiring_benefit.md` (extract can be wrong), mother rule 11
- **Context:** Pass 1 teaser uses SS modality + vínculo `started_on` only. Direct can code **sem termo** with an early start when the signed file is **termo** (or the other way around). Worked example Aug 2026: two people SS-start 2021 → remaining 0; paper starts Feb/May 2022 → 6 and 9 months left if the 60-month clock uses `signed_on`. Schema already has `employment_document` and `source = CONTRACT`. There is **no** upload UI, mismatch workflow, or engine re-run from contracts. Do not auto-change the public four figures from PDFs in Pass 1.
- **Why later:** Teaser must stay SS-only (OD-2, no recipe). Contract loop is workspace / ops (after convert). No ticket yet for the check UI.
- **Pickup:** After convert, collect `EMPLOYMENT_CONTRACT` files, set `matches_ss`, let ops set employment modality/`started_on` from `signed_on` (`source = CONTRACT`). Recompute **internal** benefit cases. Public teaser stays the guess they already saw unless a later ticket defines a “revised reading” screen without teaching the recipe.
- **Resolution:** DEV-836: company upload + Gemini/stub review sets `MATCH`/`MISMATCH`; staff queue + confirm copies paper fields onto employment (`source = CONTRACT`). Internal `benefit_case` recompute stays DEV-838. Public teaser is not rewritten.

---

### SL-009 — Gate (companies)/(admins) with Firebase + staff check
- **Opened:** 2026-08-21
- **Status:** resolved
- **Resolved-date:** 2026-08-25
- **Related:** DEV-847, `KB/40_permissions.md`, TJ `requireTjStaff` / `app/(admins)/layout.tsx`
- **Context:** DEV-847 added route groups and TJ-style shells at `/companies/dashboard` and `/admins/dashboard`. Layouts do **not** require a Firebase session or a BeTaxed-staff flag, so the chrome can be browsed while there is no admin API. Anyone who knows the URL can open the ops shell.
- **Why later:** No staff role on `user_base` wired to the Next app yet. A hard gate would 404 the screens this ticket needed to exist.
- **Pickup:** Company layout: require Firebase + membership. Admin layout: require staff (DEV allow-list or `user_base` flag). Do not invent a full ops product in that change.
- **Resolution:** DEV-836 gates `(companies)` on Firebase + `/v1/me` membership and `(admins)` on `user_base.user_type = BETAXED_STAFF`. Ops surface in this ticket is the contract-mismatch queue, not a full ops product.

---

### SL-010 — Cloud Tasks for fanout + contract LLM review
- **Opened:** 2026-08-25
- **Status:** open
- **Resolved-date:** —
- **Related:** DEV-836, DEV-850, `KB/08_schema_communications.md`, TJ `workers/cloud_tasks.py`
- **Context:** Fan-out and Gemini review run **inline after commit** (TJ local fallback). Upload HTTP waits on the stub/Gemini call. Redis pub/sub is only the SSE wake-up.
- **Why later:** No Cloud Tasks queues wired on BeTaxed Cloud Run yet. Inline is correct for tests and local DEV.
- **Pickup:** `FANOUT_DOMAIN_EVENT` + `REVIEW_CONTRACT` queues, `POST /internal/workers/…`, OIDC / `INTERNAL_JOB_TOKEN`. Keep inline fallback when unset.
