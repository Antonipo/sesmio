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

## Email templates

Build email HTML using composable Python components — no Jinja, no HTML strings,
no Node toolchain.

### Welcome email example

```python
from sesmio import SES
from sesmio.email import Html, Head, Body, Container, Heading, Text, Hr, Button, Img, Spacer

def welcome_email(name: str, cta_url: str):
    return Html(
        head=Head(title="Welcome!", preview=f"Hi {name}, thanks for signing up"),
        body=Body(
            children=Container(
                children=[
                    Img(src="https://example.com/logo.png", alt="Company logo", width=160),
                    Spacer(height=24),
                    Heading(text=f"Hello {name}!", level=1),
                    Text(text="Thanks for registering on our platform. We're thrilled to have you."),
                    Hr(),
                    Button(href=cta_url, children="Get Started", bg="#4f46e5", color="#ffffff"),
                    Spacer(height=32),
                    Text(text="Questions? Reply to this email — we read every one."),
                ]
            )
        ),
    )

ses = SES(region_name="us-east-1", default_from="no-reply@example.com")
ses.send(
    to="user@example.com",
    subject="Welcome to Example!",
    template=welcome_email("Ana", "https://example.com/start"),
)
```

`render()` returns `(html, text)` — use it directly if you need both:

```python
from sesmio.email import render

html, text = render(welcome_email("Ana", "https://example.com/start"))
print(text)  # clean plain-text version, auto-generated from the tree
```

Preview locally before sending:

```python
from sesmio.email import render_preview

render_preview(welcome_email("Ana", "https://example.com/start"), "welcome.html")
# Logs: preview.written: file:///…/welcome.html — click to open in browser
```

### Available components

| Component | Description |
|---|---|
| `Html(head, body, lang="en")` | Root document element |
| `Head(title, preview, meta)` | `<head>` with charset, viewport, and inbox preview text |
| `Body(children, bg="#ffffff")` | `<body>` with background color |
| `Container(children, width=600)` | Centered, fixed-width layout table |
| `Section(children, padding=None)` | Vertical section (`<tr><td>`) |
| `Row(children)` | Table row for multi-column layouts |
| `Column(children, width=None)` | Table column (`<td>`) |
| `Heading(text, level=1)` | `<h1>`–`<h6>` |
| `Text(text)` | `<p>` paragraph |
| `Link(href, children)` | `<a>` anchor |
| `Button(href, children, bg, color)` | Bulletproof Outlook-compatible button |
| `Img(src, alt, width, height)` | Image (alt required) |
| `Hr(color="#e5e7eb")` | Horizontal rule |
| `Spacer(height=16)` | Vertical whitespace |
| `Preview(text)` | Hidden inbox preview text |
| `CodeBlock(code, lang)` | Preformatted code |
| `Raw(html_string)` | Raw HTML escape hatch (warns on use) |

All `text`/`children` string values are HTML-escaped automatically.
Use `Raw()` only for trusted HTML — it bypasses escaping and logs a warning.

### Tailwind utilities with raw HTML

Apply Tailwind utility classes to plain HTML without a build step:

```python
ses.send(
    to="user@example.com",
    subject="Hello",
    html="""
    <div class="max-w-lg mx-auto p-6 bg-white">
      <h1 class="text-2xl font-bold text-gray-900">Hello</h1>
      <p class="mt-4 text-gray-600">Email content here.</p>
    </div>
    """,
    tailwind=True,   # resolves ~250 Tailwind classes → inline CSS
)
```

The built-in subset covers spacing (`p-*`, `m-*`, `px-*`, …), typography
(`text-*`, `font-*`, `leading-*`, `tracking-*`), colors (gray, slate, red,
blue, green, amber palettes), sizing (`w-*`, `max-w-*`), borders, and shadows.
Unknown classes are silently ignored (logged at `DEBUG`).

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
