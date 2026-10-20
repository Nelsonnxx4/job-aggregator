from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.ingestion import arbeitnow
from app.ingestion.run_tracking import (
    IngestionAlreadyRunning,
    execute_tracked_ingestion,
)
from app.models import IngestionRun, Job, JobSource
from app.main import app
from app.routers import ingestion as ingestion_router

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


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        yield db

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, object],
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    def json(self) -> dict[str, object]:
        return self.payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.requests: list[dict[str, int]] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(
        self,
        url: str,
        *,
        params: dict[str, int],
    ) -> FakeResponse:
        assert url == arbeitnow.API_URL
        self.requests.append(params)
        return next(self.responses)


def response(
    jobs: list[dict[str, object]],
    *,
    has_next: bool = False,
) -> FakeResponse:
    return FakeResponse(
        {
            "data": jobs,
            "links": {"next": "https://example.com/jobs?page=2" if has_next else None},
        }
    )


def valid_job(
    slug: str = "frontend-engineer-123",
    **overrides: object,
) -> dict[str, object]:
    job: dict[str, object] = {
        "slug": slug,
        "title": " Frontend Engineer ",
        "company_name": " Example Co ",
        "url": f"https://example.com/jobs/{slug}",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "remote": True,
        "location": "Remote",
        "description": "<p>Build <strong>great</strong> products.</p>",
        "tags": ["Python", "APIs"],
        "job_types": ["Full-time"],
    }
    job.update(overrides)
    return job


def patch_client(
    monkeypatch: pytest.MonkeyPatch,
    *batches: list[FakeResponse],
) -> list[FakeClient]:
    clients: list[FakeClient] = []
    response_batches = iter(batches)

    def make_client(*, timeout: float) -> FakeClient:
        assert timeout == 20.0
        client = FakeClient(next(response_batches))
        clients.append(client)
        return client

    monkeypatch.setattr(arbeitnow.httpx, "Client", make_client)
    return clients


