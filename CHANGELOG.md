# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
