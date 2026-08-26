# KB/02_schema_employment.md — Employees, employment, pay, events
**Depends on:** `KB/01_schema_core.md`
**Referenced by:** `KB/03_schema_ss_ingest.md`, `KB/04_schema_documents.md`, `KB/05_schema_benefit.md`

---

## Overview

Three grains, matching the SS file and future HRMS:

```
employee (person in a tenant)
  └── employment (vínculo; rehire = new row)
        └── compensation_period (rendimento / base pay)
employment_event (situations: hire, fire, leave, raise, …)
```

`employee.status` is a **cache**. History is `employment_event`.

Pre-convert, `company_id` is null and `intake_id` is set. On convert, set `company_id` and keep `intake_id` for provenance.

---

## Table: workplace

SS “local de trabalho”. Sample has one Lisbon establishment.

```sql
CREATE TABLE workplace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES company(id),
    intake_id UUID REFERENCES intake(id),
    ss_label TEXT NOT NULL,                 -- raw, e.g. '1 - R CIDADE DE …'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Table: employee

```sql
CREATE TABLE employee (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES company(id),
    intake_id UUID REFERENCES intake(id),
    niss_hash BYTEA NOT NULL,
    niss_enc BYTEA NOT NULL,
    name_enc BYTEA,                         -- often absent on SS extract
    dob_enc BYTEA,
    first_permanent_elsewhere VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (first_permanent_elsewhere IN ('UNKNOWN', 'NO', 'YES')),
    first_permanent_source VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (first_permanent_source IN ('UNKNOWN', 'COMPANY_ONBOARDING', 'OPS')),
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'ON_LEAVE', 'TERMINATED')),
    status_source VARCHAR(16) NOT NULL DEFAULT 'SS'
        CHECK (status_source IN ('SS', 'USER', 'HRMS', 'ADMIN')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CHECK (company_id IS NOT NULL OR intake_id IS NOT NULL)
);

CREATE UNIQUE INDEX idx_employee_company_niss
    ON employee(company_id, niss_hash) WHERE company_id IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX idx_employee_intake_niss
    ON employee(intake_id, niss_hash) WHERE intake_id IS NOT NULL AND company_id IS NULL AND deleted_at IS NULL;
```

**Rules:**
- Never use NISS as PK. Join uploads with `niss_hash` (`KB/07_security_encryption.md`).
- Rehire: **same** employee, new `employment`.
- `first_permanent_elsewhere`: **company-reported** (onboarding forms we receive) or ops. `YES` = they told us this person already had a sem termo (this employer or elsewhere). SS extract of **this** employer cannot prove other employers.
- **Always file anyway.** SS history is incomplete; a prior sem termo may be missing from their database. Do not treat `YES` as `ineligibility_code` that blocks `benefit_case` submit.
- Ops monitors `YES` vs `benefit_case.state` (`GRANTED` / `REJECTED`) after SS answers. Snapshot the flag on the case at submit (`KB/05`).
- `first_permanent_source`: `COMPANY_ONBOARDING` | `OPS` | `UNKNOWN`.
- HRMS later: `employee_external_id`, not a JSON map on this table.

---

## Table: employee_external_id

```sql
CREATE TABLE employee_external_id (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employee(id),
    system VARCHAR(32) NOT NULL,            -- 'HRMS', 'SS', …
    external_id VARCHAR(128) NOT NULL,
    UNIQUE (employee_id, system)
);
```

---

## Table: employment

One vínculo.

```sql
CREATE TABLE employment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employee(id),
    company_id UUID REFERENCES company(id),
    intake_id UUID REFERENCES intake(id),
    started_on DATE NOT NULL,
    ended_on DATE,
    actor_type VARCHAR(32) NOT NULL DEFAULT 'TCO',  -- mapped enum
    actor_type_raw TEXT,
    contract_modality VARCHAR(32) NOT NULL,
        -- SEM_TERMO | TERMO_CERTO | TERMO_INCERTO | OTHER
    contract_modality_raw TEXT,
    work_mode VARCHAR(32),                  -- PRESENCIAL | …
    work_mode_raw TEXT,
    hours_per_week NUMERIC(6, 2),
    days_per_month NUMERIC(6, 2),
    percent_work NUMERIC(6, 2),
    profession_raw TEXT,
    workplace_id UUID REFERENCES workplace(id),
    tsu_rate_pct NUMERIC(6, 3),             -- e.g. 34.75 or reduced
    rate_applied_from DATE,
    rate_applied_to DATE,
    ss_communicated_on DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_employment_employee ON employment(employee_id);
