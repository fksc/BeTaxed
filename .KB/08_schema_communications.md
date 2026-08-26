# KB/08_schema_communications.md — Domain events and notifications
**Depends on:** `KB/00_mother_doc.md`, `KB/01_schema_core.md`, `KB/04_schema_documents.md`
**Shape:** Talent Journey V2 communications — BeTaxed-sized. No chat. **No general email product** in v1 — exception: company **invite** mail (DEV-852, SMTP or copy-link).

---

## Rule

Business services **do not** insert `notification` rows or publish Redis. They emit `domain_event` in the **same transaction** as the write. After commit, fan-out creates per-recipient rows and publishes a wake-up.

Redis is **not** the job queue and **not** the notification store. Channel `user:{user_id}:notifications` carries a small JSON ping (`notification_created` + ids). The feed is Postgres.

---

## Table: domain_event

```sql
CREATE TABLE domain_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(60) NOT NULL,
    source_entity_type VARCHAR(32) NOT NULL,
    source_entity_id UUID NOT NULL,
    actor_id UUID REFERENCES user_base(id),
    company_id UUID REFERENCES company(id),
    payload JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

v1 event types:

| Type | Source | Recipients |
|---|---|---|
| `CONTRACT_UPLOADED` | `employment_document` | Company Admin/HR + all `BETAXED_STAFF` |
| `CONTRACT_REVIEWED` | `employment_document` | Staff (match / reviewed) |
| `CONTRACT_SS_MISMATCH` | `employment_document` | Staff only (non-optional) |
| `CONTRACT_REVIEW_FAILED` | `employment_document` | Staff only |
| `COMPANY_MEMBER_INVITED` | `company_invite` | Company Admin + all `BETAXED_STAFF` |

Payload may include ids, filename, and (staff events) SS vs paper fields. Never NISS, rates, remaining months, or “convert this contract”.

---

## Table: notification

```sql
CREATE TABLE notification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES user_base(id),
    domain_event_id UUID NOT NULL REFERENCES domain_event(id),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    in_app_delivered BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (domain_event_id, recipient_id)
);
```

Fan-out: `INSERT … ON CONFLICT DO NOTHING`. Redis publish is fire-and-forget.

Live UI: SSE `GET /v1/notifications/stream` (direct to FastAPI, ~50s then client reconnect). Do not hold a DB session on the stream.

---

## Workers

Local / unset Cloud Tasks: inline after commit (same as TJ fallback).

Parked: Cloud Tasks queues so the HTTP upload does not wait on Vertex (`KB/90` SL-010). Email delivery is not a general v1 channel. **Invite mail** (DEV-852) is the exception: Resend or Brevo when an API key is set (`EMAIL_PROVIDER`, `RESEND_API_KEY`, `BREVO_API_KEY`, `EMAIL_FROM`); otherwise the sender receives `invite_url` to copy. Do not build a notification-email product here.
