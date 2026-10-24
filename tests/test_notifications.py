from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base
from app.models import Job, JobNotification, JobSource
from app.services import notifications
from app.services.job_scoring import assess_job

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


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, object],
        *,
        status_code: int = 200,
    ) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("POST", "https://telegram.example/send")
            response = httpx.Response(
                self.status_code,
                request=request,
            )
            raise httpx.HTTPStatusError(
                "Telegram request failed",
                request=request,
                response=response,
            )


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
    ) -> FakeResponse:
        self.requests.append((url, json))
        return next(self.responses)


def _create_candidate_job(db: Session) -> Job:
    source = JobSource(
        name="Example Jobs",
        slug="example-jobs",
        base_url="https://example.com",
        is_active=True,
    )
    db.add(source)
    db.flush()
    job = Job(
        source_id=source.id,
        external_id="frontend-1",
        title="Junior Frontend Engineer",
        company="Example Company",
        url="https://example.com/jobs/frontend-1",
        description=(
            "Build products with React and TypeScript. "
            "Open to applicants worldwide."
        ),
        remote_scope="unknown",
        remote_status="remote",
        posted_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    return job


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": "sqlite+pysqlite:///:memory:",
        "telegram_bot_token": "test-token",
        "telegram_chat_id": "test-chat",
        "telegram_min_relevance_score": 30,
        "telegram_retry_attempts": 2,
        "telegram_retry_backoff_seconds": 0.01,
    }
    values.update(overrides)
    return Settings(**values)


def test_sends_only_once_for_a_new_eligible_job(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _create_candidate_job(db)
    fake_client = FakeClient([FakeResponse({"ok": True})])
    monkeypatch.setattr(
        notifications.httpx,
        "Client",
        lambda *, timeout: fake_client,
    )
    settings = _settings()

    first = notifications.dispatch_job_notifications(db, settings)
    second = notifications.dispatch_job_notifications(db, settings)

    records = list(db.scalars(select(JobNotification)).all())
    assert first["sent"] == 1
    assert second["sent"] == 0
    assert len(fake_client.requests) == 1
    assert "test-token" in fake_client.requests[0][0]
    assert "Apply:" in str(fake_client.requests[0][1]["text"])
    assert job.url in str(fake_client.requests[0][1]["text"])
    assert records[0].status == "sent"
    assert records[0].attempts == 1


def test_telegram_test_message_is_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeClient([FakeResponse({"ok": True})])
    monkeypatch.setattr(
        notifications.httpx,
        "Client",
        lambda *, timeout: fake_client,
    )

    sent, error = notifications.send_telegram_test_message(_settings())

    assert sent is True
    assert error is None
    assert len(fake_client.requests) == 1
    request_url, payload = fake_client.requests[0]
    assert request_url.endswith("/sendMessage")
    assert "test-token" in request_url
    assert payload["chat_id"] == "test-chat"
    assert payload["text"] == "Remote Job Aggregator: Telegram delivery test"


def test_telegram_test_message_reports_missing_configuration() -> None:
    with pytest.raises(ValueError, match="token and chat ID"):
        notifications.send_telegram_test_message(
            _settings(telegram_bot_token=None, telegram_chat_id=None)
        )


def test_unverified_geography_is_not_alerted(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_candidate_job(db)
    monkeypatch.setattr(
        notifications.httpx,
        "Client",
        lambda **_: pytest.fail("Telegram must not be called"),
    )
    job = db.scalar(select(Job))
    assert job is not None
    job.description = "Remote role. Applicants must be located in Canada."
    db.commit()
    assert job.eligibility_confidence == "unknown"
    assert assess_job(
        job.title,
        job.description,
        job.location,
    ).eligibility == "unknown"

    result = notifications.dispatch_job_notifications(db, _settings())

    assert result["sent"] == 0
    assert db.scalar(select(JobNotification.id)) is None


def test_unknown_remote_status_is_not_alerted(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _create_candidate_job(db)
    job.remote_status = "unknown"
    db.commit()
    monkeypatch.setattr(
        notifications.httpx,
        "Client",
        lambda **_: pytest.fail("Telegram must not be called"),
    )

    result = notifications.dispatch_job_notifications(db, _settings())

    assert result["sent"] == 0
    assert db.scalar(select(JobNotification.id)) is None


def test_rate_limited_notification_is_scheduled_for_retry(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_candidate_job(db)
    fake_client = FakeClient(
        [
            FakeResponse(
                {"ok": False, "parameters": {"retry_after": 60}},
                status_code=429,
            )
        ]
    )
    monkeypatch.setattr(
        notifications.httpx,
        "Client",
        lambda *, timeout: fake_client,
    )

    result = notifications.dispatch_job_notifications(db, _settings())
    record = db.scalar(select(JobNotification))

    assert result["failed"] == 0
    assert record is not None
    assert record.status == "pending"
    assert record.attempts == 1
    assert record.next_attempt_at is not None
    assert record.error_summary == "TelegramRateLimited"
    assert len(fake_client.requests) == 1


def test_retries_telegram_server_error_before_success(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_candidate_job(db)
    fake_client = FakeClient(
        [
            FakeResponse({"ok": False}, status_code=503),
            FakeResponse({"ok": True}),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(
        notifications.httpx,
        "Client",
        lambda *, timeout: fake_client,
    )
    monkeypatch.setattr(notifications.time, "sleep", sleeps.append)

    result = notifications.dispatch_job_notifications(db, _settings())
    record = db.scalar(select(JobNotification))

    assert result["sent"] == 1
    assert record is not None
    assert record.status == "sent"
    assert record.attempts == 2
    assert len(fake_client.requests) == 2
    assert sleeps == [0.01]


def test_missing_telegram_configuration_is_reported(
    db: Session,
) -> None:
    result = notifications.dispatch_job_notifications(
        db,
        _settings(telegram_bot_token=None, telegram_chat_id=None),
    )

    assert result == {"status": "not_configured", "sent": 0, "failed": 0}
