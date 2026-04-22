"""Django email backend for sesmio.

Usage::

    # settings.py
    EMAIL_BACKEND = "sesmio.integrations.django.SesmioBackend"
    SESMIO = {
        "region_name": "us-east-1",
        "default_from": "no-reply@example.com",
    }

    # views.py
    from django.core.mail import send_mail, EmailMultiAlternatives

    send_mail("Hello", "Text body", "from@x.com", ["to@x.com"])

    msg = EmailMultiAlternatives("Subject", "Text", "from@x.com", ["to@x.com"])
    msg.attach_alternative("<p>HTML body</p>", "text/html")
    msg.send()

The backend reads the ``SESMIO`` dict from Django settings for SES client
configuration.  All keys are passed directly to :class:`~sesmio.client.SES`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # django types only used inside methods to avoid import at module level


class SesmioBackend:
    """Django ``EMAIL_BACKEND`` that sends via AWS SES v2.

    Compatible with :func:`django.core.mail.send_mail`,
    :class:`~django.core.mail.EmailMessage`, and
    :class:`~django.core.mail.EmailMultiAlternatives`.
    """

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        self.fail_silently = fail_silently
        self._ses: Any = None

    def _get_ses(self) -> Any:
        """Lazily create the SES client using Django settings."""
        if self._ses is not None:
            return self._ses

        # Guarded Django import — safe to call only at use time, not import time.
        try:
            from django.conf import settings as django_settings
        except ImportError as exc:
            raise ImportError(
                "Django is not installed. Install it with: pip install sesmio[django]"
            ) from exc

        sesmio_config: dict[str, Any] = getattr(django_settings, "SESMIO", {})

        from sesmio.client import SES

        self._ses = SES(**sesmio_config)
        return self._ses

    def open(self) -> bool:
        """Open a connection — no-op for SES (connections are managed by boto3)."""
        return False

    def close(self) -> None:
        """Close the connection — no-op for SES."""

    def send_messages(self, email_messages: list[Any]) -> int:
        """Send a list of Django email messages via SES.

        Args:
            email_messages: List of
                :class:`~django.core.mail.EmailMessage` /
                :class:`~django.core.mail.EmailMultiAlternatives` instances.

        Returns:
            Number of messages successfully sent.
        """
        if not email_messages:
            return 0

        sent = 0
        ses = self._get_ses()

        for msg in email_messages:
            try:
                kwargs = self._translate(msg)
                ses.send(**kwargs)
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise

        return sent

    @staticmethod
    def _translate(msg: Any) -> dict[str, Any]:
        """Translate a Django EmailMessage to :meth:`~sesmio.client.SES.send` kwargs."""
        kwargs: dict[str, Any] = {
            "to": list(msg.to),
            "subject": msg.subject,
            "from_": msg.from_email,
        }

        # Body — Django stores plain text in .body; HTML in .alternatives.
        html_body: str | None = None
        alternatives = getattr(msg, "alternatives", [])
        for content, mimetype in alternatives:
            if mimetype == "text/html":
                html_body = str(content)
                break

        if html_body is not None:
            kwargs["html"] = html_body
            if msg.body:
                kwargs["text"] = msg.body
        else:
            kwargs["text"] = msg.body

        if msg.cc:
            kwargs["cc"] = list(msg.cc)
        if msg.bcc:
            kwargs["bcc"] = list(msg.bcc)

        reply_to = getattr(msg, "reply_to", None)
        if reply_to:
            kwargs["reply_to"] = list(reply_to)

        extra_headers = getattr(msg, "extra_headers", {})
        if extra_headers:
            kwargs["headers"] = dict(extra_headers)

        # Attachments: Django stores (filename, content, mimetype) tuples.
        raw_attachments = getattr(msg, "attachments", [])
        if raw_attachments:
            translated: list[dict[str, Any]] = []
            for item in raw_attachments:
                if isinstance(item, tuple) and len(item) == 3:
                    filename, content, mimetype = item
                    raw = content if isinstance(content, bytes) else str(content).encode()
                    translated.append(
                        {
                            "content": raw,
                            "filename": str(filename) if filename else "attachment",
                            "content_type": str(mimetype)
                            if mimetype
                            else "application/octet-stream",  # noqa: E501
                        }
                    )
            if translated:
                kwargs["attachments"] = translated

        return kwargs
