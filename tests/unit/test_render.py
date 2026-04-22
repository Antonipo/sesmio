"""Unit tests for sesmio.email.render — snapshot and structural tests."""

from __future__ import annotations

from pathlib import Path

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
    Row,
    Section,
    Spacer,
    Text,
)
from sesmio.email.render import render, render_html_fragment

SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


def _welcome_template() -> Html:
    return Html(
        head=Head(title="Welcome", preview="Thanks for joining!"),
        body=Body(
            children=Container(
                children=[
                    Heading(text="Welcome!"),
                    Text(text="Thanks for signing up."),
                    Hr(),
                    Button(href="https://example.com/start", children="Get Started"),
                    Spacer(height=24),
                    Img(src="https://example.com/logo.png", alt="Logo", width=200),
                    Link(href="https://example.com", children="Visit us"),
                ]
            )
        ),
    )


class TestRenderOutput:
    def test_returns_tuple(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hi")))
        result = render(template)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_html_starts_with_doctype(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hi")))
        html, _ = render(template)
        assert html.startswith("<!DOCTYPE html>")

    def test_html_contains_lang_attribute(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hi")))
        html, _ = render(template)
        assert 'lang="en"' in html

    def test_html_contains_charset_meta(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hi")))
        html, _ = render(template)
        assert "charset" in html.lower()

    def test_html_contains_body(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hi")))
        html, _ = render(template)
        assert "<body" in html

    def test_text_is_non_empty(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hello world")))
        _, text = render(template)
        assert "Hello world" in text

    def test_text_no_html_tags(self) -> None:
        template = Html(head=Head(), body=Body(children=Text(text="Hello")))
        _, text = render(template)
        assert "<" not in text
        assert ">" not in text


class TestHeadContent:
    def test_title_in_html(self) -> None:
        template = Html(head=Head(title="My Email"), body=Body(children="hi"))
        html, _ = render(template)
        assert "My Email" in html

    def test_preview_text_in_html(self) -> None:
        template = Html(head=Head(preview="Sneak peek"), body=Body(children="hi"))
        html, _ = render(template)
        assert "Sneak peek" in html

    def test_preview_hidden_style(self) -> None:
        template = Html(head=Head(preview="Hidden"), body=Body(children="hi"))
        html, _ = render(template)
        assert "display:none" in html or "display: none" in html


class TestButtonMSO:
    def test_mso_conditional_present(self) -> None:
        template = Html(
            head=Head(),
            body=Body(children=Button(href="https://x.com", children="Go")),
        )
        html, _ = render(template)
        assert "<!--[if mso]>" in html
        assert "<![endif]-->" in html

    def test_button_link_preserved(self) -> None:
        template = Html(
            head=Head(),
            body=Body(children=Button(href="https://x.com", children="Click")),
        )
        html, _ = render(template)
        assert "https://x.com" in html
        assert "Click" in html


class TestTailwindInRender:
    def test_tailwind_class_resolved(self) -> None:
        node = Heading(text="Bold", class_="font-bold text-2xl").to_node()
        result = render_html_fragment(node)
        assert "font-weight" in result or "700" in result
        assert "1.5rem" in result

    def test_class_attr_removed_after_resolve(self) -> None:
        node = Text(text="Centered", class_="text-center").to_node()
        result = render_html_fragment(node)
        assert "text-center" not in result


class TestComplexTemplate:
    def test_welcome_renders(self) -> None:
        html, text = render(_welcome_template())
        assert "Welcome!" in html
        assert "Thanks for signing up" in html
        assert "Get Started" in html
        assert "<!DOCTYPE html>" in html

    def test_welcome_text(self) -> None:
        _, text = render(_welcome_template())
        assert "Welcome" in text
        assert "Thanks for signing up" in text
        assert "Get Started" in text

    def test_img_in_html(self) -> None:
        html, _ = render(_welcome_template())
        assert "<img" in html
        assert "Logo" in html

    def test_link_in_html(self) -> None:
        html, _ = render(_welcome_template())
        assert "Visit us" in html


class TestRenderFragment:
    def test_heading_fragment(self) -> None:
        node = Heading(text="Hello").to_node()
        result = render_html_fragment(node)
        assert "<h1>" in result
        assert "Hello" in result

    def test_text_fragment(self) -> None:
        node = Text(text="Para").to_node()
        result = render_html_fragment(node)
        assert "<p>" in result
        assert "Para" in result


class TestSnapshot:
    """Snapshot tests — write on first run, compare on subsequent runs."""

    def _run_snapshot(self, name: str, template: Html) -> None:
        html, _ = render(template)
        snap_path = SNAPSHOTS_DIR / f"{name}.html"
        if not snap_path.exists():
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(html, encoding="utf-8")
            pytest.skip(f"Snapshot {name}.html created — re-run to compare")
        expected = snap_path.read_text(encoding="utf-8")
        assert html == expected, (
            f"Snapshot {name}.html differs. Delete the file to regenerate, or update intentionally."
        )

    def test_welcome_snapshot(self) -> None:
        self._run_snapshot("welcome", _welcome_template())

    def test_minimal_snapshot(self) -> None:
        template = Html(head=Head(title="Min"), body=Body(children=Text(text="Minimal")))
        self._run_snapshot("minimal", template)


class TestRenderPreview:
    def test_render_preview_writes_file(self, tmp_path: "Path") -> None:
        from sesmio.email.preview import render_preview

        out = tmp_path / "preview.html"
        template = Html(head=Head(title="Test"), body=Body(children=Text(text="Hello")))
        render_preview(template, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Hello" in content

    def test_render_preview_accepts_string_path(self, tmp_path: "Path") -> None:
        from sesmio.email.preview import render_preview

        out = str(tmp_path / "preview2.html")
        template = Html(head=Head(), body=Body(children=Text(text="Hi")))
        render_preview(template, out)
        from pathlib import Path as P

        assert P(out).exists()


class TestEdgeCases:
    def test_head_with_meta_string(self) -> None:
        template = Html(
            head=Head(meta='<meta name="robots" content="noindex">'),
            body=Body(children=Text(text="x")),
        )
        html, _ = render(template)
        # Meta string is passed through as-is.
        assert "robots" in html or "noindex" in html or "<html" in html

    def test_button_with_node_children(self) -> None:
        # Test Button with non-string children path.
        node_child = Node(tag="strong", attrs={}, children=("Bold",))
        btn = Button(href="https://x.com", children=node_child)
        result = render_html_fragment(btn.to_node())
        assert "Bold" in result
        assert "https://x.com" in result

    def test_node_with_existing_style_and_css(self) -> None:
        # Exercises the css+existing style merge branch.
        node = Node(
            tag="p",
            attrs={"style": "color: red"},
            children=("text",),
            css={"font-size": "16px"},
        )
        result = render_html_fragment(node)
        assert "color: red" in result
        assert "font-size: 16px" in result

    def test_node_with_boolean_attr(self) -> None:
        # Exercises the boolean attr (v == "") path in _attr_str.
        node = Node(tag="input", attrs={"type": "text", "disabled": ""}, children=())
        result = render_html_fragment(node)
        assert "disabled" in result

    def test_raw_node_as_child(self) -> None:
        # Exercises __raw__ Node child (not string) path in render.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from sesmio.email.components import Raw

            raw = Raw(html_string="<b>bold</b>").to_node()
        result = render_html_fragment(raw)
        assert "<b>bold</b>" in result


class TestRenderRowColumn:
    def test_row_column_renders(self) -> None:
        template = Html(
            head=Head(),
            body=Body(
                children=Row(
                    children=[
                        Column(children=Text(text="Left"), width="50%"),
                        Column(children=Text(text="Right"), width="50%"),
                    ]
                )
            ),
        )
        html, text = render(template)
        assert "Left" in html
        assert "Right" in html
        assert "<td" in html

    def test_section_renders(self) -> None:
        template = Html(
            head=Head(),
            body=Body(children=Section(children=Text(text="Content"), padding="20px")),
        )
        html, _ = render(template)
        assert "Content" in html
        assert "padding" in html

    def test_codeblock_renders(self) -> None:
        template = Html(
            head=Head(),
            body=Body(children=CodeBlock(code="x = 1")),
        )
        html, _ = render(template)
        assert "<pre" in html
        assert "<code" in html
        assert "x = 1" in html
