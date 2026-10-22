import logging
import time
from threading import Event

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.ingestion.arbeitnow import (
    SOURCE_NAME,
    SOURCE_SLUG,
    ingest_arbeitnow,
)
from app.ingestion.job_feeds import ingest_configured_job_feeds
from app.ingestion.remoteok import (
    SOURCE_NAME as REMOTEOK_SOURCE_NAME,
    SOURCE_SLUG as REMOTEOK_SOURCE_SLUG,
    ingest_remoteok,
)
from app.ingestion.run_tracking import (
    IngestionAlreadyRunning,
    execute_tracked_ingestion,
    record_unavailable_source,
)
from app.models import JobSource
from app.services.notifications import dispatch_job_notifications

logger = logging.getLogger("job_aggregator.worker")


def run_cycle() -> None:
    db = SessionLocal()
    try:
        source = db.scalar(
            select(JobSource).where(JobSource.slug == SOURCE_SLUG)
        )
        if source is not None and not source.is_active:
            record_unavailable_source(
                db,
                source_name=SOURCE_NAME,
                source_slug=SOURCE_SLUG,
                status="disabled",
            )
        else:
            try:
                execute_tracked_ingestion(
                    db,
                    source_name=SOURCE_NAME,
                    source_slug=SOURCE_SLUG,
                    ingest=lambda: ingest_arbeitnow(
                        db,
                        days=settings.ingestion_freshness_days,
                        max_pages=3,
                        retry_attempts=settings.ingestion_retry_attempts,
                        retry_backoff_seconds=(
                            settings.ingestion_retry_backoff_seconds
                        ),
                    ),
                )
            except IngestionAlreadyRunning:
                logger.info("Scheduled Arbeitnow ingestion is already active")
            except Exception as exc:
                logger.error(
                    "Scheduled Arbeitnow ingestion failed (%s)",
                    type(exc).__name__,
                )

        remoteok_source = db.scalar(
            select(JobSource).where(
                JobSource.slug == REMOTEOK_SOURCE_SLUG
            )
        )
        if remoteok_source is not None and not remoteok_source.is_active:
            record_unavailable_source(
                db,
                source_name=REMOTEOK_SOURCE_NAME,
                source_slug=REMOTEOK_SOURCE_SLUG,
                status="disabled",
            )
        else:
            try:
                execute_tracked_ingestion(
                    db,
                    source_name=REMOTEOK_SOURCE_NAME,
                    source_slug=REMOTEOK_SOURCE_SLUG,
                    ingest=lambda: ingest_remoteok(
                        db,
                        days=settings.ingestion_freshness_days,
                        retry_attempts=settings.ingestion_retry_attempts,
                        retry_backoff_seconds=(
                            settings.ingestion_retry_backoff_seconds
                        ),
                    ),
                )
            except IngestionAlreadyRunning:
                logger.info("Scheduled Remote OK ingestion is already active")
            except Exception as exc:
                logger.error(
                    "Scheduled Remote OK ingestion failed (%s)",
                    type(exc).__name__,
                )

        try:
            feed_results = ingest_configured_job_feeds(
                db,
                settings,
                days=settings.ingestion_freshness_days,
            )
            logger.info("Scheduled feed ingestion completed: %s", feed_results)
        except Exception as exc:
            logger.error(
                "Scheduled feed ingestion could not complete (%s)",
                type(exc).__name__,
            )

        try:
            notification_results = dispatch_job_notifications(db, settings)
            logger.info(
                "Scheduled notification dispatch completed: %s",
                notification_results,
            )
        except Exception as exc:
            db.rollback()
            logger.error(
                "Scheduled notification dispatch failed (%s)",
                type(exc).__name__,
            )
    finally:
        db.close()


def run_worker(stop_event: Event | None = None) -> None:
    event = stop_event or Event()
    logger.info(
        "Starting ingestion worker with a %s-second interval",
        settings.ingestion_interval_seconds,
    )
    while not event.is_set():
        cycle_started = time.monotonic()
        try:
            run_cycle()
        except Exception as exc:
            logger.error("Worker cycle failed (%s)", type(exc).__name__)
        remaining = settings.ingestion_interval_seconds - (
            time.monotonic() - cycle_started
        )
        event.wait(max(0, remaining))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        run_worker()
    except KeyboardInterrupt:
        logger.info("Ingestion worker stopped")
