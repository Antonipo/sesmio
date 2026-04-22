"""SES client — main entry point for sending email via AWS SES v2."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from sesmio._internal.logging import log_sandbox_warning, log_send_success
from sesmio._internal.retry import with_retry
from sesmio._internal.validation import (
    check_header_injection,
    check_size,
    validate_emails,
)
from sesmio.exceptions import ConfigurationError, ValidationError, _map_client_error
from sesmio.message import AttachmentLike, MimeBuilder

if TYPE_CHECKING:
    from sesmio.email.components import Html, Node
    from sesmio.sender import BulkSender, Recipient
    from sesmio.templates import SESTemplates

_default_logger = logging.getLogger("sesmio")


class SES:
    """AWS SES v2 client wrapper.

    Zero configuration to start — ``SES()`` reads credentials and region
    from the standard boto3 chain (env vars, ``~/.aws/config``, IAM role).

    Example::

        ses = SES(region_name="us-east-1", default_from="no-reply@example.com")
        msg_id = ses.send(to="user@example.com", subject="Hello", html="<p>Hi</p>")
    """

    def __init__(
        self,
        *,
        region_name: str | None = None,
        default_from: str | None = None,
        max_retries: int = 3,
        boto3_session: "boto3.Session | None" = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._region_name = region_name
        self._default_from = default_from
        self._max_retries = max_retries
        self._boto3_session = boto3_session
        self._logger = logger if logger is not None else _default_logger

        # Lazy client state — protected by _lock.
        self._client: Any = None
        self._lock = threading.Lock()
        self._sandbox_checked = False
        self._templates: SESTemplates | None = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Return (and lazily create) the thread-safe boto3 SES v2 client."""
        if self._client is not None:
            return self._client
        with self._lock:
            # Double-checked locking — another thread may have built it.
            if self._client is not None:
                return self._client
            region = self._region_name
            if self._boto3_session is not None:
                if region:
                    self._client = self._boto3_session.client("sesv2", region_name=region)
                else:
                    self._client = self._boto3_session.client("sesv2")
            else:
                if region:
                    self._client = boto3.client("sesv2", region_name=region)
                else:
                    self._client = boto3.client("sesv2")
        return self._client

    def _check_sandbox(self) -> None:
        """Warn once if the account is in SES sandbox mode."""
        if self._sandbox_checked:
            return
        self._sandbox_checked = True
        try:
            resp: dict[str, Any] = self._get_client().get_account()
            if resp.get("ProductionAccessEnabled") is False:
                region = self._region_name or "unknown"
                log_sandbox_warning(region)
        except ClientError:
            # Non-fatal — if we can't check sandbox status, keep going.
            pass

    @staticmethod
    def _normalise_recipients(value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [value]
        return list(value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        *,
        to: str | list[str],
        subject: str,
        html: str | None = None,
        text: str | None = None,
        template: "Html | Node | None" = None,
        tailwind: bool = False,
        from_: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
        reply_to: str | list[str] | None = None,
        headers: dict[str, str] | None = None,
        tags: dict[str, str] | None = None,
        attachments: list[AttachmentLike] | None = None,
        return_path: str | None = None,
        configuration_set: str | None = None,
    ) -> str:
        """Send an email via SES v2 and return the ``message_id``.

        Args:
            to: Recipient address(es).
            subject: Email subject line.
            html: HTML body. Mutually exclusive with *template*.
            text: Plain-text body. Auto-generated from *html* or *template* if omitted.
            template: Component tree root. Mutually exclusive with *html*.
                Renders to both HTML and plain-text automatically.
            tailwind: When ``True`` and *html* is provided, resolve Tailwind
                utility classes and inline all CSS. Ignored when *template* is used.
            from_: Sender address. Falls back to ``default_from`` set on the instance.
            cc: Carbon-copy recipient(s).
            bcc: Blind carbon-copy recipient(s).
            reply_to: Reply-To address(es).
            headers: Custom headers added to the message root. Values are
                checked for CRLF injection.
            tags: Key-value pairs mapped to SES ``EmailTags`` for tracking.
            attachments: List of :class:`~pathlib.Path` objects or dicts with
                ``content``, ``filename``, and ``content_type`` keys.
            return_path: Return-Path / bounce address.
            configuration_set: SES configuration set name.

        Returns:
            The SES ``MessageId`` string.

        Raises:
            ConfigurationError: No sender address available.
            ValidationError: Both *html* and *template* were provided.
            InvalidRecipientError: An address fails RFC 5322 validation.
            HeaderInjectionError: A header value contains CR or LF.
            MessageTooLargeError: Total message exceeds 10 MB.
            SendError: SES rejected the message.
            ThrottlingError: Rate limit exceeded (retried automatically).
            DailyQuotaExceededError: 24-hour quota exhausted.
            ServiceUnavailableError: SES 5xx (retried automatically).
        """
        if html is not None and template is not None:
            raise ValidationError("Provide either html= or template=, not both.")

        # Render component template → html + auto-text.
        if template is not None:
            from sesmio.email.render import render as _render

            html, auto_text = _render(template)
            if text is None:
                text = auto_text
        elif html is not None and tailwind:
            # Resolve Tailwind classes in raw HTML and inline all CSS.
            from sesmio.email.inliner import inline_css

            # Build per-class CSS block so the inliner can process class= attrs.
            html = inline_css(html)

        sender = from_ or self._default_from
        if sender is None:
            raise ConfigurationError(
                "No sender address. Pass from_= or set default_from on the SES instance."
            )

        to_list = self._normalise_recipients(to)
        cc_list = self._normalise_recipients(cc) if cc else []
        bcc_list = self._normalise_recipients(bcc) if bcc else []
        reply_to_list = self._normalise_recipients(reply_to) if reply_to else []
        headers_dict = dict(headers) if headers else {}

        # Validate.
        validate_emails(to_list)
        validate_emails(cc_list)
        validate_emails(bcc_list)
        validate_emails(reply_to_list)
        validate_emails([sender])
        if return_path:
            validate_emails([return_path])

        check_header_injection(subject, "Subject")
        for key, value in headers_dict.items():
            check_header_injection(key, "header name")
            check_header_injection(value, f"header {key!r}")

        # Build MIME.
        raw_bytes = MimeBuilder().build(
            subject=subject,
            from_=sender,
            to=to_list,
            cc=cc_list,
            bcc=bcc_list,
            reply_to=reply_to_list,
            html=html,
            text=text,
            headers=headers_dict,
            attachments=attachments or [],
        )
        check_size(raw_bytes)

        # First-send sandbox check (non-blocking on error).
        self._check_sandbox()

        # Build SES v2 params.
        params: dict[str, Any] = {
            "FromEmailAddress": sender,
            "Destination": {"ToAddresses": to_list},
            "Content": {"Raw": {"Data": raw_bytes}},
        }
        if cc_list:
            params["Destination"]["CcAddresses"] = cc_list
        if bcc_list:
            params["Destination"]["BccAddresses"] = bcc_list
        if return_path:
            params["FromEmailAddressIdentityArn"] = return_path  # not exact, documented below
            # SES v2 uses ReplyToAddresses and FeedbackForwardingEmailAddress for bounce.
            # return_path maps to FeedbackForwardingEmailAddress.
            del params["FromEmailAddressIdentityArn"]
            params["FeedbackForwardingEmailAddress"] = return_path
        if reply_to_list:
            params["ReplyToAddresses"] = reply_to_list
        if configuration_set:
            params["ConfigurationSetName"] = configuration_set
        if tags:
            params["EmailTags"] = [{"Name": k, "Value": v} for k, v in tags.items()]

        def _call() -> str:
            try:
                resp: dict[str, Any] = self._get_client().send_email(**params)
                return str(resp["MessageId"])
            except ClientError as exc:
                raise _map_client_error(exc) from exc

        message_id = with_retry(_call, self._max_retries)
        region = self._region_name or "default"
        log_send_success(message_id, len(raw_bytes), region)
        return message_id

    def bulk(
        self,
        template: "str | Html | Node",
        recipients: "list[Recipient]",
        *,
        subject: str = "",
        from_: str | None = None,
        reply_to: str | list[str] | None = None,
        tags: dict[str, str] | None = None,
        configuration_set: str | None = None,
    ) -> "BulkSender":
        """Create a :class:`~sesmio.sender.BulkSender` for bulk email sending.

        Args:
            template: A component tree, a callable that returns a component tree,
                or a pre-registered SES native template name (string).
            recipients: List of :class:`~sesmio.sender.Recipient` describing each
                destination, including per-recipient template args.
            subject: Email subject. Required when *template* is a component tree.
            from_: Sender address. Falls back to ``default_from``.
            reply_to: Reply-To address(es).
            tags: SES email tags for event tracking.
            configuration_set: SES configuration set name.

        Returns:
            A :class:`~sesmio.sender.BulkSender` — call ``.send()`` to execute.
        """
        from sesmio.sender import BulkSender

        return BulkSender(
            ses=self,
            template=template,
            recipients=recipients,
            subject=subject,
            from_=from_,
            reply_to=reply_to,
            tags=tags,
            configuration_set=configuration_set,
        )

    @property
    def templates(self) -> "SESTemplates":
        """Cached :class:`~sesmio.templates.SESTemplates` accessor."""
        if self._templates is None:
            from sesmio.templates import SESTemplates

            self._templates = SESTemplates(self)
        return self._templates
