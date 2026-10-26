# KB/05_schema_benefit.md — Regime, cases, savings ledger (INTERNAL)
**Depends on:** `KB/01_schema_core.md`, `KB/02_schema_employment.md`, `KB/03_schema_ss_ingest.md`, `KB/20_regime_ss_hiring_benefit.md`
**Visibility:** BeTaxed staff / billing engine only. **Not** company-facing APIs (`KB/10`, `KB/40`).

---

## Overview

```
incentive_regime (versioned parameters)
company_application (filing at company grain)
benefit_case (one employee × regime, 60-month file)
saving_month (per employee per month — billing fuel)
```

When the law changes, insert a new `incentive_regime`. Existing cases keep their `regime_id`. Invoiced `saving_month` rows lock.

---

## Table: incentive_regime

```sql
CREATE TABLE incentive_regime (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL,              -- e.g. 'PT_SS_YOUNG_FIRST_PERMANENT'
    valid_from DATE NOT NULL,
    valid_to DATE,
    max_age_inclusive INTEGER NOT NULL DEFAULT 30,
    window_months INTEGER NOT NULL DEFAULT 60,
    employer_rate NUMERIC(8, 6) NOT NULL DEFAULT 0.2375,
    reduction_factor NUMERIC(8, 6) NOT NULL DEFAULT 0.5,
    apply_within_days INTEGER NOT NULL DEFAULT 10,
    late_start VARCHAR(24) NOT NULL DEFAULT 'NEXT_MONTH',
    clawback_after_end_months INTEGER NOT NULL DEFAULT 24,
    no_debt_valid_months INTEGER NOT NULL DEFAULT 4,  -- SS/AT cert default window; law change = new row + per-cert override
    UNIQUE (code, valid_from)
);
```

Working values: `KB/20`. Hammer later by **new row**, not by editing live cases.

---

## Table: company_application

```sql
CREATE TABLE company_application (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    regime_id UUID NOT NULL REFERENCES incentive_regime(id),
    submitted_on DATE,
    decision VARCHAR(16) NOT NULL DEFAULT 'NOT_SUBMITTED'
        CHECK (decision IN ('NOT_SUBMITTED', 'SUBMITTED', 'GRANTED', 'REJECTED', 'CEASED')),
    decision_on DATE,
    headcount_current INTEGER,
    headcount_trailing_12_avg NUMERIC(10, 2),
    headcount_test_pass BOOLEAN,
    ss_regularized_at_submit BOOLEAN,
    at_regularized_at_submit BOOLEAN,
    payroll_not_in_arrears_at_submit BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Headcount from `company_headcount_month`. Snapshot SS/AT (and payroll) gates **at submit** from current-cache / `company_certificate` so a later upload cannot rewrite this row.

---

## Table: company_certificate

SS and AT “no debt” declarations are requested **on demand**. Each certificate is valid for **4 months** unless law changes (then ops override `valid_until`, and new certs use `incentive_regime.no_debt_valid_months`).

```sql
CREATE TABLE company_certificate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('SS_NO_DEBT', 'AT_NO_DEBT')),
    file_id UUID NOT NULL REFERENCES stored_file(id),
    issued_on DATE NOT NULL,
    valid_until DATE NOT NULL,
    valid_until_overridden BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_company_certificate_company_kind
    ON company_certificate(company_id, kind, valid_until);
```

**Rules:**
- Upload the PDF (`stored_file.kind` matches), set `issued_on`, default `valid_until = issued_on + no_debt_valid_months` (today: 4). Inclusive of `valid_until`.
- Ops may edit `valid_until` (law change or a certificate that states a different end). Set `valid_until_overridden = TRUE`.
- `company.ss_regularized` / `at_regularized` are **derived caches**: true iff a matching cert covers **today**. Do not treat them as forever flags.
- `payroll_not_in_arrears` stays a current-cache boolean until a dated document type exists.
- Keep expired certs (audit). Current checklist uses only the covering row.

---

## Table: benefit_case

```sql
CREATE TABLE benefit_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    employee_id UUID NOT NULL REFERENCES employee(id),
    employment_id UUID REFERENCES employment(id),
    regime_id UUID NOT NULL REFERENCES incentive_regime(id),
    application_id UUID REFERENCES company_application(id),
    sem_termo_on DATE,
    window_ends_on DATE,                    -- sem_termo_on + window_months
    applied_on DATE,
    benefit_starts_on DATE,                 -- next month if late
    age_at_sem_termo NUMERIC(6, 3),
    first_permanent_elsewhere_at_submit VARCHAR(16),  -- snapshot; YES = company said prior sem termo
    state VARCHAR(32) NOT NULL
        CHECK (state IN (
            'DETECTED',
            'NEEDS_CONVERSION',
            'NEEDS_FIRST_JOB_CHECK',
            'READY',
            'SUBMITTED',
            'GRANTED',
            'REJECTED',
            'CEASED',
            'EXPIRED',
            'CLAWBACK'
        )),
    ineligibility_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, regime_id, employment_id)
);

