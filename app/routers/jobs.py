
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobSource
from app.schemas import JobCreate, JobRead

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
) -> Job:
    source = db.get(JobSource, payload.source_id)

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job source not found.",
        )

    job = Job(
        **payload.model_dump(
            exclude={"url"},
        ),
        url=str(payload.url),
    )

    db.add(job)

    try:
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job may already exist for this source.",
        )

    return job


@router.get("", response_model=list[JobRead])
def list_jobs(
    remote_scope: str | None = None,
    region: str | None = None,
    source_id: int | None = Query(default=None, gt=0),
    days: int | None = Query(default=None, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Job]:
    statement = select(Job)

    if remote_scope:
        statement = statement.where(Job.remote_scope == remote_scope)

    if region:
        statement = statement.where(Job.region.ilike(f"%{region}%"))

    if source_id is not None:
        statement = statement.where(Job.source_id == source_id)

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        statement = statement.where(Job.posted_at >= cutoff)

    statement = (
        statement
        .order_by(Job.posted_at.desc().nullslast(), Job.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> Job:
    job = db.get(Job, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    return job
