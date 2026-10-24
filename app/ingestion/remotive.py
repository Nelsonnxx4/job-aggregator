import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.deduplication import find_cross_source_duplicate
from app.ingestion.http import get_with_retries
from app.models import Job, JobSource
from app.services.job_scoring import classify_eligibility

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"
SOURCE_NAME = "Remotive"
SOURCE_SLUG = "remotive"


def get_or_create_source(db: Session) -> JobSource:
    source = db.scalar(select(JobSource).where(JobSource.slug == SOURCE_SLUG))
    if source is None:
        source = JobSource(
            name=SOURCE_NAME,
            slug=SOURCE_SLUG,
            base_url="https://remotive.com",
            is_active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def _parse_posted_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def ingest_remotive(
    db: Session,
    *,
    days: int = 30,
    retry_attempts: int = 2,
    retry_backoff_seconds: float = 0.5,
) -> dict[str, int]:
    if days < 1:
        raise ValueError("days must be at least 1")

    stats = {
        "fetched": 0,
        "saved": 0,
        "duplicates": 0,
        "stale": 0,
        "skipped": 0,
    }

    try:
        source = get_or_create_source(db)
        if not source.is_active:
            raise ValueError("Remotive source is disabled")

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with httpx.Client(
            timeout=20.0,
            headers={"User-Agent": "RemoteRolesJobAggregator/1.0"},
        ) as client:
            response = get_with_retries(
                lambda: client.get(API_URL),
                retries=retry_attempts,
                backoff_seconds=retry_backoff_seconds,
            )
            payload = response.json()

        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise ValueError("Unexpected Remotive API response")

        for item in jobs:
            if not isinstance(item, dict):
                continue

            stats["fetched"] += 1
            external_id = item.get("id")
            title = item.get("title")
            company = item.get("company_name")
            url = item.get("url")
            posted_at = _parse_posted_at(item.get("publication_date"))
            if (
                external_id is None
                or not str(external_id).strip()
                or not isinstance(title, str)
                or not isinstance(company, str)
                or not isinstance(url, str)
                or posted_at is None
            ):
                stats["skipped"] += 1
                continue

            normalized_title = title.strip()
            normalized_company = company.strip()
            normalized_url = url.strip()
            parsed_url = urlparse(normalized_url)
            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.hostname
                or parsed_url.username
                or parsed_url.password
                or len(normalized_url) > 2048
            ):
                stats["skipped"] += 1
                continue

            if (
                not normalized_title
                or len(normalized_title) > 250
                or not normalized_company
                or len(normalized_company) > 200
            ):
                stats["skipped"] += 1
                continue

            existing = db.scalar(
                select(Job).where(
                    Job.source_id == source.id,
                    Job.external_id == str(external_id),
                )
            )
            if existing is not None:
                existing.last_seen_at = datetime.now(timezone.utc)
                stats["duplicates"] += 1
                continue

            if posted_at < cutoff:
                stats["stale"] += 1
                continue

            location = item.get("candidate_required_location")
            location_value = location[:250] if isinstance(location, str) else None
            description = item.get("description")
            description_value = (
                description.strip() if isinstance(description, str) else None
            )
            remote_scope, eligibility_reason = classify_eligibility(
                title=normalized_title,
                description=description_value,
                location=location_value,
            )
            duplicate_of_id = find_cross_source_duplicate(
                db,
                source_id=source.id,
                title=normalized_title,
                company=normalized_company,
                url=normalized_url,
            )

            db.add(
                Job(
                    source_id=source.id,
                    external_id=str(external_id),
                    title=normalized_title,
                    company=normalized_company,
                    url=normalized_url,
                    location=location_value,
                    description=description_value,
                    employment_type=(
                        str(item.get("job_type") or "").strip()[:100]
                        or None
                    ),
                    posted_at=posted_at,
                    remote_scope=remote_scope,
                    remote_status="remote",
                    region=None,
                    eligible_countries=[],
                    eligibility_confidence=(
                        "inferred" if remote_scope != "unknown" else "unknown"
                    ),
                    eligibility_source=(
                        "remotive_text" if remote_scope != "unknown" else "remotive_api"
                    ),
                    eligibility_reason=eligibility_reason,
                    duplicate_of_id=duplicate_of_id,
                )
            )
            stats["saved"] += 1
            if duplicate_of_id is not None:
                stats["duplicates"] += 1

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Remotive ingestion failed (%s)", type(exc).__name__)
        raise

    return stats
