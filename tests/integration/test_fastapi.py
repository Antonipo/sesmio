"""Integration tests for the FastAPI dependency."""

from __future__ import annotations

import os

import boto3
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws

from sesmio import SES
from sesmio.integrations.fastapi import _build_ses_kwargs, _get_ses_instance, get_ses


@pytest.fixture(autouse=True)
def aws_credentials() -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


class TestBuildKwargs:
    def test_empty_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SESMIO_REGION", raising=False)
        monkeypatch.delenv("SESMIO_DEFAULT_FROM", raising=False)
        monkeypatch.delenv("SESMIO_MAX_RETRIES", raising=False)
        kwargs = _build_ses_kwargs()
        assert kwargs["max_retries"] == 3
        assert "region_name" not in kwargs
        assert "default_from" not in kwargs

    def test_with_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SESMIO_REGION", "eu-west-1")
        monkeypatch.setenv("SESMIO_DEFAULT_FROM", "noreply@example.com")
        monkeypatch.setenv("SESMIO_MAX_RETRIES", "5")
        kwargs = _build_ses_kwargs()
        assert kwargs["region_name"] == "eu-west-1"
        assert kwargs["default_from"] == "noreply@example.com"
        assert kwargs["max_retries"] == 5


class TestGetSes:
    def test_get_ses_returns_ses_instance(self) -> None:
        # Clear lru_cache so each test gets a fresh instance.
        _get_ses_instance.cache_clear()
        instance = get_ses()
        assert isinstance(instance, SES)

    def test_get_ses_singleton(self) -> None:
        _get_ses_instance.cache_clear()
        a = get_ses()
        b = get_ses()
        assert a is b

    def teardown_method(self) -> None:
        _get_ses_instance.cache_clear()


class TestFastapiEndpoint:
    @mock_aws
    def test_endpoint_with_dependency(self) -> None:
        boto3.client("sesv2", region_name="us-east-1").create_email_identity(
            EmailIdentity="sender@example.com"
        )

        # Create a SES with moto session and patch the singleton.
        session = boto3.Session(region_name="us-east-1")
        mock_ses = SES(
            region_name="us-east-1",
            default_from="sender@example.com",
            boto3_session=session,
        )
        original = mock_ses._get_client

        def patched() -> object:
            client = original()
            if not hasattr(client, "_sesmio_patched"):
                client.get_account = lambda **kw: {"ProductionAccessEnabled": True}  # type: ignore[attr-defined]
                client._sesmio_patched = True  # type: ignore[attr-defined]
            return client

        mock_ses._get_client = patched  # type: ignore[method-assign]

        app = FastAPI()

        def _get_mock_ses() -> SES:
            return mock_ses

        @app.post("/send")
        def send_endpoint(ses: SES = Depends(_get_mock_ses)) -> dict[str, str]:
            msg_id = ses.send(
                to="user@example.com",
                subject="Hello",
                html="<p>Hi</p>",
            )
            return {"message_id": msg_id}

        with TestClient(app) as client:
            response = client.post("/send")
            assert response.status_code == 200
            data = response.json()
            assert "message_id" in data
            assert len(data["message_id"]) > 0

    def teardown_method(self) -> None:
        _get_ses_instance.cache_clear()
