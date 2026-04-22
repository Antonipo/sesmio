"""Unit tests for sesmio.email.components."""

from __future__ import annotations

import warnings

import pytest

from sesmio.email.components import (
    Body,
    Button,
    CodeBlock,
    Column,
    Container,
    Head,
    Heading,
    Hr,
    Html,
    Img,
    Link,
    Node,
    Preview,
    Raw,
    Row,
    Section,
    Spacer,
    Text,
)

# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class TestNode:
    def test_frozen(self) -> None:
        node = Node(tag="p", attrs={}, children=("hello",))
        with pytest.raises((AttributeError, TypeError)):
            node.tag = "div"  # type: ignore[misc]

    def test_hash_uses_id(self) -> None:
        n1 = Node(tag="p", attrs={}, children=())
        n2 = Node(tag="p", attrs={}, children=())
        # Same content, different instances — different hashes.
        assert hash(n1) != hash(n2)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


class TestPreview:
    def test_to_node_tag(self) -> None:
        node = Preview(text="Hello").to_node()
        assert node.tag == "div"

    def test_hidden_style(self) -> None:
        node = Preview(text="Hello").to_node()
        assert "display:none" in node.attrs["style"]

    def test_text_escaped(self) -> None:
        node = Preview(text="<b>Hi</b>").to_node()
        content = str(node.children[0])
        assert "<b>" not in content
        assert "&lt;b&gt;" in content


# ---------------------------------------------------------------------------
# Head
# ---------------------------------------------------------------------------


class TestHead:
    def test_basic_head(self) -> None:
        node = Head().to_node()
        assert node.tag == "head"

    def test_includes_charset(self) -> None:
        node = Head().to_node()
        tags = [c.tag for c in node.children if isinstance(c, Node)]
        assert "meta" in tags

    def test_title_included(self) -> None:
        node = Head(title="Test").to_node()
        titles = [c for c in node.children if isinstance(c, Node) and c.tag == "title"]
        assert len(titles) == 1
        assert "Test" in str(titles[0].children[0])

    def test_preview_creates_hidden_div(self) -> None:
        node = Head(preview="Check this out").to_node()
        divs = [c for c in node.children if isinstance(c, Node) and c.tag == "div"]
        assert len(divs) == 1

    def test_no_title_no_title_element(self) -> None:
        node = Head().to_node()
        titles = [c for c in node.children if isinstance(c, Node) and c.tag == "title"]
        assert len(titles) == 0


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------


class TestBody:
    def test_tag(self) -> None:
        node = Body(children=Text(text="hi").to_node()).to_node()
        assert node.tag == "body"

    def test_default_bg(self) -> None:
        node = Body(children="hi").to_node()
        assert "#ffffff" in node.attrs["style"]

    def test_custom_bg(self) -> None:
        node = Body(children="hi", bg="#ff0000").to_node()
        assert "#ff0000" in node.attrs["style"]


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class TestContainer:
    def test_outer_table_full_width(self) -> None:
        node = Container(children=Text(text="hi").to_node()).to_node()
        assert node.tag == "table"
        assert node.attrs.get("width") == "100%"

    def test_inner_table_width(self) -> None:
        node = Container(children=Text(text="hi").to_node(), width=500).to_node()
        # Inner table is nested inside outer.
        outer_td = node.children[0].children[0]  # type: ignore[union-attr]
        inner = outer_td.children[0]  # type: ignore[union-attr]
        assert isinstance(inner, Node)
        assert inner.attrs.get("width") == "500"

    def test_class_applied_to_inner(self) -> None:
        node = Container(children="hi", class_="max-w-lg").to_node()
        outer_td = node.children[0].children[0]  # type: ignore[union-attr]
        inner = outer_td.children[0]  # type: ignore[union-attr]
        assert isinstance(inner, Node)
        assert inner.class_ == "max-w-lg"


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------


class TestSection:
    def test_returns_tr(self) -> None:
        node = Section(children="hi").to_node()
        assert node.tag == "tr"

    def test_padding_in_td_style(self) -> None:
        node = Section(children="hi", padding="16px").to_node()
        td = node.children[0]
        assert isinstance(td, Node)
        assert "padding:16px" in td.attrs["style"]

    def test_no_padding_no_style(self) -> None:
        node = Section(children="hi").to_node()
        td = node.children[0]
        assert isinstance(td, Node)
        assert "style" not in td.attrs or td.attrs.get("style") == ""