CREATE INDEX idx_benefit_case_company_state ON benefit_case(company_id, state);
```

**Rules:**
- `DETECTED` from pass-1 engine; still internal. Teaser uses an aggregate only.
- `NEEDS_CONVERSION`: term contract, would qualify if sem termo (ops after they are a client).
- **First sem termo is not a filing hold.** `NEEDS_FIRST_JOB_CHECK` must not block submit. Company/ops may set `employee.first_permanent_elsewhere = YES` (onboarding); we **still apply**. Snapshot `first_permanent_elsewhere_at_submit` when the case is submitted so ops can compare `GRANTED` / `REJECTED` vs the flag (SS history is incomplete).
- Remaining window is **derived** from dates; do not use a single `remaining_months` column as source of truth (cache allowed).
- `CLAWBACK` when termination initiator/reason says so (`KB/20`). `saving_month.billable = FALSE` going forward; recoveries are billing credit notes (`KB/06`).

---

## Table: saving_month

```sql
CREATE TABLE saving_month (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    benefit_case_id UUID NOT NULL REFERENCES benefit_case(id),
    employee_id UUID NOT NULL REFERENCES employee(id),
    year_month DATE NOT NULL,               -- first of month
    base_salary NUMERIC(12, 2) NOT NULL,
    saving_amount NUMERIC(12, 2) NOT NULL,  -- typically base * employer_rate * reduction_factor
    fee_percent NUMERIC(8, 6) NOT NULL,     -- snapshot from commercial_terms
    fee_amount NUMERIC(12, 2) NOT NULL,
    billable BOOLEAN NOT NULL DEFAULT TRUE,
    locked_at TIMESTAMPTZ,                  -- set when put on an invoice
    invoice_line_id UUID,
    UNIQUE (benefit_case_id, year_month)
);
```

**Rules:**
- One row per case per month while in window and granted (or whatever ops lock as “realized”).
- `billable = FALSE` if terminated, clawback, or **leave** (OD-4 locked: no success fee on leave months).
- Once `locked_at` is set, do not update amounts. Corrections = new month or credit note.
- Company invoices **sum fee_amount** where billable; they do not list employees (`KB/06`).

---

## Request case (DEV-882) {#request-case}

The staff flag says who can still benefit. It is not a case. A `request_case` row is created when BeTaxed staff add that person to the pipeline. Company users see the stage of their own cases, a sent minuta, and an unfavorable notice. They do not see the flag, rates, or remaining months.

`benefit_case` stays the internal ledger. `request_case.benefit_case_id` may point at it. Neither row files with Segurança Social by itself.

### Stage types

A stage is a row, not a hardcoded name. Staff can add or remove stages. The code knows the type and the operations assigned to the current stage.

| `stage_type` | Meaning |
|---|---|
| `WORK` | BeTaxed staff act |
| `WAIT_CLIENT` | Waiting on the company |
| `WAIT_SS` | Waiting on Segurança Social |
| `CLOSE_WON` | Closed, approved. Like a CRM closed-won |
| `CLOSE_LOST` | Closed, refused. Like a CRM closed-lost |

Close approved and close rejected are terminal. Claim is not a close type. A claim is a work stage that later closes approved or rejected.

`ss_submission_ref` and `ss_status_read_at` stay empty until a Segurança Social sub-account can submit or read status. That result updates this case. It does not create a second case.

### Tables

```sql
CREATE TABLE pipeline_stage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    stage_type VARCHAR(16) NOT NULL
        CHECK (stage_type IN ('WORK', 'WAIT_CLIENT', 'WAIT_SS', 'CLOSE_WON', 'CLOSE_LOST')),
    position INTEGER NOT NULL,
    entry_path VARCHAR(16)
        CHECK (entry_path IS NULL OR entry_path IN ('FIXED_TERM', 'OPEN_CONTRACT')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE pipeline_operation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL
);

