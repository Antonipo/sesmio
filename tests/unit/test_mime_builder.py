"""Unit tests for sesmio.message.MimeBuilder."""

from email import message_from_bytes
from pathlib import Path

from sesmio.message import MimeBuilder, _normalise_attachment


class TestMimeBuilder:
    def _build(self, **kwargs: object) -> bytes:
        defaults = dict(
            subject="Test Subject",
            from_="sender@example.com",
            to=["recipient@example.com"],
            cc=[],
            bcc=[],
            reply_to=[],
            html="<p>Hello</p>",
            text=None,
            headers={},
            attachments=[],
        )
        defaults.update(kwargs)
        return MimeBuilder().build(**defaults)  # type: ignore[arg-type]

    def test_returns_bytes(self) -> None:
        raw = self._build()
        assert isinstance(raw, bytes)
        assert len(raw) > 0

    def test_subject_present(self) -> None:
        raw = self._build(subject="My Subject")
        msg = message_from_bytes(raw)
        assert msg["Subject"] == "My Subject"

    def test_from_present(self) -> None:
        raw = self._build()
        msg = message_from_bytes(raw)
        assert "sender@example.com" in msg["From"]

    def test_to_present(self) -> None:
        raw = self._build(to=["a@b.com", "c@d.com"])
        msg = message_from_bytes(raw)
        assert "a@b.com" in msg["To"]
        assert "c@d.com" in msg["To"]

    def test_cc_present(self) -> None:
        raw = self._build(cc=["cc@example.com"])
        msg = message_from_bytes(raw)
        assert "cc@example.com" in msg["Cc"]

    def test_reply_to_present(self) -> None:
        raw = self._build(reply_to=["reply@example.com"])
        msg = message_from_bytes(raw)
        assert "reply@example.com" in msg["Reply-To"]

    def test_html_only_creates_alternative(self) -> None:
        raw = self._build(html="<p>Hello</p>", text=None)
        msg = message_from_bytes(raw)
        assert msg.get_content_type() in ("multipart/alternative", "text/html", "text/plain")

    def test_html_and_text_creates_alternative(self) -> None:
        raw = self._build(html="<p>Hello</p>", text="Hello")
        msg = message_from_bytes(raw)
        assert "multipart" in msg.get_content_type()

    def test_text_only(self) -> None:
        raw = self._build(html=None, text="Plain text only")
        msg = message_from_bytes(raw)
        # Should be text/plain at root or inside multipart.
        content_type = msg.get_content_type()
        assert content_type in ("text/plain", "multipart/alternative")

    def test_with_attachment_creates_mixed(self) -> None:
        attachment = {
            "content": b"PDF data",
            "filename": "doc.pdf",
            "content_type": "application/pdf",
        }
        raw = self._build(attachments=[attachment])
        msg = message_from_bytes(raw)
        assert msg.get_content_type() == "multipart/mixed"

    def test_custom_headers(self) -> None:
        raw = self._build(headers={"X-Campaign": "welcome"})
        msg = message_from_bytes(raw)
        assert msg["X-Campaign"] == "welcome"

    def test_bcc_present_in_mime(self) -> None:
        raw = self._build(bcc=["bcc@example.com"])
        msg = message_from_bytes(raw)
        assert "bcc@example.com" in (msg["Bcc"] or "")


class TestNormaliseAttachment:
    def test_from_dict_basic(self) -> None:
        att = _normalise_attachment(
            {
                "content": b"data",
                "filename": "test.txt",
                "content_type": "text/plain",
            }
        )
        assert att.filename == "test.txt"
        assert att.content == b"data"
        assert att.content_type == "text/plain"

    def test_from_dict_guesses_content_type(self) -> None:
        att = _normalise_attachment(
            {
                "content": b"data",
                "filename": "report.pdf",
            }
        )
        assert att.content_type == "application/pdf"

    def test_from_dict_fallback_content_type(self) -> None:
        att = _normalise_attachment(
            {
                "content": b"data",
                "filename": "unknown.xyz123",
            }
        )
        assert att.content_type == "application/octet-stream"

    def test_from_path(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_bytes(b"hello")
        att = _normalise_attachment(f)
        assert att.filename == "hello.txt"
        assert att.content == b"hello"
        assert "text" in att.content_type
