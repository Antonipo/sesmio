"""SES native template management example.

Demonstrates creating, updating, listing, and sending with SES native templates.
"""

from __future__ import annotations

from sesmio import SES
from sesmio.email.components import Body, Button, Container, Head, Heading, Html, Text


def main() -> None:
    ses = SES(
        region_name="us-east-1",
        default_from="no-reply@example.com",
    )

    # Build the HTML using sesmio's component system.
    # Use double-braces for SES native template placeholders.
    def welcome_component() -> Html:
        return Html(
            Head(title="Welcome!", preview="Thanks for joining us"),
            Body(
                Container(
                    Heading("Welcome, {{first_name}}!"),
                    Text("Thanks for joining us."),
                    Button(href="{{cta_url}}", children="Get Started"),
                )
            ),
        )

    # Create the template (only needed once).
    ses.templates.create(
        "welcome_v1",
        subject="Welcome, {{first_name}}!",
        template=welcome_component(),
    )
    print("Template created.")

    # List templates.
    all_templates = ses.templates.list()
    for t in all_templates:
        print(f"  - {t.name}")

    # Get details.
    info = ses.templates.get("welcome_v1")
    print(f"Subject: {info.subject}")

    # Send using the template.
    msg_id = ses.templates.send(
        to="user@example.com",
        template_name="welcome_v1",
        data={"first_name": "Alice", "cta_url": "https://example.com/start"},
    )
    print(f"Sent: {msg_id}")

    # Update when the template changes.
    ses.templates.update(
        "welcome_v1",
        subject="Welcome back, {{first_name}}!",
        template="<p>Hi {{first_name}}, we've updated our platform!</p>",
    )
    print("Template updated.")

    # Delete when no longer needed.
    ses.templates.delete("welcome_v1")
    print("Template deleted.")


if __name__ == "__main__":
    main()
