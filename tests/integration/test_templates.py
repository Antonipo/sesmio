"""Integration tests for SESTemplates.

moto 5.x does not implement create_email_template / send_email(Template=...),
so we mock the boto3 client at the method level.  The happy paths exercise
_our_ mapping logic; error paths exercise _map_template_client_error.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError

from sesmio import SES
from sesmio.exceptions import TemplateDoesNotExistError
from sesmio.templates import SESTemplates, TemplateInfo


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def _make_ses_with_mock_client() -> tuple[SES, MagicMock]:
    """Return (ses, mock_client) where mock_client replaces the boto3 client."""
    ses = SES(
        region_name="us-east-1",
        default_from="sender@example.com",
    )
    mock_client = MagicMock()
    mock_client.get_account.return_value = {"ProductionAccessEnabled": True}
    ses._get_client = lambda: mock_client  # type: ignore[method-assign]
    return ses, mock_client


class TestCreate:
    def test_create_calls_boto3(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.create_email_template.return_value = {}
        ses.templates.create("welcome", subject="Hi {{name}}", template="<p>Hi</p>")
        mc.create_email_template.assert_called_once()
        call_kwargs = mc.create_email_template.call_args[1]
        assert call_kwargs["TemplateName"] == "welcome"
        assert "Subject" in call_kwargs["TemplateContent"]
        assert "Html" in call_kwargs["TemplateContent"]

    def test_create_with_component_tree(self) -> None:
        from sesmio.email.components import Body, Container, Head, Html, Text

        ses, mc = _make_ses_with_mock_client()
        mc.create_email_template.return_value = {}
        tmpl = Html(Head(), Body(Container(Text("Hello!"))))
        ses.templates.create("greeting", subject="Hi", template=tmpl)
        mc.create_email_template.assert_called_once()
        content = mc.create_email_template.call_args[1]["TemplateContent"]
        assert "<p>" in content["Html"] or "Hello" in content["Html"]

    def test_create_maps_client_error(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.create_email_template.side_effect = ClientError(
            {"Error": {"Code": "LimitExceededException", "Message": "limit"}},
            "CreateEmailTemplate",
        )
        from sesmio.exceptions import DailyQuotaExceededError

        with pytest.raises(DailyQuotaExceededError):
            ses.templates.create("t", subject="s", template="<p>h</p>")


class TestUpdate:
    def test_update_calls_boto3(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.update_email_template.return_value = {}
        ses.templates.update("t1", subject="New", template="<p>New</p>")
        mc.update_email_template.assert_called_once()
        assert mc.update_email_template.call_args[1]["TemplateName"] == "t1"

    def test_update_not_found_raises(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.update_email_template.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "not found"}},
            "UpdateEmailTemplate",
        )
        with pytest.raises(TemplateDoesNotExistError):
            ses.templates.update("ghost", subject="s", template="<p>h</p>")


class TestDelete:
    def test_delete_calls_boto3(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.delete_email_template.return_value = {}
        ses.templates.delete("mytemplate")
        mc.delete_email_template.assert_called_once_with(TemplateName="mytemplate")

    def test_delete_not_found_raises(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.delete_email_template.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "not found"}},
            "DeleteEmailTemplate",
        )
        with pytest.raises(TemplateDoesNotExistError):
            ses.templates.delete("ghost")


class TestGet:
    def test_get_returns_template_info(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.get_email_template.return_value = {
            "TemplateName": "welcome",
            "TemplateContent": {"Subject": "Welcome!", "Html": "<p>Hi</p>"},
        }
        info = ses.templates.get("welcome")
        assert isinstance(info, TemplateInfo)
        assert info.name == "welcome"
        assert info.subject == "Welcome!"

    def test_get_not_found_raises(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.get_email_template.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Template not found"}},
            "GetEmailTemplate",
        )
        with pytest.raises(TemplateDoesNotExistError):
            ses.templates.get("ghost")

    def test_get_returns_none_timestamps(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.get_email_template.return_value = {
            "TemplateName": "t",
            "TemplateContent": {"Subject": "s", "Html": "<p>h</p>"},
        }
        info = ses.templates.get("t")
        assert info.created_at is None
        assert info.updated_at is None


class TestList:
    def test_list_empty(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"TemplatesMetadata": []}]
        mc.get_paginator.return_value = paginator
        result = ses.templates.list()
        assert result == []

    def test_list_returns_template_infos(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "TemplatesMetadata": [
                    {"TemplateName": "t1"},
                    {"TemplateName": "t2"},
                ]
            }
        ]
        mc.get_paginator.return_value = paginator
        result = ses.templates.list()
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"t1", "t2"}


class TestSend:
    def test_send_calls_ses(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.send_email.return_value = {"MessageId": "msg-abc-123"}
        msg_id = ses.templates.send(
            to="user@example.com",
            template_name="welcome",
            data={"name": "Ana"},
        )
        assert msg_id == "msg-abc-123"
        mc.send_email.assert_called_once()
        call_kwargs = mc.send_email.call_args[1]
        assert call_kwargs["Content"]["Template"]["TemplateName"] == "welcome"

    def test_send_not_found_raises(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.send_email.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Template not found"}},
            "SendEmail",
        )
        with pytest.raises(TemplateDoesNotExistError):
            ses.templates.send(to="u@example.com", template_name="ghost", data={})

    def test_send_requires_from(self) -> None:
        from sesmio.exceptions import ConfigurationError

        session = boto3.Session(region_name="us-east-1")
        ses = SES(region_name="us-east-1", boto3_session=session)
        with pytest.raises(ConfigurationError):
            ses.templates.send(to="u@example.com", template_name="t", data={})

    def test_send_with_cc_bcc_reply_to_tags(self) -> None:
        ses, mc = _make_ses_with_mock_client()
        mc.send_email.return_value = {"MessageId": "msg-xyz"}
        ses.templates.send(
            to="u@example.com",
            template_name="t",
            data={"k": "v"},
            cc="cc@example.com",
            bcc="bcc@example.com",
            reply_to="reply@example.com",
            tags={"campaign": "test"},
            configuration_set="my-set",
        )
        mc.send_email.assert_called_once()
        kwargs = mc.send_email.call_args[1]
        assert "CcAddresses" in kwargs["Destination"]
        assert "BccAddresses" in kwargs["Destination"]
        assert kwargs["ReplyToAddresses"] == ["reply@example.com"]
        assert kwargs["EmailTags"] == [{"Name": "campaign", "Value": "test"}]
        assert kwargs["ConfigurationSetName"] == "my-set"


class TestTemplatesProperty:
    def test_templates_property_cached(self) -> None:
        ses, _ = _make_ses_with_mock_client()
        t1 = ses.templates
        t2 = ses.templates
        assert t1 is t2
        assert isinstance(t1, SESTemplates)
