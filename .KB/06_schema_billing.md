# KB/06_schema_billing.md — Commercial terms, invoices, payments
**Depends on:** `KB/01_schema_core.md`, `KB/05_schema_benefit.md`

---

## Overview

Success fee = percentage of **realized** SS savings for the remaining benefit window. Joiners/leavers change `saving_month.billable`; they do not rewrite old invoices.

```
commercial_terms
saving_month (internal)
  → invoice_line (internal employee_id; customer description generic)
    → invoice
      → payment
      → invoice_status_event
```

---

## Table: commercial_terms

```sql
CREATE TABLE commercial_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    fee_percent NUMERIC(8, 6) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    UNIQUE (company_id, valid_from)
);
```

Fee % is commercial, not in the regime table. Snapshot `fee_percent` onto each `saving_month`.

---

## Table: invoice

```sql
CREATE TABLE invoice (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES company(id),
    period_from DATE NOT NULL,
    period_to DATE NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN (
            'DRAFT',
            'ISSUED',
            'DUE',
            'LATE',
            'PAID',
            'CONSOLIDATED',
            'VOID',
            'MANUALLY_RESOLVED'
        )),
    currency CHAR(3) NOT NULL DEFAULT 'EUR',
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total NUMERIC(12, 2) NOT NULL DEFAULT 0,
    issued_on DATE,
    due_on DATE,
    paid_on DATE,
    consolidates_invoice_id UUID REFERENCES invoice(id),
    stripe_invoice_id VARCHAR(128),
    stripe_mandate_id VARCHAR(128),
    certified_external_id VARCHAR(128),
    proforma_file_id UUID REFERENCES stored_file(id),
    legal_invoice_file_id UUID REFERENCES stored_file(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoice_company_status ON invoice(company_id, status);
```

**Rules:**
- Company sees totals and status, not per-employee math.
- `CONSOLIDATED`: this row groups others (`consolidates_invoice_id` on children, or parent pointer — pick one in implementation and stick to it: **children point at parent** via `consolidates_invoice_id`).
- Certified path: our PDF is `PROFORMA` / supporting detail. Legal fatura (ATCUD) lives in certified software; store `certified_external_id`.
- Stripe SEPA: mandate on company/invoice; webhooks set `PAID` without a human.
- Manual resolve (bank / certified already paid): `MANUALLY_RESOLVED` + event with actor and reason. Never delete.
- IVA treatment: hammer later; keep `tax_amount` even if 0.

---

## Table: invoice_line

```sql
CREATE TABLE invoice_line (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoice(id),
    employee_id UUID REFERENCES employee(id),   -- internal only
    benefit_case_id UUID REFERENCES benefit_case(id),
    description VARCHAR(500) NOT NULL,          -- customer-safe, e.g. 'Success fee — Aug 2026'
    fee_amount NUMERIC(12, 2) NOT NULL,
    saving_amount NUMERIC(12, 2)                -- internal; omit from company serializer
);
```

Prefer **one generic line per invoice period** on the customer PDF, even if internally we explode per employee for audit.

---

## Table: payment

```sql
CREATE TABLE payment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoice(id),
    method VARCHAR(24) NOT NULL CHECK (method IN (
        'STRIPE_SEPA', 'STRIPE_OTHER', 'MANUAL', 'CERTIFIED'
    )),
    amount NUMERIC(12, 2) NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL,
    external_ref VARCHAR(128),
    raw_payload JSONB,                      -- webhook / certified payload only
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Table: invoice_status_event

```sql
CREATE TABLE invoice_status_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoice(id),
    from_status VARCHAR(24),
    to_status VARCHAR(24) NOT NULL,
    actor_user_id UUID REFERENCES user_base(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Append-only. Stripe webhook and manual resolve both write a row.
