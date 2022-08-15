import re
from typing import Optional

import pytest

from pygdbmi.gdbescapes import advance_past_string_with_gdb_escapes, unescape


# Split a Unicode character into its UTF-8 bytes and encode each one as a 3-digit
# oct char prefixed with a "\".
# This is the opposite of what the gdbescapes module does.
GDB_ESCAPED_PIZZA = "".join(rf"\{c:03o}" for c in "\N{SLICE OF PIZZA}".encode("utf-8"))
# Similar but for a simple space.
# This character was chosen because, in octal, it's shorter than three digits, so we
# can check that unescape_gdb_mi_string handles the initial `0` correctly.
# Note that a space would usually not be escaped by GDB itself, but it's fine if it
# is.
GDB_ESCAPED_SPACE = rf"\{ord(' '):03o}"


@pytest.mark.parametrize(
    "input_str, expected",
    [
        (r"a", "a"),
        (r"hello world", "hello world"),
        (r"hello\nworld", "hello\nworld"),
        (r"quote: <\">", 'quote: <">'),
        # UTF-8 text encoded as a sequence of octal characters.
        (GDB_ESCAPED_PIZZA, "\N{SLICE OF PIZZA}"),
        # Similar but for a simple space.
        (GDB_ESCAPED_SPACE, " "),
        # Several escapes in the same string.
        (
            (
                rf"\tmultiple\nescapes\tin\"the\'same\"string\"foo"
                rf"{GDB_ESCAPED_SPACE}bar{GDB_ESCAPED_PIZZA}"
            ),
            '\tmultiple\nescapes\tin"the\'same"string"foo bar\N{SLICE OF PIZZA}',
        ),
        # An octal sequence that is not valid UTF-8 doesn't get changes, see #64.
        (r"254 '\376'", r"254 '\376'"),
    ],
)
def test_unescape(input_str: str, expected: str) -> None:
    """Test the unescape function"""
    assert unescape(input_str) == expected


@pytest.mark.parametrize(
    "input_str, exc_message",
    [
        (r'"', "Unescaped quote found"),
        (r'"x', "Unescaped quote found"),
        (r'a"', "Unescaped quote found"),
        (r'a"x', "Unescaped quote found"),
        (r'a"x"foo', "Unescaped quote found"),
        (r"\777", "Invalid octal number"),
        (r"\400", "Invalid octal number"),
        (r"\X", "Invalid escape character"),
        (r"\1", "Invalid escape character"),
        (r"\11", "Invalid escape character"),
    ],
)
def test_bad_string(input_str: str, exc_message: str) -> None:
    """Test the unescape function with invalid inputs"""
    with pytest.raises(ValueError, match=re.escape(exc_message)):
        unescape(input_str)


@pytest.mark.parametrize(
    "input_escaped_str, expected_unescaped_str, expected_after_str, start",
    [
        (r'a"', "a", "", None),
        (r'a"bc', "a", "bc", None),
        (r'"a"', "a", "", 1),
        (r'"a"bc', "a", "bc", 1),
        (r'x="a"', "a", "", 3),
        (r'x="a"bc', "a", "bc", 3),
        # Escaped quotes.
        (r'\""', '"', "", None),
        (r'"\""', '"', "", 1),
        (r'"\"",foo', '"', ",foo", 1),
        (r'x="\""', '"', "", 3),
        (r'"\"hello\"world\""', '"hello"world"', "", 1),
        # Other escapes.
        (r'\n"', "\n", "", None),
        (r'"\n"', "\n", "", 1),
        (r'"\n",foo', "\n", ",foo", 1),
        (r'x="\n"', "\n", "", 3),
        (r'"\nhello\nworld\n"', "\nhello\nworld\n", "", 1),
        (
            rf'"I want a {GDB_ESCAPED_PIZZA}"something else',
            "I want a \N{SLICE OF PIZZA}",
            "something else",
            1,
        ),
    ],
)
def test_advance_past_string_with_gdb_escapes(
    input_escaped_str: str,
    expected_unescaped_str: str,
    expected_after_str: str,
    start: Optional[int],
) -> None:
    """Test the advance_past_string_with_gdb_escapes function"""
    kwargs = {}
    if start is not None:
        kwargs["start"] = start

    actual_unescaped_str, after_quote_index = advance_past_string_with_gdb_escapes(
        input_escaped_str, **kwargs
    )
    assert actual_unescaped_str == expected_unescaped_str
    actual_after_str = input_escaped_str[after_quote_index:]
    assert actual_after_str == expected_after_str


@pytest.mark.parametrize(
    "input_str",
    [
        r"",
        r"\"",
        r"a\"",
        r"\"a",
        r"a",
        r"a\"b",
    ],
)
def test_advance_past_string_with_gdb_escapes_raises(input_str: str) -> None:
    """Test the advance_past_string_with_gdb_escapes function with invalid input"""
    with pytest.raises(ValueError, match=r"Missing closing quote"):
        advance_past_string_with_gdb_escapes(input_str)
