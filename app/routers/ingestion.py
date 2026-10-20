
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.ingestion.arbeitnow import (
    SOURCE_NAME,
    SOURCE_SLUG,
    ingest_arbeitnow,
)
from app.ingestion.job_feeds import ingest_configured_job_feeds
from app.ingestion.run_tracking import (
    IngestionAlreadyRunning,
    execute_tracked_ingestion,
    record_unavailable_source,
)
from app.models import IngestionRun, JobSource
from app.schemas import IngestionRunRead

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.post("/arbeitnow/run")
def run_arbeitnow_ingestion(
    db: Session = Depends(get_db),
) -> dict[str, object]:
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
            return {
                "message": "Arbeitnow ingestion skipped",
                "status": "disabled",
            }
        stats = execute_tracked_ingestion(
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
        return {
            "message": "Arbeitnow ingestion completed",
            "stats": stats,
        }
    except IngestionAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Arbeitnow ingestion is already running.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Arbeitnow ingestion failed. Check the server logs.",
        ) from exc


@router.post("/feeds/run")
def run_configured_feed_ingestion(
    db: Session = Depends(get_db),
) -> dict[str, object]:
    results = ingest_configured_job_feeds(
        db,
        settings,
        days=settings.ingestion_freshness_days,
    )
    statuses = {result["status"] for result in results.values()}

    if statuses == {"not_configured"}:
        overall_status = "not_configured"
    elif "already_running" in statuses and statuses <= {
        "already_running",
        "not_configured",
        "disabled",
    }:
        overall_status = "already_running"
    elif statuses <= {"not_configured", "disabled"}:
        overall_status = "disabled"
    elif "failed" in statuses:
        overall_status = "partial_failure" if "completed" in statuses else "failed"
    else:
        overall_status = "completed"

    return {
        "message": "Configured job feed ingestion finished",
        "status": overall_status,
        "sources": results,
    }


@router.get("/runs", response_model=list[IngestionRunRead])
def list_ingestion_runs(
    source_id: int | None = Query(default=None, gt=0),
    run_status: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[IngestionRun]:
    statement = select(IngestionRun)
    if source_id is not None:
        statement = statement.where(IngestionRun.source_id == source_id)
    if run_status is not None:
        statement = statement.where(IngestionRun.status == run_status)
    statement = statement.order_by(IngestionRun.started_at.desc())
    statement = statement.limit(limit).offset(offset)
    return list(db.scalars(statement).all())
