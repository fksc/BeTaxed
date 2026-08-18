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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Headcount from `company_headcount_month`. Certificates attach via `stored_file` (AT no-debt, etc.).

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
