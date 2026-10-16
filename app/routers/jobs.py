from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobSource
from app.schemas import JobCreate, JobRead, ScoredJobRead
from app.services.job_scoring import assess_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])

Eligibility = Literal[
    "worldwide",
    "emea",
    "country_restricted",
    "unknown",
]


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
        **payload.model_dump(exclude={"url"}),
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


@router.get("", response_model=list[ScoredJobRead])
def list_jobs(
    remote_scope: str | None = None,
    region: str | None = None,
    source_id: int | None = Query(default=None, gt=0),
    days: int | None = Query(default=30, ge=1, le=365),
    min_score: int = Query(default=0, ge=0, le=100),
    eligibility: Eligibility | None = None,
    sort_by: Literal["date", "relevance"] = "relevance",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
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

    #
    jobs = list(db.scalars(statement).all())

    scored_jobs: list[dict] = []

    for job in jobs:
        assessment = assess_job(
            title=job.title,
            description=job.description or "",
            location=job.location or "",
        )

        if assessment.relevance_score < min_score:
            continue

        if (
            eligibility is not None
            and assessment.eligibility != eligibility
        ):
            continue

        scored_jobs.append(
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "url": str(job.url),
                "source_id": job.source_id,
                "external_id": job.external_id,
                "location": job.location,
                "description": job.description,
                "employment_type": job.employment_type,
                "experience_level": job.experience_level,
                "remote_scope": job.remote_scope,
                "region": job.region,
                "posted_at": job.posted_at,
                "created_at": job.created_at,
                "relevance_score": assessment.relevance_score,
                "eligibility": assessment.eligibility,
                "relevance_reasons": assessment.relevance_reasons,
                "eligibility_reason": assessment.eligibility_reason,
            }
        )

    if sort_by == "relevance":
        scored_jobs.sort(
            key=lambda item: (
                item["relevance_score"],
                item["posted_at"] or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
                item["id"],
            ),
            reverse=True,
        )
    else:
        scored_jobs.sort(
            key=lambda item: (
                item["posted_at"] is not None,
                item["posted_at"] or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
                item["id"],
            ),
            reverse=True,
        )

    return scored_jobs[offset : offset + limit]


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