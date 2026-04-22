"""sesmio — Framework-agnostic AWS SES wrapper for Python.

A lightweight library that wraps SES v2 with typed exceptions, MIME
multipart building, automatic retry, and PII-free logging.

Quick start::

    from sesmio import SES

    ses = SES(region_name="us-east-1", default_from="no-reply@example.com")
    msg_id = ses.send(
        to="user@example.com",
        subject="Welcome",
        html="<p>Hello!</p>",
    )

Exports:
    SES: Main client class.
    SesmioError and subclasses: Full exception hierarchy.
"""

__version__ = "0.2.0"

from sesmio.client import SES  # noqa: E402
from sesmio.exceptions import (
    AccountSuspendedError,
    ConfigurationError,
    DailyQuotaExceededError,
    HeaderInjectionError,
    IdentityNotVerifiedError,
    InvalidRecipientError,
    MailFromDomainNotVerifiedError,
    MessageRejectedError,
    MessageTooLargeError,
    RecipientSuppressedError,
    SendError,
    SendingPausedError,
    ServiceUnavailableError,
    SesmioError,
    ThrottlingError,
    ValidationError,
)

__all__ = [
    "__version__",
    "SES",
    "SesmioError",
    "ConfigurationError",
    "ValidationError",
    "InvalidRecipientError",
    "MessageTooLargeError",
    "HeaderInjectionError",
    "SendError",
    "MessageRejectedError",
    "IdentityNotVerifiedError",
    "AccountSuspendedError",
    "SendingPausedError",
    "MailFromDomainNotVerifiedError",
    "RecipientSuppressedError",
    "ThrottlingError",
    "DailyQuotaExceededError",
    "ServiceUnavailableError",
]
