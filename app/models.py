
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="source")


class Job(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_jobs_source_external_id",
        ),
        Index("ix_jobs_remote_scope_region", "remote_scope", "region"),
        Index("ix_jobs_posted_at", "posted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(250), index=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    location: Mapped[str | None] = mapped_column(String(250), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(
        String(250), nullable=True
    )

    employment_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    experience_level: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # Examples: worldwide, emea, country_restricted, onsite
    remote_scope: Mapped[str] = mapped_column(
        String(40), default="unknown", nullable=False
    )
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("job_sources.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    source: Mapped["JobSource"] = relationship(back_populates="jobs")
