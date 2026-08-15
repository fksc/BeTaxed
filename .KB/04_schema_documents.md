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
    doc_kind VARCHAR(24) NOT NULL CHECK (doc_kind IN ('SEM_TERMO', 'TERMO', 'CONVERSION')),
    signed_on DATE,                         -- permanent contract date starts the 60-month clock when applicable
    matches_ss VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (matches_ss IN ('UNKNOWN', 'MATCH', 'MISMATCH')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Rules:**
- `signed_on` for `SEM_TERMO` / `CONVERSION` is the date we use for age-at-contract and window start when it disagrees with SS `started_on` — ops resolve mismatch.
- First-job confirmation is **not** proven by the file alone; ops set `employee.first_permanent_elsewhere`.
- Company sees “please upload this person’s contract”, not “upload because they are 28 and on termo”.
