
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobSource
from app.schemas import JobSourceCreate, JobSourceRead

router = APIRouter(prefix="/sources", tags=["Job Sources"])


@router.post(
    "",
    response_model=JobSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    payload: JobSourceCreate,
    db: Session = Depends(get_db),
) -> JobSource:
    source = JobSource(
        name=payload.name,
        slug=payload.slug,
        base_url=str(payload.base_url) if payload.base_url else None,
    )

    db.add(source)

    try:
        db.commit()
        db.refresh(source)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this name or slug already exists.",
        )

    return source


@router.get("", response_model=list[JobSourceRead])
def list_sources(
    db: Session = Depends(get_db),
) -> list[JobSource]:
    statement = select(JobSource).order_by(JobSource.name)
    return list(db.scalars(statement).all())
