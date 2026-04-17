"""Miscellaneous client coverage tests."""

from __future__ import annotations

import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@mock_aws
def test_send_with_configuration_set() -> None:
    from sesmio import SES

    boto3.client("sesv2", region_name="us-east-1").create_email_identity(
        EmailIdentity="sender@example.com"
    )
    session = boto3.Session(region_name="us-east-1")
    ses = SES(
        region_name="us-east-1",
        default_from="sender@example.com",
        boto3_session=session,
    )

    with patch.object(ses, "_get_client") as mock_client:
        mock_client.return_value.get_account.return_value = {"ProductionAccessEnabled": True}
        mock_client.return_value.send_email.return_value = {"MessageId": "cfg-id"}
        msg_id = ses.send(
            to="r@example.com",
            subject="Config set",
            html="<p>Hi</p>",
            configuration_set="my-config-set",
        )
    assert msg_id == "cfg-id"
    call_kwargs = mock_client.return_value.send_email.call_args.kwargs
    assert call_kwargs.get("ConfigurationSetName") == "my-config-set"


@mock_aws
def test_get_client_without_boto3_session() -> None:
    """Test _get_client when no boto3_session is provided (uses boto3.client directly)."""
    from sesmio import SES

    boto3.client("sesv2", region_name="us-east-1").create_email_identity(
        EmailIdentity="sender@example.com"
    )
    # No boto3_session — exercises the else branch in _get_client.
    ses = SES(region_name="us-east-1", default_from="sender@example.com")

    with patch.object(ses, "_check_sandbox"):
        with patch("sesmio.client.boto3") as mock_boto3:
            mock_client = mock_boto3.client.return_value
            mock_client.send_email.return_value = {"MessageId": "direct-id"}
            # Reset lazy cache so it rebuilds.
            ses._client = None
            msg_id = ses.send(to="r@example.com", subject="s", html="<p>h</p>")
    assert msg_id == "direct-id"
