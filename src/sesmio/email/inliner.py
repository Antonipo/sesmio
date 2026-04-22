"""CSS inliner — converts ``<style>`` blocks and ``class=`` attributes to inline styles.

Uses only stdlib ``html.parser``. No external dependencies.

Supported selectors: ``tag``, ``.class``, ``#id``, ``tag.class``,
``parent > child``, ``:first-child``.

Media queries and dynamic pseudo-classes (e.g. ``:hover``) are left in a
residual ``<style>`` block so responsive/interactive clients still benefit.

Complexity: O(n·m) where n = elements, m = CSS rules.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional

# ---------------------------------------------------------------------------
# Internal element tree
# ---------------------------------------------------------------------------


class _Element:
    """Minimal element node produced by the two-pass HTML parser."""

    __slots__ = ("tag", "attrs", "children", "parent", "index_in_parent")

    def __init__(
        self,
        tag: str,
        attrs: dict[str, str],
        parent: Optional["_Element"] = None,
    ) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Element | str] = []
        self.parent = parent
        self.index_in_parent: int = 0


# Void elements that must not emit a closing tag.
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

# Tags whose text content must not be escaped further (raw content).
_RAW_TEXT = frozenset({"script", "style"})


class _TreeBuilder(HTMLParser):
    """Build an internal element tree from HTML source."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._root = _Element("__root__", {})
        self._stack: list[_Element] = [self._root]
        # Accumulate raw text inside <style>/<script> without entity decoding.
        self._raw_tag: str | None = None

    # -- HTMLParser overrides --------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v or "") for k, v in attrs}
        parent = self._stack[-1]
        el = _Element(tag, attrs_dict, parent)
        # Track position among sibling *elements* (not text nodes).
        sibling_count = sum(1 for c in parent.children if isinstance(c, _Element))
        el.index_in_parent = sibling_count
        parent.children.append(el)
        if tag not in _VOID:
            self._stack.append(el)
        if tag in _RAW_TEXT:
            self._raw_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in _RAW_TEXT:
            self._raw_tag = None
        if tag not in _VOID and len(self._stack) > 1:
            # Pop matching open tag, handling malformed HTML gracefully.
            for i in range(len(self._stack) - 1, 0, -1):
                if self._stack[i].tag == tag:
                    self._stack = self._stack[:i]
                    break

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)

    def handle_comment(self, data: str) -> None:
        # Preserve HTML comments (MSO conditionals live here).
        self._stack[-1].children.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._stack[-1].children.append(f"<!{decl}>")

    def handle_entityref(self, name: str) -> None:
        self._stack[-1].children.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._stack[-1].children.append(f"&#{name};")


# ---------------------------------------------------------------------------
# CSS tokeniser
# ---------------------------------------------------------------------------

_RULE_RE = re.compile(
    r"([^{]+)\{([^}]*)\}",
    re.DOTALL,
)

_MEDIA_RE = re.compile(
    r"@[a-zA-Z][^{]*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
    re.DOTALL,
)


def _parse_css(css: str) -> tuple[list[tuple[str, dict[str, str]]], str]:
    """Return (inlineable_rules, residual_css).

    *inlineable_rules*: list of ``(selector, {prop: val, ...})``.
    *residual_css*: media queries and dynamic pseudo-class rules unchanged.
    """
    residual_parts: list[str] = []

    # Pull out @-rules (media queries, keyframes, …) first.
    def _collect_at(m: re.Match[str]) -> str:
        residual_parts.append(m.group(0))
        return ""

    stripped = _MEDIA_RE.sub(_collect_at, css)

    inlineable: list[tuple[str, dict[str, str]]] = []
    for m in _RULE_RE.finditer(stripped):
        selector_raw = m.group(1).strip()
        declarations_raw = m.group(2).strip()

        # Selectors containing pseudo-classes other than :first-child go to residual.
        if re.search(r":(?!first-child)[a-zA-Z\-]+", selector_raw):
            residual_parts.append(f"{selector_raw} {{ {declarations_raw} }}")
            continue

        props: dict[str, str] = {}
        for decl in declarations_raw.split(";"):
            decl = decl.strip()
            if ":" in decl:
                prop, _, val = decl.partition(":")
                props[prop.strip()] = val.strip()

        for sel in selector_raw.split(","):
            sel = sel.strip()
            if sel:
                inlineable.append((sel, props))

    return inlineable, "\n".join(residual_parts)


# ---------------------------------------------------------------------------
# Selector matching
# ---------------------------------------------------------------------------


def _matches(el: _Element, selector: str) -> bool:
    """Return True if *el* matches *selector* (subset implementation)."""
    selector = selector.strip()

    # ``parent > child`` — direct-child combinator.
    if ">" in selector:
        parts = [p.strip() for p in selector.split(">")]
        if len(parts) == 2:
            child_sel, parent_sel = parts[1], parts[0]
            return (
                _matches(el, child_sel)
                and el.parent is not None
                and _matches(el.parent, parent_sel)
            )
        return False

    # ``:first-child`` pseudo-class.
    if selector.endswith(":first-child"):
        base = selector[: -len(":first-child")]
        return el.index_in_parent == 0 and _matches(el, base)

    # ``tag.class``
    if "." in selector and not selector.startswith("."):
        tag_part, _, class_part = selector.partition(".")
        return el.tag == tag_part and class_part in el.attrs.get("class", "").split()

    # ``.class``
    if selector.startswith("."):
        cls = selector[1:]
        return cls in el.attrs.get("class", "").split()

    # ``#id``
    if selector.startswith("#"):
        return el.attrs.get("id") == selector[1:]

    # ``tag``
    return el.tag == selector


