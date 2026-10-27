from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base
from app.models import Job, JobSource
from app.telegram_commands import handle_command

test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(
    bind=test_engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        telegram_bot_token="test-token",
        telegram_chat_id="12345",
    )


def _add_job(db: Session) -> Job:
    source = JobSource(
        name="Example Board",
        slug="example-board",
        base_url="https://example.com",
        is_active=True,
    )
    db.add(source)
    db.flush()
    job = Job(
        source_id=source.id,
        external_id="job-1",
        title="Frontend Developer",
        company="Example Co",
        url="https://example.com/careers/job-1",
        posted_at=datetime.now(timezone.utc),
        remote_status="remote",
        remote_scope="unknown",
        eligibility_confidence="unknown",
    )
    db.add(job)
    db.commit()
    return job


def test_help_command_lists_available_commands(db: Session) -> None:
    reply = handle_command(db, "/help", _settings(), fetch_jobs=lambda: "")

    assert "/fetch" in reply
    assert "/verify <job ID or exact listing URL>" in reply


def test_fetch_command_runs_fetch_callback(db: Session) -> None:
    reply = handle_command(
        db,
        "/fetch@MyJobBot",
        _settings(),
        fetch_jobs=lambda: "Fetch finished. No new jobs were added.",
    )

    assert reply == "Fetch finished. No new jobs were added."


def test_verify_command_reports_checks_without_claiming_authenticity(
    db: Session,
) -> None:
    job = _add_job(db)

    reply = handle_command(
        db,
        f"/verify {job.id}",
        _settings(),
        fetch_jobs=lambda: "",
    )

    assert f"Listing #{job.id}" in reply
    assert "Imported source: Example Board" in reply
    assert "Application link: HTTPS" in reply
    assert "not proof" in reply


def test_verify_command_requires_a_listing_reference(db: Session) -> None:
    reply = handle_command(db, "/verify", _settings(), fetch_jobs=lambda: "")

    assert reply == "Usage: /verify <job ID or exact listing URL>"


def test_unknown_command_gets_help_hint(db: Session) -> None:
    reply = handle_command(db, "/delete", _settings(), fetch_jobs=lambda: "")

    assert reply == "Unknown command. Send /help to see available commands."
