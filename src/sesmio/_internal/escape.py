"""HTML escape utilities. Phase 2 will use this more extensively."""

from __future__ import annotations

import html


def escape(text: str) -> str:
    """Return *text* with HTML special characters escaped.

    Uses ``html.escape(quote=True)`` to cover attribute contexts as well as
    element text content.
    """
    return html.escape(text, quote=True)
