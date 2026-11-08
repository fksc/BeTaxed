# CI/CD — Anteater

Branch flow:

```
Feature/DEV-xxx → PR → dev → (staging) → Release PR → main → (production)
```

## Workflows

| File | Trigger | What it does |
| --- | --- | --- |
| `workflows/deploy-staging.yml` | Push to `dev` | Build images, Alembic through the Cloud SQL proxy, swap the Cloud Run image, sync Linear Anteater-Staging |
| `workflows/deploy-production.yml` | Manual only, for now | Same path for production. It does not run on a push to `main` until production Cloud Run is finished |

`gcloud run deploy` changes the image only. Environment variables, secrets, the service account, and Cloud SQL stay on the existing service.

A merge that does not touch `backend/**` or `frontend/**` does not deploy. Use **Run workflow** with the force inputs on production when a release must ship unchanged paths.

## GitHub environments

`staging` and `production` already hold `LINEAR_ACCESS_KEY_STAGING` and `LINEAR_ACCESS_KEY_PRODUCTION`.

Each environment also needs:

| Name | Kind | Purpose |
| --- | --- | --- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | secret | Workload Identity provider resource name |
| `GCP_SERVICE_ACCOUNT` | secret | `anteater-deploy@project-76d4a590-35c3-4fa2-936.iam.gserviceaccount.com` |
| `DATABASE_URL` | secret | Async SQLAlchemy URL. The workflow rewrites the Cloud SQL socket host to `127.0.0.1:5432` for Alembic |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | secret | Firebase web API key, inlined into the frontend image |
| `NEXT_PUBLIC_API_URL` | variable | Backend origin baked into the frontend image |
| `NEXT_PUBLIC_MARKETING_URL` | variable | Marketing site origin baked into the frontend image. Defaults to `https://anteater.pt` |
| `CLOUD_SQL_CONNECTION_NAME` | variable | Optional. Defaults are `anteater-staging` and `anteater-prod` |

See `.KB/GIT_STRATEGY.md`.
