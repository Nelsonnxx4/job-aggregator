import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Job, JobNotification
from app.services.job_scoring import assess_job

logger = logging.getLogger(__name__)

MAX_NOTIFICATION_BATCH = 100


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _eligibility(job: Job) -> tuple[str, str]:
    assessment = assess_job(
        title=job.title,
        description=job.description or "",
        location=job.location or "",
    )
    persisted_scope = job.remote_scope
    if (
        job.eligibility_confidence in {"verified", "inferred"}
        and persisted_scope
        in {
            "worldwide",
            "emea",
            "region_restricted",
            "country_restricted",
            "non_remote",
        }
    ):
        return persisted_scope, job.eligibility_reason or assessment.eligibility_reason
    if job.remote_status == "onsite":
        return "non_remote", "Listing is explicitly marked onsite"
    return assessment.eligibility, assessment.eligibility_reason


def _is_notification_candidate(
    job: Job,
    *,
    settings: Settings,
    cutoff: datetime,
) -> bool:
    if job.posted_at is None or _as_utc(job.posted_at) < cutoff:
        return False
    if job.remote_status != "remote":
        return False

    assessment = assess_job(
        title=job.title,
        description=job.description or "",
        location=job.location or "",
    )
    if assessment.relevance_score < settings.telegram_min_relevance_score:
        return False

    eligibility, _ = _eligibility(job)
    if eligibility in {"worldwide", "emea"}:
        return True
    return (
        settings.telegram_include_country_restricted
        and eligibility == "country_restricted"
        and any(country.casefold() == "nigeria" for country in job.eligible_countries)
    )


def _message(job: Job, eligibility: str, score: int) -> str:
    return (
        f"{job.title}\n"
        f"{job.company}\n"
        f"Relevance: {score}/100\n"
        f"Eligibility: {eligibility}\n"
        f"Apply: {job.url}"
    )


def _send_message(
    client: httpx.Client,
    *,
    token: str,
    chat_id: str,
    text: str,
    max_attempts: int,
    backoff_seconds: float,
) -> tuple[bool, datetime | None, str | None, int]:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.post(
                endpoint,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            if attempt < max_attempts:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))
                continue
            return False, None, type(exc).__name__, attempt
        except httpx.TransportError as exc:
            return False, None, type(exc).__name__, attempt

        if response.status_code == 429:
            retry_after: int | None = None
            try:
                payload = response.json()
            except ValueError:
                payload = {}
                logger.warning("Telegram rate-limit response was not valid JSON")
            if isinstance(payload, dict):
                parameters = payload.get("parameters")
                if isinstance(parameters, dict):
                    value = parameters.get("retry_after")
                    if isinstance(value, int) and value > 0:
                        retry_after = value
            delay = retry_after or max(
                1,
                int(backoff_seconds * (2 ** (attempt - 1))),
            )
            return (
                False,
                datetime.now(timezone.utc) + timedelta(seconds=delay),
                "TelegramRateLimited",
                attempt,
            )

        if response.status_code >= 500:
            if attempt < max_attempts:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))
                continue
            return False, None, "TelegramServerError", attempt

        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as exc:
            return False, None, type(exc).__name__, attempt

        if not isinstance(payload, dict) or payload.get("ok") is not True:
            return False, None, "TelegramRejectedMessage", attempt
        return True, None, None, attempt

    return False, None, "TelegramRetryLimitReached", max_attempts


def dispatch_job_notifications(
    db: Session,
    settings: Settings,
) -> dict[str, int | str]:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"status": "not_configured", "sent": 0, "failed": 0}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.ingestion_freshness_days)
    candidate_jobs = db.scalars(
        select(Job).where(
            Job.posted_at.is_not(None),
            Job.duplicate_of_id.is_(None),
        )
    ).all()
    queued = 0
    for job in candidate_jobs:
        if not _is_notification_candidate(
            job,
            settings=settings,
            cutoff=cutoff,
        ):
            continue
        notification_exists = db.scalar(
            select(JobNotification.id).where(
                JobNotification.job_id == job.id
            )
        )
        if notification_exists is not None:
            continue
        db.add(
            JobNotification(
                job_id=job.id,
                status="pending",
                next_attempt_at=now,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        queued += 1

    pending = db.scalars(
        select(JobNotification)
        .where(
            JobNotification.status == "pending",
            JobNotification.next_attempt_at <= now,
            JobNotification.attempts < settings.telegram_retry_attempts,
        )
        .order_by(JobNotification.created_at, JobNotification.id)
        .limit(MAX_NOTIFICATION_BATCH)
        .with_for_update(skip_locked=True)
    ).all()
    sent = 0
    failed = 0

    if not pending:
        return {
            "status": "completed",
            "queued": queued,
            "sent": sent,
            "failed": failed,
        }

    with httpx.Client(timeout=20.0) as client:
        for notification in pending:
            job = db.get(Job, notification.job_id)
            if job is None:
                notification.status = "failed"
                notification.error_summary = "JobNotFound"
                failed += 1
                db.commit()
                continue

            eligibility, _ = _eligibility(job)
            assessment = assess_job(
                title=job.title,
                description=job.description or "",
                location=job.location or "",
            )
            prior_attempts = notification.attempts
            notification.status = "sending"
            notification.attempts += 1
            notification.last_attempt_at = datetime.now(timezone.utc)
            notification.error_summary = None
            db.commit()

            success, retry_at, error, attempts_used = _send_message(
                client,
                token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                text=_message(
                    job,
                    eligibility,
                    assessment.relevance_score,
                ),
                max_attempts=max(
                    1,
                    settings.telegram_retry_attempts - prior_attempts,
                ),
                backoff_seconds=settings.telegram_retry_backoff_seconds,
            )
            notification.attempts += attempts_used - 1
            if success:
                notification.status = "sent"
                notification.sent_at = datetime.now(timezone.utc)
                notification.next_attempt_at = None
                sent += 1
            elif retry_at is not None and notification.attempts < (
                settings.telegram_retry_attempts
            ):
                notification.status = "pending"
                notification.next_attempt_at = retry_at
                notification.error_summary = error
            else:
                notification.status = "failed"
                notification.next_attempt_at = None
                notification.error_summary = error
                failed += 1
                logger.warning(
                    "Telegram delivery failed for job notification %s: %s",
                    notification.id,
                    error,
                )
            db.commit()

    return {
        "status": "completed",
        "queued": queued,
        "sent": sent,
        "failed": failed,
    }