# ---------------------------------------------------------------------------
# Style merging helpers
# ---------------------------------------------------------------------------


def _parse_inline_style(style: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for decl in style.split(";"):
        decl = decl.strip()
        if ":" in decl:
            prop, _, val = decl.partition(":")
            props[prop.strip()] = val.strip()
    return props


def _merge_styles(base: dict[str, str], override: dict[str, str]) -> str:
    """Merge *override* into *base*, returning a ``; ``-joined CSS string.

    Inline styles (override) win per CSS specificity.
    """
    merged = {**base, **override}
    return "; ".join(f"{k}: {v}" for k, v in merged.items())


# ---------------------------------------------------------------------------
# Tree → HTML serialiser
# ---------------------------------------------------------------------------


def _attr_str(attrs: dict[str, str]) -> str:
    parts: list[str] = []
    for k, v in attrs.items():
        # Preserve boolean-style attributes (value == "").
        if v == "":
            parts.append(k)
        else:
            escaped = v.replace("&", "&amp;").replace('"', "&quot;")
            parts.append(f'{k}="{escaped}"')
    return (" " + " ".join(parts)) if parts else ""


def _serialise(node: _Element, skip_root: bool = True) -> str:
    if skip_root and node.tag == "__root__":
        return "".join(
            _serialise(c, skip_root=False) if isinstance(c, _Element) else c for c in node.children
        )

    attr_s = _attr_str(node.attrs)
    if node.tag in _VOID:
        return f"<{node.tag}{attr_s}>"

    inner = "".join(
        _serialise(c, skip_root=False) if isinstance(c, _Element) else c for c in node.children
    )
    return f"<{node.tag}{attr_s}>{inner}</{node.tag}>"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def inline_css(html: str, extra_css: str = "") -> str:
    """Inline ``<style>`` block CSS into element ``style=`` attributes.

    Also resolves Tailwind-like ``class=`` attributes when *extra_css*
    contains the matching declarations (pass output of
    :func:`~sesmio.email.tailwind.resolve_classes` as *extra_css* when needed).

    Args:
        html: Full HTML document or fragment.
        extra_css: Additional CSS declarations to process (e.g. from Tailwind
            resolver). These are prepended to any ``<style>`` block found.

    Returns:
        HTML with ``<style>`` blocks removed (or reduced to media-query
        fallback) and all inlineable rules merged into ``style=`` attributes.
    """
    # Python 3.12.3's html.parser truncates input when it encounters certain
    # conditional comments (fixed in 3.12.4+). We stash every comment behind an
    # opaque placeholder before parsing and splice them back in on output.
    stashed_comments: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        stashed_comments.append(m.group(0))
        return f"\x00SESMIO_COMMENT_{len(stashed_comments) - 1}\x00"

    # Stash both real comments and downlevel-revealed MSO markers like
    # `<![endif]-->`, which are not valid HTML comments and confuse the parser.
    html = re.sub(r"<!--.*?-->|<!\[[^\]]+\]-->", _stash, html, flags=re.DOTALL)

    builder = _TreeBuilder()
    builder.feed(html)
    root = builder._root

    # Collect and remove <style> elements from the tree.
    style_texts: list[str] = []
    if extra_css:
        style_texts.append(extra_css)

    def _collect_styles(el: _Element) -> None:
        remove: list[_Element] = []
        for child in el.children:
            if isinstance(child, _Element):
                if child.tag == "style":
                    text = "".join(c for c in child.children if isinstance(c, str))
                    style_texts.append(text)
                    remove.append(child)
                else:
                    _collect_styles(child)
        for r in remove:
            el.children.remove(r)

    _collect_styles(root)

    all_css = "\n".join(style_texts)
    rules, residual = _parse_css(all_css)

    def _apply(el: _Element) -> None:
        for child in el.children:
            if isinstance(child, _Element):
                _apply(child)

        # Determine CSS from matched rules (lower specificity).
        matched: dict[str, str] = {}
        for selector, props in rules:
            if _matches(el, selector):
                matched.update(props)

        # Inline style wins over matched rules.
        inline_raw = el.attrs.get("style", "")
        inline_props = _parse_inline_style(inline_raw) if inline_raw else {}

        if matched or inline_props:
            el.attrs["style"] = _merge_styles(matched, inline_props)

        # Remove class= (not useful in email after inlining).
        el.attrs.pop("class", None)

    _apply(root)

    # Re-inject residual CSS (media queries etc.) into a <style> tag.
    result = _serialise(root)
    residual = residual.strip()
    if residual:
        # Insert before </head> if present, otherwise prepend.
        style_block = f"<style>{residual}</style>"
        if "</head>" in result:
            result = result.replace("</head>", f"{style_block}</head>", 1)
        else:
            result = style_block + result

    if stashed_comments:
        result = re.sub(
            r"\x00SESMIO_COMMENT_(\d+)\x00",
            lambda m: stashed_comments[int(m.group(1))],
            result,
        )

    return result
