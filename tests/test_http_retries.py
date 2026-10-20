import httpx
import pytest

from app.ingestion import http as ingestion_http


def _response(status_code: int) -> httpx.Response:
    request = httpx.Request("GET", "https://example.com/feed")
    return httpx.Response(status_code, request=request)


def test_retries_transient_http_failure_with_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            _response(503),
            _response(200),
        ]
    )
    sleeps: list[float] = []

    def request() -> httpx.Response:
        return next(responses)

    monkeypatch.setattr(ingestion_http.time, "sleep", sleeps.append)

    result = ingestion_http.get_with_retries(
        request,
        retries=2,
        backoff_seconds=0.2,
    )

    assert result.status_code == 200
    assert sleeps == [0.2]


def test_does_not_retry_non_transient_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0

    def request() -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return _response(404)

    monkeypatch.setattr(
        ingestion_http.time,
        "sleep",
        lambda _: pytest.fail("non-transient failure must not retry"),
    )

    with pytest.raises(httpx.HTTPStatusError):
        ingestion_http.get_with_retries(
            request,
            retries=3,
            backoff_seconds=0.1,
        )

    assert request_count == 1
