"""Integration tests for SES.send() using moto."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    """Provide fake AWS credentials so moto never hits real AWS."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def _make_ses(mock_get_account: bool = True) -> object:
    """Create a SES instance with mocked get_account to avoid moto limitation."""
    from sesmio import SES

    session = boto3.Session(region_name="us-east-1")
    ses = SES(
        region_name="us-east-1",
        default_from="sender@example.com",
        boto3_session=session,
    )
    if mock_get_account:
        # moto does not implement get_account; patch it to return sandbox=False.
        original_get_client = ses._get_client

        def patched_get_client() -> object:
            client = original_get_client()
            if not hasattr(client, "_sesmio_patched"):

                def get_account(**kwargs: object) -> dict[str, object]:
                    return {"ProductionAccessEnabled": True}

                client.get_account = get_account
                client._sesmio_patched = True  # type: ignore[attr-defined]
            return client

        ses._get_client = patched_get_client  # type: ignore[method-assign]
    return ses


class TestHappyPath:
    @mock_aws
    def test_send_returns_message_id(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Hello",
            html="<p>Hi there</p>",
        )
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    @mock_aws
    def test_send_text_only(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Text only",
            text="Hello plain",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_html_and_text(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Both",
            html="<p>Hello</p>",
            text="Hello",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_multiple_recipients(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to=["recipient@example.com", "another@example.com"],
            subject="Multi",
            html="<p>Hi all</p>",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_cc_and_bcc(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="CC BCC",
            html="<p>Hi</p>",
            cc="recipient@example.com",
            bcc="recipient@example.com",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_tags(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Tagged",
            html="<p>Hi</p>",
            tags={"campaign": "welcome", "tier": "free"},
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_custom_headers(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Headers",
            html="<p>Hi</p>",
            headers={"X-Custom": "value"},
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_attachment_bytes(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Attachment",
            html="<p>See attached</p>",
            attachments=[
                {
                    "content": b"%PDF fake",
                    "filename": "doc.pdf",
                    "content_type": "application/pdf",
                }
            ],
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_attachment_path(self, tmp_path: Path) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        f = tmp_path / "report.txt"
        f.write_bytes(b"report content")
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Path attachment",
            html="<p>Report</p>",
            attachments=[f],
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_from_default_used(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(to="r@example.com", subject="Default from", html="<p>Hi</p>")
        assert isinstance(msg_id, str)

    @mock_aws
    def test_explicit_from_overrides_default(self) -> None:
        from sesmio import SES

        raw = boto3.client("sesv2", region_name="us-east-1")
        raw.create_email_identity(EmailIdentity="sender@example.com")
        raw.create_email_identity(EmailIdentity="explicit@example.com")

        session = boto3.Session(region_name="us-east-1")
        ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        # Patch get_account for this instance too.
        original = ses._get_client

        def pg() -> object:
            c = original()
            if not hasattr(c, "_patched2"):
                c.get_account = lambda **kw: {"ProductionAccessEnabled": True}  # type: ignore[attr-defined]
                c._patched2 = True  # type: ignore[attr-defined]
            return c

        ses._get_client = pg  # type: ignore[method-assign]
        msg_id = ses.send(
            to="r@example.com",
            subject="Explicit from",
            html="<p>Hi</p>",
            from_="explicit@example.com",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_reply_to(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Reply-To",
            html="<p>Hi</p>",
            reply_to="replies@example.com",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_with_return_path(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Return-Path",
            html="<p>Hi</p>",
            return_path="bounces@example.com",
        )
        assert isinstance(msg_id, str)


class TestExceptions:
    def test_no_from_raises_configuration_error(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import ConfigurationError

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(region_name="us-east-1", boto3_session=session)
            with pytest.raises(ConfigurationError):
                ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_invalid_recipient_raises(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import InvalidRecipientError

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with pytest.raises(InvalidRecipientError):
                ses.send(to="notanemail", subject="s", html="<p>h</p>")

    def test_header_injection_raises(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import HeaderInjectionError

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with pytest.raises(HeaderInjectionError):
                ses.send(
                    to="r@example.com",
                    subject="bad\nsubject",
                    html="<p>h</p>",
                )

    def test_message_too_large_raises(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import MessageTooLargeError

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            big = "x" * (11 * 1024 * 1024)
            with pytest.raises(MessageTooLargeError):
                ses.send(to="r@example.com", subject="Big", html=big)

    def test_throttling_error_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import ThrottlingError

        error_response = {"Error": {"Code": "TooManyRequestsException", "Message": "rate exceeded"}}

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                max_retries=0,
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(ThrottlingError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_message_rejected_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import MessageRejectedError

        error_response = {"Error": {"Code": "MessageRejected", "Message": "spam"}}

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(MessageRejectedError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_daily_quota_exceeded_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import DailyQuotaExceededError

        error_response = {"Error": {"Code": "LimitExceededException", "Message": "daily quota"}}

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(DailyQuotaExceededError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_service_unavailable_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import ServiceUnavailableError

        error_response = {"Error": {"Code": "ServiceUnavailableException", "Message": "down"}}

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                max_retries=0,
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(ServiceUnavailableError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_identity_not_verified_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import IdentityNotVerifiedError

        error_response = {"Error": {"Code": "NotFoundException", "Message": "not verified"}}

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(IdentityNotVerifiedError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_recipient_suppressed_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import RecipientSuppressedError

        error_response = {
            "Error": {
                "Code": "SomeError",
                "Message": "Address is on the suppression list",
            }
        }

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(RecipientSuppressedError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")

    def test_account_suspended_mapped(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import AccountSuspendedError

        error_response = {"Error": {"Code": "AccountSuspendedException", "Message": "suspended"}}

        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )
            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.side_effect = ClientError(
                    error_response, "SendEmail"
                )
                with pytest.raises(AccountSuspendedError):
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")


class TestSandboxWarning:
    def test_sandbox_warning_logged(self) -> None:
        from sesmio import SES

        with mock_aws():
            raw = boto3.client("sesv2", region_name="us-east-1")
            raw.create_email_identity(EmailIdentity="sender@example.com")
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )

            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": False
                }
                mock_client.return_value.send_email.return_value = {"MessageId": "mock-id"}

                with patch("sesmio._internal.logging._logger") as mock_logger:
                    ses.send(to="r@example.com", subject="s", html="<p>h</p>")
                    mock_logger.warning.assert_called()

    def test_sandbox_only_checked_once(self) -> None:
        from sesmio import SES

        with mock_aws():
            raw = boto3.client("sesv2", region_name="us-east-1")
            raw.create_email_identity(EmailIdentity="sender@example.com")
            session = boto3.Session(region_name="us-east-1")
            ses = SES(
                region_name="us-east-1",
                default_from="sender@example.com",
                boto3_session=session,
            )

            with patch.object(ses, "_get_client") as mock_client:
                mock_client.return_value.get_account.return_value = {
                    "ProductionAccessEnabled": True
                }
                mock_client.return_value.send_email.return_value = {"MessageId": "mock-id-1"}
                ses.send(to="r@example.com", subject="s", html="<p>h</p>")

                mock_client.return_value.send_email.return_value = {"MessageId": "mock-id-2"}
                ses.send(to="r@example.com", subject="s2", html="<p>h2</p>")

                assert mock_client.return_value.get_account.call_count == 1
