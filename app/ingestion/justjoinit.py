import logging
import os
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

API_URL = "https://api.justjoin.it/v2/user-panel/offers"
SOURCE_NAME = "JustJoin.it"
SOURCE_SLUG = "justjoinit"
JOB_URL_PREFIX = "https://justjoin.it/job-offer/"
DEFAULT_CATEGORIES = (1, 2)


def _categories_from_env() -> tuple[int, ...]:
    raw = os.getenv("JUSTJOINIT_CATEGORIES", "").strip()
    if not raw:
        return DEFAULT_CATEGORIES

    values: list[int] = []
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            values.append(int(value))
        except ValueError:
            continue
    return tuple(values) if values else DEFAULT_CATEGORIES


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


def _build_location(item: dict[str, object]) -> str | None:
    city = str(item.get("city") or "").strip()
    workplace = str(item.get("workplaceType") or "").strip()
    multi_locations: list[str] = []
    for location in item.get("multilocation") or []:
        if not isinstance(location, dict):
            continue
        value = str(location.get("city") or "").strip()
        if value and value.lower() != city.lower():
            multi_locations.append(value)

    parts: list[str] = []
    if city:
        parts.append(city)
    if multi_locations:
        parts.append("+ " + ", ".join(multi_locations[:3]))
    if workplace and workplace.lower() != "office":
        parts.append(f"({workplace})")
    if not parts:
        return None
    return " ".join(parts)


def _build_description(item: dict[str, object]) -> str | None:
    text_bits: list[str] = []
    skills = item.get("requiredSkills")
    if isinstance(skills, list):
        normalized = [str(skill).strip() for skill in skills if str(skill).strip()]
        if normalized:
            text_bits.append("Skills: " + ", ".join(normalized[:12]))

    experience = str(item.get("experienceLevel") or "").strip()
    if experience:
        text_bits.append(f"Experience level: {experience}")

    employment_types = item.get("employmentTypes")
    if isinstance(employment_types, list):
        for entry in employment_types:
            if not isinstance(entry, dict):
                continue
            type_name = str(entry.get("type") or "").strip()
            lower_bound = entry.get("from")
            upper_bound = entry.get("to")
            currency = str(entry.get("currency") or "").strip()
            if type_name:
                payload = f"{type_name}"
                if lower_bound or upper_bound or currency:
                    payload = f"{payload} ({lower_bound or '?'}-{upper_bound or '?'} {currency})".strip()
                text_bits.append(f"Employment: {payload}")
                break

    return "\n".join(text_bits) if text_bits else None


def get_or_create_source(db: Session) -> JobSource:
    source = db.scalar(select(JobSource).where(JobSource.slug == SOURCE_SLUG))
    if source is None:
        source = JobSource(
            name=SOURCE_NAME,
            slug=SOURCE_SLUG,
            base_url="https://justjoin.it",
            is_active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def ingest_justjoinit(
    db: Session,
    *,
    days: int = 30,
    max_pages: int = 1,
    retry_attempts: int = 2,
    retry_backoff_seconds: float = 0.5,
) -> dict[str, int]:
    if days < 1 or max_pages < 1:
        raise ValueError("days and max_pages must be at least 1")

    stats = {
        "fetched": 0,
        "saved": 0,
        "duplicates": 0,
        "stale": 0,
        "skipped": 0,
    }
    source = get_or_create_source(db)
    if not source.is_active:
        raise ValueError("JustJoin.it source is disabled")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    categories = _categories_from_env()
    seen_slugs: set[str] = set()

    try:
        for category in categories:
            for page in range(1, max_pages + 1):
                params = [
                    ("categories[0]", str(category)),
                    ("perPage", "50"),
                    ("sortBy", "newest"),
                    ("page", str(page)),
                ]
                with httpx.Client(timeout=20.0) as client:
                    response = get_with_retries(
                        lambda: client.get(API_URL, params=params, headers={
                            "Accept": "application/json",
                            "User-Agent": "RemoteRolesJobAggregator/1.0",
                            "Referer": "https://justjoin.it/",
                            "Origin": "https://justjoin.it",
                        }),
                        retries=retry_attempts,
                        backoff_seconds=retry_backoff_seconds,
                    )
                payload = response.json()
                offers: list[dict[str, object]] = []
                if isinstance(payload, dict):
                    if isinstance(payload.get("data"), list):
                        offers = payload["data"]
                    elif isinstance(payload.get("offers"), list):
                        offers = payload["offers"]
                elif isinstance(payload, list):
                    offers = payload

                if not offers:
                    break

                for item in offers:
                    if not isinstance(item, dict):
                        continue
                    stats["fetched"] += 1
                    slug = str(item.get("slug") or "").strip()
                    if not slug or slug in seen_slugs:
                        stats["skipped"] += 1
                        continue
                    seen_slugs.add(slug)

                    title = str(item.get("title") or "").strip()
                    company = str(item.get("companyName") or "").strip()
                    if not title or not company:
                        stats["skipped"] += 1
                        continue

                    url = JOB_URL_PREFIX + slug
                    posted_at = _parse_posted_at(item.get("publishedAt"))
                    if posted_at is None:
                        stats["skipped"] += 1
                        continue

                    existing = db.scalar(
                        select(Job).where(
                            Job.source_id == source.id,
                            Job.external_id == slug,
                        )
                    )
                    if existing is not None:
                        existing.last_seen_at = datetime.now(timezone.utc)
                        stats["duplicates"] += 1
                        continue

                    if posted_at < cutoff:
                        stats["stale"] += 1
                        continue

                    workplace = str(item.get("workplaceType") or "").strip().lower()
                    location = _build_location(item)
                    description = _build_description(item)
                    remote_scope, eligibility_reason = classify_eligibility(
                        title=title,
                        description=description,
                        location=location,
                    )
                    if workplace == "remote" or "remote" in (location or "").lower():
                        remote_status = "remote"
                    elif workplace == "hybrid":
                        remote_status = "hybrid"
                    else:
                        remote_status = "unknown"

                    duplicate_of_id = find_cross_source_duplicate(
                        db,
                        source_id=source.id,
                        title=title,
                        company=company,
                        url=url,
                    )

                    db.add(
                        Job(
                            source_id=source.id,
                            external_id=slug,
                            title=title,
                            company=company,
                            url=url,
                            location=location,
                            description=description,
                            employment_type=(
                                str(item.get("employmentTypes") or "")[:100]
                                if isinstance(item.get("employmentTypes"), str)
                                else None
                            ),
                            experience_level=(
                                str(item.get("experienceLevel") or "").strip()[:100]
                                or None
                            ),
                            posted_at=posted_at,
                            remote_scope=remote_scope,
                            remote_status=remote_status,
                            region=None,
                            eligible_countries=[],
                            eligibility_confidence=(
                                "inferred" if remote_scope != "unknown" else "unknown"
                            ),
                            eligibility_source=(
                                "justjoinit_text"
                                if remote_scope != "unknown"
                                else "justjoinit_api"
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
        logger.error("JustJoin.it ingestion failed (%s)", type(exc).__name__)
        raise

    return stats
