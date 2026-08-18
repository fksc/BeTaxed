# Cloud SQL and GCS CMEK (DEV-830)

Customer-managed encryption keys (CMEK) for data at rest. App-level envelope encryption for NISS/name/DOB is separate — see `KB/07_security_encryption.md`.

## Cloud SQL CMEK

1. Create a KMS key ring and key in the same region as the Cloud SQL instance.
2. Grant the Cloud SQL service account `cloudkms.cryptoKeyEncrypterDecrypter` on the key.
3. Create or migrate the instance with CMEK:

```bash
gcloud sql instances create betaxed-db \
  --database-version=POSTGRES_18 \
  --tier=db-custom-2-7680 \
  --region=REGION \
  --disk-auto-resize \
  --database-flags=cloudsql.enable_pgaudit=on \
  --disk-encryption-key=projects/PROJECT_ID/locations/REGION/keyRings/betaxed/keyRings/cryptoKeys/cloudsql-cmek
```

For an existing instance, use `gcloud sql instances patch` with `--disk-encryption-key` (requires maintenance window).

**OD-3:** Salary and billable amounts stay `NUMERIC` in this database — CMEK protects disks/backups, not live SQL sessions.

## GCS CMEK

1. Create a KMS key (can share key ring with Cloud SQL or use a dedicated `gcs-cmek` key).
2. Grant the GCS service account `cloudkms.cryptoKeyEncrypterDecrypter`.
3. Create the bucket with default encryption:

```bash
gcloud storage buckets create gs://betaxed-uploads-ENV \
  --location=REGION \
  --default-encryption-key=projects/PROJECT_ID/locations/REGION/keyRings/betaxed/cryptoKeys/gcs-cmek
```

4. Set backend env:

- `GCS_BUCKET=betaxed-uploads-ENV`
- `GCS_KMS_KEY_NAME=projects/PROJECT_ID/locations/REGION/keyRings/betaxed/cryptoKeys/gcs-cmek`

The backend sets `blob.kms_key_name` on upload so objects use CMEK even if the bucket default changes.

## App-level keys (not CMEK)

Set in Cloud Run / Secret Manager — never commit:

- `ENCRYPTION_MASTER_KEY` — base64-encoded 32-byte AES key wrapping per-tenant DEKs
- `NISS_HMAC_SECRET` — base64-encoded 32-byte secret for per-tenant `niss_hash`

Local DEV omits these and uses built-in dev-only defaults (`backend/.env.dev.example`).

## Wipe on decline

Delete GCS objects via `ObjectStorage.delete()` before removing `stored_file` rows (`KB/10`).
