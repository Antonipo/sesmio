"""Integration tests for the Django SesmioBackend."""

from __future__ import annotations

import os

import boto3
import django
import pytest
from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives
from moto import mock_aws


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(autouse=True, scope="module")
def configure_django() -> None:
    """Configure minimal Django settings for testing."""
    if not django_settings.configured:
        django_settings.configure(
            EMAIL_BACKEND="sesmio.integrations.django.SesmioBackend",
            SESMIO={
                "region_name": "us-east-1",
                "default_from": "sender@example.com",
            },
            DATABASES={},
            INSTALLED_APPS=[],
        )
        django.setup()


def _make_boto3_session() -> boto3.Session:
    return boto3.Session(region_name="us-east-1")


class TestSendMail:
    @mock_aws
    def test_send_mail_basic(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        # Patch the backend's SES with a moto-aware session.
        from sesmio.integrations.django import SesmioBackend

        session = boto3.Session(region_name="us-east-1")
        backend = SesmioBackend()
        from sesmio import SES

        backend._ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(backend._ses)

        from django.core.mail import EmailMessage

        msg = EmailMessage(
            subject="Hello",
            body="Text body",
            from_email="sender@example.com",
            to=["user@example.com"],
        )
        count = backend.send_messages([msg])
        assert count == 1

    @mock_aws
    def test_send_mail_html_alternative(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        from sesmio import SES
        from sesmio.integrations.django import SesmioBackend

        session = boto3.Session(region_name="us-east-1")
        backend = SesmioBackend()
        backend._ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(backend._ses)

        msg = EmailMultiAlternatives(
            subject="Hello HTML",
            body="Plain text body",
            from_email="sender@example.com",
            to=["user@example.com"],
        )
        msg.attach_alternative("<p>HTML body</p>", "text/html")
        count = backend.send_messages([msg])
        assert count == 1

    @mock_aws
    def test_send_mail_with_attachment(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        from django.core.mail import EmailMessage

        from sesmio import SES
        from sesmio.integrations.django import SesmioBackend

        session = boto3.Session(region_name="us-east-1")
        backend = SesmioBackend()
        backend._ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(backend._ses)

        msg = EmailMessage(
            subject="With attachment",
            body="See attached",
            from_email="sender@example.com",
            to=["user@example.com"],
        )
        msg.attach("report.txt", b"file content", "text/plain")
        count = backend.send_messages([msg])
        assert count == 1

    @mock_aws
    def test_empty_list_returns_zero(self) -> None:
        from sesmio.integrations.django import SesmioBackend

        backend = SesmioBackend()
        assert backend.send_messages([]) == 0

    @mock_aws
    def test_fail_silently_swallows_errors(self) -> None:
        from django.core.mail import EmailMessage

        from sesmio import SES
        from sesmio.integrations.django import SesmioBackend

        # No identity created → sending will fail.
        session = boto3.Session(region_name="us-east-1")
        backend = SesmioBackend(fail_silently=True)
        backend._ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(backend._ses)

        msg = EmailMessage(
            subject="Test",
            body="Body",
            from_email="sender@example.com",
            to=["user@example.com"],
        )
        # Should not raise.
        count = backend.send_messages([msg])
        assert count == 0

    @mock_aws
    def test_fail_silently_false_raises(self) -> None:
        from django.core.mail import EmailMessage

        from sesmio import SES
        from sesmio.integrations.django import SesmioBackend

        session = boto3.Session(region_name="us-east-1")
        backend = SesmioBackend(fail_silently=False)
        backend._ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(backend._ses)

        msg = EmailMessage(
            subject="Test",
            body="Body",
            from_email="sender@example.com",
            to=["user@example.com"],
        )
        with pytest.raises(Exception):
            backend.send_messages([msg])

    @mock_aws
    def test_multiple_messages_count(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        from django.core.mail import EmailMessage

        from sesmio import SES
        from sesmio.integrations.django import SesmioBackend

        session = boto3.Session(region_name="us-east-1")
        backend = SesmioBackend()
        backend._ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(backend._ses)

        messages = [
            EmailMessage(
                subject=f"Msg {i}",
                body="body",
                from_email="sender@example.com",
                to=["user@example.com"],
            )
            for i in range(5)
        ]
        count = backend.send_messages(messages)
        assert count == 5

    @mock_aws
    def test_translate_cc_bcc_reply_to(self) -> None:
        from django.core.mail import EmailMessage

        from sesmio.integrations.django import SesmioBackend

        msg = EmailMessage(
            subject="Test",
            body="body",
            from_email="s@example.com",
            to=["to@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            reply_to=["reply@example.com"],
            headers={"X-Custom": "value"},
        )
        kwargs = SesmioBackend._translate(msg)
        assert kwargs["cc"] == ["cc@example.com"]
        assert kwargs["bcc"] == ["bcc@example.com"]
        assert kwargs["reply_to"] == ["reply@example.com"]
        assert kwargs["headers"] == {"X-Custom": "value"}


def _patch_get_account(ses: object) -> None:
    from sesmio import SES

    real_ses: SES = ses  # type: ignore[assignment]
    original = real_ses._get_client

    def patched() -> object:
        client = original()
        if not hasattr(client, "_sesmio_patched"):
            client.get_account = lambda **kw: {"ProductionAccessEnabled": True}  # type: ignore[attr-defined]
            client._sesmio_patched = True  # type: ignore[attr-defined]
        return client

    real_ses._get_client = patched  # type: ignore[method-assign]
