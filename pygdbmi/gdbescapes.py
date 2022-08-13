"""
Support for unescaping strings produced by GDB MI.
"""

import re
from typing import Iterator, Tuple


__all__ = [
    "advance_past_string_with_gdb_escapes",
    "unescape",
]


def unescape(escaped_str: str) -> str:
    """Unescape a string escaped by GDB in MI mode.

    Args:
        escaped_str: String to unescape (without initial and final double quote).

    Returns:
        The strings with escape codes transformed into normal characters.
    """
    unescaped_str, after_string_index = _unescape_internal(
        escaped_str, expect_closing_quote=False
    )
    assert after_string_index == -1, (
        f"after_string_index is {after_string_index} but it was "
        "expected to be -1 as expect_closing_quote is set to False"
    )
    return unescaped_str


def advance_past_string_with_gdb_escapes(
    escaped_str: str, *, start: int = 0
) -> Tuple[str, int]:
    """Unescape a string escaped by GDB in MI mode, and find the double quote
    terminating it.

    Args:
        escaped_str: String to unescape (without initial double quote).
        start: the position in escaped_str at which to start unescaping the string

    Returns:
        A tuple containing the unescaped string and the index in escaped_str just after
        the escape string (that is, escaped_str[start-1] is always the closing double
        quote and escaped_str[start:] is the portion of escaped_str after the escaped
        string).
    """
    return _unescape_internal(escaped_str, expect_closing_quote=True, start=start)


# Regular expression matching both escapes and unescaped quotes in GDB MI escaped
# strings.
_ESCAPES_RE = re.compile(
    r"""
    # Match all text before an escape or quote so it can be preserved as is.
    (?P<before>
        .*?
    )
    # Match either an escape or an unescaped quote.
    (
        (
            # All escapes start with a backslash...
            \\
            # ... and are followed by either a 3-digit octal number or a single
            # character for common escapes. See _GDB_MI_NON_OCTAL_ESCAPES for valid
            # ones.
            (
                # Instead of matching a single octal escape we match multiple ones in a
                # row.
                # This is because a single Unicode character can be encoded as multiple
                # escape sequences so, if we decoded the escape sequences one at a time,
                # the resulting string would not be valid until all the bytes are
                # converted.
                # This could also be solved by converting the input string into bytes
                # but that's much slower for long strings.
                (?P<escaped_octal>
                    # First octal number without backslash which we matched earlier.
                    [0-7]{3}
                    # Addional (and optional) octal numbers, including a backslash.
                    (
                        \\
                        [0-7]{3}
                    )*
                )
                |
                (?P<escaped_char>.)
            )
        )
        |
        # Match an unescaped quote.
        # If expect_closing_quote is true, then this means the string is finished.
        # If false, then the quote should have been escaped.
        (?P<unescaped_quote>")
    )
    """,
    flags=re.VERBOSE,
)

# Map from single character escape codes allowed in GDB MI strings to the corresponding
# unescaped value.
_NON_OCTAL_ESCAPES = {
    "'": "'",
    "\\": "\\",
    "a": "\a",
    "b": "\b",
    "e": "\033",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    '"': '"',
}


def _unescape_internal(
    escaped_str: str, *, expect_closing_quote: bool, start: int = 0
) -> Tuple[str, int]:
    """Common code for unescaping strings escaped by GDB in MI mode.

    MI-mode escapes are similar to standard Python escapes but:
    * "\\e" is a valid escape.
    * "\\NNN" escapes use numbers represented in octal format.
      For instance, "\\040" encodes character 0o40, that is character 32 in decimal,
      that is a space.

    For details, see printchar in gdb/utils.c in the binutils-gdb repo.

    Args:
        escaped_str: String to unescape
        expect_closing_quote: If true the closing quote must be in escaped_str[start:].
            Otherwise, no unescaped quote is allowed.
        start: the position in escaped_str at which to start unescaping the string.

    Returns:
        A tuple containing the unescaped string and the index in escaped_str just after
        the escape string, or -1 if expect_closing_quote is False.
    """
    # The _ESCAPES_RE expression only matches escapes or unescaped quotes, plus the
    # preeeding part of the escaped string.
    # This variable tracks the end of the last match so the portion of escaped_str after
    # that is not lost.
    unmatched_start_index = start

    # Was the closing quote found?
    # This can be true only if expect_closing_quote is true.
    found_closing_quote = False

    unescaped_parts = []
    for match in _ESCAPES_RE.finditer(escaped_str, pos=start):
        # Text before the match (and after any previous match).
        unescaped_parts.append(match["before"])

        escaped_octal = match["escaped_octal"]
        escaped_char = match["escaped_char"]
        unescaped_quote = match["unescaped_quote"]

        _, unmatched_start_index = match.span()

        if escaped_octal is not None:
            # We found one or more octal escapes. These are in the form "NNN" or, for
            # multiple characters in a row, "NNN\NNN\NNN[...]".
            # escaped_octal is guaranteed to be in the correct format by _ESCAPES_RE.
            octal_sequence_bytes = bytearray()
            # Strip the backslashes and iterate over the octal codes 3 by 3.
            for octal_number in _split_n_chars(escaped_octal.replace("\\", ""), 3):
                # Convert the 3 digits into a single byte.
                try:
                    octal_sequence_bytes.append(int(octal_number, base=8))
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid octal number {octal_number!r} in {escaped_str!r}"
                    ) from exc
            try:
                replaced = octal_sequence_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # GDB should never generate invalid sequences but, according to #64,
                # it can do that on Windows. In this case we just keep the sequence
                # unchanged.
                replaced = f"\\{escaped_octal}"

        elif escaped_char is not None:
            # We found a single escaped character.
            try:
                replaced = _NON_OCTAL_ESCAPES[escaped_char]
            except KeyError as exc:
                raise ValueError(
                    f"Invalid escape character {escaped_char!r} in {escaped_str!r}"
                ) from exc

        elif unescaped_quote:
            # We found an unescaped quote.
            if not expect_closing_quote:
                raise ValueError(f"Unescaped quote found in {escaped_str!r}")

            # This is the ending quote, so stop processing.
            found_closing_quote = True
            break

        else:
            raise AssertionError(
                f"This code should not be reached for string {escaped_str!r}"
            )

        unescaped_parts.append(replaced)

    if not found_closing_quote:
        if expect_closing_quote:
            raise ValueError(f"Missing closing quote in {escaped_str!r}")

        # Don't drop the part of the escaped string after the last escape.
        unescaped_parts.append(escaped_str[unmatched_start_index:])
        # With expect_closing_quote being false, the whole string must always be matched
        # so unmatched_start_index is not useful so we set it to -1.
        # (We could set it to len(unmatched_start_index) as well but we would not get
        # any benefit from having it set to a correct value.)
        unmatched_start_index = -1

    return "".join(unescaped_parts), unmatched_start_index


def _split_n_chars(s: str, n: int) -> Iterator[str]:
    """Iterates over string s `n` characters at a time"""
    for i in range(0, len(s), n):
        yield s[i : i + n]
