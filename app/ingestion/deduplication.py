from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Job


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
}


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    port = parsed.port
    netloc = hostname
    if port and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
        and not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path.rstrip("/") or "/",
            urlencode(query, doseq=True),
            "",
        )
    )


def find_cross_source_duplicate(
    db: Session,
    *,
    source_id: int,
    title: str,
    company: str,
    url: str,
) -> int | None:
    candidates = db.scalars(
        select(Job).where(
            Job.source_id != source_id,
            func.lower(Job.title) == title.strip().lower(),
            func.lower(Job.company) == company.strip().lower(),
        )
    ).all()
    canonical_url = canonicalize_job_url(url)
    for candidate in candidates:
        if canonicalize_job_url(candidate.url) == canonical_url:
            return candidate.duplicate_of_id or candidate.id
    return None
