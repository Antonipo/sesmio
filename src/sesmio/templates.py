"""SES native template management.

Wraps the SES v2 CreateEmailTemplate / UpdateEmailTemplate / DeleteEmailTemplate /
GetEmailTemplate / ListEmailTemplates / SendEmail(template) API calls.

Usage::

    ses = SES(default_from="no-reply@example.com")
    ses.templates.create(
        "welcome",
        subject="Welcome, {{name}}!",
        template=welcome_component,   # Component tree with {{name}} placeholders
    )
    ses.templates.send(
        to="user@example.com",
        template_name="welcome",
        data={"name": "Ana"},
    )

Note on placeholders: SES native templates use ``{{variable}}`` syntax.
When building Component trees destined for SES template storage, use Python
f-strings or concatenation to produce literal ``{{name}}`` strings in the
rendered HTML (double-braces survive Python string formatting).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, List

from botocore.exceptions import ClientError

from sesmio.exceptions import TemplateDoesNotExistError, _map_client_error

if TYPE_CHECKING:
    from sesmio.client import SES
    from sesmio.email.components import Html, Node

_logger = logging.getLogger("sesmio")


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata for a stored SES email template.

    Attributes:
        name: Template name as stored in SES.
        subject: Subject line (may contain ``{{placeholder}}`` tokens).
        created_at: UTC timestamp of creation (``None`` if not returned by SES).
        updated_at: UTC timestamp of last update (``None`` if not returned by SES).
    """

    name: str
    subject: str
    created_at: datetime | None
    updated_at: datetime | None


def _render_to_html_text(template: "Html | Node | str") -> tuple[str, str | None]:
    """Return ``(html, text)`` from a component tree or raw HTML string."""
    if isinstance(template, str):
        return template, None
    from sesmio.email.render import render as _render

    html, text = _render(template)
    return html, text


def _map_template_client_error(exc: ClientError) -> Exception:
    """Map NotFoundException specifically to TemplateDoesNotExistError."""
    code: str = exc.response["Error"]["Code"]
    if code == "NotFoundException":
        message: str = exc.response["Error"].get("Message", "")
        err = TemplateDoesNotExistError(message)
        err.__cause__ = exc
        return err
    return _map_client_error(exc)


