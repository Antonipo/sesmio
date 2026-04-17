"""Unit tests for sesmio._internal.validation."""

import pytest

from sesmio._internal.validation import (
    check_header_injection,
    check_size,
    validate_email,
    validate_emails,
)
from sesmio.exceptions import HeaderInjectionError, InvalidRecipientError, MessageTooLargeError


class TestValidateEmail:
    def test_valid_simple(self) -> None:
        validate_email("user@example.com")

    def test_valid_subdomain(self) -> None:
        validate_email("user@mail.example.co.uk")

    def test_valid_plus(self) -> None:
        validate_email("user+tag@example.com")

    def test_valid_dots(self) -> None:
        validate_email("first.last@example.com")

    def test_invalid_no_at(self) -> None:
        with pytest.raises(InvalidRecipientError):
            validate_email("notanemail")

    def test_invalid_no_domain(self) -> None:
        with pytest.raises(InvalidRecipientError):
            validate_email("user@")

    def test_invalid_no_tld(self) -> None:
        with pytest.raises(InvalidRecipientError):
            validate_email("user@example")

    def test_invalid_double_at(self) -> None:
        with pytest.raises(InvalidRecipientError):
            validate_email("user@@example.com")

    def test_too_long(self) -> None:
        long_addr = "a" * 250 + "@example.com"
        with pytest.raises(InvalidRecipientError):
            validate_email(long_addr)

    def test_empty_string(self) -> None:
        with pytest.raises(InvalidRecipientError):
            validate_email("")


class TestValidateEmails:
    def test_multiple_valid(self) -> None:
        validate_emails(["a@b.com", "c@d.org"])

    def test_first_invalid_raises(self) -> None:
        with pytest.raises(InvalidRecipientError):
            validate_emails(["bad", "ok@ok.com"])

    def test_empty_list(self) -> None:
        validate_emails([])  # should not raise


class TestCheckHeaderInjection:
    def test_clean_value(self) -> None:
        check_header_injection("Clean Header Value")

    def test_cr_raises(self) -> None:
        with pytest.raises(HeaderInjectionError):
            check_header_injection("value\rinjected")

    def test_lf_raises(self) -> None:
        with pytest.raises(HeaderInjectionError):
            check_header_injection("value\ninjected")

    def test_crlf_raises(self) -> None:
        with pytest.raises(HeaderInjectionError):
            check_header_injection("value\r\ninjected")

    def test_header_name_included_in_message(self) -> None:
        with pytest.raises(HeaderInjectionError, match="X-Custom"):
            check_header_injection("bad\nvalue", "X-Custom")


class TestCheckSize:
    def test_under_limit(self) -> None:
        check_size(b"x" * (10 * 1024 * 1024 - 1))

    def test_at_limit(self) -> None:
        check_size(b"x" * (10 * 1024 * 1024))

    def test_over_limit(self) -> None:
        with pytest.raises(MessageTooLargeError):
            check_size(b"x" * (10 * 1024 * 1024 + 1))
