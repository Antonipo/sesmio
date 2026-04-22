"""Unit tests for sesmio.email.text — tree → plain-text traversal."""

from __future__ import annotations

import warnings

from sesmio.email.components import (
    Body,
    Button,
    CodeBlock,
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
    Spacer,
    Text,
)
from sesmio.email.text import build_text, traverse_text


class TestHeadingText:
    def test_h1_has_equals_underline(self) -> None:
        node = Heading(text="Hello World").to_node()
        result = traverse_text(node)
        assert "Hello World" in result
        assert "=" * len("Hello World") in result

    def test_h2_has_dash_underline(self) -> None:
        node = Heading(text="Section", level=2).to_node()
        result = traverse_text(node)
        assert "Section" in result
        assert "---" in result

    def test_h3_no_underline(self) -> None:
        node = Heading(text="Sub", level=3).to_node()
        result = traverse_text(node)
        assert "Sub" in result
        assert "===" not in result
        assert "---" not in result

    def test_h1_surrounded_by_newlines(self) -> None:
        node = Heading(text="Title").to_node()
        result = traverse_text(node)
        assert result.startswith("\n\n")


class TestTextParagraph:
    def test_text_content(self) -> None:
        node = Text(text="Hello paragraph").to_node()
        result = traverse_text(node)
        assert "Hello paragraph" in result

    def test_text_preceded_by_newlines(self) -> None:
        node = Text(text="Para").to_node()
        result = traverse_text(node)
        assert "\n\n" in result


class TestLinkText:
    def test_link_format(self) -> None:
        node = Link(href="https://example.com", children="Click here").to_node()
        result = traverse_text(node)
        assert "Click here" in result
        assert "https://example.com" in result
        assert "(" in result and ")" in result

    def test_link_no_href(self) -> None:
        node = Node(tag="a", attrs={}, children=("label",))
        result = traverse_text(node)
        assert "label" in result


class TestButtonText:
    def test_button_format(self) -> None:
        node = Button(href="https://example.com", children="Get Started").to_node()
        result = traverse_text(node)
        assert "Get Started" in result
        assert "https://example.com" in result
        assert "[" in result and "]" in result

    def test_button_square_brackets(self) -> None:
        node = Button(href="https://x.com", children="Go").to_node()
        result = traverse_text(node)
        assert "[Go]" in result


class TestHrText:
    def test_hr_renders_dashes(self) -> None:
        node = Hr().to_node()
        result = traverse_text(node)
        assert "---" in result


class TestImgText:
    def test_img_format(self) -> None:
        node = Img(src="https://x.com/img.png", alt="Company logo").to_node()
        result = traverse_text(node)
        assert "[Image: Company logo]" in result

    def test_img_alt_unescaped(self) -> None:
        node = Img(src="x", alt="A & B").to_node()
        result = traverse_text(node)
        assert "A & B" in result


class TestRawText:
    def test_raw_skipped(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            node = Raw(html_string="<p>some html</p>").to_node()
        result = traverse_text(node)
        assert result == ""


class TestPreviewHidden:
    def test_preview_div_skipped(self) -> None:
        node = Preview(text="Preview text").to_node()
        result = traverse_text(node)
        assert "Preview text" not in result


class TestHeadSkipped:
    def test_head_skipped(self) -> None:
        node = Head(title="My Email").to_node()
        result = traverse_text(node)
        assert "My Email" not in result


class TestCodeBlock:
    def test_code_content_preserved(self) -> None:
        node = CodeBlock(code="print('hello')").to_node()
        result = traverse_text(node)
        assert "print" in result and "hello" in result


class TestSpacerText:
    def test_spacer_produces_no_visible_text(self) -> None:
        node = Spacer(height=16).to_node()
        result = traverse_text(node).strip()
        # Spacer may produce whitespace but nothing meaningful.
        assert len(result) <= 1


class TestBrText:
    def test_br_returns_newline(self) -> None:
        node = Node(tag="br", attrs={}, children=())
        result = traverse_text(node)
        assert result == "\n"


class TestBuildText:
    def test_full_template(self) -> None:
        template = Html(
            head=Head(title="Test"),
            body=Body(
                children=Container(
                    children=[
                        Heading(text="Welcome"),
                        Text(text="Thanks for signing up."),
                        Hr(),
                        Button(href="https://example.com", children="Start"),
                    ]
                )
            ),
        )
        root = template.to_node()
        result = build_text(root)
        assert "Welcome" in result
        assert "Thanks for signing up" in result
        assert "---" in result
        assert "Start" in result
        assert "https://example.com" in result

    def test_no_triple_blank_lines(self) -> None:
        template = Html(
            head=Head(),
            body=Body(children=[Text(text="A"), Text(text="B"), Text(text="C")]),
        )
        root = template.to_node()
        result = build_text(root)
        assert "\n\n\n" not in result

    def test_result_stripped(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hello")))
        root = template.to_node()
        result = build_text(root)
        assert result == result.strip()
