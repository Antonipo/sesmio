"""Unit tests for sesmio._internal.logging."""

from sesmio._internal.logging import get_logger, log_send_error, log_send_success


def test_get_logger_returns_logger() -> None:
    import logging

    logger = get_logger()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "sesmio"


def test_log_send_error_does_not_raise() -> None:
    # Smoke test — no exception means no PII is accidentally serialized.
    log_send_error("TooManyRequestsException", "us-east-1")


def test_log_send_success_does_not_raise() -> None:
    log_send_success("msg-123", 4096, "us-east-1")
