"""Plain-text extraction from a Node tree.

Traverses the component tree without any regex over HTML strings, producing
a clean, readable plain-text version of an email template.
"""

from __future__ import annotations

import html as html_mod

from sesmio.email.components import Node


def _unescape(s: str) -> str:
    """Reverse HTML escaping on leaf text before writing to plain text."""
    return html_mod.unescape(s)


def traverse_text(node: Node | str) -> str:  # noqa: C901 (acceptable complexity)
    """Convert a Node tree to a clean plain-text string.

    Rendering rules:
    - :class:`~sesmio.email.components.Heading` — blank lines + ``====`` / ``----``
      underline for h1/h2; no underline for h3+.
    - :class:`~sesmio.email.components.Text` — separated by ``\\n\\n``.
    - :class:`~sesmio.email.components.Link` — ``label (url)``.
    - :class:`~sesmio.email.components.Button` — ``[label] (url)``.
    - :class:`~sesmio.email.components.Hr` — ``---``.
    - :class:`~sesmio.email.components.Img` — ``[Image: alt]``.
    - :class:`~sesmio.email.components.Raw` — skipped (unreliable extraction).
    - Head / style blocks — skipped.

    Args:
        node: Root node of the tree (or any subtree).

    Returns:
        Plain-text string with whitespace normalised.
    """
    if isinstance(node, str):
        return _unescape(node)

    tag = node.tag

    # --- Skip non-visual nodes ------------------------------------------------
    if tag in ("head", "style", "title", "meta", "__raw__"):
        return ""

    # Hidden preview-text div — skip entirely.
    style = node.attrs.get("style", "")
    if "display:none" in style.replace(" ", ""):
        return ""

    # --- Leaf content ---------------------------------------------------------
    def _inner() -> str:
        parts = [traverse_text(c) for c in node.children]
        return "".join(parts)

    # --- Block elements with special formatting -------------------------------
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        text = _inner().strip()
        level = int(tag[1])
        if level == 1:
            underline = "=" * len(text)
            return f"\n\n{text}\n{underline}\n"
        if level == 2:
            underline = "-" * len(text)
            return f"\n\n{text}\n{underline}\n"
        return f"\n\n{text}\n"

    if tag == "p":
        return f"\n\n{_inner().strip()}"

    if tag == "hr":
        return "\n\n---\n"

    if tag == "img":
        alt = _unescape(node.attrs.get("alt", ""))
        return f"[Image: {alt}]"

    if tag == "a":
        href = _unescape(node.attrs.get("href", ""))
        label = _inner().strip()
        if href:
            return f"{label} ({href})"
        return label

    # Button detection: table with data-sesmio-button attr wraps a link.
    if tag == "table" and node.attrs.get("data-sesmio-button"):
        # Drill into tr > td > a to extract label + href.
        label = ""
        href = ""
        for tr in node.children:
            if isinstance(tr, Node) and tr.tag == "tr":
                for td in tr.children:
                    if isinstance(td, Node) and td.tag == "td":
                        for a in td.children:
                            if isinstance(a, Node) and a.tag == "a":
                                href = _unescape(a.attrs.get("href", ""))
                                label = "".join(traverse_text(c) for c in a.children).strip()
        return f"\n\n[{label}] ({href})\n"

    if tag == "pre":
        return f"\n\n{_inner()}\n"

    if tag == "code":
        return _inner()

    if tag == "br":
        return "\n"

    # --- Container / layout elements — just recurse ---------------------------
    return _inner()


def build_text(node: Node) -> str:
    """Build a clean plain-text document from the root Node.

    Strips leading/trailing whitespace and collapses runs of more than two
    consecutive blank lines.

    Args:
        node: Root :class:`~sesmio.email.components.Node` of the tree.

    Returns:
        Clean plain-text string.
    """
    import re

    raw = traverse_text(node)
    # Collapse more than two consecutive newlines.
    cleaned = re.sub(r"\n{3,}", "\n\n", raw)
    return cleaned.strip()
