
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobSource
from app.schemas import JobSourceCreate, JobSourceRead, JobSourceUpdate

router = APIRouter(prefix="/sources", tags=["Job Sources"])


@router.post(
    "",
    response_model=JobSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    payload: JobSourceCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> JobSource:
    existing_sources = list(
        db.scalars(
            select(JobSource).where(
                or_(
                    JobSource.name == payload.name,
                    JobSource.slug == payload.slug,
                )
            )
        ).all()
    )
    if existing_sources:
        if (
            len(existing_sources) == 1
            and existing_sources[0].name == payload.name
            and existing_sources[0].slug == payload.slug
            and existing_sources[0].base_url
            == (str(payload.base_url) if payload.base_url else None)
        ):
            response.status_code = status.HTTP_200_OK
            return existing_sources[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this name or slug already exists.",
        )

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


@router.patch("/{source_id}", response_model=JobSourceRead)
def update_source(
    source_id: int,
    payload: JobSourceUpdate,
    db: Session = Depends(get_db),
) -> JobSource:
    source = db.get(JobSource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job source not found.",
        )

    source.is_active = payload.is_active
    db.commit()
    db.refresh(source)
    return source


@router.get("", response_model=list[JobSourceRead])
def list_sources(
    db: Session = Depends(get_db),
) -> list[JobSource]:
    statement = select(JobSource).order_by(JobSource.name)
    return list(db.scalars(statement).all())
