"""Email component library — Python equivalents of react.email components.

Each component is a frozen dataclass. Calling the dataclass produces a
:class:`Node` tree that the render pipeline converts to email-safe HTML and
plain text.

All string ``children`` are HTML-escaped automatically via
:func:`sesmio._internal.escape.escape`. Only :class:`Raw` bypasses escaping.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Protocol, Union, runtime_checkable

from sesmio._internal.escape import escape

_logger = logging.getLogger("sesmio")

# ---------------------------------------------------------------------------
# Node — the universal tree element
# ---------------------------------------------------------------------------

# Children can be Node instances or plain strings (already escaped by callers).
ChildType = Union["Node", str]


@runtime_checkable
class _HasToNode(Protocol):
    """Protocol for components that can be converted to a Node."""

    def to_node(self) -> "Node": ...


@dataclass(frozen=True)
class Node:
    """Internal tree node produced by every component.

    Attributes:
        tag: HTML tag name (``"table"``, ``"p"``, etc.).
        attrs: HTML attribute mapping, values already escaped.
        children: Ordered child nodes / text strings (already escaped).
        css: Declarative CSS properties contributed by this component.
        class_: Optional Tailwind / custom class string.
    """

    tag: str
    attrs: dict[str, str]
    children: tuple[ChildType, ...]
    css: dict[str, str] = field(default_factory=dict)
    class_: str | None = None

    def __hash__(self) -> int:  # needed because attrs/css are dicts
        return id(self)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """Escape a user-supplied string for inclusion in HTML."""
    return escape(text)


def _resolve_child(child: Any) -> ChildType:
    """Convert a component (or Node/str) to a ChildType by calling to_node() if needed."""
    if isinstance(child, (Node, str)):
        return child
    if isinstance(child, _HasToNode):
        return child.to_node()
    return str(child)


def _children_to_tuple(children: Any) -> tuple[ChildType, ...]:
    """Normalise any children input to a tuple of ChildType."""
    if isinstance(children, (Node, str)):
        return (children,)
    if isinstance(children, _HasToNode):
        return (children.to_node(),)
    # Iterable — list, tuple, generator.
    return tuple(_resolve_child(c) for c in children)


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Preview:
    """Hidden preview-text span shown in email client inbox previews.

    Args:
        text: The preview string (max ~90 chars for broad client support).
    """

    text: str

    def to_node(self) -> Node:
        """Return the preview-text Node."""
        # Zero-size, transparent text followed by repeated whitespace/ZWJ to
        # suppress the email client showing body text in the preview area.
        filler = "‌ " * 60
        safe = _esc(self.text)
        return Node(
            tag="div",
            attrs={"style": "display:none;max-height:0;overflow:hidden;mso-hide:all"},
            children=(f"{safe}{filler}",),
        )


@dataclass(frozen=True)
class Head:
    """Email ``<head>`` with title, charset, viewport and optional preview text.

    Args:
        title: Document ``<title>`` text.
        preview: Preview-text shown in inbox before opening the email.
        meta: Extra ``<meta>`` HTML strings injected verbatim (use sparingly).
    """

    title: str | None = None
    preview: str | None = None
    meta: str | None = None

    def to_node(self) -> Node:
        """Return the head Node."""
        children: list[ChildType] = [
            Node(tag="meta", attrs={"charset": "utf-8"}, children=()),
            Node(
                tag="meta",
                attrs={
                    "name": "viewport",
                    "content": "width=device-width, initial-scale=1.0",
                },
                children=(),
            ),
        ]
        if self.title is not None:
            children.append(Node(tag="title", attrs={}, children=(_esc(self.title),)))
        # Base email-reset styles kept minimal; media queries survive inliner.
        base_css = (
            "body{margin:0;padding:0;width:100%!important;-webkit-text-size-adjust:100%}"
            "img{border:0;display:block;outline:none;text-decoration:none}"
            "table{border-collapse:collapse}"
        )
        children.append(Node(tag="style", attrs={}, children=(base_css,)))
        if self.meta is not None:
            # Raw meta string inserted as text (caller's responsibility).
            children.append(Node(tag="__raw__", attrs={}, children=(self.meta,)))
        if self.preview is not None:
            children.append(Preview(text=self.preview).to_node())
        return Node(tag="head", attrs={}, children=tuple(children))


@dataclass(frozen=True)
class Body:
    """Email ``<body>`` wrapper with background color.

    Args:
        children: Body content.
        bg: Background color hex value (default ``#ffffff``).
    """

    children: ChildType | tuple[ChildType, ...] | list[ChildType]
    bg: str = "#ffffff"

    def to_node(self) -> Node:
        """Return the body Node."""
        ch = _children_to_tuple(self.children)
        return Node(
            tag="body",
            attrs={"style": f"background-color:{self.bg};margin:0;padding:0"},
            children=ch,
        )


@dataclass(frozen=True)
class Container:
    """Centered, fixed-width email container using a bulletproof table layout.

    Args:
        children: Content to center.
        width: Max width in pixels (default 600).
        class_: Optional CSS / Tailwind classes.
    """

    children: ChildType | tuple[ChildType, ...] | list[ChildType]
    width: int = 600
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the container Node."""
        ch = _children_to_tuple(self.children)
        td = Node(
            tag="td",
            attrs={"align": "center", "style": "padding:0"},
            children=ch,
        )
        tr = Node(tag="tr", attrs={}, children=(td,))
        # Inner table carries actual width.
        inner = Node(
            tag="table",
            attrs={
                "role": "presentation",
                "width": str(self.width),
                "cellpadding": "0",
                "cellspacing": "0",
                "border": "0",
                "style": f"width:{self.width}px;max-width:100%",
            },
            children=(tr,),
            class_=self.class_,
        )
        # Outer table stretches full-width for alignment.
        outer_td = Node(
            tag="td",
            attrs={"align": "center"},
            children=(inner,),
        )
        outer_tr = Node(tag="tr", attrs={}, children=(outer_td,))
        return Node(
            tag="table",
            attrs={
                "role": "presentation",
                "width": "100%",
                "cellpadding": "0",
                "cellspacing": "0",
                "border": "0",
            },
            children=(outer_tr,),
        )


@dataclass(frozen=True)
class Section:
    """A vertical section, rendered as a ``<tr><td>`` pair.

    Args:
        children: Section content.
        padding: CSS padding shorthand (e.g. ``"24px"``).
        class_: Optional CSS / Tailwind classes.
    """

    children: ChildType | tuple[ChildType, ...] | list[ChildType]
    padding: str | None = None
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the section Node."""
        ch = _children_to_tuple(self.children)
        style = f"padding:{self.padding}" if self.padding else ""
        td = Node(
            tag="td",
            attrs={"style": style} if style else {},
            children=ch,
            class_=self.class_,
        )
        return Node(tag="tr", attrs={}, children=(td,))


@dataclass(frozen=True)
class Row:
    """A table row for multi-column layouts.

    Args:
        children: :class:`Column` components.
    """

    children: ChildType | tuple[ChildType, ...] | list[ChildType]

    def to_node(self) -> Node:
        """Return the row Node."""
        ch = _children_to_tuple(self.children)
        return Node(tag="tr", attrs={}, children=ch)


@dataclass(frozen=True)
class Column:
    """A table column (``<td>``) within a :class:`Row`.

    Args:
        children: Column content.
        width: Column width as CSS value (e.g. ``"50%"`` or ``"300px"``).
        class_: Optional CSS / Tailwind classes.
    """

    children: ChildType | tuple[ChildType, ...] | list[ChildType]
    width: str | None = None
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the column Node."""
        ch = _children_to_tuple(self.children)
        attrs: dict[str, str] = {}
        if self.width:
            attrs["width"] = self.width
            attrs["style"] = f"width:{self.width}"
        return Node(tag="td", attrs=attrs, children=ch, class_=self.class_)


@dataclass(frozen=True)
class Heading:
    """An HTML heading element (h1–h6).

    Args:
        text: Heading text (HTML-escaped automatically).
        level: Heading level 1–6 (default 1).
        class_: Optional CSS / Tailwind classes.
    """

    text: str
    level: int = 1
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the heading Node."""
        tag = f"h{max(1, min(6, self.level))}"
        return Node(tag=tag, attrs={}, children=(_esc(self.text),), class_=self.class_)


@dataclass(frozen=True)
class Text:
    """A paragraph of text.

    Args:
        text: Paragraph text (HTML-escaped automatically).
        class_: Optional CSS / Tailwind classes.
    """

    text: str
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the paragraph Node."""
        return Node(tag="p", attrs={}, children=(_esc(self.text),), class_=self.class_)


@dataclass(frozen=True)
class Link:
    """An anchor link.

    Args:
        href: Destination URL.
        children: Link label (string or nested Nodes).
        class_: Optional CSS / Tailwind classes.
    """

    href: str
    children: ChildType | tuple[ChildType, ...] | list[ChildType]
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the link Node."""
        if isinstance(self.children, str):
            ch: tuple[ChildType, ...] = (_esc(self.children),)
        else:
            ch = _children_to_tuple(self.children)
        return Node(
            tag="a",
            attrs={"href": _esc(self.href)},
            children=ch,
            class_=self.class_,
        )


@dataclass(frozen=True)
class Button:
    """A bulletproof, table-based email button with MSO fallback.

    Args:
        href: Button destination URL.
        children: Button label text or Node.
        bg: Background color (default ``#000000``).
        color: Text color (default ``#ffffff``).
        class_: Optional CSS / Tailwind classes.
    """

    href: str
    children: ChildType | tuple[ChildType, ...] | list[ChildType]
    bg: str = "#000000"
    color: str = "#ffffff"
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the bulletproof button Node."""
        if isinstance(self.children, str):
            ch: tuple[ChildType, ...] = (_esc(self.children),)
        else:
            ch = _children_to_tuple(self.children)
        link_style = (
            f"display:inline-block;padding:12px 24px;"
            f"background-color:{self.bg};color:{self.color};"
            f"text-decoration:none;border-radius:4px;font-weight:600"
        )
        link = Node(
            tag="a",
            attrs={"href": _esc(self.href), "style": link_style},
            children=ch,
        )
        td = Node(
            tag="td",
            attrs={"align": "center", "style": f"background-color:{self.bg};border-radius:4px"},
            children=(link,),
        )
        tr = Node(tag="tr", attrs={}, children=(td,))
        # MSO VML wrapper is injected by render.py as a raw comment block.
        return Node(
            tag="table",
            attrs={
                "role": "presentation",
                "cellpadding": "0",
                "cellspacing": "0",
                "border": "0",
                "style": "margin:0 auto",
                "data-sesmio-button": "1",
            },
            children=(tr,),
            class_=self.class_,
        )


@dataclass(frozen=True)
class Img:
    """An email-safe image element.

    Args:
        src: Image URL.
        alt: Alt text — required; raises :class:`ValueError` if empty.
        width: Image width in pixels.
        height: Image height in pixels.
        class_: Optional CSS / Tailwind classes.

    Raises:
        ValueError: If *alt* is empty or whitespace.
    """

    src: str
    alt: str
    width: int | None = None
    height: int | None = None
    class_: str | None = None

    def __post_init__(self) -> None:
        if not self.alt or not self.alt.strip():
            raise ValueError("Img requires a non-empty alt attribute.")

    def to_node(self) -> Node:
        """Return the image Node."""
        attrs: dict[str, str] = {
            "src": _esc(self.src),
            "alt": _esc(self.alt),
            "border": "0",
            "style": "display:block;max-width:100%",
        }
        if self.width is not None:
            attrs["width"] = str(self.width)
        if self.height is not None:
            attrs["height"] = str(self.height)
        return Node(tag="img", attrs=attrs, children=(), class_=self.class_)


@dataclass(frozen=True)
class Hr:
    """A horizontal rule / divider.

    Args:
        color: Border color (default ``#e5e7eb``).
        class_: Optional CSS / Tailwind classes.
    """

    color: str = "#e5e7eb"
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the divider Node."""
        return Node(
            tag="hr",
            attrs={"style": f"border:0;border-top:1px solid {self.color};margin:16px 0"},
            children=(),
            class_=self.class_,
        )


@dataclass(frozen=True)
class Spacer:
    """A vertical spacer using a transparent table row.

    Args:
        height: Spacer height in pixels (default 16).
    """

    height: int = 16

    def to_node(self) -> Node:
        """Return the spacer Node."""
        td = Node(
            tag="td",
            attrs={
                "height": str(self.height),
                "style": (
                    f"height:{self.height}px;font-size:{self.height}px;line-height:{self.height}px"
                ),
            },
            children=(" ",),
        )
        tr = Node(tag="tr", attrs={}, children=(td,))
        return Node(
            tag="table",
            attrs={
                "role": "presentation",
                "width": "100%",
                "cellpadding": "0",
                "cellspacing": "0",
                "border": "0",
            },
            children=(tr,),
        )


@dataclass(frozen=True)
class CodeBlock:
    """A preformatted code block.

    Args:
        code: Source code (HTML-escaped automatically).
        lang: Optional language hint (not rendered, for future syntax
            highlighting extensions).
        class_: Optional CSS / Tailwind classes.
    """

    code: str
    lang: str | None = None
    class_: str | None = None

    def to_node(self) -> Node:
        """Return the code block Node."""
        code_node = Node(tag="code", attrs={}, children=(_esc(self.code),))
        style = (
            "background-color:#f3f4f6;border-radius:4px;font-family:monospace;"
            "font-size:0.875rem;padding:16px;display:block;overflow-x:auto;white-space:pre"
        )
        return Node(tag="pre", attrs={"style": style}, children=(code_node,), class_=self.class_)


@dataclass(frozen=True)
class Raw:
    """Escape hatch for injecting arbitrary HTML.

    Usage of this component is intentional and logged as a warning —
    XSS protection is the caller's responsibility.

    Args:
        html_string: Raw HTML to embed verbatim.
    """

    html_string: str

    def __post_init__(self) -> None:
        warnings.warn(
            "Raw() bypasses HTML escaping. Ensure the content is trusted.",
            stacklevel=3,
        )
        _logger.warning("raw.component.used: Raw() component bypasses HTML escaping")

    def to_node(self) -> Node:
        """Return the raw Node."""
        return Node(tag="__raw__", attrs={}, children=(self.html_string,))


@dataclass(frozen=True)
class Html:
    """Root email document component.

    Args:
        head: :class:`Head` component.
        body: :class:`Body` component.
        lang: ``lang`` attribute for the ``<html>`` element (default ``"en"``).
    """

    head: Head
    body: Body
    lang: str = "en"

    def to_node(self) -> Node:
        """Return the root HTML Node."""
        return Node(
            tag="html",
            attrs={"lang": self.lang, "xmlns": "http://www.w3.org/1999/xhtml"},
            children=(self.head.to_node(), self.body.to_node()),
        )


# ---------------------------------------------------------------------------
# Convenience: allow components to accept other components as children.
# ---------------------------------------------------------------------------

# Public type alias for anything that has to_node() or is a Node/str.
Component = Union[
    Html,
    Head,
    Body,
    Container,
    Section,
    Row,
    Column,
    Heading,
    Text,
    Link,
    Button,
    Img,
    Hr,
    Spacer,
    Preview,
    CodeBlock,
    Raw,
    Node,
]
