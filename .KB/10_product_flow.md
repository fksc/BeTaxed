# KB/10_product_flow.md — Product Flow
**Depends on:** `KB/00_mother_doc.md`
**Referenced by:** `KB/01_schema_core.md` (intake), `KB/03_schema_ss_ingest.md`, `KB/40_permissions.md`

---

## Two-pass intake

The product is a **funnel**, then a **workspace**. It is not a consulting walkthrough of the regime.

```
Pass 1 (look)     SS file → internal engine → teaser
Pass 2 (stay)     Create/attach account + company workspace → contracts, monthly loop, invoices
Pass 2 (leave)    Decline → hard-delete everything from pass 1
```

Identity **when** pass 1 runs is **OD-1 locked (both):** the prospect may create an account first, or upload first and create an account later. Schema: `intake.user_id` nullable; anonymous pass 1 binds with `session_token_hash`.

---

## Pass 1 — look

1. Company (or a prospect) provides the Segurança Social extract (vínculos + contratos; one workbook or two files).
2. We store the file encrypted, parse it, match people on `niss_hash`, run the engine **only on our side**.
3. We show a **teaser**: enough to believe there is a real opportunity. No recipe.

**Teaser must not include:** 50% of 23.75%, named employees, remaining months, “convert this contract to sem termo”, year-by-year tables. That material belongs in a controlled sales PDF, not the result screen.

Store four teaser figures (and regime version) so we do not contradict ourselves if they continue. **OD-2 locked:** (1) **now** — already sem termo, unused benefit; (2) **potential** — convert to sem termo; each as **monthly** and **5-year**. Still no recipe, named people, remaining months per person, or convert-this-contract how-to.

---

## Pass 2 — stay

Promote the same intake:

1. Ensure a `user_base` exists and is bound to the intake (account-first already has it; upload-first creates/links now).
2. Create `company`, membership (uploader = `ADMIN`).
3. Set `ss_batch.company_id`, `employee.company_id` on rows already parsed.
4. Workspace: ask for employment contracts (and later monthly SS files, status, invoices).
5. Still no methodology dump. They see **work to do** and **money** (invoices), not a DIY calculator.

---

## Wipe on decline

If they do not continue:

- Status `intake.status = DECLINED` then **PURGED**.
- Delete GCS objects for that intake.
- Hard-delete `ss_raw_*`, unmatched staging, teaser run, hashes, `ss_batch`, then the intake row (or retain a tombstone with no PII: `id`, `purged_at`, `reason`).
- This is not an archive. Pass 1 must not become a free calculator or a PII store for non-customers.

If they already have a `user_base` (account-first), **wipe the intake data**; do not keep the parsed employees. Keeping an empty login is allowed.

---

## After the workspace exists

Monthly: they upload the two SS declaration files (or the combined export). Diff vs last **applied** batch → `employment_event` (joined, left, pay change, leave when the file supports it, missing from declaration).

Company users can set employee status (`ACTIVE` / `ON_LEAVE` / `TERMINATED`) until HRMS exists. If SS disagrees, record a **conflict**; do not silently overwrite the user.

Billing: success fee on realized savings for the remaining benefit window. Stripe SEPA or certified PT invoice + our PDF as proforma/detail. Ledger: draft / issued / due / late / paid / consolidated / void / manually resolved. Stripe auto-marks paid.

---

## What the company never sees

Internal only (`KB/05_schema_benefit.md`, `KB/20_regime_ss_hiring_benefit.md`):

- Eligibility reasons and remaining months
- Conversion recommendations and € per person
- Employer rate math
- Clawback classification (ops may see this; company UI does not explain the legal recipe)
