
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.arbeitnow import ingest_arbeitnow

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
