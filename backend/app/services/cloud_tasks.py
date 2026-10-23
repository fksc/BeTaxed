"""Enqueue contract jobs on the existing Cloud Tasks queue.

The queue retry limit lives in GCP (`maxAttempts` on `betaxed-staging`).
This module does not change it. Inline work runs when the target URL is unset.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import uuid

from app.settings import (
    get_cloud_tasks_invoker_sa,
    get_cloud_tasks_location,
    get_cloud_tasks_oidc_audience,
    get_cloud_tasks_queue,
    get_cloud_tasks_target_url,
    get_internal_job_token,
)

logger = logging.getLogger(__name__)


def contract_tasks_configured() -> bool:
    url = os.environ.get("CLOUD_TASKS_TARGET_URL", "").strip()
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        or os.environ.get("GCP_PROJECT", "").strip()
    )
    return bool(url and project)


def should_retry_task(retry_count: int | None) -> bool:
    """First Cloud Tasks delivery sends retry count 0. One more try, then stop."""
    return retry_count is not None and retry_count < 1


def enqueue_contract_inbox(inbox_id: uuid.UUID) -> None:
    _enqueue({"inbox_id": str(inbox_id)})


def enqueue_contract_review(document_id: uuid.UUID) -> None:
    _enqueue({"employment_document_id": str(document_id)})


def worker_authorized(authorization: str | None, job_token: str | None) -> bool:
    expected = get_internal_job_token()
    if expected and job_token and hmac.compare_digest(job_token, expected):
        return True
    if not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False
    audience = get_cloud_tasks_oidc_audience()
    if not audience:
        return False
    return _oidc_ok(token.strip(), audience)


def _enqueue(payload: dict) -> None:
    target = get_cloud_tasks_target_url()
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        or os.environ.get("GCP_PROJECT", "").strip()
    )
    if not target or not project:
        raise RuntimeError("CLOUD_TASKS_TARGET_URL and GOOGLE_CLOUD_PROJECT are required")

    from google.cloud import tasks_v2

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, get_cloud_tasks_location(), get_cloud_tasks_queue())
    headers = {"Content-Type": "application/json"}
    token = get_internal_job_token()
    if token:
        headers["X-Internal-Job-Token"] = token
    http_request: dict = {
        "http_method": tasks_v2.HttpMethod.POST,
        "url": target,
        "headers": headers,
        "body": json.dumps(payload).encode(),
    }
    invoker = get_cloud_tasks_invoker_sa()
    if invoker:
        http_request["oidc_token"] = {
            "service_account_email": invoker,
            "audience": get_cloud_tasks_oidc_audience() or target,
        }
    client.create_task(request={"parent": parent, "task": {"http_request": http_request}})


def _oidc_ok(token: str, audience: str) -> bool:
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        id_token.verify_oauth2_token(token, google_requests.Request(), audience)
    except Exception:
        logger.info("contract worker oidc rejected")
        return False
    return True
