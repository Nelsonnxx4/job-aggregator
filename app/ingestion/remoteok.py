import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.arbeitnow import clean_html
from app.ingestion.deduplication import find_cross_source_duplicate
from app.ingestion.http import get_with_retries
from app.models import Job, JobSource
from app.services.job_scoring import classify_eligibility

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"
SOURCE_NAME = "Remote OK"
SOURCE_SLUG = "remoteok"
SOURCE_URL = "https://remoteok.com"


def get_or_create_source(db: Session) -> JobSource:
    source = db.scalar(select(JobSource).where(JobSource.slug == SOURCE_SLUG))
    if source is None:
        source = JobSource(
            name=SOURCE_NAME,
            slug=SOURCE_SLUG,
            base_url=SOURCE_URL,
            is_active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def _remoteok_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    parsed = urlparse(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"remoteok.com", "www.remoteok.com"}
        or parsed.username
        or parsed.password
    ):
        return None
    try:
        parsed.port
    except ValueError:
        return None
    return value.strip()


def ingest_remoteok(
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
            raise ValueError("Remote OK source is disabled")

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

        if not isinstance(payload, list):
            raise ValueError("Unexpected Remote OK API response")

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for item in payload:
            if not isinstance(item, dict) or "legal" in item:
                continue

            stats["fetched"] += 1
            external_id = item.get("id")
            title = item.get("position")
            company = item.get("company")
            url = _remoteok_url(item.get("url"))
            try:
                posted_at = datetime.fromtimestamp(
                    float(item["epoch"]), tz=timezone.utc
                )
            except (KeyError, ValueError, TypeError, OverflowError, OSError):
                stats["skipped"] += 1
                continue

            if (
                external_id is None
                or not str(external_id).strip()
                or len(str(external_id)) > 250
                or not isinstance(title, str)
                or not isinstance(company, str)
                or not url
            ):
                stats["skipped"] += 1
                continue

            normalized_title = title.strip()
            normalized_company = company.strip()
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

            raw_tags = item.get("tags")
            tags = (
                [tag.strip() for tag in raw_tags if isinstance(tag, str) and tag.strip()]
                if isinstance(raw_tags, list)
                else []
            )
            raw_description = item.get("description")
            description = clean_html(
                raw_description if isinstance(raw_description, str) else None
            )
            if tags:
                description = (
                    f"{description or ''}\n\nSkills/tags: " + ", ".join(tags)
                ).strip()
            location = item.get("location")
            location = location[:250] if isinstance(location, str) else None
            remote_scope, eligibility_reason = classify_eligibility(
                title=normalized_title,
                description=description,
                location=location,
            )
            duplicate_of_id = find_cross_source_duplicate(
                db,
                source_id=source.id,
                title=normalized_title,
                company=normalized_company,
                url=url,
            )

            db.add(
                Job(
                    source_id=source.id,
                    external_id=str(external_id),
                    title=normalized_title,
                    company=normalized_company,
                    url=url,
                    location=location,
                    description=description,
                    employment_type=(
                        str(item["position_type"])[:100]
                        if item.get("position_type")
                        else None
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
                        "remoteok_text"
                        if remote_scope != "unknown"
                        else "remoteok_remote_board"
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
        logger.error("Remote OK ingestion failed (%s)", type(exc).__name__)
        raise

    return stats
