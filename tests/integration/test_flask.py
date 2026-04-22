"""Integration tests for the Flask SESExtension."""

from __future__ import annotations

import os

import boto3
import pytest
from flask import Flask
from moto import mock_aws

from sesmio import SES
from sesmio.integrations.flask import SESExtension


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def _patch_get_account(ses: SES) -> None:
    original = ses._get_client

    def patched() -> object:
        client = original()
        if not hasattr(client, "_sesmio_patched"):
            client.get_account = lambda **kw: {"ProductionAccessEnabled": True}  # type: ignore[attr-defined]
            client._sesmio_patched = True  # type: ignore[attr-defined]
        return client

    ses._get_client = patched  # type: ignore[method-assign]


class TestDirectInit:
    @mock_aws
    def test_direct_init_and_send(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )

        app = Flask(__name__)
        session = boto3.Session(region_name="us-east-1")
        ses_ext = SESExtension(
            app,
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(ses_ext._ses)

        @app.route("/send")
        def send_route() -> str:
            msg_id = ses_ext.send(
                to="user@example.com",
                subject="Hello",
                html="<p>Hi</p>",
            )
            return msg_id

        with app.test_client() as client:
            response = client.get("/send")
            assert response.status_code == 200
            assert len(response.data) > 0

    @mock_aws
    def test_extension_stored_in_app_extensions(self) -> None:
        app = Flask(__name__)
        ses_ext = SESExtension(
            app,
            region_name="us-east-1",
            default_from="sender@example.com",
        )
        assert "sesmio" in app.extensions
        assert app.extensions["sesmio"] is ses_ext


class TestAppFactory:
    @mock_aws
    def test_init_app_pattern(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )

        ses_ext = SESExtension()

        app = Flask(__name__)
        app.config["SESMIO_REGION"] = "us-east-1"
        app.config["SESMIO_DEFAULT_FROM"] = "sender@example.com"

        session = boto3.Session(region_name="us-east-1")

        def create_app() -> Flask:
            # Override with real session after config is set.
            ses_ext.init_app(app)
            # Inject a session-based client for moto.
            ses_ext._ses._boto3_session = session  # type: ignore[attr-defined]
            ses_ext._ses._client = None  # Force re-init with session.
            _patch_get_account(ses_ext._ses)
            return app

        created = create_app()

        @created.route("/send")
        def send_route() -> str:
            msg_id = ses_ext.send(
                to="user@example.com",
                subject="Hi",
                html="<p>Hello</p>",
            )
            return msg_id

        with created.test_client() as c:
            response = c.get("/send")
            assert response.status_code == 200

    @mock_aws
    def test_init_app_reads_config(self) -> None:
        app = Flask(__name__)
        app.config["SESMIO_REGION"] = "eu-west-1"
        app.config["SESMIO_DEFAULT_FROM"] = "from@example.com"
        app.config["SESMIO_MAX_RETRIES"] = "5"

        ses_ext = SESExtension()
        ses_ext.init_app(app)

        ses: SES = ses_ext._ses  # type: ignore[assignment]
        assert ses._region_name == "eu-west-1"
        assert ses._default_from == "from@example.com"
        assert ses._max_retries == 5

    def test_require_ses_raises_before_init(self) -> None:
        ses_ext = SESExtension()
        with pytest.raises(RuntimeError, match="not initialised"):
            ses_ext.send(to="u@example.com", subject="s", html="<p>h</p>")


class TestTemplatesAndBulk:
    def test_templates_property_returns_ses_templates(self) -> None:
        from sesmio.templates import SESTemplates

        app = Flask(__name__)
        ses_ext = SESExtension(app, region_name="us-east-1", default_from="s@example.com")
        assert isinstance(ses_ext.templates, SESTemplates)

    @mock_aws
    def test_bulk_method_available(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )

        app = Flask(__name__)
        session = boto3.Session(region_name="us-east-1")
        ses_ext = SESExtension(
            app,
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        _patch_get_account(ses_ext._ses)

        from sesmio.email.components import Body, Container, Head, Html, Text
        from sesmio.sender import Recipient

        def tmpl(name: str = "") -> Html:
            return Html(Head(), Body(Container(Text(name))))

        recipients = [Recipient(to="r@example.com", args={"name": "Alice"})]
        results = ses_ext.bulk(tmpl, recipients, subject="Hi").send()
        assert len(results) == 1
        assert results[0].status == "success"
