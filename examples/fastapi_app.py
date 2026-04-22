"""FastAPI integration example for sesmio.

Install:
    pip install sesmio[fastapi] uvicorn

Run:
    SESMIO_REGION=us-east-1 SESMIO_DEFAULT_FROM=no-reply@example.com uvicorn fastapi_app:app
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from sesmio import SES
from sesmio.integrations.fastapi import get_ses

app = FastAPI()


@app.post("/signup")
def signup(email: str, ses: SES = Depends(get_ses)) -> dict[str, str]:
    """Send a welcome email when a user signs up."""
    msg_id = ses.send(
        to=email,
        subject="Welcome to our app!",
        html="<h1>Welcome!</h1><p>Thanks for signing up.</p>",
        text="Welcome! Thanks for signing up.",
    )
    return {"message_id": msg_id}


@app.post("/newsletter")
def send_newsletter(ses: SES = Depends(get_ses)) -> dict[str, str]:
    """Bulk send a newsletter to multiple recipients."""
    from sesmio.email.components import Body, Button, Container, Head, Heading, Html, Text
    from sesmio.sender import Recipient

    def newsletter_template(first_name: str = "there") -> Html:
        return Html(
            Head(title="Monthly Newsletter", preview="This month's highlights"),
            Body(
                Container(
                    Heading("Monthly Newsletter"),
                    Text(f"Hi {first_name},"),
                    Text("Here are this month's highlights..."),
                    Button(href="https://example.com/read-more", children="Read More"),
                )
            ),
        )

    recipients = [
        Recipient(to="alice@example.com", args={"first_name": "Alice"}),
        Recipient(to="bob@example.com", args={"first_name": "Bob"}),
    ]

    results = ses.bulk(
        newsletter_template,
        recipients,
        subject="Monthly Newsletter",
    ).send()

    return {
        "sent": str(sum(1 for r in results if r.status == "success")),
        "failed": str(sum(1 for r in results if r.status == "error")),
    }
