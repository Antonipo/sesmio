"""Input validation: RFC 5322 email addresses, CRLF injection, 10 MB size limit."""

from __future__ import annotations

import re

from sesmio.exceptions import HeaderInjectionError, InvalidRecipientError, MessageTooLargeError

# RFC 5322 simplified — covers the vast majority of real addresses.
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}$"
)

_MAX_EMAIL_LENGTH = 254  # RFC 5321 hard limit
_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_email(address: str) -> None:
    """Raise :class:`InvalidRecipientError` if *address* is not a valid RFC 5322 email."""
    if len(address) > _MAX_EMAIL_LENGTH or not _EMAIL_RE.match(address):
        raise InvalidRecipientError(f"Invalid email address: {address!r}")


def validate_emails(addresses: list[str]) -> None:
    """Validate a list of email addresses, raising on the first invalid one."""
    for addr in addresses:
        validate_email(addr)


def check_header_injection(value: str, header_name: str = "header") -> None:
    """Raise :class:`HeaderInjectionError` if *value* contains CR or LF characters."""
    if "\r" in value or "\n" in value:
        raise HeaderInjectionError(f"CRLF injection attempt detected in {header_name!r}: {value!r}")


def check_size(data: bytes) -> None:
    """Raise :class:`MessageTooLargeError` if *data* exceeds 10 MB."""
    if len(data) > _MAX_SIZE_BYTES:
        raise MessageTooLargeError(f"Message size {len(data):,} bytes exceeds the 10 MB SES limit")
