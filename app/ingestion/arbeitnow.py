
import html
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobSource

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
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        with httpx.Client(timeout=20.0) as client:
            for page in range(1, max_pages + 1):
                response = client.get(API_URL, params={"page": page})
                response.raise_for_status()
                payload = response.json()

                jobs = payload.get("data", [])
                if not isinstance(jobs, list):
                    raise ValueError("Unexpected Arbeitnow API response")

                if not jobs:
                    break

                for item in jobs:
                    stats["fetched"] += 1

                    slug = item.get("slug")
                    title = item.get("title")
                    company = item.get("company_name")
                    url = item.get("url")
                    created_at = item.get("created_at")

                    if not all([slug, title, company, url, created_at]):
                        stats["skipped"] += 1
                        continue

                    try:
                        posted_at = datetime.fromtimestamp(
                            float(created_at), tz=timezone.utc
                        )
                    except (ValueError, TypeError, OverflowError, OSError):
                        stats["skipped"] += 1
                        continue

                    if posted_at < cutoff:
                        stats["stale"] += 1
                        continue

                    # This first connector only imports listings explicitly
                    # marked remote by Arbeitnow.
                    if item.get("remote") is not True:
                        stats["skipped"] += 1
                        continue

                    existing = db.scalar(
                        select(Job.id).where(
                            Job.source_id == source.id,
                            Job.external_id == str(slug),
                        )
                    )

                    if existing is not None:
                        stats["duplicates"] += 1
                        continue

                    tags = item.get("tags") or []
                    job_types = item.get("job_types") or []

                    description = clean_html(item.get("description"))
                    if tags:
                        description = (
                            f"{description or ''}\n\nSkills/tags: "
                            + ", ".join(str(tag) for tag in tags)
                        ).strip()

                    job = Job(
                        source_id=source.id,
                        external_id=str(slug),
                        title=str(title).strip(),
                        company=str(company).strip(),
                        url=str(url),
                        location=item.get("location"),
                        description=description,
                        employment_type=", ".join(job_types) or None,
                        posted_at=posted_at,

                        # Remote does not automatically mean worldwide.
                        # Leave geographic eligibility unconfirmed until
                        # a source explicitly provides that information.
                        remote_scope="unknown",
                        region=None,
                    )

                    db.add(job)
                    stats["saved"] += 1

                # Save each page, not every individual record.
                db.commit()

                # Stop if the API has no next page.
                if not payload.get("links", {}).get("next"):
                    break

    except Exception:
        db.rollback()
        logger.exception("Arbeitnow ingestion failed")
        raise

    return stats
