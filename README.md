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
- [Multiple recipients and privacy](#multiple-recipients-and-privacy)
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

## Multiple recipients and privacy

By default, `ses.send(to=[...])` sends **a single email** with every address
listed in the `To:` header — **all recipients see each other's emails**. This
is standard SMTP behavior, identical to writing a regular email to several
people at once. The same applies to `cc=[...]`.

```python
ses.send(
    to=["a@example.com", "b@example.com", "c@example.com"],
    subject="Team update",
    html="<p>Hi team</p>",
)
# → one email, 'To:' header shows all three addresses
```

This is intentional: sesmio never silently changes what the recipient sees.
If you need each recipient to receive a separate email without seeing the
others, use one of these patterns explicitly:

**BCC — same content, few recipients:**

```python
ses.send(
    to="no-reply@yourdomain.com",              # visible To
    bcc=["a@example.com", "b@example.com"],    # hidden recipients
    subject="Announcement",
    html="<p>...</p>",
)
```

**Loop — per-recipient content:**

```python
for user in users:
    ses.send(to=user.email, subject=f"Hi {user.name}", html=render(user))
```

**`ses.bulk()` — many recipients, personalised content, automatic chunking:**

```python
from sesmio import Recipient

ses.bulk(
    template=welcome_template,
    recipients=[Recipient(to=u.email, args={"name": u.name}) for u in users],
    subject="Welcome",
    from_="no-reply@yourdomain.com",
).send()
```

See [Bulk sending](#bulk-sending) for details — it handles per-recipient
errors, retries, and chunking at SES's 50-per-call limit automatically.

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

## Bulk sending

Send to many recipients efficiently — recipients are chunked into groups of 50,
processed concurrently, and errors per recipient are captured without aborting
the batch.

```python
from sesmio import SES
from sesmio.email import Html, Head, Body, Container, Heading, Text, Button
from sesmio.sender import Recipient

ses = SES(region_name="us-east-1", default_from="no-reply@example.com")

def welcome_template(first_name: str = "there", cta_url: str = "") -> Html:
    return Html(
        Head(title="Welcome!"),
        Body(Container(
            Heading(f"Hi {first_name}!"),
            Text("Thanks for joining us."),
            Button(href=cta_url, children="Get Started"),
        )),
    )

results = ses.bulk(
    welcome_template,          # called with each recipient's args
    recipients=[
        Recipient(to="alice@example.com", args={"first_name": "Alice", "cta_url": "https://example.com/alice"}),
        Recipient(to="bob@example.com",   args={"first_name": "Bob",   "cta_url": "https://example.com/bob"}),
    ],
    subject="Welcome to our platform!",
).send()

for r in results:
    print(r.message_id if r.status == "success" else r.error)
```

Use a pre-registered SES native template for maximum efficiency (`SendBulkEmail`):

```python
ses.templates.create("welcome_v1", subject="Welcome, {{name}}!", template="<p>Hi {{name}}</p>")

results = ses.bulk(
    "welcome_v1",  # string → uses SendBulkEmail API
    recipients=[
        Recipient(to="alice@example.com", args={"name": "Alice"}),
        Recipient(to="bob@example.com",   args={"name": "Bob"}),
    ],
    subject="Welcome!",
).send()
```

## Native SES templates

```python
ses.templates.create("welcome", subject="Hello, {{name}}!", template="<p>Hi {{name}}</p>")
ses.templates.send(to="user@example.com", template_name="welcome", data={"name": "Ana"})
ses.templates.update("welcome", subject="Updated subject", template="<p>New body</p>")
ses.templates.delete("welcome")
for t in ses.templates.list():
    print(t.name)
```

## Framework integrations

### Flask

```bash
pip install sesmio[flask]
```

```python
from flask import Flask, request
from sesmio.integrations.flask import SESExtension

app = Flask(__name__)
ses = SESExtension(app, default_from="no-reply@example.com")

@app.route("/signup", methods=["POST"])
def signup():
    ses.send(
        to=request.json["email"],
        subject="Welcome!",
        html="<p>Thanks for signing up.</p>",
    )
    return "ok"
```

Application factory pattern:

```python
ses = SESExtension()

def create_app():
    app = Flask(__name__)
    app.config["SESMIO_REGION"] = "us-east-1"
    app.config["SESMIO_DEFAULT_FROM"] = "no-reply@example.com"
    ses.init_app(app)
    return app
```

### FastAPI

```bash
pip install sesmio[fastapi]
```

```python
from fastapi import FastAPI, Depends
from sesmio import SES
from sesmio.integrations.fastapi import get_ses

app = FastAPI()

@app.post("/signup")
def signup(email: str, ses: SES = Depends(get_ses)):
    msg_id = ses.send(to=email, subject="Welcome!", html="<p>Thanks for signing up.</p>")
    return {"message_id": msg_id}
```

Set config via environment variables:
```bash
export SESMIO_REGION=us-east-1
export SESMIO_DEFAULT_FROM=no-reply@example.com
```

### Django

```bash
pip install sesmio[django]
```

```python
# settings.py
EMAIL_BACKEND = "sesmio.integrations.django.SesmioBackend"
SESMIO = {
    "region_name": "us-east-1",
    "default_from": "no-reply@example.com",
}

# views.py
from django.core.mail import send_mail, EmailMultiAlternatives

# Plain text
send_mail("Hello", "Text body", "from@example.com", ["to@example.com"])

# HTML
msg = EmailMultiAlternatives("Subject", "Text body", "from@example.com", ["to@example.com"])
msg.attach_alternative("<p>HTML body</p>", "text/html")
msg.send()
```

## Releasing to PyPI

### First-time setup (once)

1. Go to [PyPI Trusted Publishers](https://pypi.org/manage/account/publishing/) and add a publisher:
   - **Owner**: your GitHub username or org
   - **Repository name**: `sesmio`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
2. In your GitHub repository settings → Environments → create `pypi` environment.

### Publish a release

```bash
git tag v0.3.0
git push origin v0.3.0
```

GitHub Actions runs the full test matrix (ruff, mypy, pytest) and, on success,
builds and publishes to PyPI via OIDC — no API token needed. You can also trigger
manually via Actions → Publish to PyPI → Run workflow.

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
ruff check src/ tests/          # lint
ruff format src/ tests/         # format
mypy --strict src/sesmio/       # type check
```

## License

Apache 2.0
