"""Example Django views using sesmio as the email backend.

Set in manage.py or wsgi.py:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
"""

from __future__ import annotations

from django.core.mail import EmailMultiAlternatives, send_mail


def send_welcome_email(user_email: str, user_name: str) -> None:
    """Send a plain-text welcome email using Django's send_mail."""
    send_mail(
        subject="Welcome!",
        message=f"Hi {user_name}, welcome to our platform.",
        from_email="no-reply@example.com",
        recipient_list=[user_email],
    )


def send_welcome_html_email(user_email: str, user_name: str) -> None:
    """Send an HTML welcome email using EmailMultiAlternatives."""
    subject = "Welcome to our platform"
    text_body = f"Hi {user_name}, welcome to our platform."
    html_body = f"<h1>Welcome, {user_name}!</h1><p>Thanks for joining us.</p>"

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email="no-reply@example.com",
        to=[user_email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()
