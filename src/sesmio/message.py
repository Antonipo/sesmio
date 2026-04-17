"""MIME multipart message builder using stdlib ``email``."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Union


@dataclass
class Attachment:
    """Normalised representation of an email attachment."""

    content: bytes
    filename: str
    content_type: str


# Accepted types for the public ``attachments=`` parameter.
AttachmentLike = Union[Path, "dict[str, object]"]


def _normalise_attachment(item: AttachmentLike) -> Attachment:
    """Convert a ``Path`` or dict attachment descriptor into an :class:`Attachment`."""
    if isinstance(item, Path):
        content_type, _ = mimetypes.guess_type(str(item))
        return Attachment(
            content=item.read_bytes(),
            filename=item.name,
            content_type=content_type or "application/octet-stream",
        )

    # dict form: {"content": bytes, "filename": str, "content_type": str}
    d = item
    raw_content = d.get("content", b"")
    content = raw_content if isinstance(raw_content, bytes) else str(raw_content).encode()
    filename = str(d.get("filename", "attachment"))
    raw_ct = d.get("content_type")
    if raw_ct is None:
        guessed, _ = mimetypes.guess_type(filename)
        ct = guessed or "application/octet-stream"
    else:
        ct = str(raw_ct)
    return Attachment(content=content, filename=filename, content_type=ct)


@dataclass
class MimeBuilder:
    """Build a raw MIME message suitable for ``sesv2.send_email(Raw=...)``."""

    def build(
        self,
        *,
        subject: str,
        from_: str,
        to: list[str],
        cc: list[str],
        bcc: list[str],
        reply_to: list[str],
        html: str | None,
        text: str | None,
        headers: dict[str, str],
        attachments: list[AttachmentLike],
    ) -> bytes:
        """Build and return the serialised MIME message as bytes.

        Structure:
        - No attachments: ``multipart/alternative`` (text + html parts).
        - With attachments: ``multipart/mixed`` wrapping a ``multipart/alternative``.
        - Plain text only: ``text/plain``.
        """
        normalised = [_normalise_attachment(a) for a in attachments]

        # Build the body part.
        if html and text:
            body_part: MIMEBase = MIMEMultipart("alternative")
            body_part.attach(MIMEText(text, "plain", "utf-8"))
            body_part.attach(MIMEText(html, "html", "utf-8"))
        elif html:
            plain_fallback = _strip_tags(html)
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(plain_fallback, "plain", "utf-8"))
            body_part.attach(MIMEText(html, "html", "utf-8"))
        else:
            # text-only
            body_part = MIMEText(text or "", "plain", "utf-8")

        if normalised:
            root: MIMEBase = MIMEMultipart("mixed")
            root.attach(body_part)
            for att in normalised:
                main_type, _, sub_type = att.content_type.partition("/")
                part = MIMEBase(main_type, sub_type or "octet-stream")
                part.set_payload(att.content)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=att.filename,
                )
                root.attach(part)
        else:
            root = body_part

        # Encode subject for unicode support.
        root["Subject"] = subject
        root["From"] = from_
        root["To"] = ", ".join(to)
        if cc:
            root["Cc"] = ", ".join(cc)
        if bcc:
            root["Bcc"] = ", ".join(bcc)
        if reply_to:
            root["Reply-To"] = ", ".join(reply_to)

        for name, value in headers.items():
            root[name] = value

        return root.as_bytes()


def _strip_tags(html_text: str) -> str:
    """Very basic tag stripper to generate a plain-text fallback from HTML."""
    import re

    text = re.sub(r"<[^>]+>", " ", html_text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
