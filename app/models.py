
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="source")
    ingestion_runs: Mapped[list["IngestionRun"]] = relationship(
        back_populates="source"
    )


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
        Index("ix_jobs_duplicate_of_id", "duplicate_of_id"),
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
        String(100), nullable=True
    )
    experience_level: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Examples: worldwide, emea, country_restricted, onsite
    remote_scope: Mapped[str] = mapped_column(
        String(40), default="unknown", nullable=False
    )
    remote_status: Mapped[str] = mapped_column(
        String(30),
        default="unknown",
        server_default="unknown",
        nullable=False,
    )
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    eligible_countries: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
        nullable=False,
    )
    eligibility_confidence: Mapped[str] = mapped_column(
        String(30),
        default="unknown",
        server_default="unknown",
        nullable=False,
    )
    eligibility_source: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    eligibility_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
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
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    source: Mapped["JobSource"] = relationship(back_populates="jobs")
    duplicate_of: Mapped["Job | None"] = relationship(
        remote_side=[id],
        foreign_keys=[duplicate_of_id],
    )
    notifications: Mapped[list["JobNotification"]] = relationship(
        back_populates="job"
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    __table_args__ = (
        Index("ix_ingestion_runs_started_at", "started_at"),
        Index("ix_ingestion_runs_status", "status"),
        Index(
            "uq_ingestion_runs_active_source",
            "source_slug",
            unique=True,
            sqlite_where=text("status = 'running'"),
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    fetched: Mapped[int] = mapped_column(default=0, nullable=False)
    saved: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(default=0, nullable=False)
    stale: Mapped[int] = mapped_column(default=0, nullable=False)
    failed: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[JobSource | None] = relationship(
        back_populates="ingestion_runs"
    )


class JobNotification(Base):
    __tablename__ = "job_notifications"

    __table_args__ = (
        UniqueConstraint("job_id", name="uq_job_notifications_job_id"),
        Index(
            "ix_job_notifications_status_next_attempt",
            "status",
            "next_attempt_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped[Job] = relationship(back_populates="notifications")
