"""FastAPI dependency for sesmio.

Usage::

    from fastapi import FastAPI, Depends
    from sesmio.integrations.fastapi import get_ses
    from sesmio import SES

    app = FastAPI()

    @app.post("/signup")
    def signup(email: str, ses: SES = Depends(get_ses)):
        ses.send(to=email, subject="Welcome", html="<p>Hi!</p>")

Configuration via environment variables (or ``pydantic_settings`` if installed):
    ``SESMIO_REGION``        → ``region_name``
    ``SESMIO_DEFAULT_FROM``  → ``default_from``
    ``SESMIO_MAX_RETRIES``   → ``max_retries`` (int, default 3)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _build_ses_kwargs() -> dict[str, Any]:
    """Read SES configuration from environment variables.

    When ``pydantic_settings`` is installed, env-file (``.env``) support and
    type coercion are available automatically because SES construction reads the
    same env vars.  We intentionally avoid a direct pydantic_settings dependency
    here to keep the integration importable without ``pip install sesmio[fastapi]``.
    """
    kwargs: dict[str, Any] = {}
    region = os.environ.get("SESMIO_REGION")
    if region:
        kwargs["region_name"] = region
    default_from = os.environ.get("SESMIO_DEFAULT_FROM")
    if default_from:
        kwargs["default_from"] = default_from
    max_retries_raw = os.environ.get("SESMIO_MAX_RETRIES")
    kwargs["max_retries"] = int(max_retries_raw) if max_retries_raw else 3
    return kwargs


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_ses_instance() -> Any:
    """Create a thread-safe singleton SES client, cached for the process lifetime."""
    from sesmio.client import SES

    return SES(**_build_ses_kwargs())


def get_ses() -> Any:
    """FastAPI dependency that returns the singleton :class:`~sesmio.client.SES` instance.

    Use as ``Depends(get_ses)`` in FastAPI route parameters.

    Returns:
        The shared :class:`~sesmio.client.SES` instance.
    """
    return _get_ses_instance()
