import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingestion.arbeitnow import clean_html
from app.models import Job, JobSource

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 250
MAX_COMPANY_LENGTH = 200
MAX_URL_LENGTH = 2048
MAX_LOCATION_LENGTH = 250
MAX_EMPLOYMENT_TYPE_LENGTH = 100
MAX_EXPERIENCE_LEVEL_LENGTH = 100
MAX_EXTERNAL_ID_LENGTH = 250


@dataclass(frozen=True)
class FeedSource:
    name: str
    slug: str
    base_url: str
    setting_name: str
    feed_url: str | None


@dataclass(frozen=True)
class FeedJob:
    external_id: str
    title: str
    company: str
    url: str
    posted_at: datetime
    description: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None


@dataclass(frozen=True)
class FeedIngestionResult:
    status: str
    stats: dict[str, int] | None = None
    error: str | None = None
    configuration: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"status": self.status}
        if self.stats is not None:
            result["stats"] = self.stats
        if self.error is not None:
            result["error"] = self.error
        if self.configuration is not None:
            result["configuration"] = self.configuration
        return result


def configured_feed_sources(settings: Settings) -> list[FeedSource]:
    return [
        FeedSource(
            name="Hiring Cafe",
            slug="hiring-cafe",
            base_url="https://hiringcafe.com",
            setting_name="HIRING_CAFE_FEED_URL",
            feed_url=settings.hiring_cafe_feed_url,
        ),
        FeedSource(
            name="Dover",
            slug="dover",
            base_url="https://www.dover.com",
            setting_name="DOVER_FEED_URL",
            feed_url=settings.dover_feed_url,
        ),
        FeedSource(
            name="Wellfound",
            slug="wellfound",
            base_url="https://wellfound.com",
            setting_name="WELLFOUND_FEED_URL",
            feed_url=settings.wellfound_feed_url,
        ),
        FeedSource(
            name="Jobberman",
            slug="jobberman",
            base_url="https://www.jobberman.com",
            setting_name="JOBBERMAN_FEED_URL",
            feed_url=settings.jobberman_feed_url,
        ),
        FeedSource(
            name="JobTogether",
            slug="jobtogether",
            base_url="https://jobtogether.com",
            setting_name="JOBTOGETHER_FEED_URL",
            feed_url=settings.jobtogether_feed_url,
        ),
    ]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _xml_text(element: ET.Element, names: Iterable[str]) -> str | None:
    wanted = {name.lower() for name in names}
    for child in element:
        if _local_name(child.tag) in wanted:
            text = " ".join(part.strip() for part in child.itertext())
            if text.strip():
                return text.strip()
    return None


def _xml_author(element: ET.Element) -> str | None:
    for child in element:
        if _local_name(child.tag) in {"author", "creator"}:
            name = _xml_text(child, {"name"})
            if name:
                return name
            text = " ".join(part.strip() for part in child.itertext()).strip()
            if text:
                return text
    return None


def _xml_link(element: ET.Element) -> str | None:
    for child in element:
        if _local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href and child.attrib.get("rel", "alternate") == "alternate":
                return href.strip()
            text = (child.text or "").strip()
            if text:
                return text
    return None


def _json_author(item: dict[str, Any]) -> str | None:
    author = item.get("author")
    if isinstance(author, str):
        return author.strip() or None
    if isinstance(author, dict):
        name = author.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    authors = item.get("authors")
    if isinstance(authors, list):
        for entry in authors:
            if isinstance(entry, dict):
                name = entry.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
            elif isinstance(entry, str) and entry.strip():
                return entry.strip()
    return None


