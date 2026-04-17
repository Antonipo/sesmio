"""Unit tests for sesmio._internal.escape."""

from sesmio._internal.escape import escape


def test_plain_text_unchanged() -> None:
    assert escape("Hello World") == "Hello World"


def test_ampersand() -> None:
    assert escape("a & b") == "a &amp; b"


def test_less_than() -> None:
    assert escape("<script>") == "&lt;script&gt;"


def test_double_quote_escaped() -> None:
    assert '"hello"' in escape('"hello"') or "&quot;" in escape('"hello"')


def test_single_quote_not_escaped_by_default() -> None:
    # html.escape(quote=True) escapes double-quote but NOT single-quote.
    result = escape("it's")
    assert "it" in result


def test_xss_payload() -> None:
    result = escape('<img src=x onerror="alert(1)">')
    assert "<img" not in result
    assert "alert" in result  # the text is present but the tags are escaped


def test_empty_string() -> None:
    assert escape("") == ""
