from typing import List

from pygdbmi.gdbescapes import advance_past_string_with_gdb_escapes


__all__ = ["StringStream"]


class StringStream:
    """A simple class to hold text so that when passed
    between functions, the object is passed by reference
    and memory does not need to be repeatedly allocated for the string.

    This class was written here to avoid adding a dependency
    to the project.
    """

    def __init__(self, raw_text: str, debug: bool = False) -> None:
        self.raw_text = raw_text
        self.index = 0
        self.len = len(raw_text)

    def read(self, count: int) -> str:
        """Read count characters starting at self.index,
        and return those characters as a string
        """
        new_index = self.index + count
        if new_index > self.len:
            buf = self.raw_text[self.index :]  # return to the end, don't fail
        else:
            buf = self.raw_text[self.index : new_index]
        self.index = new_index

        return buf

    def seek(self, offset: int) -> None:
        """Advance the index of this StringStream by offset characters"""
        self.index = self.index + offset

    def advance_past_chars(self, chars: List[str]) -> str:
        """Advance the index past specific chars
        Args chars (list): list of characters to advance past

        Return substring that was advanced past
        """
        start_index = self.index
        while True:
            current_char = self.raw_text[self.index]
            self.index += 1
            if current_char in chars:
                break

            elif self.index == self.len:
                break

        return self.raw_text[start_index : self.index - 1]

    def advance_past_string_with_gdb_escapes(self) -> str:
        """Advance the index past a quoted string until the end quote is reached, and
        return the string (after unescaping it)

        Must be called only after encountering a quote character.
        """
        assert self.index > 0 and self.raw_text[self.index - 1] == '"', (
            "advance_past_string_with_gdb_escapes called not at the start of a string "
            f"(at index {self.index} of text {self.raw_text!r}, "
            f"remaining string {self.raw_text[self.index:]!r})"
        )

        unescaped_str, self.index = advance_past_string_with_gdb_escapes(
            self.raw_text, start=self.index
        )
        return unescaped_str
