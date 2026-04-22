"""Email rendering pipeline: component tree → (HTML, plain-text).

Pipeline:
    Node tree
        → apply_tailwind  (resolve class_ via TAILWIND_MAP → node.css)
        → HTML string     (recursive serialisation with inline style= attrs)
        → inline_css      (merge <style> blocks into style= attrs)
        → final HTML
    Node tree
        → build_text      (tree traversal, no HTML regex)
        → plain text
"""

from __future__ import annotations

import re

from sesmio.email.components import (
    Html,
    Node,
)
from sesmio.email.inliner import inline_css
from sesmio.email.tailwind import resolve_classes
from sesmio.email.text import build_text

# Void elements — no closing tag.
_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


# ---------------------------------------------------------------------------
# Step 1: resolve Tailwind classes → css dict on each node
# ---------------------------------------------------------------------------


def _apply_tailwind(node: Node) -> Node:
    """Recursively resolve ``node.class_`` via TAILWIND_MAP into ``node.css``.

    Returns a new Node tree (frozen dataclasses, must copy to change).
    """
    extra_css: dict[str, str] = {}
    if node.class_:
        tw_decls = resolve_classes(node.class_)
        if tw_decls:
            for decl in tw_decls.split(";"):
                decl = decl.strip()
                if ":" in decl:
                    prop, _, val = decl.partition(":")
                    extra_css[prop.strip()] = val.strip()

    new_css = {**extra_css, **node.css}  # node.css (explicit) wins

    new_children = tuple(_apply_tailwind(c) if isinstance(c, Node) else c for c in node.children)

    return Node(
        tag=node.tag,
        attrs=node.attrs,
        children=new_children,
        css=new_css,
        class_=node.class_,
    )


# ---------------------------------------------------------------------------
# Step 2: serialise Node tree → HTML string
# ---------------------------------------------------------------------------


def _attr_str(attrs: dict[str, str], css: dict[str, str]) -> str:
    """Build HTML attribute string, merging *css* dict into ``style=``."""
    merged_attrs = dict(attrs)
    if css:
        existing = merged_attrs.get("style", "")
        # Explicit inline style= wins (appended last, same-prop overrides).
        css_str = "; ".join(f"{k}: {v}" for k, v in css.items())
        if existing:
            merged_attrs["style"] = f"{css_str}; {existing}"
        else:
            merged_attrs["style"] = css_str

    parts: list[str] = []
    for k, v in merged_attrs.items():
        if v == "":
            parts.append(k)
        else:
            escaped_v = v.replace("&", "&amp;").replace('"', "&quot;")
            parts.append(f'{k}="{escaped_v}"')
    return (" " + " ".join(parts)) if parts else ""


def _serialise_node(node: Node) -> str:
    """Recursively serialise a Node to an HTML string."""
    tag = node.tag

    # Raw escape-hatch node — emit children verbatim.
    if tag == "__raw__":
        return "".join(c if isinstance(c, str) else _serialise_node(c) for c in node.children)

    attr_s = _attr_str(node.attrs, node.css)

    if tag in _VOID:
        return f"<{tag}{attr_s}>"

    inner = "".join(c if isinstance(c, str) else _serialise_node(c) for c in node.children)

    return f"<{tag}{attr_s}>{inner}</{tag}>"


# ---------------------------------------------------------------------------
# MSO button wrapper injection
# ---------------------------------------------------------------------------

_BUTTON_RE = re.compile(
    r'<table[^>]*data-sesmio-button="1"[^>]*>(.*?)</table>',
    re.DOTALL,
)


def _inject_mso_buttons(html: str) -> str:
    """Wrap button tables with MSO VML for Outlook compatibility."""

    def _wrap(m: re.Match[str]) -> str:
        inner = m.group(0)
        # Extract href from the inner <a>.
        href_m = re.search(r'href="([^"]+)"', inner)
        href = href_m.group(1) if href_m else "#"
        # Extract background color for VML fill.
        bg_m = re.search(r"background-color:([^;\"]+)", inner)
        bg = bg_m.group(1).strip() if bg_m else "#000000"
        # Remove the data attr so it's not in final HTML.
        inner = re.sub(r'\s*data-sesmio-button="1"', "", inner)
        mso_open = (
            f'<!--[if mso]><v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" '
            f'xmlns:w="urn:schemas-microsoft-com:office:word" '
            f'href="{href}" style="height:44px;v-text-anchor:middle;width:200px;" '
            f'arcsize="5%%" stroke="f" fillcolor="{bg}">'
            f"<w:anchorlock/>"
            f'<center style="color:#ffffff;font-family:sans-serif;font-size:16px;'
            f'font-weight:bold;">'
        )
        mso_close = "</center></v:roundrect><![endif]-->"
        # Non-MSO clients see the normal table button.
        non_mso_open = "<!--[if !mso]><!-->"
        non_mso_close = "<!--<![endif]-->"
        return f"{mso_open}{non_mso_open}{inner}{non_mso_close}{mso_close}"

    return _BUTTON_RE.sub(_wrap, html)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(template: Html | Node) -> tuple[str, str]:
    """Render a component tree to ``(html, text)``.

    Args:
        template: Root :class:`~sesmio.email.components.Html` component or a
            bare :class:`~sesmio.email.components.Node`.

    Returns:
        A 2-tuple of ``(html_string, plain_text_string)``.
        The HTML string is a complete email-safe document with ``<!DOCTYPE>``,
        inlined CSS, and MSO conditionals.
    """
    # Resolve component dataclasses to Node tree.
    root: Node = template.to_node() if isinstance(template, Html) else template

    # Apply Tailwind class resolution.
    root = _apply_tailwind(root)

    # Build plain-text before serialisation (tree traversal is cleaner on
    # the original structured tree).
    plain_text = build_text(root)

    # Serialise to HTML.
    html_body = _serialise_node(root)

    # Inject MSO VML button wrappers.
    html_body = _inject_mso_buttons(html_body)

    # Inline any <style> blocks that weren't component-generated.
    html_body = inline_css(html_body)

    # Prepend DOCTYPE.
    html_out = f"<!DOCTYPE html>\n{html_body}"

    return html_out, plain_text


def render_html_fragment(node: Node) -> str:
    """Render a single Node to an HTML fragment string (no DOCTYPE, no inlining).

    Useful for unit tests and snapshot comparisons.

    Args:
        node: Any :class:`~sesmio.email.components.Node`.

    Returns:
        HTML string for the node and its descendants.
    """
    after_tw = _apply_tailwind(node)
    return _serialise_node(after_tw)
