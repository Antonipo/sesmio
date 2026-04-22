# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - unreleased

### Added

- `SES.bulk(template, recipients, subject=...)` — bulk email builder with `.send()`.
  Accepts component factories (per-recipient render) or native SES template names
  (`SendBulkEmail`). Auto-chunks to 50 recipients per SES v2 call. Per-recipient
  errors captured in `BulkResult` rather than aborting the batch.
- `sesmio.sender.Recipient` — frozen dataclass for per-recipient bulk config:
  `to`, `args`, `cc`, `bcc`, `replacement_from`, `replacement_reply_to`.
- `sesmio.sender.BulkResult` — frozen dataclass for per-recipient results:
  `message_id`, `status`, `error`.
- `sesmio.templates.SESTemplates` — SES native template manager accessed via
  `SES.templates`. Methods: `create`, `update`, `delete`, `get`, `list`, `send`.
- `sesmio.templates.TemplateInfo` — frozen dataclass with `name`, `subject`,
  `created_at`, `updated_at`.
- `TemplateDoesNotExistError` — raised when a referenced SES template is not found.
- `sesmio.integrations.flask.SESExtension` — Flask extension with `send`,
  `bulk`, `templates`. Supports direct init and application factory (`init_app`).
  Reads `SESMIO_REGION`, `SESMIO_DEFAULT_FROM`, `SESMIO_MAX_RETRIES` from `app.config`.
- `sesmio.integrations.fastapi.get_ses` — FastAPI dependency for a singleton
  `SES` instance. Reads config from `SESMIO_REGION` / `SESMIO_DEFAULT_FROM` /
  `SESMIO_MAX_RETRIES` env vars.
- `sesmio.integrations.django.SesmioBackend` — Django `EMAIL_BACKEND` compatible
  with `send_mail`, `EmailMessage`, `EmailMultiAlternatives`. Reads `settings.SESMIO`
  dict for config.
- Optional extras: `sesmio[flask]`, `sesmio[fastapi]`, `sesmio[django]`.
- PyPI publish GitHub Actions workflow (`.github/workflows/publish.yml`) triggered
  on `v*` tag push via OIDC Trusted Publishing.
- Examples: `examples/flask_app.py`, `examples/fastapi_app.py`,
  `examples/django_project/`, `examples/bulk_send.py`, `examples/native_templates.py`.

## [0.2.0] - unreleased

### Added

- `sesmio.email.components` — full component library: `Html`, `Head`, `Body`,
  `Container`, `Section`, `Row`, `Column`, `Heading`, `Text`, `Link`, `Button`,
  `Img`, `Hr`, `Spacer`, `Preview`, `CodeBlock`, `Raw`. All components are
  frozen dataclasses. String children are HTML-escaped automatically; `Raw()`
  bypasses escaping and logs a warning.
- `sesmio.email.render.render(template)` — renders a component tree to a
  `(html, text)` tuple. HTML is a complete email-safe document with `<!DOCTYPE>`,
  inlined CSS, and MSO conditional comments for Outlook buttons.
- `sesmio.email.render.render_html_fragment(node)` — render a single node to
  an HTML string (no DOCTYPE, no inliner) for testing and debugging.
- `sesmio.email.inliner.inline_css(html)` — stdlib-only CSS inliner. Supports
  `tag`, `.class`, `#id`, `tag.class`, `parent > child`, `:first-child`
  selectors. Merges `<style>` rules into `style=` attributes; media queries
  and `:hover` rules are preserved in a residual `<style>` block.
- `sesmio.email.tailwind` — `TAILWIND_MAP` dict with ~270 Tailwind utility
  classes and `resolve_classes(class_string)` to convert class strings to
  inline CSS declarations. Unknown classes are silently ignored (debug log).
- `sesmio.email.text.build_text(node)` — plain-text extraction from a Node
  tree via tree traversal (no HTML regex). Heading underlines, link URLs,
  button labels, image alt text all preserved.
- `sesmio.email.preview.render_preview(template, path)` — writes rendered HTML
  to a file and logs the `file://` URL for local browser preview.
- `SES.send(template=...)` — accepts a component tree, renders to HTML+text
  automatically. `text=` can still override the auto-generated plain text.
- `SES.send(html=..., tailwind=True)` — resolves Tailwind classes and inlines
  all CSS in a raw HTML string before sending.
- Passing both `html=` and `template=` raises `ValidationError`.

## [0.1.0] - unreleased

### Added

- `sesmio.SES` class with `send()` supporting `to`, `cc`, `bcc`, `reply_to`,
  `from_`, `subject`, `html`, `text`, `headers`, `tags`, `attachments`,
  `return_path`, and `configuration_set`.
- `sesmio.message.MimeBuilder` — MIME multipart builder via stdlib `email`.
  Supports `multipart/alternative` (text + html) and `multipart/mixed` (with
  attachments). Accepts `Path` or `dict` attachment descriptors.
- `sesmio.exceptions` — full typed exception hierarchy inheriting from
  `SesmioError`, including `RecipientSuppressedError` and `DailyQuotaExceededError`.
- `sesmio._internal.validation` — RFC 5322 email validation, CRLF
  anti-injection for all header values, 10 MB size guard.
- `sesmio._internal.retry` — exponential backoff with jitter. Retries
  `ThrottlingError` and `ServiceUnavailableError`. Never retries
  `DailyQuotaExceededError`.
- `sesmio._internal.logging` — PII-free logger. Never logs recipients,
  subject, or body content.
- `sesmio._internal.escape` — `html.escape` wrapper for Phase 2 use.
- Sandbox warning on first send via `sesv2.get_account`.
- Lazy, thread-safe boto3 client via `threading.Lock`.
- `py.typed` marker for mypy/pyright compatibility.
- GitHub Actions CI: matrix Python 3.10–3.13 on ubuntu-latest, with
  ruff check, ruff format, mypy --strict, and pytest with coverage.
