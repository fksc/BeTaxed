# KB/03_schema_ss_ingest.md — SS declarations, raw rows, diffs
**Depends on:** `KB/01_schema_core.md`, `KB/02_schema_employment.md`
**Referenced by:** `KB/10_product_flow.md`

---

## Overview

Companies declare to Segurança Social every month (two files, usually csv). They upload the same (or the combined Excel export) here. Parental/sickness leave is **not** on the sample vínculos+contratos extract. When present, a remunerações **leave** sheet or third file is stored on `ss_raw_leave` (DEV-849).

```
ss_batch (one upload / one month)
  ├── stored files (GCS)
  ├── ss_raw_vinculo  (immutable)
  ├── ss_raw_contrato (immutable)
  ├── ss_raw_leave    (immutable; optional remunerações leave sheet)
  └── apply → employee / employment / compensation_period + employment_event
```

Ignore analyst-only columns (idade, fee/ano, VLOOKUP). Parser maps official vínculos/contratos headers (`KB/20`). Leave uses the BeTaxed ingest headers below — **not** official SS Declaração de Remunerações column names (no sample).

---

## Table: ss_batch

```sql
CREATE TABLE ss_batch (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES company(id),
    intake_id UUID REFERENCES intake(id),
    period_year_month DATE NOT NULL,        -- first of month
    uploaded_by UUID REFERENCES user_base(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    employer_niss_hash BYTEA,
    parse_status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
        CHECK (parse_status IN ('PENDING', 'PARSED', 'FAILED', 'APPLIED', 'DISCARDED')),
    parse_error TEXT,
    export_label TEXT,                      -- e.g. query name 25157…_vinculos_2026_08_12
    leave_declared BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (company_id IS NOT NULL OR intake_id IS NOT NULL)
);

CREATE INDEX idx_ss_batch_company_period ON ss_batch(company_id, period_year_month);
```

**Rules:**
- Pass 1: `intake_id` set, `company_id` null. On convert, set `company_id`.
- After convert, `employer_niss_hash` must match `company.employer_niss_hash` or fail closed (ops exception).
- `APPLIED` means canonical tables were updated and events emitted.
- Decline/purge: batches for that intake are deleted with the files.

---

## Table: ss_batch_file

```sql
CREATE TABLE ss_batch_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES ss_batch(id) ON DELETE CASCADE,
    file_id UUID NOT NULL,                  -- stored_file.id
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('COMBINED_XLSX', 'VINCULOS', 'CONTRATOS', 'REMUNERACOES', 'OTHER'))
);
```

One combined xlsx (sample) or two files (xlsx or csv), optionally plus a remunerações leave file — same batch. `leave_declared` is true when that sheet/file was present (including empty of rows), so apply can end SS leave. Omitting the file does **not** invent `LEAVE_ENDED`.

---

## Table: ss_raw_vinculo / ss_raw_contrato

Immutable parsed sheets. Column names follow the export (Portuguese). Store `niss_hash` (not plaintext NISS). Keep raw NISS only inside `niss_enc` if needed for re-hash; prefer hashing at parse and not retaining plaintext.

Minimum vínculo columns: niss_hash, dob (enc or hashed+enc), vínculo raw, communicated_on, started_on, ended_on, rate_from, rate_to, taxa_pct, workplace raw.

Minimum contrato columns: niss_hash, modality raw, work mode, contract start/end, profession, percent/hours/days, rendimento from/to, base_salary, motivo.

Exact CREATE TABLE column lists can match parser structs; **do not** invent fee columns.

Re-parse is allowed: new raw rows from the same file bytes, or `DISCARDED` + new batch. Do not mutate applied canonical history; emit correcting events.

---

## Table: ss_raw_leave

BeTaxed remunerações **leave** ingest (DEV-849). Required folded headers: `niss`, `tipo de ausencia` (aliases: `tipo de baixa`, `leave type`), `inicio ausencia` (aliases: `data inicio ausencia`, `started on`). Optional `fim ausencia`. Leave type cells map to `PARENTAL` | `SICKNESS` | `UNPAID` | `OTHER` (Portuguese aliases: doença, licença parental, não remunerada, outra). Unknown values fail closed. **Do not** treat these names as official Segurança Social DR columns; map official headers here when a sample exists.

```sql
CREATE TABLE ss_raw_leave (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES ss_batch(id) ON DELETE CASCADE,
    source_row INTEGER NOT NULL,
    niss_hash BYTEA NOT NULL,
    niss_enc BYTEA NOT NULL,
    leave_type VARCHAR(24) NOT NULL
        CHECK (leave_type IN ('PARENTAL', 'SICKNESS', 'UNPAID', 'OTHER')),
    started_on DATE NOT NULL,
    ended_on DATE,
    leftover JSONB
);
```

---

## Apply and diff

1. Parse → raw tables, `parse_status = PARSED`.
2. Match `niss_hash` → `employee` (create if new).
3. Upsert `employment` / `compensation_period` from **current** contrato period (`period_to` empty = current).
4. Diff vs previous **APPLIED** batch for the same company (or intake): insert `employment_event`.
5. Mark `APPLIED`.

Diff mapping (v1 from vínculos + contratos):

| Observation | Event |
|---|---|
| New niss_hash | `HIRED` |
| `fim vínculo` set or disappeared from active | `TERMINATED` |
| Same person, new vínculo after end | `REHIRED` |
| New rendimento period / salary | `SALARY_CHANGED` |
| Modality term → sem termo | `MODALITY_CHANGED` |
| Taxa changed | `TSU_RATE_CHANGED` |
| Present last month, absent this month | `MISSING_FROM_DECLARATION` |
| User status ≠ SS | `SOURCE_CONFLICT` (do not auto-overwrite user) |
| Remunerações open leave (`ended_on` empty) | `LEAVE_STARTED`, `source = SS_DIFF`, `employee.status = ON_LEAVE` |
| Remunerações file present and person no longer on leave | `LEAVE_ENDED`, `source = SS_DIFF` |

Vínculos + contratos must **not** fake `LEAVE_*`. USER/ADMIN `status_source` still wins: disagreeing remunerações emits `SOURCE_CONFLICT` and does not clobber.

---

## Table: company_headcount_month

For the application headcount test (`KB/20`).

```sql
CREATE TABLE company_headcount_month (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    year_month DATE NOT NULL,               -- first of month
    headcount INTEGER NOT NULL,
    source VARCHAR(16) NOT NULL CHECK (source IN ('SS_BATCH', 'USER')),
    source_batch_id UUID REFERENCES ss_batch(id),
    UNIQUE (company_id, year_month, source)
);
```

Until we have 12 months of batches, `source = USER` is allowed. Engine compares current month vs average of previous 12 (`KB/05` application).
