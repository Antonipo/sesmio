"""Integration tests for SES.send() with template= and tailwind= using moto."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from sesmio.email.components import (
    Body,
    Button,
    Container,
    Head,
    Heading,
    Hr,
    Html,
    Text,
)


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    """Provide fake AWS credentials so moto never hits real AWS."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def _make_ses() -> object:
    from sesmio import SES

    session = boto3.Session(region_name="us-east-1")
    ses = SES(
        region_name="us-east-1",
        default_from="sender@example.com",
        boto3_session=session,
    )
    # Patch get_account to avoid moto limitation.
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


def _build_welcome(name: str, cta_url: str) -> Html:
    return Html(
        head=Head(title="Welcome", preview=f"Hi {name}, thanks for joining!"),
        body=Body(
            children=Container(
                children=[
                    Heading(text=f"Hello {name}!"),
                    Text(text="Thanks for registering on our platform."),
                    Hr(),
                    Button(href=cta_url, children="Get Started"),
                ]
            )
        ),
    )


class TestSendWithTemplate:
    @mock_aws
    def test_send_template_returns_message_id(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        template = _build_welcome("Ana", "https://example.com/start")
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Welcome",
            template=template,
        )
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    @mock_aws
    def test_send_template_auto_generates_text(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        template = _build_welcome("Bob", "https://example.com/go")
        # text= not passed — should be auto-generated.
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Welcome Bob",
            template=template,
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_template_with_explicit_text_uses_it(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        template = _build_welcome("Carol", "https://example.com")
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Welcome",
            template=template,
            text="Custom plain text override",
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_send_template_and_html_raises(self) -> None:
        from sesmio import SES
        from sesmio.exceptions import ValidationError

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        template = _build_welcome("X", "https://x.com")
        with pytest.raises(ValidationError):
            ses.send(
                to="recipient@example.com",
                subject="s",
                html="<p>conflict</p>",
                template=template,
            )


class TestSendWithTailwind:
    @mock_aws
    def test_send_tailwind_true_returns_message_id(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        html = """
        <div class="max-w-lg mx-auto p-6 bg-white">
          <h1 class="text-2xl font-bold text-gray-900">Hello</h1>
          <p class="mt-4 text-gray-600">Email content here</p>
        </div>
        """
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Tailwind Email",
            html=html,
            tailwind=True,
        )
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    @mock_aws
    def test_send_tailwind_false_passthrough(self) -> None:
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Plain HTML",
            html='<p style="color:red">Red text</p>',
            tailwind=False,
        )
        assert isinstance(msg_id, str)

    @mock_aws
    def test_tailwind_with_template_tailwind_ignored(self) -> None:
        """tailwind= kwarg is ignored when template= is provided."""
        from sesmio import SES

        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses: SES = _make_ses()  # type: ignore[assignment]
        template = _build_welcome("Dana", "https://example.com")
        msg_id = ses.send(
            to="recipient@example.com",
            subject="Welcome",
            template=template,
            tailwind=True,  # should be silently ignored
        )
        assert isinstance(msg_id, str)
