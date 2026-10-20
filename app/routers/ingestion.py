
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.ingestion.arbeitnow import ingest_arbeitnow
from app.ingestion.job_feeds import ingest_configured_job_feeds

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.post("/arbeitnow/run")
def run_arbeitnow_ingestion(
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        stats = ingest_arbeitnow(db, days=30, max_pages=3)
        return {
            "message": "Arbeitnow ingestion completed",
            "stats": stats,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Arbeitnow ingestion failed. Check the server logs.",
        ) from exc


@router.post("/feeds/run")
def run_configured_feed_ingestion(
    db: Session = Depends(get_db),
) -> dict[str, object]:
    results = ingest_configured_job_feeds(db, settings, days=30)
    statuses = {result["status"] for result in results.values()}

    if statuses == {"not_configured"}:
        overall_status = "not_configured"
    elif "failed" in statuses:
        overall_status = "partial_failure" if "completed" in statuses else "failed"
    else:
        overall_status = "completed"

    return {
        "message": "Configured job feed ingestion finished",
        "status": overall_status,
        "sources": results,
    }
