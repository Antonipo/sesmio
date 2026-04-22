"""Flask extension for sesmio.

Usage::

    from flask import Flask
    from sesmio.integrations.flask import SESExtension

    # Option A — direct init
    app = Flask(__name__)
    ses = SESExtension(app, default_from="no-reply@example.com")

    # Option B — application factory pattern
    ses = SESExtension()

    def create_app():
        app = Flask(__name__)
        app.config["SESMIO_DEFAULT_FROM"] = "no-reply@example.com"
        ses.init_app(app)
        return app

Config keys read from ``app.config`` (only when ``ses_kwargs`` are empty):
    ``SESMIO_REGION`` → ``region_name``
    ``SESMIO_DEFAULT_FROM`` → ``default_from``
    ``SESMIO_MAX_RETRIES`` → ``max_retries``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask

    from sesmio.templates import SESTemplates


class SESExtension:
    """Flask extension that manages a :class:`~sesmio.client.SES` instance.

    Compatible with both direct initialisation and the application factory
    pattern (``init_app``).
    """

    def __init__(self, app: "Flask | None" = None, **ses_kwargs: Any) -> None:
        self._ses_kwargs = ses_kwargs
        self._ses: Any = None  # SES instance, set in init_app
        if app is not None:
            self.init_app(app)

    def init_app(self, app: "Flask") -> None:
        """Bind this extension to *app*.

        Reads ``SESMIO_*`` config keys when no ``ses_kwargs`` were provided at
        construction time.

        Args:
            app: The :class:`flask.Flask` application instance.
        """
        kwargs = dict(self._ses_kwargs)

        # Read from app.config only when no explicit kwargs were passed.
        if not kwargs:
            if "SESMIO_REGION" in app.config:
                kwargs["region_name"] = app.config["SESMIO_REGION"]
            if "SESMIO_DEFAULT_FROM" in app.config:
                kwargs["default_from"] = app.config["SESMIO_DEFAULT_FROM"]
            if "SESMIO_MAX_RETRIES" in app.config:
                kwargs["max_retries"] = int(app.config["SESMIO_MAX_RETRIES"])

        from sesmio.client import SES

        ses_instance = SES(**kwargs)
        self._ses = ses_instance

        # Store in app.extensions for access via current_app.extensions["sesmio"].
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["sesmio"] = self

    def _require_ses(self) -> Any:
        if self._ses is None:
            raise RuntimeError(
                "SESExtension is not initialised. Call init_app(app) before using it."
            )
        return self._ses

    def send(self, **kwargs: Any) -> str:
        """Send an email. Accepts all :meth:`~sesmio.client.SES.send` kwargs.

        Returns:
            The SES ``MessageId`` string.
        """
        return self._require_ses().send(**kwargs)  # type: ignore[no-any-return]

    def bulk(self, *args: Any, **kwargs: Any) -> Any:
        """Create a bulk sender. Accepts all :meth:`~sesmio.client.SES.bulk` args.

        Returns:
            A :class:`~sesmio.sender.BulkSender` — call ``.send()`` to execute.
        """
        return self._require_ses().bulk(*args, **kwargs)

    @property
    def templates(self) -> "SESTemplates":
        """Cached :class:`~sesmio.templates.SESTemplates` accessor."""
        return self._require_ses().templates  # type: ignore[no-any-return]
