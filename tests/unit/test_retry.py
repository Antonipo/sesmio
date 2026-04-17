"""Unit tests for sesmio._internal.retry."""

from unittest.mock import patch

import pytest

from sesmio._internal.retry import with_retry
from sesmio.exceptions import (
    DailyQuotaExceededError,
    MessageRejectedError,
    ServiceUnavailableError,
    ThrottlingError,
)


def test_success_no_retry() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = with_retry(fn, max_retries=3)
    assert result == "ok"
    assert calls == 1


def test_retries_throttling_then_succeeds() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ThrottlingError("too fast")
        return "ok"

    with patch("sesmio._internal.retry.time.sleep"):
        result = with_retry(fn, max_retries=3)

    assert result == "ok"
    assert calls == 3


def test_retries_service_unavailable_then_succeeds() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ServiceUnavailableError("down")
        return "good"

    with patch("sesmio._internal.retry.time.sleep"):
        result = with_retry(fn, max_retries=3)

    assert result == "good"
    assert calls == 2


def test_exhausts_retries_raises_last_exception() -> None:
    def fn() -> str:
        raise ThrottlingError("always fails")

    with patch("sesmio._internal.retry.time.sleep"):
        with pytest.raises(ThrottlingError):
            with_retry(fn, max_retries=2)


def test_does_not_retry_daily_quota() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        raise DailyQuotaExceededError("quota done")

    with pytest.raises(DailyQuotaExceededError):
        with_retry(fn, max_retries=3)

    assert calls == 1  # no retry


def test_does_not_retry_message_rejected() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        raise MessageRejectedError("spam")

    with pytest.raises(MessageRejectedError):
        with_retry(fn, max_retries=3)

    assert calls == 1


def test_zero_retries() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        raise ThrottlingError("fast fail")

    with pytest.raises(ThrottlingError):
        with_retry(fn, max_retries=0)

    assert calls == 1
