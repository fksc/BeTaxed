# Infra — Cloud Run placeholders

Independent backend and frontend Cloud Run services (`KB/00_mother_doc.md`).

- `cloudrun/backend.service.yaml` — FastAPI (port 8080)
- `cloudrun/frontend.service.yaml` — Next.js standalone (port 3000)
- `gcp/cmek.md` — Cloud SQL and GCS CMEK setup (DEV-830)

Replace `PROJECT_ID`, `REGION`, and Artifact Registry paths before deploy. No CI/CD in this issue.