CREATE TABLE pipeline_stage_operation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id UUID NOT NULL REFERENCES pipeline_stage(id),
    operation_id UUID NOT NULL REFERENCES pipeline_operation(id),
    next_stage_id UUID REFERENCES pipeline_stage(id),
    next_won_stage_id UUID REFERENCES pipeline_stage(id),
    next_lost_stage_id UUID REFERENCES pipeline_stage(id),
    next_claim_stage_id UUID REFERENCES pipeline_stage(id),
    UNIQUE (stage_id, operation_id)
);

CREATE TABLE rejection_reason (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL UNIQUE,
    label VARCHAR(255) NOT NULL,
    blocks_claim BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE minuta_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    body_html TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE request_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    employee_id UUID NOT NULL REFERENCES employee(id),
    employment_id UUID NOT NULL REFERENCES employment(id),
    opened_by UUID NOT NULL REFERENCES user_base(id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stage_id UUID NOT NULL REFERENCES pipeline_stage(id),
    stage_stack UUID[] NOT NULL DEFAULT ARRAY[]::uuid[],
    path VARCHAR(16) NOT NULL
        CHECK (path IN ('FIXED_TERM', 'OPEN_CONTRACT')),
    probation_ends_on DATE,
    benefit_starts_on DATE,
    applied_on DATE,
    applied_by UUID REFERENCES user_base(id),
    decision_on DATE,
    rejection_reason_id UUID REFERENCES rejection_reason(id),
    benefit_case_id UUID REFERENCES benefit_case(id),
    ss_submission_ref VARCHAR(128),
    ss_status_read_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_request_case_open_employment
    ON request_case (employment_id)
    WHERE closed_at IS NULL;

CREATE TABLE request_case_minuta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_case_id UUID NOT NULL REFERENCES request_case(id),
    template_id UUID NOT NULL REFERENCES minuta_template(id),
    body_html TEXT NOT NULL,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE request_case_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    request_case_id UUID REFERENCES request_case(id),
    kind VARCHAR(32) NOT NULL
        CHECK (kind IN ('SIGNED_MINUTA', 'UNFAVORABLE_NOTICE', 'CLAIM_SUPPORT')),
    file_id UUID NOT NULL REFERENCES stored_file(id),
    uploaded_by UUID REFERENCES user_base(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Seeded board

No minuta types are seeded. One rejection reason is seeded: `PRIOR_SEM_TERMO`, and it blocks a claim. Further blocking reasons are added as rows.

| Code | Type | Entry | Operations |
|---|---|---|---|
| `probation` | Work | `OPEN_CONTRACT` | Record probation. Next stage is Ready |
| `minuta` | Work | `FIXED_TERM` | Generate minuta (stays). Send minuta (next is Signature) |
| `signature` | Waiting on the client | — | Attach signed scan. Next is Ready |
| `ready` | Work | — | Record filing. Next is Awaiting decision |
| `awaiting_decision` | Waiting on Segurança Social | — | Record a decision: won, lost, or claim |
| `claim` | Work | — | Record a decision: won or lost |
| `closed_approved` | Close approved | — | — |
| `closed_rejected` | Close rejected | — | — |

`path` is taken from the employment when the case opens. `TERMO_CERTO` and `TERMO_INCERTO` are `FIXED_TERM` and enter on the stage whose `entry_path` is `FIXED_TERM`. Anything else is `OPEN_CONTRACT` and enters on the probation entry. Recording “no probation” moves to Ready and never creates a minuta. A probation end date may set `benefit_starts_on` so the 60 months start later.

A decision of won moves to the assignment’s `next_won_stage_id`. Lost moves to `next_lost_stage_id` and requires a reason and an unfavorable notice. Claim moves to `next_claim_stage_id` only when `blocks_claim` is false. The same decision operation on Claim has no claim destination, so the claim closes won or lost.

`stage_stack` is the stages this case has actually entered, latest last. Staff can move the card back one visit. Dates, the minuta, and uploaded files stay. Leaving a close stage clears `closed_at`. A case that only has its current stage on the stack steps back along its path: fixed term is minuta, signature, ready, awaiting decision; an open contract is probation, ready, awaiting decision. Claim, and a close with no earlier visit recorded, step back to awaiting decision.

Remaining months are derived for staff when the stage type is close won, from `benefit_starts_on` when set, otherwise the employment start. Company payloads omit that number.

`{{ key }}` in a minuta body is filled from the person and the company. Staff can edit `body_html` before send. Tokens: `person_name`, `company_name`, `contract_started_on`, `benefit_starts_on`.

Signed scans may be uploaded in bulk with `request_case_id` empty until staff attach one to a case that is on a stage with the attach operation.
