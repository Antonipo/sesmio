"""Unit tests for sesmio.email.tailwind."""

from __future__ import annotations

from sesmio.email.tailwind import TAILWIND_MAP, resolve_classes


class TestTailwindMap:
    def test_map_is_dict(self) -> None:
        assert isinstance(TAILWIND_MAP, dict)

    def test_has_sufficient_entries(self) -> None:
        # The spec requires ~250 classes.
        assert len(TAILWIND_MAP) >= 200

    def test_spacing_p4(self) -> None:
        assert "padding" in TAILWIND_MAP["p-4"]

    def test_spacing_px_6(self) -> None:
        assert "padding-left" in TAILWIND_MAP["px-6"]
        assert "padding-right" in TAILWIND_MAP["px-6"]

    def test_spacing_py_4(self) -> None:
        assert "padding-top" in TAILWIND_MAP["py-4"]
        assert "padding-bottom" in TAILWIND_MAP["py-4"]

    def test_spacing_m_4(self) -> None:
        assert "margin" in TAILWIND_MAP["m-4"]

    def test_spacing_mx_auto(self) -> None:
        assert "auto" in TAILWIND_MAP["mx-auto"]

    def test_typography_text_2xl(self) -> None:
        assert "1.5rem" in TAILWIND_MAP["text-2xl"]

    def test_typography_font_bold(self) -> None:
        assert "700" in TAILWIND_MAP["font-bold"]

    def test_typography_italic(self) -> None:
        assert "italic" in TAILWIND_MAP["italic"]

    def test_typography_text_center(self) -> None:
        assert "center" in TAILWIND_MAP["text-center"]

    def test_sizing_w_full(self) -> None:
        assert "100%" in TAILWIND_MAP["w-full"]

    def test_sizing_max_w_lg(self) -> None:
        assert "32rem" in TAILWIND_MAP["max-w-lg"]

    def test_color_text_gray_900(self) -> None:
        assert "#111827" in TAILWIND_MAP["text-gray-900"]

    def test_color_bg_white(self) -> None:
        assert "#ffffff" in TAILWIND_MAP["bg-white"]

    def test_color_bg_gray_100(self) -> None:
        assert TAILWIND_MAP["bg-gray-100"]

    def test_color_text_blue_500(self) -> None:
        assert TAILWIND_MAP["text-blue-500"]

    def test_border_rounded_md(self) -> None:
        assert "0.375rem" in TAILWIND_MAP["rounded-md"]

    def test_border_rounded_full(self) -> None:
        assert "9999px" in TAILWIND_MAP["rounded-full"]

    def test_shadow_md(self) -> None:
        assert "box-shadow" in TAILWIND_MAP["shadow-md"]

    def test_layout_hidden(self) -> None:
        assert "none" in TAILWIND_MAP["hidden"]

    def test_layout_block(self) -> None:
        assert "block" in TAILWIND_MAP["block"]

    def test_slate_color(self) -> None:
        assert "text-slate-700" in TAILWIND_MAP

    def test_all_spacing_scales(self) -> None:
        for scale in ["0", "1", "2", "3", "4", "5", "6", "8", "10", "12", "16"]:
            assert f"p-{scale}" in TAILWIND_MAP, f"p-{scale} missing"

    def test_leading_tight(self) -> None:
        assert "1.25" in TAILWIND_MAP["leading-tight"]

    def test_tracking_wide(self) -> None:
        assert "0.05em" in TAILWIND_MAP["tracking-wide"]


class TestResolveClasses:
    def test_single_class(self) -> None:
        result = resolve_classes("p-4")
        assert "padding" in result

    def test_multiple_classes_joined(self) -> None:
        result = resolve_classes("p-4 m-2")
        assert "padding" in result
        assert "margin" in result

    def test_unknown_class_ignored(self) -> None:
        # Should not raise; unknown classes are silently dropped.
        result = resolve_classes("p-4 this-does-not-exist")
        assert "padding" in result
        assert "does-not-exist" not in result

    def test_empty_string(self) -> None:
        result = resolve_classes("")
        assert result == ""

    def test_only_unknown_classes(self) -> None:
        result = resolve_classes("xyz-999 abc-def")
        assert result == ""

    def test_output_is_semicolon_separated(self) -> None:
        result = resolve_classes("p-4 font-bold")
        # Both classes resolved; output should contain semicolons joining them.
        assert ";" in result

    def test_resolve_bg_white(self) -> None:
        result = resolve_classes("bg-white")
        assert "#ffffff" in result

    def test_resolve_text_gray_900(self) -> None:
        result = resolve_classes("text-gray-900")
        assert "#111827" in result

    def test_resolve_max_w_lg_mx_auto(self) -> None:
        result = resolve_classes("max-w-lg mx-auto")
        assert "32rem" in result
        assert "auto" in result

    def test_whitespace_only_string(self) -> None:
        result = resolve_classes("   ")
        assert result == ""
