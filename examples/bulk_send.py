"""Bulk email send example using sesmio.

Demonstrates both component-based and native SES template approaches.
"""

from __future__ import annotations

from sesmio import SES
from sesmio.email.components import Body, Button, Container, Head, Heading, Html, Text
from sesmio.sender import Recipient


def welcome_email(first_name: str = "there", cta_url: str = "https://example.com") -> Html:
    """Component factory — called per recipient with their args."""
    return Html(
        Head(title="Welcome!", preview="Thanks for joining us"),
        Body(
            Container(
                Heading("Welcome!"),
                Text(f"Hi {first_name}, great to have you on board."),
                Button(href=cta_url, children="Get Started"),
            )
        ),
    )


def main() -> None:
    ses = SES(
        region_name="us-east-1",
        default_from="no-reply@example.com",
    )

    # Component template approach — render per recipient.
    recipients = [
        Recipient(
            to="alice@example.com",
            args={"first_name": "Alice", "cta_url": "https://example.com/alice"},
        ),
        Recipient(
            to="bob@example.com",
            args={"first_name": "Bob", "cta_url": "https://example.com/bob"},
        ),
    ]

    results = ses.bulk(
        welcome_email,
        recipients,
        subject="Welcome to our platform!",
    ).send()

    for r in results:
        if r.status == "success":
            print(f"Sent: {r.message_id}")
        else:
            print(f"Failed: {r.error}")

    # Native SES template approach (template must be pre-registered).
    # First, create the template once:
    # ses.templates.create(
    #     "welcome_v2",
    #     subject="Welcome, {{first_name}}!",
    #     template="<h1>Hi {{first_name}}!</h1><p>Great to have you.</p>",
    # )
    #
    # Then bulk send:
    # results = ses.bulk(
    #     "welcome_v2",  # template name as string → uses SendBulkEmail
    #     recipients=[
    #         Recipient(to="alice@example.com", args={"first_name": "Alice"}),
    #         Recipient(to="bob@example.com", args={"first_name": "Bob"}),
    #     ],
    #     subject="Welcome!",
    # ).send()


if __name__ == "__main__":
    main()
