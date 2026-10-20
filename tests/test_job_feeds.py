import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_db
from app.ingestion import job_feeds
from app.main import app
from app.models import IngestionRun, Job, JobSource
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


def _rfc_date() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _rss_feed(*items: str) -> str:
    return (
        "<rss version='2.0'><channel>"
        + "".join(items)
        + "</channel></rss>"
    )


def _rss_job(
    job_id: str = "job-1",
    *,
    company: str = "Example Co",
    pub_date: str | None = None,
) -> str:
    date = pub_date or _rfc_date()
    return f"""
    <item>
      <guid>{job_id}</guid>
      <title>Frontend Engineer</title>
      <link>https://jobs.example.com/{job_id}</link>
      <company>{company}</company>
      <pubDate>{date}</pubDate>
      <description>&lt;p&gt;Build accessible interfaces.&lt;/p&gt;</description>
      <location>Remote</location>
      <job_type>Full-time</job_type>
      <seniority>Junior</seniority>
    </item>
    """


class FakeResponse:
    def __init__(self, text: str, error: Exception | None = None) -> None:
        self.text = text
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, dict[str, str]]] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        self.requests.append((url, headers))
        return next(self.responses)


def _patch_clients(
    monkeypatch: pytest.MonkeyPatch,
    *batches: list[FakeResponse],
) -> list[FakeClient]:
    clients: list[FakeClient] = []
    responses = iter(batches)

    def make_client(*, timeout: float) -> FakeClient:
        assert timeout == 20.0
        client = FakeClient(next(responses))
        clients.append(client)
        return client

    monkeypatch.setattr(job_feeds.httpx, "Client", make_client)
    return clients


def test_parses_rss_feed_into_normalized_job() -> None:
    feed_url = "https://jobs.example.com/feed.xml"
    jobs = job_feeds.parse_job_feed(_rss_feed(_rss_job()), feed_url)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "job-1"
    assert job.title == "Frontend Engineer"
    assert job.company == "Example Co"
    assert job.url == "https://jobs.example.com/job-1"
    assert job.description == "Build accessible interfaces."
    assert job.location == "Remote"
    assert job.employment_type == "Full-time"
    assert job.experience_level == "Junior"


def test_empty_rss_feed_is_a_valid_empty_result() -> None:
    assert job_feeds.parse_job_feed(
        "<rss version='2.0'><channel /></rss>",
        "https://example.com/feed.xml",
    ) == []


def test_parses_json_feed_and_supports_author_as_company() -> None:
    payload = json.dumps(
        {
            "version": "https://jsonfeed.org/version/1.1",
            "items": [
                {
                    "id": "json-job-1",
                    "title": "Backend Engineer",
                    "url": "/jobs/backend-1",
                    "date_published": "2026-10-16T09:30:00Z",
                    "author": {"name": "Example Startup"},
                    "content_html": "<p>Build APIs.</p>",
                    "experience_level": "Mid-level",
                }
            ],
        }
    )

    jobs = job_feeds.parse_job_feed(
        payload, "https://example.com/jobs/feed.json"
    )

    assert len(jobs) == 1
    assert jobs[0].company == "Example Startup"
    assert jobs[0].url == "https://example.com/jobs/backend-1"
    assert jobs[0].experience_level == "Mid-level"
    assert jobs[0].posted_at == datetime(
        2026, 10, 16, 9, 30, tzinfo=timezone.utc
    )


def test_json_modified_date_does_not_substitute_for_publication_date() -> None:
    payload = json.dumps(
        {
            "version": "https://jsonfeed.org/version/1.1",
            "items": [
                {
                    "id": "modified-job",
                    "title": "Frontend Engineer",
                    "url": "https://example.com/jobs/modified",
                    "date_modified": _rfc_date(),
                    "author": {"name": "Example Co"},
                }
            ],
        }
    )

    assert job_feeds.parse_job_feed(
        payload,
        "https://example.com/feed.json",
    ) == []


