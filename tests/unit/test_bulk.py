"""Unit tests for bulk sender: chunking logic and BulkResult aggregation."""

from __future__ import annotations

import pytest

from sesmio.sender import BulkResult, Recipient, _chunked, _normalise


class TestChunking:
    def test_empty_list(self) -> None:
        assert _chunked([], 50) == []

    def test_single_chunk(self) -> None:
        recipients = [Recipient(to=f"r{i}@example.com") for i in range(10)]
        chunks = _chunked(recipients, 50)
        assert len(chunks) == 1
        assert len(chunks[0]) == 10

    def test_exact_chunk_boundary(self) -> None:
        recipients = [Recipient(to=f"r{i}@example.com") for i in range(50)]
        chunks = _chunked(recipients, 50)
        assert len(chunks) == 1
        assert len(chunks[0]) == 50

    def test_two_chunks(self) -> None:
        recipients = [Recipient(to=f"r{i}@example.com") for i in range(51)]
        chunks = _chunked(recipients, 50)
        assert len(chunks) == 2
        assert len(chunks[0]) == 50
        assert len(chunks[1]) == 1

    def test_many_chunks(self) -> None:
        recipients = [Recipient(to=f"r{i}@example.com") for i in range(155)]
        chunks = _chunked(recipients, 50)
        assert len(chunks) == 4
        assert len(chunks[0]) == 50
        assert len(chunks[1]) == 50
        assert len(chunks[2]) == 50
        assert len(chunks[3]) == 5

    def test_order_preserved(self) -> None:
        recipients = [Recipient(to=f"r{i}@example.com") for i in range(120)]
        chunks = _chunked(recipients, 50)
        flattened = [r for chunk in chunks for r in chunk]
        assert flattened == recipients


class TestNormalise:
    def test_str_becomes_list(self) -> None:
        assert _normalise("a@example.com") == ["a@example.com"]

    def test_list_preserved(self) -> None:
        assert _normalise(["a@example.com", "b@example.com"]) == [
            "a@example.com",
            "b@example.com",
        ]


class TestBulkResult:
    def test_success_result(self) -> None:
        r = BulkResult(message_id="msg-123", status="success", error=None)
        assert r.message_id == "msg-123"
        assert r.status == "success"
        assert r.error is None

    def test_error_result(self) -> None:
        exc = Exception("network error")
        r = BulkResult(message_id=None, status="error", error=exc)
        assert r.message_id is None
        assert r.status == "error"
        assert r.error is exc

    def test_frozen(self) -> None:
        r = BulkResult(message_id="m", status="success", error=None)
        with pytest.raises(Exception):
            r.message_id = "other"  # type: ignore[misc]


class TestRecipient:
    def test_defaults(self) -> None:
        r = Recipient(to="a@example.com")
        assert r.to == "a@example.com"
        assert r.args == {}
        assert r.cc is None
        assert r.bcc is None
        assert r.replacement_from is None
        assert r.replacement_reply_to is None

    def test_frozen(self) -> None:
        r = Recipient(to="a@example.com")
        with pytest.raises(Exception):
            r.to = "b@example.com"  # type: ignore[misc]

    def test_with_args(self) -> None:
        r = Recipient(to="a@example.com", args={"name": "Ana"})
        assert r.args["name"] == "Ana"
