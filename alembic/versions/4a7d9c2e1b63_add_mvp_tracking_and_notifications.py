"""add MVP tracking and notifications

Revision ID: 4a7d9c2e1b63
Revises: 9f2c1d6a4b80
Create Date: 2026-10-20 17:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4a7d9c2e1b63"
down_revision: Union[str, Sequence[str], None] = "9f2c1d6a4b80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_sources",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text("UPDATE job_sources SET updated_at = created_at")
    )
    with op.batch_alter_table("job_sources") as batch:
        batch.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )

    op.add_column(
        "jobs",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "remote_status",
            sa.String(length=30),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "eligible_countries",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "eligibility_confidence",
            sa.String(length=30),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("eligibility_source", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("eligibility_reason", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE jobs SET first_seen_at = created_at, "
            "last_seen_at = created_at"
        )
    )
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "first_seen_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch.alter_column(
            "last_seen_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch.add_column(
            sa.Column("duplicate_of_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_jobs_duplicate_of_id_jobs",
            "jobs",
            ["duplicate_of_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "ix_jobs_duplicate_of_id", "jobs", ["duplicate_of_id"]
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_slug", sa.String(length=120), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "fetched", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("saved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "duplicates", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("stale", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"], ["job_sources.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"]
    )
    op.create_index(
        "ix_ingestion_runs_status", "ingestion_runs", ["status"]
    )
    op.create_index(
        "uq_ingestion_runs_active_source",
        "ingestion_runs",
        ["source_slug"],
        unique=True,
        sqlite_where=sa.text("status = 'running'"),
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "job_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "last_attempt_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_job_notifications_job_id"),
    )
    op.create_index(
        "ix_job_notifications_status_next_attempt",
        "job_notifications",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_job_notifications_status_next_attempt",
        table_name="job_notifications",
    )
    op.drop_table("job_notifications")
    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index(
        "uq_ingestion_runs_active_source",
        table_name="ingestion_runs",
    )
    op.drop_index(
        "ix_ingestion_runs_started_at", table_name="ingestion_runs"
    )
    op.drop_table("ingestion_runs")
    op.drop_index("ix_jobs_duplicate_of_id", table_name="jobs")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint(
            "fk_jobs_duplicate_of_id_jobs",
            type_="foreignkey",
        )
        batch.drop_column("duplicate_of_id")
    op.drop_column("jobs", "eligibility_reason")
    op.drop_column("jobs", "eligibility_source")
    op.drop_column("jobs", "eligibility_confidence")
    op.drop_column("jobs", "eligible_countries")
    op.drop_column("jobs", "remote_status")
    op.drop_column("jobs", "last_seen_at")
    op.drop_column("jobs", "first_seen_at")
    op.drop_column("job_sources", "updated_at")