def test_parses_atom_feed() -> None:
    atom = f"""
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://example.com/jobs/atom-1</id>
        <title>Product Engineer</title>
        <link href="/jobs/atom-1" />
        <author><name>Acme Ltd</name></author>
        <published>2026-10-16T09:30:00Z</published>
        <summary>Build products.</summary>
      </entry>
    </feed>
    """

    jobs = job_feeds.parse_job_feed(atom, "https://example.com/feed.atom")

    assert len(jobs) == 1
    assert jobs[0].company == "Acme Ltd"
    assert jobs[0].external_id == "https://example.com/jobs/atom-1"
    assert jobs[0].url == "https://example.com/jobs/atom-1"


def test_ingests_jobs_deduplicates_and_keeps_eligibility_unknown(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = job_feeds.FeedSource(
        name="Dover",
        slug="dover",
        base_url="https://www.dover.com",
        setting_name="DOVER_FEED_URL",
        feed_url="https://feeds.example.com/dover.xml",
    )
    feed = _rss_feed(_rss_job())
    _patch_clients(
        monkeypatch,
        [FakeResponse(feed)],
        [FakeResponse(feed)],
    )

    first_run = job_feeds.ingest_job_feed(db, source)
    second_run = job_feeds.ingest_job_feed(db, source)
    jobs = list(db.scalars(select(Job)).all())
    saved_source = db.scalar(
        select(JobSource).where(JobSource.slug == "dover")
    )

    assert first_run == {
        "fetched": 1,
        "saved": 1,
        "duplicates": 0,
        "stale": 0,
        "skipped": 0,
    }
    assert second_run["saved"] == 0
    assert second_run["duplicates"] == 1
    assert len(jobs) == 1
    assert saved_source is not None
    assert jobs[0].source_id == saved_source.id
    assert jobs[0].remote_scope == "unknown"
    assert jobs[0].region is None


def test_repeat_ingestion_refreshes_last_seen_for_stored_stale_job(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = job_feeds.FeedSource(
        name="Dover",
        slug="dover",
        base_url="https://www.dover.com",
        setting_name="DOVER_FEED_URL",
        feed_url="https://feeds.example.com/dover.xml",
    )
    feed = _rss_feed(_rss_job())
    _patch_clients(
        monkeypatch,
        [FakeResponse(feed)],
        [FakeResponse(feed)],
    )
    job_feeds.ingest_job_feed(db, source)
    stored_job = db.scalar(select(Job))
    assert stored_job is not None
    old_seen_at = stored_job.last_seen_at
    stored_job.posted_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db.commit()

    stats = job_feeds.ingest_job_feed(db, source)

    db.refresh(stored_job)
    assert stats["duplicates"] == 1
    assert stats["stale"] == 0
    assert stored_job.last_seen_at >= old_seen_at


def test_cross_source_duplicate_is_linked_without_discarding_source(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_source = JobSource(
        name="Original Source",
        slug="original-source",
        base_url="https://example.com",
        is_active=True,
    )
    db.add(original_source)
    db.flush()
    original_job = Job(
        source_id=original_source.id,
        external_id="canonical-1",
        title="Frontend Engineer",
        company="Example Co",
        url="https://www.jobs.example.com/job-1?utm_source=old",
        posted_at=datetime.now(timezone.utc),
        remote_scope="unknown",
    )
    db.add(original_job)
    db.commit()

    feed_source = job_feeds.FeedSource(
        name="Dover",
        slug="dover",
        base_url="https://www.dover.com",
        setting_name="DOVER_FEED_URL",
        feed_url="https://feeds.example.com/dover.xml",
    )
    feed = _rss_feed(
        _rss_job(
            "job-1",
            company="Example Co",
        ).replace(
            "https://jobs.example.com/job-1",
            "https://jobs.example.com/job-1?utm_source=new",
        )
    )
    _patch_clients(monkeypatch, [FakeResponse(feed)])

    stats = job_feeds.ingest_job_feed(db, feed_source)
    jobs = list(db.scalars(select(Job).order_by(Job.id)).all())

    assert stats["saved"] == 1
    assert stats["duplicates"] == 1
    assert len(jobs) == 2
    assert jobs[1].duplicate_of_id == original_job.id
    assert jobs[1].source_id != original_job.source_id


def test_counts_stale_and_invalid_items(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_date = "Mon, 01 Jan 2024 12:00:00 +0000"
    feed = _rss_feed(
        _rss_job("stale", pub_date=stale_date),
        _rss_job("missing-company", company=""),
    )
    _patch_clients(monkeypatch, [FakeResponse(feed)])
    source = job_feeds.FeedSource(
        name="Wellfound",
        slug="wellfound",
        base_url="https://wellfound.com",
        setting_name="WELLFOUND_FEED_URL",
        feed_url="https://feeds.example.com/wellfound.xml",
    )

    stats = job_feeds.ingest_job_feed(db, source, days=30)

    assert stats == {
        "fetched": 2,
        "saved": 0,
        "duplicates": 0,
        "stale": 1,
        "skipped": 1,
    }
    assert db.scalar(select(Job.id)) is None


def test_rejects_non_http_feed_urls(
    db: Session,
) -> None:
    source = job_feeds.FeedSource(
        name="Jobberman",
        slug="jobberman",
        base_url="https://www.jobberman.com",
        setting_name="JOBBERMAN_FEED_URL",
        feed_url="file:///private/jobs.xml",
    )

    with pytest.raises(ValueError, match="absolute HTTP or HTTPS URL"):
        job_feeds.ingest_job_feed(db, source)


def test_configured_source_failures_do_not_stop_other_sources(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        hiring_cafe_feed_url="https://feed.example.com/hiring-cafe.json",
        dover_feed_url="https://feed.example.com/dover.json",
    )

    def fake_ingest(
        _db: Session,
        source: job_feeds.FeedSource,
        *,
        days: int,
        retry_attempts: int,
        retry_backoff_seconds: float,
    ) -> dict[str, int]:
        assert days == 30
        assert retry_attempts == 2
        assert retry_backoff_seconds == 0.5
        if source.slug == "hiring-cafe":
            raise RuntimeError("upstream error details")
        return {
            "fetched": 1,
            "saved": 1,
            "duplicates": 0,
            "stale": 0,
            "skipped": 0,
        }

    monkeypatch.setattr(job_feeds, "ingest_job_feed", fake_ingest)

    results = job_feeds.ingest_configured_job_feeds(db, settings)

    assert results["hiring-cafe"] == {
        "status": "failed",
        "error": "RuntimeError",
    }
    assert results["dover"]["status"] == "completed"
    assert results["jobberman"] == {
        "status": "not_configured",
        "configuration": "JOBBERMAN_FEED_URL",
    }
    runs = {
        run.source_slug: run
        for run in db.scalars(select(IngestionRun)).all()
    }
    assert runs["hiring-cafe"].status == "failed"
    assert runs["dover"].status == "completed"
    assert runs["jobberman"].status == "not_configured"


def test_feed_endpoint_reports_unconfigured_sources(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ingestion_router,
        "settings",
        Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:"),
    )
    response = client.post("/ingestion/feeds/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_configured"
    assert body["sources"]["hiring-cafe"] == {
        "status": "not_configured",
        "configuration": "HIRING_CAFE_FEED_URL",
    }
    assert set(body["sources"]) == {
        "hiring-cafe",
        "dover",
        "wellfound",
        "jobberman",
        "jobtogether",
    }
    runs = list(db.scalars(select(IngestionRun)).all())
    assert len(runs) == 5
    assert {run.status for run in runs} == {"not_configured"}
    history = client.get("/ingestion/runs?status=not_configured")
    assert history.status_code == 200
    assert len(history.json()) == 5
