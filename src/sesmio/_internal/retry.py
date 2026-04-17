"""Exponential backoff with jitter for transient SES errors."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from sesmio.exceptions import ServiceUnavailableError, SesmioError, ThrottlingError

_T = TypeVar("_T")

# Only these exceptions trigger a retry — DailyQuotaExceededError is NOT retried.
_RETRYABLE = (ThrottlingError, ServiceUnavailableError)

_BASE_DELAY = 0.1  # seconds
_JITTER_MAX = 0.1  # seconds


def with_retry(fn: Callable[[], _T], max_retries: int = 3) -> _T:
    """Call *fn* up to *max_retries* times, retrying on transient SES errors.

    Uses ``0.1 * 2^attempt + jitter(0, 0.1)`` backoff. Only retries
    :class:`~sesmio.exceptions.ThrottlingError` and
    :class:`~sesmio.exceptions.ServiceUnavailableError`.
    """
    last_exc: SesmioError | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (ThrottlingError, ServiceUnavailableError) as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = _BASE_DELAY * (2**attempt) + random.uniform(0, _JITTER_MAX)
            time.sleep(delay)
    # last_exc is always set — we only reach here after a retryable exception.
    assert last_exc is not None
    raise last_exc
