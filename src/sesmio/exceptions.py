"""Exception hierarchy for sesmio.

All exceptions inherit from :class:`SesmioError`, making it easy to
catch any library-specific error with a single ``except SesmioError``.

The hierarchy maps common SES v2 ``ClientError`` codes to semantically
meaningful Python exceptions::

    SesmioError
    ├── ConfigurationError
    ├── ValidationError
    │   ├── InvalidRecipientError
    │   ├── MessageTooLargeError
    │   └── HeaderInjectionError
    ├── SendError
    │   ├── MessageRejectedError
    │   ├── IdentityNotVerifiedError
    │   ├── AccountSuspendedError
    │   ├── SendingPausedError
    │   ├── MailFromDomainNotVerifiedError
    │   ├── RecipientSuppressedError
    │   └── TemplateDoesNotExistError
    ├── ThrottlingError
    ├── DailyQuotaExceededError
    └── ServiceUnavailableError
"""

from __future__ import annotations

from botocore.exceptions import ClientError


class SesmioError(Exception):
    """Base exception for all sesmio errors."""


class ConfigurationError(SesmioError):
    """Raised for missing region, missing sender identity, or invalid credentials."""


class ValidationError(SesmioError):
    """Raised for invalid email addresses, oversized messages, or CRLF injection."""


class InvalidRecipientError(ValidationError):
    """Raised when an email address fails RFC 5322 validation."""


class MessageTooLargeError(ValidationError):
    """Raised when the total message size exceeds 10 MB."""


class HeaderInjectionError(ValidationError):
    """Raised when a header value contains CR or LF characters."""


class SendError(SesmioError):
    """Base class for errors returned by SES during a send operation."""


class MessageRejectedError(SendError):
    """Raised when SES rejects the message (spam, invalid content, etc.)."""


class IdentityNotVerifiedError(SendError):
    """Raised when the From/Return-Path identity has not been verified in SES."""


class AccountSuspendedError(SendError):
    """Raised when the AWS account's sending capability has been suspended."""


class SendingPausedError(SendError):
    """Raised when sending is paused for the configuration set."""


class MailFromDomainNotVerifiedError(SendError):
    """Raised when the MAIL FROM domain is not verified."""


class RecipientSuppressedError(SendError):
    """Raised when the recipient address is on the account-level suppression list."""


class TemplateDoesNotExistError(SendError):
    """Raised when the referenced SES native template does not exist."""


class ThrottlingError(SesmioError):
    """Raised when SES rate limits are exceeded. Retried automatically."""


class DailyQuotaExceededError(SesmioError):
    """Raised when the 24-hour sending quota is exhausted. Not retried."""


class ServiceUnavailableError(SesmioError):
    """Raised on SES 5xx errors. Retried automatically."""


# Maps SES v2 ClientError codes to sesmio exceptions.
_ERROR_MAP: dict[str, type[SesmioError]] = {
    "MessageRejected": MessageRejectedError,
    "MailFromDomainNotVerifiedException": MailFromDomainNotVerifiedError,
    "AccountSuspendedException": AccountSuspendedError,
    "SendingPausedException": SendingPausedError,
    "LimitExceededException": DailyQuotaExceededError,
    "TooManyRequestsException": ThrottlingError,
    "ThrottlingException": ThrottlingError,
    "AccountSendingPausedException": SendingPausedError,
    "NotFoundException": IdentityNotVerifiedError,
    "ServiceUnavailableException": ServiceUnavailableError,
    "InternalFailure": ServiceUnavailableError,
}

_SUPPRESSION_MESSAGES = ("suppression list", "suppressed", "AccountSuppressedAddress")


def _map_client_error(exc: ClientError) -> SesmioError:
    """Map a botocore ``ClientError`` to the appropriate :class:`SesmioError` subclass."""
    code: str = exc.response["Error"]["Code"]
    message: str = exc.response["Error"].get("Message", "")

    # Check suppression indicators in the message before the generic code map.
    if any(indicator in message for indicator in _SUPPRESSION_MESSAGES):
        mapped: SesmioError = RecipientSuppressedError(message)
        mapped.__cause__ = exc
        return mapped

    exc_class = _ERROR_MAP.get(code, SendError)
    result: SesmioError = exc_class(message)
    result.__cause__ = exc
    return result
