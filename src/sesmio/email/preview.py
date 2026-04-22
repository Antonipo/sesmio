"""Local preview rendering — writes HTML to a file for browser inspection."""

from __future__ import annotations

import logging
from pathlib import Path

from sesmio.email.components import Html, Node
from sesmio.email.render import render

_logger = logging.getLogger("sesmio")


def render_preview(template: Html | Node, path: str | Path) -> None:
    """Render *template* to an HTML file and log the file:// URL.

    Intended for local development — open the logged URL in any browser to
    inspect the email visually before sending.

    Args:
        template: Root :class:`~sesmio.email.components.Html` component or
            a bare :class:`~sesmio.email.components.Node`.
        path: Output file path. Parent directories must already exist.

    Returns:
        None
    """
    html, _text = render(template)
    out = Path(path).resolve()
    out.write_text(html, encoding="utf-8")
    _logger.info("preview.written: file://%s", out)
