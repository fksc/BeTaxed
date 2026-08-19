# KB/01_schema_core.md — Core Schema
**Depends on:** nothing (spine).
**Referenced by:** every other schema doc.

---

## Overview

Identity, tenancy, and two-pass intake. Every other entity references `company` (after convert) or `intake` (pass 1).

---

## Table: user_base

Every human actor has exactly one `user_base`. Firebase identity → internal UUID.

```sql
CREATE TABLE user_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('BETAXED_STAFF', 'COMPANY_STAFF')),
    preferred_language VARCHAR(10) NOT NULL DEFAULT 'pt',
    timezone VARCHAR(64) NOT NULL DEFAULT 'Europe/Lisbon',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX idx_user_base_firebase_uid ON user_base(firebase_uid);
CREATE INDEX idx_user_base_email ON user_base(email);
```

**Rules:**
- `firebase_uid` is set at account creation and never changes.
- `email` matches Firebase Auth; sync on login.
- `preferred_language` drives UI (BCP 47, e.g. `pt`, `en`).
- `is_active = FALSE` soft-disables access; do not delete (audit).
- One row per email.

Upload-first pass 1 has **no** `user_base` yet (`intake.user_id` null; `session_token_hash` binds the browser). Account-first sets `user_id` before the upload.

---

## Table: company

Client tenant. Created **only** when intake is converted (pass 2 stay).

```sql
CREATE TABLE company (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name VARCHAR(255) NOT NULL,
    trading_name VARCHAR(255),
    nif_enc BYTEA,
    employer_niss_hash BYTEA,
    employer_niss_enc BYTEA,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CHURNED')),
    locale VARCHAR(10) NOT NULL DEFAULT 'pt',
    ss_regularized BOOLEAN,                 -- current-cache: a valid SS_NO_DEBT cert covers today
    at_regularized BOOLEAN,                 -- current-cache: a valid AT_NO_DEBT cert covers today
    payroll_not_in_arrears BOOLEAN,         -- current-cache only (no dated cert type yet)
    stripe_customer_id VARCHAR(128),
    invoicing_method VARCHAR(32)
        CHECK (invoicing_method IN ('STRIPE_SEPA', 'CERTIFIED_SOFTWARE')),
    certified_vendor_name VARCHAR(128),     -- nullable until finance picks a tool
    created_from_intake_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_company_employer_niss_hash
    ON company(employer_niss_hash) WHERE employer_niss_hash IS NOT NULL AND deleted_at IS NULL;
```

**Rules:**
- `employer_niss_hash` matches the SS export (Power Query name in the sample: `{niss}_vinculos_{date}`). After convert, later batches must match this hash.
- Access-condition booleans (`ss_regularized`, `at_regularized`, `payroll_not_in_arrears`) are a **current checklist**, not the recipe. SS/AT no-debt **certificates** are dated (`issued_on` + `valid_until`, default 4 months) on `company_certificate` (`KB/05`, DEV-838). Snapshot gates onto `company_application` at submit so a later cert cannot rewrite history.
- `invoicing_method` may be null until finance sets it. `certified_vendor_name` stays null until they pick the certified tool (DEV-841).
- Soft-delete with `deleted_at`.

---

## Table: company_membership

```sql
CREATE TABLE company_membership (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_base(id),
    company_id UUID NOT NULL REFERENCES company(id),
    role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN', 'HR', 'FINANCE')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, company_id)
);

CREATE INDEX idx_membership_company ON company_membership(company_id);
```

**Rules:**
- Uploader who continues becomes `ADMIN`.
- BeTaxed staff are **not** members. They act with explicit `company_id` in the request (`KB/40_permissions.md`).
- One person may belong to multiple companies.

---

## Table: intake

Pass 1 container. Either converted to a company or purged.

```sql
CREATE TABLE intake (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_base(id),          -- null until account exists (upload-first)
    email VARCHAR(255),                             -- optional contact
    session_token_hash BYTEA,                       -- anonymous/browser bind (upload-first)
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'CONVERTED', 'DECLINED', 'PURGED')),
    teaser_now_monthly NUMERIC(14, 2),              -- OD-2: already sem termo, unused benefit
    teaser_now_window NUMERIC(14, 2),               -- same bucket, ~5-year / remaining window
    teaser_potential_monthly NUMERIC(14, 2),        -- OD-2: convert to sem termo
    teaser_potential_window NUMERIC(14, 2),
    teaser_currency CHAR(3) NOT NULL DEFAULT 'EUR',
    teaser_regime_id UUID,                          -- FK added when incentive_regime exists
    converted_company_id UUID REFERENCES company(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    purged_at TIMESTAMPTZ
);

CREATE INDEX idx_intake_user ON intake(user_id);
CREATE INDEX idx_intake_status ON intake(status);
```

**Rules:**
- `user_id` nullable **on purpose** (OD-1 locked: both account-first and upload-first).
- The four `teaser_*` amounts are what we **showed** (OD-2), not a live ledger. Do not use JSONB.
- Convert: create `company`, set `converted_company_id`, `status = CONVERTED`, attach batches/employees (`KB/10_product_flow.md#pass-2--stay`).
- Decline: `DECLINED` then purge (`KB/10_product_flow.md#wipe-on-decline`). After purge, do not keep PII. A tombstone (`id`, `status=PURGED`, `purged_at`) is allowed.
- Add FK `intake.teaser_regime_id → incentive_regime(id)` in the benefit migration.

**Circular FK:** `company.created_from_intake_id` → `intake(id)` added after both tables exist (nullable, set on convert).
