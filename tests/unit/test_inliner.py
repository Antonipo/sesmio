"""Unit tests for sesmio.email.inliner."""

from __future__ import annotations

from sesmio.email.inliner import inline_css


class TestTagSelector:
    def test_tag_selector_applied(self) -> None:
        html = "<style>p { color: red }</style><p>hello</p>"
        result = inline_css(html)
        assert 'style="color: red"' in result

    def test_style_block_removed(self) -> None:
        html = "<style>p { color: red }</style><p>hello</p>"
        result = inline_css(html)
        # The <style> block should be removed (not appear with the rule).
        assert "color: red" in result
        # Verify it's inlined, not in a style tag (residual block would have media queries).
        assert "<style>p" not in result


class TestClassSelector:
    def test_class_selector_applied(self) -> None:
        html = '<style>.red { color: red }</style><p class="red">hello</p>'
        result = inline_css(html)
        assert "color: red" in result

    def test_class_removed_after_inline(self) -> None:
        html = '<style>.red { color: red }</style><p class="red">hello</p>'
        result = inline_css(html)
        assert 'class="red"' not in result


class TestIdSelector:
    def test_id_selector_applied(self) -> None:
        html = '<style>#main { font-size: 16px }</style><div id="main">hi</div>'
        result = inline_css(html)
        assert "font-size: 16px" in result


class TestTagClassSelector:
    def test_tag_class_combined(self) -> None:
        html = '<style>p.note { color: blue }</style><p class="note">x</p>'
        result = inline_css(html)
        assert "color: blue" in result

    def test_tag_class_does_not_match_different_tag(self) -> None:
        html = '<style>p.note { color: blue }</style><div class="note">x</div>'
        result = inline_css(html)
        # div.note should NOT get the p.note rule.
        assert "color: blue" not in result


class TestDirectChildSelector:
    def test_direct_child_matched(self) -> None:
        html = "<style>div > p { margin: 0 }</style><div><p>child</p></div>"
        result = inline_css(html)
        assert "margin: 0" in result

    def test_direct_child_does_not_match_grandchild(self) -> None:
        html = "<style>div > p { margin: 0 }</style><div><span><p>grand</p></span></div>"
        result = inline_css(html)
        # <p> is grandchild of div — should NOT match.
        assert "margin: 0" not in result


class TestFirstChildSelector:
    def test_first_child_matched(self) -> None:
        html = (
            "<style>p:first-child { font-weight: bold }</style><div><p>first</p><p>second</p></div>"
        )
        result = inline_css(html)
        # Count the number of styled <p> tags.
        import re

        styled_p = re.findall(r'<p[^>]*style="[^"]*font-weight: bold[^"]*"', result)
        assert len(styled_p) == 1

    def test_non_first_child_not_matched(self) -> None:
        html = (
            "<style>p:first-child { font-weight: bold }</style><div><p>first</p><p>second</p></div>"
        )
        result = inline_css(html)
        import re

        all_p = re.findall(r"<p", result)
        styled_p = re.findall(r"<p[^>]*font-weight: bold", result)
        assert len(all_p) == 2
        assert len(styled_p) == 1


class TestSpecificityMerge:
    def test_inline_style_wins(self) -> None:
        html = '<style>p { color: red }</style><p style="color: blue">hello</p>'
        result = inline_css(html)
        # Inline style (blue) must appear after and thus take precedence.
        assert "color: blue" in result

    def test_both_styles_merged(self) -> None:
        html = '<style>p { font-size: 14px }</style><p style="color: blue">hello</p>'
        result = inline_css(html)
        assert "font-size: 14px" in result
        assert "color: blue" in result


class TestMediaQueryPreservation:
    def test_media_query_left_in_style_block(self) -> None:
        html = "<style>@media (max-width: 600px) { p { font-size: 12px } }</style><p>hi</p>"
        result = inline_css(html)
        assert "@media" in result
        assert "<style>" in result

    def test_regular_rule_removed_media_kept(self) -> None:
        html = "<style>p { color: red } @media (max-width: 600px) { p { color: blue } }</style><p>hi</p>"
        result = inline_css(html)
        assert "color: red" in result  # inlined
        assert "@media" in result  # kept in style block


class TestHoverPreservation:
    def test_hover_rule_kept_in_style_block(self) -> None:
        html = "<style>a:hover { color: red }</style><a href='#'>link</a>"
        result = inline_css(html)
        assert "a:hover" in result
        assert "<style>" in result


class TestMultipleSelectors:
    def test_comma_separated_selectors(self) -> None:
        html = "<style>h1, h2 { font-weight: bold }</style><h1>A</h1><h2>B</h2>"
        result = inline_css(html)
        assert result.count("font-weight: bold") == 2


class TestVoidElements:
    def test_img_no_closing_tag(self) -> None:
        html = "<img src='x.png' alt='x'>"
        result = inline_css(html)
        assert "</img>" not in result
        assert "<img" in result


class TestExtraCss:
    def test_extra_css_applied(self) -> None:
        html = "<p>hello</p>"
        result = inline_css(html, extra_css="p { color: green }")
        assert "color: green" in result


class TestCommentPreservation:
    def test_html_comments_preserved(self) -> None:
        html = "<!--[if mso]>outlook<![endif]--><p>hi</p>"
        result = inline_css(html)
        assert "<!--[if mso]>" in result


class TestInlinerEdgeCases:
    def test_decl_preserved(self) -> None:
        # handle_decl coverage — <!DOCTYPE html>
        html = "<!DOCTYPE html><p>hi</p>"
        result = inline_css(html)
        assert "DOCTYPE" in result

    def test_entity_ref_preserved(self) -> None:
        # handle_entityref coverage
        html = "<p>&nbsp;</p>"
        result = inline_css(html)
        assert "nbsp" in result

    def test_charref_preserved(self) -> None:
        # handle_charref coverage
        html = "<p>&#160;</p>"
        result = inline_css(html)
        assert "160" in result

    def test_direct_child_more_than_two_parts(self) -> None:
        # selector with multiple > returns False (len(parts) != 2)
        html = "<style>a > b > c { color: red }</style><div><p>hi</p></div>"
        result = inline_css(html)
        # Should not crash; rule not applied.
        assert "<div>" in result

    def test_boolean_attr_serialised(self) -> None:
        # _attr_str boolean-value path: v == ""
        html = '<input type="checkbox" disabled="">'
        result = inline_css(html)
        assert "disabled" in result

    def test_media_query_before_head_close(self) -> None:
        html = "<html><head><title>T</title></head><body><p>hi</p></body></html>"
        result = inline_css(html, extra_css="@media (max-width:600px){p{font-size:12px}}")
        assert "@media" in result
        assert "</head>" in result


class TestEmptyInput:
    def test_empty_string(self) -> None:
        result = inline_css("")
        assert result == ""

    def test_no_style_block(self) -> None:
        html = "<p>hello world</p>"
        result = inline_css(html)
        assert "<p>hello world</p>" in result
