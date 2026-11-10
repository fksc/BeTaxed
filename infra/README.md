# Infra — Cloud Run placeholders

Independent backend and frontend Cloud Run services (`KB/00_mother_doc.md`).

- `cloudrun/backend.service.yaml` — FastAPI placeholder (port 8080)
- `cloudrun/frontend.service.yaml` — Next.js placeholder (port 3000)
- `cloudrun/backend.staging.yaml` — staging API, scale to 0, 1 CPU, 1Gi
- `cloudrun/frontend.staging.yaml` — staging web, scale to 0, 1 CPU, 512Mi
- `cloudbuild/backend.yaml` — build and push `anteater/backend:staging`
- `cloudbuild/frontend.yaml` — build and push `anteater/frontend:staging`
- `gcp/cmek.md` — Cloud SQL and GCS CMEK setup (DEV-830)

Staging images land in `europe-west1-docker.pkg.dev/project-76d4a590-35c3-4fa2-936/anteater`. Create that Docker repository once, then build, then `gcloud run services replace`. A service cannot be created for a tag that is not already in the registry.
