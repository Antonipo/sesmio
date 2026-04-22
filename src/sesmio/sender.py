"""Bulk email sender for SES v2.

WHY a separate module: client.py stays focused on single-message send().
Bulk logic is non-trivial (chunking, thread pool, per-recipient error isolation)
and would push client.py past 200 lines.

WHY per-recipient render + chunked SendEmail (not SendBulkEmail with templates):
- SendBulkEmail requires pre-registered SES native templates; an ephemeral
  create-send-delete approach has race conditions under concurrency and burns
  API quota for each bulk call.
- Per-recipient render + concurrent SendEmail keeps the API surface simple: the
  caller just passes a component factory or plain string HTML, no template
  registration ceremony.  For workloads that already use SES native templates
  (template: str), SendBulkEmail IS used for efficiency.
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from botocore.exceptions import ClientError

from sesmio._internal.retry import with_retry
from sesmio._internal.validation import validate_emails
from sesmio.exceptions import ConfigurationError, _map_client_error
from sesmio.message import MimeBuilder

if TYPE_CHECKING:
    from sesmio.client import SES
    from sesmio.email.components import Html, Node

_logger = logging.getLogger("sesmio")

# SES v2 SendBulkEmail limit per API call.
_CHUNK_SIZE = 50

# Bounded thread pool size — keeps concurrent SES connections reasonable.
_MAX_WORKERS = 10


@dataclass(frozen=True)
class Recipient:
    """One entry in a bulk send batch.

    Attributes:
        to: Recipient address or list of addresses.
        args: Template rendering arguments (passed to the component factory).
        cc: CC addresses.
        bcc: BCC addresses.
        replacement_from: Override the From address for this recipient.
        replacement_reply_to: Override Reply-To for this recipient.
    """

    to: str | list[str]
    args: dict[str, Any] = field(default_factory=dict)
    cc: str | list[str] | None = None
    bcc: str | list[str] | None = None
    replacement_from: str | None = None
    replacement_reply_to: str | list[str] | None = None


@dataclass(frozen=True)
class BulkResult:
    """Result for a single recipient in a bulk send batch.

    Attributes:
        message_id: SES message ID on success, ``None`` on failure.
        status: ``"success"`` or ``"error"``.
        error: Exception instance if the send failed, ``None`` otherwise.
    """

    message_id: str | None
    status: str
    error: Exception | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _send_one_mime(
    *,
    client: Any,
    subject: str,
    from_: str,
    recipient: Recipient,
    html: str,
    text: str,
    tags: dict[str, str] | None,
    configuration_set: str | None,
    max_retries: int,
) -> str:
    """Build MIME and call SES v2 send_email for one recipient, with retry."""
    to_list = _normalise(recipient.to)
    cc_list = _normalise(recipient.cc) if recipient.cc else []
    bcc_list = _normalise(recipient.bcc) if recipient.bcc else []
    effective_from = recipient.replacement_from or from_
    reply_to_list = (
        _normalise(recipient.replacement_reply_to) if recipient.replacement_reply_to else []
    )

    raw_bytes = MimeBuilder().build(
        subject=subject,
        from_=effective_from,
        to=to_list,
        cc=cc_list,
        bcc=bcc_list,
        reply_to=reply_to_list,
        html=html,
        text=text,
        headers={},
        attachments=[],
    )

    params: dict[str, Any] = {
        "FromEmailAddress": effective_from,
        "Destination": {"ToAddresses": to_list},
        "Content": {"Raw": {"Data": raw_bytes}},
    }
    if cc_list:
        params["Destination"]["CcAddresses"] = cc_list
    if bcc_list:
        params["Destination"]["BccAddresses"] = bcc_list
    if reply_to_list:
        params["ReplyToAddresses"] = reply_to_list
    if configuration_set:
        params["ConfigurationSetName"] = configuration_set
    if tags:
        params["EmailTags"] = [{"Name": k, "Value": v} for k, v in tags.items()]

    def _call() -> str:
        try:
            resp: dict[str, Any] = client.send_email(**params)
            return str(resp["MessageId"])
        except ClientError as exc:
            raise _map_client_error(exc) from exc

    return with_retry(_call, max_retries)


def _send_bulk_native(
    *,
    client: Any,
    template_name: str,
    default_data: dict[str, str],
    recipients: list[Recipient],
    from_: str,
    reply_to: list[str],
    tags: dict[str, str] | None,
    configuration_set: str | None,
    max_retries: int,
) -> list[BulkResult]:
    """Call SendBulkEmail for a chunk using a pre-registered SES native template."""
    entries: list[dict[str, Any]] = []
    for rec in recipients:
        dest: dict[str, Any] = {"Destination": {"ToAddresses": _normalise(rec.to)}}
        if rec.cc:
            dest["Destination"]["CcAddresses"] = _normalise(rec.cc)
        if rec.bcc:
            dest["Destination"]["BccAddresses"] = _normalise(rec.bcc)
        # Per-recipient template data merges with defaults.
        merged = {**default_data, **{str(k): str(v) for k, v in rec.args.items()}}
        if merged:
            import json

            dest["ReplacementTemplateData"] = json.dumps(merged)
        if rec.replacement_from:
            dest["ReplacementEmailParameters"] = [
                {"Name": "FromEmailAddress", "Value": rec.replacement_from}
            ]
        entries.append(dest)

    params: dict[str, Any] = {
        "FromEmailAddress": from_,
        "BulkEmailEntries": entries,
        "DefaultContent": {
            "Template": {
                "TemplateName": template_name,
                "TemplateData": "{}",
            }
        },
    }
    if default_data:
        import json

        params["DefaultContent"]["Template"]["TemplateData"] = json.dumps(default_data)
    if reply_to:
        params["ReplyToAddresses"] = reply_to
    if configuration_set:
        params["ConfigurationSetName"] = configuration_set
    if tags:
        params["EmailTags"] = [{"Name": k, "Value": v} for k, v in tags.items()]

    def _call() -> list[dict[str, Any]]:
        try:
            resp: dict[str, Any] = client.send_bulk_email(**params)
            result: list[dict[str, Any]] = resp.get("BulkEmailEntryResults", [])
            return result
        except ClientError as exc:
            raise _map_client_error(exc) from exc

    raw_results = with_retry(_call, max_retries)

    bulk_results: list[BulkResult] = []
    for idx, entry_result in enumerate(raw_results):
        status = str(entry_result.get("Status", "FAILED")).upper()
        msg_id = entry_result.get("MessageId")
        error_str = entry_result.get("Error")
        if status == "SUCCESS" and msg_id:
            bulk_results.append(BulkResult(message_id=str(msg_id), status="success", error=None))
        else:
            err = Exception(error_str or f"Entry {idx} failed with status {status}")
            bulk_results.append(BulkResult(message_id=None, status="error", error=err))

    # Pad if SES returns fewer results than entries (shouldn't happen, but defensive).
    while len(bulk_results) < len(recipients):
        bulk_results.append(
            BulkResult(message_id=None, status="error", error=Exception("No result returned"))
        )
    return bulk_results


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class BulkSender:
    """Fluent builder for bulk email operations.

    Do not instantiate directly — use :meth:`SES.bulk` instead.
    """

    def __init__(
        self,
        *,
        ses: "SES",
        template: "str | Html | Node | Callable[..., Html | Node]",
        recipients: list[Recipient],
        subject: str,
        from_: str | None,
        reply_to: str | list[str] | None,
        tags: dict[str, str] | None,
        configuration_set: str | None,
    ) -> None:
        self._ses = ses
        self._template = template
        self._recipients = recipients
        self._subject = subject
        self._from_ = from_
        self._reply_to = reply_to
        self._tags = tags
        self._configuration_set = configuration_set

    def send(self) -> list[BulkResult]:
        """Execute the bulk send and return one :class:`BulkResult` per recipient.

        Errors on individual recipients are captured in the result rather than
        raising — the batch always completes.

        Returns:
            List of :class:`BulkResult` in the same order as *recipients*.
        """
        sender = self._from_ or self._ses._default_from
        if sender is None:
            raise ConfigurationError(
                "No sender address. Pass from_= or set default_from on the SES instance."
            )

        # Validate all recipients eagerly before sending anything.
        for rec in self._recipients:
            validate_emails(_normalise(rec.to))
            if rec.cc:
                validate_emails(_normalise(rec.cc))
            if rec.bcc:
                validate_emails(_normalise(rec.bcc))
            if rec.replacement_from:
                validate_emails([rec.replacement_from])

        # Route to the appropriate send strategy.
        if isinstance(self._template, str):
            return self._send_native_template(sender)
        return self._send_component_template(sender)

    # ------------------------------------------------------------------
    # Strategy A: SES native template (template is a str name)
    # ------------------------------------------------------------------

    def _send_native_template(self, sender: str) -> list[BulkResult]:
        template_name: str = self._template  # type: ignore[assignment]
        reply_to_list = _normalise(self._reply_to) if self._reply_to else []
        client = self._ses._get_client()

        results: list[BulkResult] = []
        chunks = _chunked(self._recipients, _CHUNK_SIZE)
        for chunk in chunks:
            chunk_results = _send_bulk_native(
                client=client,
                template_name=template_name,
                default_data={},
                recipients=chunk,
                from_=sender,
                reply_to=reply_to_list,
                tags=self._tags,
                configuration_set=self._configuration_set,
                max_retries=self._ses._max_retries,
            )
            results.extend(chunk_results)

        _logger.info(
            "bulk.native_template.complete",
            extra={
                "total": len(results),
                "success": sum(1 for r in results if r.status == "success"),
                "error": sum(1 for r in results if r.status == "error"),
            },
        )
        return results

    # ------------------------------------------------------------------
    # Strategy B: component / callable template — per-recipient render
    # ------------------------------------------------------------------

    def _send_component_template(self, sender: str) -> list[BulkResult]:
        from sesmio.email.render import render as _render

        client = self._ses._get_client()
        max_retries = self._ses._max_retries
        subject = self._subject
        tags = self._tags
        conf_set = self._configuration_set

        def _process_one(recipient: Recipient) -> BulkResult:
            try:
                tmpl = self._template
                # If it's a callable (factory function), call it with recipient args.
                if callable(tmpl):
                    node = tmpl(**recipient.args)
                else:
                    # tmpl is Html | Node here (str was routed to _send_native_template)
                    from sesmio.email.components import Html
                    from sesmio.email.components import Node as _Node

                    assert isinstance(tmpl, (Html, _Node))
                    node = tmpl
                html, text = _render(node)
                msg_id = _send_one_mime(
                    client=client,
                    subject=subject,
                    from_=sender,
                    recipient=recipient,
                    html=html,
                    text=text,
                    tags=tags,
                    configuration_set=conf_set,
                    max_retries=max_retries,
                )
                return BulkResult(message_id=msg_id, status="success", error=None)
            except Exception as exc:
                return BulkResult(message_id=None, status="error", error=exc)

        # Process chunks in order; within each chunk submit concurrently but collect
        # results indexed so final list preserves original recipient order.
        ordered: list[BulkResult] = []
        for chunk in _chunked(self._recipients, _CHUNK_SIZE):
            with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                futures_map = {pool.submit(_process_one, rec): i for i, rec in enumerate(chunk)}
                chunk_results: list[BulkResult | None] = [None] * len(chunk)
                for fut in concurrent.futures.as_completed(futures_map):
                    idx = futures_map[fut]
                    chunk_results[idx] = fut.result()
                for r in chunk_results:
                    ordered.append(r)  # type: ignore[arg-type]

        _logger.info(
            "bulk.component_template.complete",
            extra={
                "total": len(ordered),
                "success": sum(1 for r in ordered if r.status == "success"),
                "error": sum(1 for r in ordered if r.status == "error"),
            },
        )
        return ordered


def _chunked(lst: list[Recipient], size: int) -> list[list[Recipient]]:
    """Split *lst* into sub-lists of at most *size* elements."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
