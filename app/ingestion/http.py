import time
from collections.abc import Callable

import httpx


def get_with_retries(
    request: Callable[[], httpx.Response],
    *,
    retries: int,
    backoff_seconds: float,
) -> httpx.Response:
    for attempt in range(retries + 1):
        try:
            response = request()
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            retryable = (
                exc.response.status_code == 429
                or exc.response.status_code >= 500
            )
            if not retryable or attempt == retries:
                raise
        except httpx.TransportError:
            if attempt == retries:
                raise

        time.sleep(backoff_seconds * (2**attempt))

    raise RuntimeError("HTTP retry loop ended unexpectedly")
