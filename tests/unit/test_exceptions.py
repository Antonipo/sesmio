"""Unit tests for sesmio.exceptions."""

from botocore.exceptions import ClientError

from sesmio.exceptions import (
    AccountSuspendedError,
    DailyQuotaExceededError,
    IdentityNotVerifiedError,
    MailFromDomainNotVerifiedError,
    MessageRejectedError,
    RecipientSuppressedError,
    SendError,
    SendingPausedError,
    ServiceUnavailableError,
    SesmioError,
    ThrottlingError,
    _map_client_error,
)


def _make_client_error(code: str, message: str = "error") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "SendEmail")


class TestExceptionHierarchy:
    def test_sesmisoerror_is_exception(self) -> None:
        assert issubclass(SesmioError, Exception)

    def test_send_error_is_sesmio_error(self) -> None:
        assert issubclass(SendError, SesmioError)

    def test_throttling_is_sesmio_error(self) -> None:
        assert issubclass(ThrottlingError, SesmioError)

    def test_daily_quota_is_sesmio_error(self) -> None:
        assert issubclass(DailyQuotaExceededError, SesmioError)

    def test_service_unavailable_is_sesmio_error(self) -> None:
        assert issubclass(ServiceUnavailableError, SesmioError)


class TestMapClientError:
    def test_message_rejected(self) -> None:
        exc = _make_client_error("MessageRejected")
        result = _map_client_error(exc)
        assert isinstance(result, MessageRejectedError)

    def test_throttling_exception(self) -> None:
        exc = _make_client_error("ThrottlingException")
        result = _map_client_error(exc)
        assert isinstance(result, ThrottlingError)

    def test_too_many_requests(self) -> None:
        exc = _make_client_error("TooManyRequestsException")
        result = _map_client_error(exc)
        assert isinstance(result, ThrottlingError)

    def test_limit_exceeded(self) -> None:
        exc = _make_client_error("LimitExceededException")
        result = _map_client_error(exc)
        assert isinstance(result, DailyQuotaExceededError)

    def test_not_found(self) -> None:
        exc = _make_client_error("NotFoundException")
        result = _map_client_error(exc)
        assert isinstance(result, IdentityNotVerifiedError)

    def test_account_suspended(self) -> None:
        exc = _make_client_error("AccountSuspendedException")
        result = _map_client_error(exc)
        assert isinstance(result, AccountSuspendedError)

    def test_sending_paused(self) -> None:
        exc = _make_client_error("SendingPausedException")
        result = _map_client_error(exc)
        assert isinstance(result, SendingPausedError)

    def test_mail_from_not_verified(self) -> None:
        exc = _make_client_error("MailFromDomainNotVerifiedException")
        result = _map_client_error(exc)
        assert isinstance(result, MailFromDomainNotVerifiedError)

    def test_service_unavailable(self) -> None:
        exc = _make_client_error("ServiceUnavailableException")
        result = _map_client_error(exc)
        assert isinstance(result, ServiceUnavailableError)

    def test_internal_failure(self) -> None:
        exc = _make_client_error("InternalFailure")
        result = _map_client_error(exc)
        assert isinstance(result, ServiceUnavailableError)

    def test_unknown_code_falls_back_to_send_error(self) -> None:
        exc = _make_client_error("SomeUnknownCode")
        result = _map_client_error(exc)
        assert isinstance(result, SendError)

    def test_suppression_message_detected(self) -> None:
        exc = _make_client_error("SomeCode", "Address is on the suppression list")
        result = _map_client_error(exc)
        assert isinstance(result, RecipientSuppressedError)

    def test_cause_is_set(self) -> None:
        exc = _make_client_error("MessageRejected", "spam")
        result = _map_client_error(exc)
        assert result.__cause__ is exc
