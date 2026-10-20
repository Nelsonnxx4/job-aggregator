import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IngestionRun, JobSource

logger = logging.getLogger(__name__)
STALE_RUN_AGE = timedelta(hours=2)


class IngestionAlreadyRunning(RuntimeError):
    pass


def execute_tracked_ingestion(
    db: Session,
    *,
    source_name: str,
    source_slug: str,
    ingest: Callable[[], dict[str, int]],
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    active_run = db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.source_slug == source_slug,
            IngestionRun.status == "running",
        )
        .order_by(IngestionRun.started_at.desc())
    )
    if active_run is not None:
        started_at = active_run.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if started_at <= now - STALE_RUN_AGE:
            active_run.status = "failed"
            active_run.finished_at = now
            active_run.failed = 1
            active_run.error_summary = "StaleRunRecovered"
            db.commit()
        else:
            raise IngestionAlreadyRunning(
                f"Ingestion is already running for {source_slug}"
            )

    source = db.scalar(
        select(JobSource).where(JobSource.slug == source_slug)
    )
    run = IngestionRun(
        source_id=source.id if source is not None else None,
        source_slug=source_slug,
        source_name=source_name,
        status="running",
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise IngestionAlreadyRunning(
            f"Ingestion is already running for {source_slug}"
        ) from exc
    run_id = run.id

    try:
        stats = ingest()
    except Exception as exc:
        db.rollback()
        run = db.get(IngestionRun, run_id)
        if run is None:
            raise RuntimeError("Ingestion run record disappeared") from exc
        run.source_id = _source_id(db, source_slug)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.failed = 1
        run.error_summary = type(exc).__name__
        db.commit()
        logger.error(
            "Ingestion run %s failed for source %s (%s)",
            run_id,
            source_slug,
            type(exc).__name__,
        )
        raise

    run = db.get(IngestionRun, run_id)
    if run is None:
        raise RuntimeError("Ingestion run record disappeared")
    run.source_id = _source_id(db, source_slug)
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    for name in ("fetched", "saved", "skipped", "duplicates", "stale", "failed"):
        setattr(run, name, stats.get(name, 0))
    db.commit()
    return stats


def record_unavailable_source(
    db: Session,
    *,
    source_name: str,
    source_slug: str,
    status: str,
) -> None:
    source = db.scalar(
        select(JobSource).where(JobSource.slug == source_slug)
    )
    now = datetime.now(timezone.utc)
    db.add(
        IngestionRun(
            source_id=source.id if source is not None else None,
            source_slug=source_slug,
            source_name=source_name,
            started_at=now,
            finished_at=now,
            status=status,
        )
    )
    db.commit()


def _source_id(db: Session, source_slug: str) -> int | None:
    source = db.scalar(
        select(JobSource.id).where(JobSource.slug == source_slug)
    )
    return source
