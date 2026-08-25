# KB/04_schema_documents.md — Files and contracts
**Depends on:** `KB/01_schema_core.md`, `KB/02_schema_employment.md`

---

## Table: stored_file

GCS only. DB holds the ref.

```sql
CREATE TABLE stored_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES company(id),
    intake_id UUID REFERENCES intake(id),
    gcs_path TEXT NOT NULL,
    sha256 CHAR(64),
    mime_type VARCHAR(128),
    original_filename TEXT,
    kind VARCHAR(32) NOT NULL CHECK (kind IN (
        'SS_EXPORT',
        'EMPLOYMENT_CONTRACT',
        'CONVERSION_DECLARATION',
        'AT_NO_DEBT',
        'SS_NO_DEBT',
        'INVOICE_PDF',
        'PROFORMA',
        'OTHER'
    )),
    uploaded_by UUID REFERENCES user_base(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
```

**Rules:**
- Encrypt objects at rest (CMEK / app envelope — `KB/07`).
- Signed URLs on demand; never persist them.
- Purge intake: delete GCS objects then rows.
- Sample files in `.KB/Samples/` are **not** this table and **not** git.

---

## Table: employment_document

Post-teaser workspace: contracts to cross-check SS.

```sql
CREATE TABLE employment_document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employee(id),
    employment_id UUID REFERENCES employment(id),
    file_id UUID NOT NULL REFERENCES stored_file(id),
    doc_kind VARCHAR(24),                   -- null until LLM/ops fill it
        CHECK (doc_kind IS NULL OR doc_kind IN ('SEM_TERMO', 'TERMO', 'CONVERSION')),
    signed_on DATE,                         -- permanent contract date starts the 60-month clock when applicable
    term_end_on DATE,                       -- paper end for termo (e.g. 1-year CDD); null for sem termo
    matches_ss VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (matches_ss IN ('UNKNOWN', 'MATCH', 'MISMATCH')),
    review_status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
        CHECK (review_status IN ('PENDING', 'REVIEWED', 'FAILED')),
    review_leftover JSONB,                  -- raw LLM leftover only; not queryable product fields
    review_error TEXT,
    ops_confirmed_at TIMESTAMPTZ,           -- staff applied CONTRACT source onto employment
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Rules:**
- `signed_on` for `SEM_TERMO` / `CONVERSION` is the date we use for age-at-contract and window start when it disagrees with SS `started_on` — ops resolve mismatch. Term files use `doc_kind = TERMO`; that can **remove** someone from the NOW bucket the extract put them in.
- `term_end_on` is the paper end date for `TERMO`. Typical mismatch: SS `SEM_TERMO` + open `ended_on`, PDF is a 1-year termo.
- First-sem-termo **flag** is not proven by the contract file. Company/ops set `employee.first_permanent_elsewhere`; we still file (`KB/20`).
- SS/AT no-debt PDFs are `kind` `SS_NO_DEBT` / `AT_NO_DEBT` and attach to `company_certificate` (`KB/05`), not to `employment_document`.
- Company sees “please upload this person’s contract”, not “upload because they are 28 and on termo”. Company APIs never expose `matches_ss = MISMATCH` or SS-vs-PDF field diffs (recipe-adjacent). Staff ops queue does.
- **Upload → review:** persist the file with `review_status = PENDING`. Emit `CONTRACT_UPLOADED` (`KB/08`). A worker (Gemini, or DEV stub) fills typed columns, sets `MATCH` / `MISMATCH`, emits `CONTRACT_REVIEWED` or `CONTRACT_SS_MISMATCH`. Do **not** auto-rewrite `employment.*`. Staff confirm copies modality / `signed_on` / `term_end_on` onto employment with `source = CONTRACT`.
- **Flow (locked as product, not as Pass-1 math):** teaser from SS only → client uploads contracts → LLM/ops one-by-one vs the extract → `MATCH` / `MISMATCH`. Do not auto-rewrite the public teaser from PDFs.
