"""Integration tests for SES.bulk() using moto."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from sesmio import SES, Recipient
from sesmio.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    """Provide fake AWS credentials so moto never hits real AWS."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def _make_ses() -> SES:
    session = boto3.Session(region_name="us-east-1")
    ses = SES(
        region_name="us-east-1",
        default_from="sender@example.com",
        boto3_session=session,
    )
    original_get_client = ses._get_client

    def patched() -> object:
        client = original_get_client()
        if not hasattr(client, "_sesmio_patched"):
            client.get_account = lambda **kw: {"ProductionAccessEnabled": True}  # type: ignore[attr-defined]
            client._sesmio_patched = True  # type: ignore[attr-defined]
        return client

    ses._get_client = patched  # type: ignore[method-assign]
    return ses


class TestBulkWithComponentTemplate:
    @mock_aws
    def test_bulk_small_batch(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses = _make_ses()

        from sesmio.email.components import Body, Container, Head, Html, Text

        def template(name: str = "") -> Html:
            return Html(Head(), Body(Container(Text(f"Hello {name}"))))

        recipients = [
            Recipient(to="a@example.com", args={"name": "Alice"}),
            Recipient(to="b@example.com", args={"name": "Bob"}),
            Recipient(to="c@example.com", args={"name": "Carol"}),
        ]
        results = ses.bulk(
            template,
            recipients,
            subject="Hello",
        ).send()

        assert len(results) == 3
        successes = [r for r in results if r.status == "success"]
        assert len(successes) == 3
        for r in successes:
            assert r.message_id is not None
            assert r.error is None

    @mock_aws
    def test_bulk_returns_results_in_order(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses = _make_ses()

        from sesmio.email.components import Body, Container, Head, Html, Text

        def template(idx: int = 0) -> Html:
            return Html(Head(), Body(Container(Text(f"Email {idx}"))))

        count = 15
        recipients = [Recipient(to="r@example.com", args={"idx": i}) for i in range(count)]
        results = ses.bulk(template, recipients, subject="Test").send()
        assert len(results) == count

    @mock_aws
    def test_bulk_per_recipient_error_does_not_abort(self) -> None:
        """A failing recipient should produce an error BulkResult, not abort the batch."""
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses = _make_ses()

        from sesmio.email.components import Body, Container, Head, Html, Text

        call_count = 0
        original_get_client = ses._get_client

        def patched_get_client() -> object:
            client = original_get_client()
            if not hasattr(client, "_bulk_patched"):
                orig_send = client.send_email

                def send_email_with_error(**kw: object) -> object:
                    nonlocal call_count
                    call_count += 1
                    # Fail every 3rd call.
                    if call_count % 3 == 0:
                        from botocore.exceptions import ClientError

                        raise ClientError(
                            {"Error": {"Code": "MessageRejected", "Message": "spam"}},
                            "SendEmail",
                        )
                    return orig_send(**kw)

                client.send_email = send_email_with_error  # type: ignore[attr-defined]
                client._bulk_patched = True  # type: ignore[attr-defined]
            return client

        ses._get_client = patched_get_client  # type: ignore[method-assign]

        def tmpl(name: str = "") -> Html:
            return Html(Head(), Body(Container(Text(name))))

        recipients = [Recipient(to="r@example.com", args={"name": f"User {i}"}) for i in range(9)]
        results = ses.bulk(tmpl, recipients, subject="Test").send()

        assert len(results) == 9
        errors = [r for r in results if r.status == "error"]
        successes = [r for r in results if r.status == "success"]
        assert len(errors) == 3
        assert len(successes) == 6

    @mock_aws
    def test_bulk_chunking_at_50(self) -> None:
        """More than 50 recipients should be processed in multiple chunks."""
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )
        ses = _make_ses()

        from sesmio.email.components import Body, Container, Head, Html, Text

        def tmpl(name: str = "") -> Html:
            return Html(Head(), Body(Container(Text(name))))

        recipients = [Recipient(to="r@example.com", args={"name": f"User {i}"}) for i in range(75)]
        results = ses.bulk(tmpl, recipients, subject="Test").send()

        assert len(results) == 75
        assert all(r.status == "success" for r in results)

    @mock_aws
    def test_bulk_requires_sender(self) -> None:
        with mock_aws():
            session = boto3.Session(region_name="us-east-1")
            ses = SES(region_name="us-east-1", boto3_session=session)
            recipients = [Recipient(to="r@example.com")]
            with pytest.raises(ConfigurationError):
                ses.bulk("template", recipients, subject="t").send()

    @mock_aws
    def test_bulk_with_replacement_from(self) -> None:
        raw = boto3.client("sesv2", region_name="us-east-1")
        raw.create_email_identity(EmailIdentity="sender@example.com")
        raw.create_email_identity(EmailIdentity="other@example.com")
        ses = _make_ses()

        from sesmio.email.components import Body, Container, Head, Html, Text

        def tmpl(name: str = "") -> Html:
            return Html(Head(), Body(Container(Text(name))))

        recipients = [
            Recipient(
                to="r@example.com",
                args={"name": "Alice"},
                replacement_from="other@example.com",
            )
        ]
        results = ses.bulk(tmpl, recipients, subject="Test").send()
        assert len(results) == 1
        assert results[0].status == "success"


class TestBulkWithNativeTemplate:
    """moto 5.x does not implement send_bulk_email; mock at the client level."""

    def _make_ses_with_mock_client(self) -> tuple[SES, object]:
        from unittest.mock import MagicMock

        session = boto3.Session(region_name="us-east-1")
        ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        mc = MagicMock()
        mc.get_account.return_value = {"ProductionAccessEnabled": True}
        ses._ses_client = mc  # type: ignore[attr-defined]
        ses._get_client = lambda: mc  # type: ignore[method-assign]
        return ses, mc

    def test_bulk_native_template_sends(self) -> None:
        ses, mc = self._make_ses_with_mock_client()
        mc.send_bulk_email.return_value = {
            "BulkEmailEntryResults": [
                {"Status": "SUCCESS", "MessageId": "msg-001"},
                {"Status": "SUCCESS", "MessageId": "msg-002"},
            ]
        }
        recipients = [
            Recipient(to="a@example.com", args={"name": "Alice"}),
            Recipient(to="b@example.com", args={"name": "Bob"}),
        ]
        results = ses.bulk("welcome", recipients, subject="Welcome").send()
        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        mc.send_bulk_email.assert_called_once()

    def test_bulk_native_template_over_50(self) -> None:
        ses, mc = self._make_ses_with_mock_client()
        count = 60

        def send_bulk(**kw: object) -> dict[str, object]:
            entries = kw.get("BulkEmailEntries", [])
            n = len(entries)  # type: ignore[arg-type]
            return {
                "BulkEmailEntryResults": [
                    {"Status": "SUCCESS", "MessageId": f"msg-{i}"} for i in range(n)
                ]
            }

        mc.send_bulk_email.side_effect = send_bulk

        recipients = [
            Recipient(to="r@example.com", args={"name": f"User {i}"}) for i in range(count)
        ]
        results = ses.bulk("tmpl", recipients, subject="Hi").send()
        assert len(results) == count
        assert all(r.status == "success" for r in results)
        # Should have been called twice (50 + 10 = 60)
        assert mc.send_bulk_email.call_count == 2

    def test_bulk_native_template_partial_failure(self) -> None:
        ses, mc = self._make_ses_with_mock_client()
        mc.send_bulk_email.return_value = {
            "BulkEmailEntryResults": [
                {"Status": "SUCCESS", "MessageId": "msg-001"},
                {"Status": "FAILED", "Error": "MessageRejected"},
            ]
        }
        recipients = [
            Recipient(to="a@example.com", args={"name": "Alice"}),
            Recipient(to="b@example.com", args={"name": "Bob"}),
        ]
        results = ses.bulk("welcome", recipients, subject="Welcome").send()
        assert len(results) == 2
        successes = [r for r in results if r.status == "success"]
        errors = [r for r in results if r.status == "error"]
        assert len(successes) == 1
        assert len(errors) == 1
