# KB/07_security_encryption.md — Encryption and isolation
**Depends on:** `KB/00_mother_doc.md`, `KB/01_schema_core.md`

---

## Tenant isolation

- Every company-scoped query filters `company_id`.
- Pass 1 filters `intake_id`.
- BeTaxed staff still pass explicit context (`KB/40`).
- `niss_hash` uniqueness is **per company** (and per intake pre-convert), not global plaintext.

---

## What to encrypt (app-level envelope)

| Data | How |
|---|---|
| Employee NISS | `niss_enc` + `niss_hash = HMAC(niss, tenant_or_app_secret)` |
| Employer NISS, company NIF | `*_enc` + employer `*_hash` for matching uploads |
| Name, date of birth | `*_enc` |
| SS export bytes, contract PDFs | GCS CMEK + optional app encrypt before put |
| Session token for anonymous intake (OD-1 B) | store hash only |

**Do not** use NISS as a primary key or in URLs.

KMS: GCP KMS wrapping a per-company (or per-intake) DEK. Rotate by rewrap; do not leave plaintext DEKs in env.

---

## What stays numeric (OD-3 **locked**)

Base salary, TSU amounts, `saving_amount`, `fee_amount`, invoice totals: `NUMERIC` in Cloud SQL with **CMEK**. Billing must `SUM` in SQL. Identifiers (NISS, NIF, name, DOB) stay app-encrypted.

A SQL dump can still see UUID + amounts + plaintext quasi-identifiers (workplace label, profession, dates). CMEK does not hide live SQL. Company APIs must still omit per-employee recipe fields.

---

## Wipe

Declined intake: delete GCS objects, DEK, raw rows, employees bound only to that intake, then tombstone the intake (`KB/10`).

---

## Samples

`.KB/Samples/` is gitignored. Local copies may still contain live NISS/DOB/pay. Do not paste them into Linear, chats, or logs. Logs may include `employee.id` and `niss_hash` prefix, never plaintext NISS.
