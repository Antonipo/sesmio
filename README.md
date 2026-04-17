# sesmio

[![Tests](https://github.com/Antonipo/sesmio/actions/workflows/tests.yml/badge.svg)](https://github.com/Antonipo/sesmio/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/sesmio)](https://pypi.org/project/sesmio/)
[![Python](https://img.shields.io/pypi/pyversions/sesmio)](https://pypi.org/project/sesmio/)

Framework-agnostic AWS SES v2 wrapper for Python. Send HTML email with attachments in one call, with typed exceptions, automatic retry, and PII-free logging.

```python
from sesmio import SES

ses = SES(region_name="us-east-1", default_from="no-reply@example.com")

msg_id = ses.send(
    to="user@example.com",
    subject="Welcome",
    html="<p>Hello <b>World</b></p>",
    attachments=[Path("/tmp/invoice.pdf")],
)
```

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Attachments](#attachments)
- [Tags](#tags)
- [Custom headers](#custom-headers)
- [Minimal IAM policy](#minimal-iam-policy)
- [Exceptions and error handling](#exceptions-and-error-handling)
- [Sandbox mode](#sandbox-mode)
- [Logging](#logging)
- [Connection options](#connection-options)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Features

- **One import** -- `from sesmio import SES` is all you need
- **Typed exceptions** -- `MessageRejectedError`, `ThrottlingError`, `DailyQuotaExceededError`, etc. instead of raw `ClientError`
- **Automatic retry** -- throttling and 5xx errors are retried with exponential backoff + jitter
- **MIME multipart** -- text + HTML + attachments built with stdlib `email`, zero extra deps
- **CRLF injection protection** -- header values are validated before sending
- **10 MB size guard** -- message size is checked before the AWS call
- **Sandbox warning** -- logs a warning on first send if your account is in sandbox mode
- **PII-free logging** -- never logs recipients, subject, or body. Only `message_id`, region, size, error codes
- **Lazy boto3 client** -- no AWS calls at import time; client is created on first `send()`
- **Thread-safe** -- lazy client init uses `threading.Lock`
- **Framework-agnostic** -- works with FastAPI, Flask, Django, Celery, Lambda, or plain scripts

## Installation

```bash
pip install sesmio
```

Only runtime dependency: `boto3>=1.34`.

For development (pytest, moto, ruff, mypy):

```bash
pip install sesmio[dev]
```

## Quick start

```python
from sesmio import SES

ses = SES(region_name="us-east-1", default_from="no-reply@example.com")

# HTML email
msg_id = ses.send(
    to="user@example.com",
    subject="Welcome",
    html="<p>Hello!</p>",
)

# Plain text
msg_id = ses.send(
    to="user@example.com",
    subject="Ping",
    text="Hello!",
)

# HTML + explicit plain text
msg_id = ses.send(
    to="user@example.com",
    subject="Welcome",
    html="<p>Hello!</p>",
    text="Hello!",
)
```

`from_` overrides `default_from` per call:

```python
msg_id = ses.send(
    to="user@example.com",
    from_="billing@example.com",
    subject="Invoice",
    html="<p>Your invoice</p>",
)
```

Multiple recipients, CC, BCC:

```python
msg_id = ses.send(
    to=["a@example.com", "b@example.com"],
    cc="manager@example.com",
    bcc="audit@example.com",
    subject="Team update",
    html="<p>Hello team</p>",
)
```

## Attachments

Pass a `Path` (auto-detects filename and MIME type) or a `dict`:

```python
from pathlib import Path

msg_id = ses.send(
    to="user@example.com",
    subject="Invoice",
    html="<p>See attached</p>",
    attachments=[
        Path("/tmp/invoice.pdf"),
        {"content": csv_bytes, "filename": "data.csv", "content_type": "text/csv"},
    ],
)
```

## Tags

Map to SES `EmailTags` for tracking via event destinations:

```python
msg_id = ses.send(
    to="user@example.com",
    subject="Welcome",
    html="<p>Hi</p>",
    tags={"campaign": "onboarding", "tier": "free"},
)
```

## Custom headers

```python
msg_id = ses.send(
    to="user@example.com",
    subject="Notification",
    html="<p>Alert</p>",
    headers={"X-Priority": "1", "X-Campaign-Id": "abc123"},
)
```

Values are checked for CRLF injection before sending.

## Minimal IAM policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ses:SendEmail"],
      "Resource": "*"
    }
  ]
}
```

Add `ses:GetAccount` if you want sandbox detection to work (optional — the check is non-fatal).

## Exceptions and error handling

All exceptions inherit from `SesmioError`. Never leaks `botocore.exceptions.ClientError`.

```python
from sesmio import (
    SesmioError,               # base — catch all sesmio errors
    ConfigurationError,        # missing from_/default_from, bad credentials
    ValidationError,           # base for all validation errors
    InvalidRecipientError,     # email fails RFC 5322 validation
    MessageTooLargeError,      # message exceeds 10 MB
    HeaderInjectionError,      # CR or LF in a header value
    SendError,                 # base for SES send errors
    MessageRejectedError,      # SES flagged the message (spam, etc.)
    IdentityNotVerifiedError,  # From identity not verified in SES
    AccountSuspendedError,     # account sending suspended
    SendingPausedError,        # sending paused on config set
    MailFromDomainNotVerifiedError,  # MAIL FROM domain not verified
    RecipientSuppressedError,  # recipient on account suppression list
    ThrottlingError,           # rate limit — retried automatically
    DailyQuotaExceededError,   # 24h quota exhausted — not retried
    ServiceUnavailableError,   # SES 5xx — retried automatically
)
```

Example:

```python
from sesmio import SES, MessageRejectedError, DailyQuotaExceededError, ThrottlingError

ses = SES(region_name="us-east-1", default_from="no-reply@example.com")

try:
    ses.send(to="user@example.com", subject="Hello", html="<p>Hi</p>")
except DailyQuotaExceededError:
    print("24h sending quota exhausted — try again tomorrow")
except ThrottlingError:
    print("Rate limited — already retried 3 times with backoff")
except MessageRejectedError as e:
    print(f"Message rejected by SES: {e}")
```

## Sandbox mode

When your SES account is in sandbox mode, only verified email addresses can receive mail. On the first `send()` call, sesmio checks your account status via `ses:GetAccount` and logs a warning if sandbox is active:

```
WARNING sesmio SES account is in sandbox mode in region us-east-1.
Outbound email is restricted to verified addresses only.
```

The check is non-fatal and only runs once per `SES` instance.

## Logging

sesmio uses `logging.getLogger("sesmio")`. It never logs PII (no recipients, subjects, or body content).

What it does log:

- `INFO send.success` — `message_id`, `size_bytes`, `region`
- `WARNING send.error` — `error_code`, `region`
- `WARNING` — sandbox mode on first send

```python
import logging

logging.getLogger("sesmio").setLevel(logging.DEBUG)
```

Route sesmio logs through your own logger:

```python
import logging
from sesmio import SES

ses = SES(
    region_name="us-east-1",
    logger=logging.getLogger("myapp.email"),
)
```

## Connection options

```python
from sesmio import SES
import boto3

# Automatic — reads AWS_DEFAULT_REGION, credentials from env or ~/.aws/config
ses = SES()

# Explicit region
ses = SES(region_name="eu-west-1")

# Default sender so you don't repeat from_= on every call
ses = SES(region_name="us-east-1", default_from="no-reply@example.com")

# Custom boto3 session (e.g. with a specific profile or assumed role)
session = boto3.Session(profile_name="production")
ses = SES(boto3_session=session)

# Custom retry count (default 3)
ses = SES(region_name="us-east-1", max_retries=5)
```

## Troubleshooting

**`ConfigurationError: No sender address`** — pass `from_="..."` to `send()` or set `default_from` when creating the `SES` instance.

**`IdentityNotVerifiedError`** — the `from_` address or domain is not verified in SES. Go to the SES console → Verified Identities and add it.

**`AccountSuspendedError`** — your SES account has been suspended, usually due to high bounce/complaint rates. Check the SES console and contact AWS support.

**`DailyQuotaExceededError`** — you have sent more emails than your account's 24-hour quota allows. Request a quota increase in the SES console.

**Sandbox mode** — in sandbox mode only verified email addresses can send or receive. Either verify the recipient address or request production access.

**`InvalidRecipientError`** — the address failed basic RFC 5322 validation. Check for typos.

**`HeaderInjectionError`** — one of your header values (including `subject`) contains a newline character. Remove `\r` or `\n` from the value.

## Development

```bash
git clone https://github.com/Antonipo/sesmio.git
cd sesmio
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest                          # run all tests (moto mocks AWS)
pytest --cov=sesmio             # with coverage
pytest -k "sandbox"             # run specific tests
ruff check src/                 # lint
ruff format src/                # format
mypy --strict src/sesmio/       # type check
```

## License

Apache 2.0
