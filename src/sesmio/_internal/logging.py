"""PII-free logger for sesmio.

Never logs: to, cc, bcc, subject, body, or attachment content.
Always safe to log: message_id, region, size_bytes, error codes.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("sesmio")


def get_logger() -> logging.Logger:
    """Return the sesmio library logger."""
    return _logger


def log_send_success(message_id: str, size_bytes: int, region: str) -> None:
    """Log a successful send without any PII."""
    _logger.info(
        "send.success",
        extra={"message_id": message_id, "size_bytes": size_bytes, "region": region},
    )


def log_send_error(error_code: str, region: str) -> None:
    """Log a send error by error code only — no recipient or content data."""
    _logger.warning(
        "send.error",
        extra={"error_code": error_code, "region": region},
    )


def log_sandbox_warning(region: str) -> None:
    """Warn that the SES account is in sandbox mode on the first send."""
    _logger.warning(
        "SES account is in sandbox mode in region %s. "
        "Outbound email is restricted to verified addresses only. "
        "Request production access at https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html",
        region,
    )