```

**Rules:**
- Store mapped enum **and** raw Portuguese SS label.
- Open employment: `ended_on IS NULL`.
- `tsu_rate_pct` moving off 34.75 is how we see SS **granted** a reduction (internal).
- `contract_modality = SEM_TERMO` + `started_on` (or document `signed_on` if it differs) feeds the 60-month clock — see `KB/05` / `KB/20`.

---

## Table: compensation_period

Contratos / período de rendimento.

```sql
CREATE TABLE compensation_period (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employment_id UUID NOT NULL REFERENCES employment(id),
    period_from DATE NOT NULL,
    period_to DATE,                         -- null = current
    base_salary NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comp_employment ON compensation_period(employment_id);
CREATE UNIQUE INDEX idx_comp_open
    ON compensation_period(employment_id) WHERE period_to IS NULL;
```

**Rules:**
- Current pay = the open period. Never “first row in the sheet” (sample VLOOKUP is unsafe).
- Closed periods keep history for diffs and raises.

Salary storage: OD-3 — lean NUMERIC in CMEK Postgres (`KB/00_mother_doc.md#open-decisions`).

---

## Table: employment_event

Situations we must keep: joined, left, leave, raise, conversion, rate change, user override.

```sql
CREATE TABLE employment_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES company(id),
    intake_id UUID REFERENCES intake(id),
    employee_id UUID NOT NULL REFERENCES employee(id),
    employment_id UUID REFERENCES employment(id),
    event_type VARCHAR(32) NOT NULL
        CHECK (event_type IN (
            'HIRED',
            'TERMINATED',
            'REHIRED',
            'SALARY_CHANGED',
            'MODALITY_CHANGED',
            'TSU_RATE_CHANGED',
            'LEAVE_STARTED',
            'LEAVE_ENDED',
            'MISSING_FROM_DECLARATION',
            'STATUS_OVERRIDE',
            'SOURCE_CONFLICT'
        )),
    effective_on DATE NOT NULL,
    source VARCHAR(16) NOT NULL
        CHECK (source IN ('SS_DIFF', 'USER', 'ADMIN', 'HRMS', 'CONTRACT')),
    -- typed extras (null when N/A):
    old_salary NUMERIC(12, 2),
    new_salary NUMERIC(12, 2),
    old_modality VARCHAR(32),
    new_modality VARCHAR(32),
    old_rate_pct NUMERIC(6, 3),
    new_rate_pct NUMERIC(6, 3),
    leave_type VARCHAR(24),                 -- PARENTAL | SICKNESS | UNPAID | OTHER
    initiator VARCHAR(16),                  -- EMPLOYER | EMPLOYEE | MUTUAL | OTHER
    reason VARCHAR(32),                     -- NO_FAIR_MOTIVE | COLLECTIVE | JOB_EXTINCTION | UNSUITABILITY | RESIGNATION | END_OF_TERM | OTHER
    old_status VARCHAR(16),
    new_status VARCHAR(16),
    ss_batch_id UUID,                       -- FK in ingest migration
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_event_employee ON employment_event(employee_id, effective_on);
CREATE INDEX idx_event_company_type ON employment_event(company_id, event_type);
```

**Rules:**
- Diff of two applied SS batches **inserts** events; it does not rewrite history.
- `STATUS_OVERRIDE`: company user changes `employee.status` before the next file (or instead of HRMS).
- `SOURCE_CONFLICT`: e.g. user says `TERMINATED`, latest SS still active. Ops/HR resolve; do not auto-win SS.
- Termination `initiator` + `reason` exist for clawback (`KB/20_regime_ss_hiring_benefit.md#cease-and-clawback`). Hammer the legal list later; keep the columns.
- Parental leave may be absent from vínculos/contratos; `USER` override or remunerações leave ingest (`source = SS_DIFF`, DEV-849) sets `ON_LEAVE`.