def _json_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_posted_at(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            parsed = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            raw_value = value.strip()
            if not raw_value:
                return None
            try:
                parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            except ValueError:
                parsed = parsedate_to_datetime(raw_value)
    except (ValueError, TypeError, OverflowError, OSError):
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_feed_job(
    *,
    item_id: str | None,
    title: str | None,
    company: str | None,
    url: str | None,
    posted_at: datetime | None,
    description: str | None,
    location: str | None,
    employment_type: str | None,
    experience_level: str | None,
    feed_url: str,
) -> FeedJob | None:
    if not title or not company or not url or posted_at is None:
        return None

    normalized_url = urljoin(feed_url, url)
    if urlparse(normalized_url).scheme not in {"http", "https"}:
        return None

    normalized_title = title.strip()
    normalized_company = company.strip()
    if (
        not normalized_title
        or len(normalized_title) > MAX_TITLE_LENGTH
        or not normalized_company
        or len(normalized_company) > MAX_COMPANY_LENGTH
        or len(normalized_url) > MAX_URL_LENGTH
    ):
        return None

    external_id = (item_id or normalized_url).strip()
    if not external_id:
        return None
    if len(external_id) > MAX_EXTERNAL_ID_LENGTH:
        external_id = hashlib.sha256(external_id.encode("utf-8")).hexdigest()

    normalized_description = clean_html(description)
    normalized_location = location.strip() if location else None
    normalized_employment_type = (
        employment_type.strip() if employment_type else None
    )
    if normalized_employment_type and len(normalized_employment_type) > (
        MAX_EMPLOYMENT_TYPE_LENGTH
    ):
        normalized_employment_type = None
    normalized_experience_level = (
        experience_level.strip() if experience_level else None
    )
    if normalized_experience_level and len(normalized_experience_level) > (
        MAX_EXPERIENCE_LEVEL_LENGTH
    ):
        normalized_experience_level = None

    return FeedJob(
        external_id=external_id,
        title=normalized_title,
        company=normalized_company,
        url=normalized_url,
        posted_at=posted_at,
        description=normalized_description,
        location=normalized_location[:MAX_LOCATION_LENGTH]
        if normalized_location
        else None,
        employment_type=normalized_employment_type,
        experience_level=normalized_experience_level,
    )


def _parse_json_feed(payload: dict[str, Any], feed_url: str) -> list[FeedJob]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Unexpected JSON Feed response: items must be a list")

    parsed_jobs: list[FeedJob] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        company = _json_string(
            item, "company", "company_name", "employer", "organization"
        ) or _json_author(item)
        job = _to_feed_job(
            item_id=_json_string(item, "id"),
            title=_json_string(item, "title"),
            company=company,
            url=_json_string(item, "url", "external_url"),
            posted_at=_parse_posted_at(
                item.get("date_published") or item.get("date_modified")
            ),
            description=_json_string(
                item, "content_html", "content_text", "summary"
            ),
            location=_json_string(item, "location", "job_location"),
            employment_type=_json_string(
                item, "employment_type", "job_type"
            ),
            experience_level=_json_string(
                item, "experience_level", "seniority"
            ),
            feed_url=feed_url,
        )
        if job is not None:
            parsed_jobs.append(job)
    return parsed_jobs


def _parse_xml_feed(payload: str, feed_url: str) -> list[FeedJob]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("Feed response is not valid XML") from exc

    entries = [
        element
        for element in root.iter()
        if _local_name(element.tag) in {"item", "entry"}
    ]
    if not entries and _local_name(root.tag) not in {"rss", "feed", "rdf"}:
        raise ValueError("XML feed contains no RSS items or Atom entries")

    parsed_jobs: list[FeedJob] = []
    for entry in entries:
        company = _xml_text(
            entry, {"company", "company_name", "employer", "organization"}
        ) or _xml_author(entry)
        job = _to_feed_job(
            item_id=_xml_text(entry, {"guid", "id"}),
            title=_xml_text(entry, {"title"}),
            company=company,
            url=_xml_link(entry),
            posted_at=_parse_posted_at(
                _xml_text(entry, {"pubdate", "published", "updated", "date"})
            ),
            description=_xml_text(
                entry, {"description", "summary", "content", "encoded"}
            ),
            location=_xml_text(entry, {"location", "job_location"}),
            employment_type=_xml_text(
                entry, {"employment_type", "job_type"}
            ),
            experience_level=_xml_text(
                entry, {"experience_level", "seniority"}
            ),
            feed_url=feed_url,
        )
        if job is not None:
            parsed_jobs.append(job)
    return parsed_jobs


def parse_job_feed(payload: str, feed_url: str) -> list[FeedJob]:
    content = payload.lstrip()
    if content.startswith("{"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Feed response is not valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Unexpected JSON Feed response")
        return _parse_json_feed(data, feed_url)
    return _parse_xml_feed(payload, feed_url)


def _get_or_create_source(db: Session, source: FeedSource) -> JobSource:
    existing_source = db.scalar(
        select(JobSource).where(JobSource.slug == source.slug)
    )
    if existing_source is not None:
        return existing_source

    new_source = JobSource(
        name=source.name,
        slug=source.slug,
        base_url=source.base_url,
        is_active=True,
    )
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return new_source


def _validated_feed_url(feed_url: str) -> str:
    parsed = urlparse(feed_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Feed URL must be an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("Feed URL must not include embedded credentials")
    return feed_url


def ingest_job_feed(
    db: Session,
    source: FeedSource,
    *,
    days: int = 30,
) -> dict[str, int]:
    if days < 1:
        raise ValueError("days must be at least 1")
    if not source.feed_url:
        raise ValueError(f"{source.setting_name} is not configured")

    feed_url = _validated_feed_url(source.feed_url)
    stats = {
        "fetched": 0,
        "saved": 0,
        "duplicates": 0,
        "stale": 0,
        "skipped": 0,
    }

    try:
        db_source = _get_or_create_source(db, source)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                feed_url,
                headers={
                    "Accept": (
                        "application/feed+json, application/json, "
                        "application/atom+xml, application/rss+xml, "
                        "application/xml, text/xml"
                    )
                },
            )
            response.raise_for_status()

        jobs = parse_job_feed(response.text, feed_url)
        stats["fetched"] = _count_feed_entries(response.text)
        for job in jobs:
            if job.posted_at < cutoff:
                stats["stale"] += 1
                continue

            existing_job = db.scalar(
                select(Job.id).where(
                    Job.source_id == db_source.id,
                    Job.external_id == job.external_id,
                )
            )
            if existing_job is not None:
                stats["duplicates"] += 1
                continue

            db.add(
                Job(
                    source_id=db_source.id,
                    external_id=job.external_id,
                    title=job.title,
                    company=job.company,
                    url=job.url,
                    description=job.description,
                    location=job.location,
                    employment_type=job.employment_type,
                    experience_level=job.experience_level,
                    posted_at=job.posted_at,
                    remote_scope="unknown",
                    region=None,
                )
            )
            stats["saved"] += 1

        stats["skipped"] = stats["fetched"] - len(jobs)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Job feed ingestion failed for source %s", source.slug)
        raise

    return stats


def _count_feed_entries(payload: str) -> int:
    content = payload.lstrip()
    if content.startswith("{"):
        data = json.loads(content)
        items = data.get("items")
        if not isinstance(items, list):
            raise ValueError("Unexpected JSON Feed response: items must be a list")
        return len(items)

    root = ET.fromstring(payload)
    return sum(
        1
        for element in root.iter()
        if _local_name(element.tag) in {"item", "entry"}
    )


def ingest_configured_job_feeds(
    db: Session,
    settings: Settings,
    *,
    days: int = 30,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for source in configured_feed_sources(settings):
        if not source.feed_url:
            results[source.slug] = FeedIngestionResult(
                status="not_configured",
                configuration=source.setting_name,
            ).as_dict()
            continue

        try:
            stats = ingest_job_feed(db, source, days=days)
        except Exception as exc:
            results[source.slug] = FeedIngestionResult(
                status="failed",
                error=type(exc).__name__,
            ).as_dict()
            continue

        results[source.slug] = FeedIngestionResult(
            status="completed",
            stats=stats,
        ).as_dict()

    return results