# ---------------------------------------------------------------------------
# Row / Column
# ---------------------------------------------------------------------------


class TestRowColumn:
    def test_row_tag(self) -> None:
        node = Row(children=Column(children="x").to_node()).to_node()
        assert node.tag == "tr"

    def test_column_tag(self) -> None:
        node = Column(children="x").to_node()
        assert node.tag == "td"

    def test_column_width(self) -> None:
        node = Column(children="x", width="50%").to_node()
        assert node.attrs.get("width") == "50%"

    def test_column_class(self) -> None:
        node = Column(children="x", class_="w-1/2").to_node()
        assert node.class_ == "w-1/2"


# ---------------------------------------------------------------------------
# Heading
# ---------------------------------------------------------------------------


class TestHeading:
    def test_h1(self) -> None:
        node = Heading(text="Title").to_node()
        assert node.tag == "h1"

    def test_h3(self) -> None:
        node = Heading(text="Sub", level=3).to_node()
        assert node.tag == "h3"

    def test_level_clamped_low(self) -> None:
        node = Heading(text="x", level=0).to_node()
        assert node.tag == "h1"

    def test_level_clamped_high(self) -> None:
        node = Heading(text="x", level=9).to_node()
        assert node.tag == "h6"

    def test_text_escaped(self) -> None:
        node = Heading(text="<b>Hello</b>").to_node()
        assert "&lt;b&gt;" in str(node.children[0])

    def test_class_preserved(self) -> None:
        node = Heading(text="x", class_="text-2xl").to_node()
        assert node.class_ == "text-2xl"


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


class TestText:
    def test_tag_is_p(self) -> None:
        node = Text(text="Hello").to_node()
        assert node.tag == "p"

    def test_text_escaped(self) -> None:
        node = Text(text='<script>alert("xss")</script>').to_node()
        content = str(node.children[0])
        assert "<script>" not in content

    def test_class_preserved(self) -> None:
        node = Text(text="x", class_="text-gray-700").to_node()
        assert node.class_ == "text-gray-700"


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------


class TestLink:
    def test_tag(self) -> None:
        node = Link(href="https://example.com", children="Click").to_node()
        assert node.tag == "a"

    def test_href_escaped(self) -> None:
        node = Link(href='https://x.com?a=1&b=2"', children="x").to_node()
        assert '"' not in node.attrs["href"] or "&quot;" in node.attrs["href"]

    def test_children_string_escaped(self) -> None:
        node = Link(href="https://x.com", children="<bad>").to_node()
        assert "<bad>" not in str(node.children[0])

    def test_children_node_passthrough(self) -> None:
        child = Text(text="label").to_node()
        node = Link(href="https://x.com", children=child).to_node()
        assert node.children[0] is child


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------


class TestButton:
    def test_outer_tag_is_table(self) -> None:
        node = Button(href="https://x.com", children="Go").to_node()
        assert node.tag == "table"

    def test_data_attr_set(self) -> None:
        node = Button(href="https://x.com", children="Go").to_node()
        assert node.attrs.get("data-sesmio-button") == "1"

    def test_link_has_correct_href(self) -> None:
        node = Button(href="https://example.com", children="Go").to_node()
        tr = node.children[0]
        assert isinstance(tr, Node)
        td = tr.children[0]
        assert isinstance(td, Node)
        link = td.children[0]
        assert isinstance(link, Node)
        assert link.attrs["href"] == "https://example.com"

    def test_bg_and_color_in_style(self) -> None:
        node = Button(href="https://x.com", children="Go", bg="#123456", color="#abcdef").to_node()
        tr = node.children[0]
        assert isinstance(tr, Node)
        td = tr.children[0]
        assert isinstance(td, Node)
        link = td.children[0]
        assert isinstance(link, Node)
        assert "#123456" in link.attrs["style"]
        assert "#abcdef" in link.attrs["style"]

    def test_children_string_escaped(self) -> None:
        node = Button(href="https://x.com", children="<label>").to_node()
        tr = node.children[0]
        assert isinstance(tr, Node)
        td = tr.children[0]
        assert isinstance(td, Node)
        link = td.children[0]
        assert isinstance(link, Node)
        label = link.children[0]
        assert "<label>" not in str(label)


# ---------------------------------------------------------------------------
# Img
# ---------------------------------------------------------------------------


