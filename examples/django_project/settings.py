"""Minimal Django settings for sesmio backend example."""

SECRET_KEY = "change-me-in-production"
DEBUG = True
DATABASES = {}
INSTALLED_APPS: list[str] = []

# sesmio email backend
EMAIL_BACKEND = "sesmio.integrations.django.SesmioBackend"
SESMIO = {
    "region_name": "us-east-1",
    "default_from": "no-reply@example.com",
    # "max_retries": 3,
}