def test_ingests_and_normalizes_paginated_jobs(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_data = valid_job()
    clients = patch_client(
        monkeypatch,
        [
            response([job_data], has_next=True),
            response([valid_job("backend-engineer-456")]),
        ],
    )

    stats = arbeitnow.ingest_arbeitnow(db, days=30, max_pages=3)

    jobs = list(db.scalars(select(Job).order_by(Job.external_id)).all())
    source = db.scalar(select(JobSource).where(JobSource.slug == "arbeitnow"))

    assert stats == {
        "fetched": 2,
        "saved": 2,
        "duplicates": 0,
        "stale": 0,
        "skipped": 0,
    }
    assert source is not None
    assert source.name == "Arbeitnow"
    assert source.base_url == "https://www.arbeitnow.com"
    assert [client.requests for client in clients] == [
        [{"page": 1}, {"page": 2}]
    ]
    assert len(jobs) == 2
    first_job = jobs[0]
    assert first_job.title == "Frontend Engineer"
    assert first_job.company == "Example Co"
    assert first_job.description == (
        "Build great products.\n\nSkills/tags: Python, APIs"
    )
    assert first_job.employment_type == "Full-time"
    assert first_job.remote_scope == "unknown"
    assert first_job.region is None
    assert first_job.posted_at == datetime.fromtimestamp(
        job_data["created_at"], tz=timezone.utc
    ).replace(tzinfo=None)


def test_repeat_ingestion_skips_existing_job(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = valid_job()
    patch_client(
        monkeypatch,
        [response([job])],
        [response([job])],
    )

    first_run = arbeitnow.ingest_arbeitnow(db)
    second_run = arbeitnow.ingest_arbeitnow(db)

    assert first_run["saved"] == 1
    assert first_run["duplicates"] == 0
    assert second_run["saved"] == 0
    assert second_run["duplicates"] == 1
    assert db.scalar(select(Job.id)) is not None
    assert len(db.scalars(select(Job)).all()) == 1
    assert len(db.scalars(select(JobSource)).all()) == 1


def test_skips_stale_incomplete_invalid_date_and_non_remote_jobs(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_timestamp = int(
        (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    )
    patch_client(
        monkeypatch,
        [
            response(
                [
                    valid_job("stale", created_at=stale_timestamp),
                    valid_job("bad-date", created_at="not-a-timestamp"),
                    valid_job("missing-company", company_name=""),
                    valid_job("not-remote", remote=False),
                    valid_job("current"),
                ]
            )
        ],
    )

    stats = arbeitnow.ingest_arbeitnow(db, days=30)

    assert stats == {
        "fetched": 5,
        "saved": 1,
        "duplicates": 0,
        "stale": 1,
        "skipped": 3,
    }
    assert [job.external_id for job in db.scalars(select(Job)).all()] == [
        "current"
    ]


def test_rejects_unexpected_api_payload_and_preserves_source(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_client(
        monkeypatch,
        [FakeResponse({"data": "not a list", "links": {}})],
    )

    with pytest.raises(ValueError, match="Unexpected Arbeitnow API response"):
        arbeitnow.ingest_arbeitnow(db)

    assert db.scalar(select(JobSource).where(JobSource.slug == "arbeitnow"))
    assert db.scalar(select(Job.id)) is None


def test_logs_and_reraises_external_http_failure(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    patch_client(
        monkeypatch,
        [
            FakeResponse(
                {},
                error=RuntimeError("upstream request failed"),
            )
        ],
    )

    with pytest.raises(RuntimeError, match="upstream request failed"):
        arbeitnow.ingest_arbeitnow(db)

    assert "Arbeitnow ingestion failed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "upstream request failed" not in caplog.text
    assert db.scalar(select(JobSource).where(JobSource.slug == "arbeitnow"))
    assert db.scalar(select(Job.id)) is None


def test_rolls_back_jobs_when_page_commit_fails(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_client(monkeypatch, [response([valid_job()])])
    original_commit = db.commit
    commit_calls = 0

    def fail_job_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            original_commit()
            return
        raise RuntimeError("database write failed")

    monkeypatch.setattr(db, "commit", fail_job_commit)

    with pytest.raises(RuntimeError, match="database write failed"):
        arbeitnow.ingest_arbeitnow(db)

    assert db.scalar(select(JobSource).where(JobSource.slug == "arbeitnow"))
    assert db.scalar(select(Job.id)) is None


def test_rolls_back_all_pages_when_a_later_fetch_fails(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_client(
        monkeypatch,
        [
            response([valid_job()], has_next=True),
            FakeResponse({}, error=RuntimeError("second page failed")),
        ],
    )

    with pytest.raises(RuntimeError, match="second page failed"):
        arbeitnow.ingest_arbeitnow(db, max_pages=3)

    assert db.scalar(select(JobSource).where(JobSource.slug == "arbeitnow"))
    assert db.scalar(select(Job.id)) is None


def test_rejects_overlapping_runs_for_the_same_source(
    db: Session,
) -> None:
    db.add(
        IngestionRun(
            source_slug="arbeitnow",
            source_name="Arbeitnow",
            started_at=datetime.now(timezone.utc),
            status="running",
        )
    )
    db.commit()

    with pytest.raises(IngestionAlreadyRunning):
        execute_tracked_ingestion(
            db,
            source_name="Arbeitnow",
            source_slug="arbeitnow",
            ingest=lambda: pytest.fail("overlapping run must not execute"),
        )


def test_recovers_a_stale_running_record(
    db: Session,
) -> None:
    stale_run = IngestionRun(
        source_slug="arbeitnow",
        source_name="Arbeitnow",
        started_at=datetime.now(timezone.utc) - timedelta(hours=3),
        status="running",
    )
    db.add(stale_run)
    db.commit()
    stale_run_id = stale_run.id

    stats = execute_tracked_ingestion(
        db,
        source_name="Arbeitnow",
        source_slug="arbeitnow",
        ingest=lambda: {"fetched": 1, "saved": 1},
    )

    db.refresh(stale_run)
    assert stats == {"fetched": 1, "saved": 1}
    assert stale_run.status == "failed"
    assert stale_run.error_summary == "StaleRunRecovered"
    assert db.scalar(
        select(IngestionRun.id).where(IngestionRun.id != stale_run_id)
    ) is not None


def test_ingestion_endpoint_returns_success_statistics(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stats = {
        "fetched": 3,
        "saved": 1,
        "duplicates": 1,
        "stale": 1,
        "skipped": 0,
    }

    def fake_ingest(
        _db: Session,
        *,
        days: int,
        max_pages: int,
        retry_attempts: int,
        retry_backoff_seconds: float,
    ) -> dict[str, int]:
        assert _db.is_active
        assert days == 30
        assert max_pages == 3
        assert retry_attempts == 2
        assert retry_backoff_seconds == 0.5
        return stats

    monkeypatch.setattr(
        ingestion_router, "ingest_arbeitnow", fake_ingest
    )

    response = client.post("/ingestion/arbeitnow/run")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Arbeitnow ingestion completed",
        "stats": stats,
    }
    run = db.scalar(select(IngestionRun))
    assert run is not None
    assert run.status == "completed"
    assert run.saved == 1


def test_ingestion_endpoint_returns_safe_error_on_failure(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_ingest(
        _db: Session,
        *,
        days: int,
        max_pages: int,
        retry_attempts: int,
        retry_backoff_seconds: float,
    ) -> dict[str, int]:
        assert _db.is_active
        assert days == 30
        assert max_pages == 3
        assert retry_attempts == 2
        assert retry_backoff_seconds == 0.5
        raise RuntimeError("private database details")

    monkeypatch.setattr(
        ingestion_router, "ingest_arbeitnow", fail_ingest
    )

    response = client.post("/ingestion/arbeitnow/run")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Arbeitnow ingestion failed. Check the server logs."
    }
    assert "private database details" not in response.text
    run = db.scalar(select(IngestionRun))
    assert run is not None
    assert run.status == "failed"
    assert run.error_summary == "RuntimeError"


@pytest.mark.parametrize(
    ("days", "max_pages"),
    [(0, 1), (30, 0), (-1, 2)],
)
def test_rejects_invalid_ingestion_limits(
    db: Session,
    days: int,
    max_pages: int,
) -> None:
    with pytest.raises(ValueError, match="days and max_pages must be at least 1"):
        arbeitnow.ingest_arbeitnow(db, days=days, max_pages=max_pages)