class TestImg:
    def test_tag_is_img(self) -> None:
        node = Img(src="https://x.com/img.png", alt="A photo").to_node()
        assert node.tag == "img"

    def test_alt_required(self) -> None:
        with pytest.raises(ValueError, match="alt"):
            Img(src="https://x.com/img.png", alt="")

    def test_alt_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError):
            Img(src="https://x.com/img.png", alt="   ")

    def test_alt_escaped(self) -> None:
        node = Img(src="x", alt='<"bad>').to_node()
        assert "<" not in node.attrs["alt"]

    def test_width_and_height(self) -> None:
        node = Img(src="x", alt="x", width=100, height=50).to_node()
        assert node.attrs["width"] == "100"
        assert node.attrs["height"] == "50"

    def test_no_width_no_attr(self) -> None:
        node = Img(src="x", alt="x").to_node()
        assert "width" not in node.attrs

    def test_class_preserved(self) -> None:
        node = Img(src="x", alt="x", class_="w-full").to_node()
        assert node.class_ == "w-full"


# ---------------------------------------------------------------------------
# Hr
# ---------------------------------------------------------------------------


class TestHr:
    def test_tag(self) -> None:
        node = Hr().to_node()
        assert node.tag == "hr"

    def test_default_color(self) -> None:
        node = Hr().to_node()
        assert "#e5e7eb" in node.attrs["style"]

    def test_custom_color(self) -> None:
        node = Hr(color="#ff0000").to_node()
        assert "#ff0000" in node.attrs["style"]


# ---------------------------------------------------------------------------
# Spacer
# ---------------------------------------------------------------------------


class TestSpacer:
    def test_outer_tag(self) -> None:
        node = Spacer().to_node()
        assert node.tag == "table"

    def test_default_height(self) -> None:
        node = Spacer().to_node()
        tr = node.children[0]
        assert isinstance(tr, Node)
        td = tr.children[0]
        assert isinstance(td, Node)
        assert "16px" in td.attrs["style"]

    def test_custom_height(self) -> None:
        node = Spacer(height=32).to_node()
        tr = node.children[0]
        assert isinstance(tr, Node)
        td = tr.children[0]
        assert isinstance(td, Node)
        assert "32px" in td.attrs["style"]


# ---------------------------------------------------------------------------
# CodeBlock
# ---------------------------------------------------------------------------


class TestCodeBlock:
    def test_outer_is_pre(self) -> None:
        node = CodeBlock(code="print('hi')").to_node()
        assert node.tag == "pre"

    def test_inner_is_code(self) -> None:
        node = CodeBlock(code="x = 1").to_node()
        inner = node.children[0]
        assert isinstance(inner, Node)
        assert inner.tag == "code"

    def test_code_escaped(self) -> None:
        node = CodeBlock(code="<script>").to_node()
        inner = node.children[0]
        assert isinstance(inner, Node)
        assert "&lt;script&gt;" in str(inner.children[0])


# ---------------------------------------------------------------------------
# Raw
# ---------------------------------------------------------------------------


class TestRaw:
    def test_to_node_tag(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            node = Raw(html_string="<b>bold</b>").to_node()
        assert node.tag == "__raw__"

    def test_content_verbatim(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            node = Raw(html_string="<b>bold</b>").to_node()
        assert node.children[0] == "<b>bold</b>"

    def test_warning_emitted(self) -> None:
        with pytest.warns(UserWarning, match="Raw"):
            Raw(html_string="<p>x</p>")

    def test_frozen(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw = Raw(html_string="x")
        with pytest.raises((AttributeError, TypeError)):
            raw.html_string = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Html root
# ---------------------------------------------------------------------------


class TestHtml:
    def test_root_tag(self) -> None:
        node = Html(head=Head(), body=Body(children="hi")).to_node()
        assert node.tag == "html"

    def test_lang_default(self) -> None:
        node = Html(head=Head(), body=Body(children="hi")).to_node()
        assert node.attrs.get("lang") == "en"

    def test_lang_custom(self) -> None:
        node = Html(head=Head(), body=Body(children="hi"), lang="es").to_node()
        assert node.attrs.get("lang") == "es"

    def test_children_are_head_and_body(self) -> None:
        node = Html(head=Head(), body=Body(children="hi")).to_node()
        assert len(node.children) == 2
        assert isinstance(node.children[0], Node)
        assert isinstance(node.children[1], Node)
        assert node.children[0].tag == "head"
        assert node.children[1].tag == "body"
