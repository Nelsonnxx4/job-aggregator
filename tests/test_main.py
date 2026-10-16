
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSession = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_source_and_job(client):
    source_response = client.post(
        "/sources",
        json={
            "name": "Example Jobs",
            "slug": "example-jobs",
            "base_url": "https://example.com",
        },
    )

    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    job_response = client.post(
        "/jobs",
        json={
            "title": "Junior Frontend Developer",
            "company": "Example Company",
            "url": "https://example.com/jobs/123",
            "external_id": "123",
            "source_id": source_id,
            "remote_scope": "worldwide",
            "region": "EMEA",
        },
    )

    assert job_response.status_code == 201
    assert job_response.json()["title"] == "Junior Frontend Developer"


def test_filter_jobs_by_remote_scope(client):
    source_response = client.post(
        "/sources",
        json={
            "name": "Example Jobs",
            "slug": "example-jobs",
        },
    )
    source_id = source_response.json()["id"]

    client.post(
        "/jobs",
        json={
            "title": "Remote Developer",
            "company": "Company A",
            "url": "https://example.com/jobs/1",
            "source_id": source_id,
            "remote_scope": "worldwide",
            "posted_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    response = client.get("/jobs?remote_scope=worldwide")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["remote_scope"] == "worldwide"


def test_duplicate_external_job_is_rejected(client):
    source_response = client.post(
        "/sources",
        json={
            "name": "Example Jobs",
            "slug": "example-jobs",
        },
    )
    source_id = source_response.json()["id"]

    payload = {
        "title": "Backend Developer",
        "company": "Company B",
        "url": "https://example.com/jobs/456",
        "external_id": "456",
        "source_id": source_id,
    }

    assert client.post("/jobs", json=payload).status_code == 201
    assert client.post("/jobs", json=payload).status_code == 409