class SESTemplates:
    """SES native email template manager.

    Accessed via :attr:`SES.templates` — do not instantiate directly.
    """

    def __init__(self, ses: "SES") -> None:
        self._ses = ses

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _client(self) -> Any:
        return self._ses._get_client()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        *,
        subject: str,
        template: "Html | Node | str",
        text: str | None = None,
    ) -> None:
        """Create a new SES native email template.

        Args:
            name: Unique template name (SES-wide, per account + region).
            subject: Subject line. May include ``{{placeholder}}`` tokens.
            template: Component tree or raw HTML string. The rendered HTML
                is stored as the template body. Use ``{{var}}`` tokens in
                component text to make them substitutable at send time.
            text: Optional plain-text version. Auto-derived from component
                tree if *template* is a component and *text* is omitted.
        """
        html, auto_text = _render_to_html_text(template)
        plain = text if text is not None else (auto_text or "")
        template_content: dict[str, Any] = {
            "Subject": subject,
            "Html": html,
        }
        if plain:
            template_content["Text"] = plain
        try:
            self._client().create_email_template(
                TemplateName=name,
                TemplateContent=template_content,
            )
        except ClientError as exc:
            raise _map_template_client_error(exc) from exc

    def update(
        self,
        name: str,
        *,
        subject: str,
        template: "Html | Node | str",
        text: str | None = None,
    ) -> None:
        """Update an existing SES native email template.

        Args:
            name: Template name to update.
            subject: New subject line.
            template: New component tree or raw HTML.
            text: New plain-text version.
        """
        html, auto_text = _render_to_html_text(template)
        plain = text if text is not None else (auto_text or "")
        template_content: dict[str, Any] = {
            "Subject": subject,
            "Html": html,
        }
        if plain:
            template_content["Text"] = plain
        try:
            self._client().update_email_template(
                TemplateName=name,
                TemplateContent=template_content,
            )
        except ClientError as exc:
            raise _map_template_client_error(exc) from exc

    def delete(self, name: str) -> None:
        """Delete a SES native email template by name.

        Args:
            name: Template name to delete.
        """
        try:
            self._client().delete_email_template(TemplateName=name)
        except ClientError as exc:
            raise _map_template_client_error(exc) from exc

    def get(self, name: str) -> TemplateInfo:
        """Retrieve metadata for a SES native email template.

        Args:
            name: Template name to retrieve.

        Returns:
            :class:`TemplateInfo` with name, subject, and timestamps.

        Raises:
            TemplateDoesNotExistError: Template with *name* was not found.
        """
        try:
            resp: dict[str, Any] = self._client().get_email_template(TemplateName=name)
        except ClientError as exc:
            raise _map_template_client_error(exc) from exc

        content: dict[str, Any] = resp.get("TemplateContent", {})
        subject = str(content.get("Subject", ""))

        # SES v2 GetEmailTemplate does not return timestamps in the API response;
        # we store None rather than invent a value.
        return TemplateInfo(
            name=str(resp.get("TemplateName", name)),
            subject=subject,
            created_at=None,
            updated_at=None,
        )

    def list(self) -> List[TemplateInfo]:
        """List all SES native email templates in the account + region.

        Returns:
            List of :class:`TemplateInfo` objects (timestamps are ``None``
            because SES ListEmailTemplates only returns name + creation time).
        """
        try:
            results: List[TemplateInfo] = []
            paginator = self._client().get_paginator("list_email_templates")
            for page in paginator.paginate():
                for item in page.get("TemplatesMetadata", []):
                    created_at_raw = item.get("CreatedTimestamp")
                    created_at: datetime | None = None
                    if isinstance(created_at_raw, datetime):
                        created_at = created_at_raw
                    results.append(
                        TemplateInfo(
                            name=str(item.get("TemplateName", "")),
                            subject="",
                            created_at=created_at,
                            updated_at=None,
                        )
                    )
            return results
        except ClientError as exc:
            raise _map_client_error(exc) from exc

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send(
        self,
        *,
        to: "str | List[str]",
        template_name: str,
        data: "dict[str, str]",
        from_: str | None = None,
        subject_override: str | None = None,
        cc: "str | List[str] | None" = None,
        bcc: "str | List[str] | None" = None,
        reply_to: "str | List[str] | None" = None,
        tags: "dict[str, str] | None" = None,
        configuration_set: str | None = None,
    ) -> str:
        """Send an email using a pre-registered SES native template.

        Args:
            to: Recipient address(es).
            template_name: Name of the SES template to use.
            data: Substitution data for ``{{placeholder}}`` tokens.
            from_: Sender address. Falls back to ``SES.default_from``.
            subject_override: Override the template subject (not supported by
                all SES accounts; left here for completeness).
            cc: CC addresses.
            bcc: BCC addresses.
            reply_to: Reply-To addresses.
            tags: SES email tags.
            configuration_set: SES configuration set name.

        Returns:
            The SES ``MessageId`` string.

        Raises:
            ConfigurationError: No sender address available.
            TemplateDoesNotExistError: *template_name* not found.
        """
        import json

        from sesmio._internal.validation import validate_emails
        from sesmio.exceptions import ConfigurationError

        sender = from_ or self._ses._default_from
        if sender is None:
            raise ConfigurationError(
                "No sender address. Pass from_= or set default_from on the SES instance."
            )

        to_list = [to] if isinstance(to, str) else list(to)
        cc_list = ([cc] if isinstance(cc, str) else list(cc)) if cc else []
        bcc_list = ([bcc] if isinstance(bcc, str) else list(bcc)) if bcc else []
        reply_to_list = (
            ([reply_to] if isinstance(reply_to, str) else list(reply_to)) if reply_to else []
        )

        validate_emails(to_list)
        validate_emails(cc_list)
        validate_emails(bcc_list)
        validate_emails([sender])

        destination: dict[str, Any] = {"ToAddresses": to_list}
        if cc_list:
            destination["CcAddresses"] = cc_list
        if bcc_list:
            destination["BccAddresses"] = bcc_list

        params: dict[str, Any] = {
            "FromEmailAddress": sender,
            "Destination": destination,
            "Content": {
                "Template": {
                    "TemplateName": template_name,
                    "TemplateData": json.dumps(data) if data else "{}",
                }
            },
        }
        if reply_to_list:
            params["ReplyToAddresses"] = reply_to_list
        if configuration_set:
            params["ConfigurationSetName"] = configuration_set
        if tags:
            params["EmailTags"] = [{"Name": k, "Value": v} for k, v in tags.items()]

        from sesmio._internal.retry import with_retry

        def _call() -> str:
            try:
                resp: dict[str, Any] = self._client().send_email(**params)
                return str(resp["MessageId"])
            except ClientError as exc:
                raise _map_template_client_error(exc) from exc

        message_id = with_retry(_call, self._ses._max_retries)
        _logger.info("templates.send.success", extra={"message_id": message_id})
        return message_id
