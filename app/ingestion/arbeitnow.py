
import html
import logging
import re
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

API_URL = "https://www.arbeitnow.com/api/job-board-api"
SOURCE_NAME = "Arbeitnow"
SOURCE_SLUG = "arbeitnow"


def clean_html(value: str | None) -> str | None:
    """Convert an HTML description into readable plain text."""
    if not value:
        return None

    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", value,
                   flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def get_or_create_source(db: Session) -> JobSource:
    source = db.scalar(
        select(JobSource).where(JobSource.slug == SOURCE_SLUG)
    )

    if source is None:
        source = JobSource(
            name=SOURCE_NAME,
            slug=SOURCE_SLUG,
            base_url="https://www.arbeitnow.com",
            is_active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    return source


def ingest_arbeitnow(
    db: Session,
    days: int = 30,
    max_pages: int = 3,
    retry_attempts: int = 2,
    retry_backoff_seconds: float = 0.5,
) -> dict[str, int]:
    """Fetch recent remote jobs and save new listings to the database."""

    if days < 1 or max_pages < 1:
        raise ValueError("days and max_pages must be at least 1")

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
            raise ValueError("Arbeitnow source is disabled")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        with httpx.Client(timeout=20.0) as client:
            for page in range(1, max_pages + 1):
                response = get_with_retries(
                    lambda: client.get(API_URL, params={"page": page}),
                    retries=retry_attempts,
                    backoff_seconds=retry_backoff_seconds,
                )
                payload = response.json()

                jobs = payload.get("data", [])
                if not isinstance(jobs, list):
                    raise ValueError("Unexpected Arbeitnow API response")

                if not jobs:
                    break

                for item in jobs:
                    stats["fetched"] += 1
                    if not isinstance(item, dict):
                        stats["skipped"] += 1
                        continue

                    slug = item.get("slug")
                    title = item.get("title")
                    company = item.get("company_name")
                    url = item.get("url")
                    created_at = item.get("created_at")

                    if not all([slug, title, company, url, created_at]):
                        stats["skipped"] += 1
                        continue
                    if len(str(slug)) > 250:
                        stats["skipped"] += 1
                        continue

                    normalized_url = str(url).strip()
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
                    try:
                        parsed_url.port
                    except ValueError:
                        stats["skipped"] += 1
                        continue

                    try:
                        posted_at = datetime.fromtimestamp(
                            float(created_at), tz=timezone.utc
                        )
                    except (ValueError, TypeError, OverflowError, OSError):
                        stats["skipped"] += 1
                        continue

                    existing = db.scalar(
                        select(Job).where(
                            Job.source_id == source.id,
                            Job.external_id == str(slug),
                        )
                    )

                    if existing is not None:
                        existing.last_seen_at = datetime.now(timezone.utc)
                        stats["duplicates"] += 1
                        continue

                    if posted_at < cutoff:
                        stats["stale"] += 1
                        continue

                    # This first connector only imports listings explicitly
                    # marked remote by Arbeitnow.
                    if item.get("remote") is not True:
                        stats["skipped"] += 1
                        continue

                    normalized_title = str(title).strip()
                    normalized_company = str(company).strip()
                    if (
                        not normalized_title
                        or not normalized_company
                        or len(normalized_title) > 250
                        or len(normalized_company) > 200
                        or len(normalized_url) > 2048
                    ):
                        stats["skipped"] += 1
                        continue

                    duplicate_of_id = find_cross_source_duplicate(
                        db,
                        source_id=source.id,
                        title=normalized_title,
                        company=normalized_company,
                        url=normalized_url,
                    )
                    raw_tags = item.get("tags")
                    tags = raw_tags if isinstance(raw_tags, list) else []
                    raw_job_types = item.get("job_types")
                    job_types = (
                        raw_job_types
                        if isinstance(raw_job_types, list)
                        else []
                    )

                    raw_description = item.get("description")
                    description = clean_html(
                        raw_description
                        if isinstance(raw_description, str)
                        else None
                    )
                    if tags:
                        description = (
                            f"{description or ''}\n\nSkills/tags: "
                            + ", ".join(str(tag) for tag in tags)
                        ).strip()

                    location = (
                        str(item["location"])[:250]
                        if item.get("location") is not None
                        else None
                    )
                    remote_scope, eligibility_reason = classify_eligibility(
                        title=normalized_title,
                        description=description,
                        location=location,
                    )
                    eligibility_confidence = (
                        "inferred" if remote_scope != "unknown" else "unknown"
                    )
                    job = Job(
                        source_id=source.id,
                        external_id=str(slug),
                        title=normalized_title,
                        company=normalized_company,
                        url=normalized_url,
                        location=location,
                        description=description,
                        employment_type=(
                            ", ".join(str(value) for value in job_types)[:100]
                            or None
                        ),
                        posted_at=posted_at,

                        # Remote does not automatically mean worldwide.
                        # Leave geographic eligibility unconfirmed until
                        # a source explicitly provides that information.
                        remote_scope=remote_scope,
                        remote_status="remote",
                        region=None,
                        eligible_countries=[],
                        eligibility_confidence=eligibility_confidence,
                        eligibility_source=(
                            "arbeitnow_text"
                            if eligibility_confidence == "inferred"
                            else "arbeitnow_remote_flag"
                        ),
                        eligibility_reason=eligibility_reason,
                        duplicate_of_id=duplicate_of_id,
                    )

                    db.add(job)
                    stats["saved"] += 1
                    if duplicate_of_id is not None:
                        stats["duplicates"] += 1

                # Stop if the API has no next page.
                if not payload.get("links", {}).get("next"):
                    break

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error("Arbeitnow ingestion failed (%s)", type(exc).__name__)
        raise

    return stats
