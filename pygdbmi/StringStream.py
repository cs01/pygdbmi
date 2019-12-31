import logging
from typing import List
import traceback
import sys


from pygdbmi.constants import GDB_ESCAPE_CHAR, GDB_MI_CHAR_STRING_START

logger = logging.getLogger(__name__)


class StringStream:
    """A simple class to hold text so that when passed
    between functions, the object is passed by reference
    and memory does not need to be repeatedly allocated for the string.

    This class was written here to avoid adding a dependency
    to the project.
    """

    stream_end = ""

    def __init__(self, raw_text: str):
        self.raw_text = raw_text  # type: str
        self.index = 0  # type: int
        self.len = len(raw_text)  # type: int

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
        """Return substring that was advanced past

        Advances past string until encountering one of chars.
        """
        start_index = self.index
        while True:
            c = self.read(1)
            if c in chars:
                break
            elif c == StringStream.stream_end:
                break
        return self.raw_text[start_index : self.index - 1]

    def advance_past_string_with_gdb_escapes(self) -> str:
        """Return substring that was advanced past while checking for
        gdb escaped characters
        """

        buf = ""
        c = self.read(1)

        if c != GDB_MI_CHAR_STRING_START:
            logger.error("Unexpected character %s at start (expected '\"'", c)
            return buf

        while True:
            c = self.read(1)

            if c == GDB_ESCAPE_CHAR:
                # Skip this char, but store the next (escaped) char
                # which is probably something special like a '"' or a '['
                c2 = self.read(1)
                buf += c2
            elif c == '"':
                # Quote is closed. Exit (and don't include the end quote).
                break
            elif c == StringStream.stream_end:
                print("bad", self.raw_text)
                # try:
                #     raise ValueError("Unexpected end of stream")
                # except Exception:
                #     # print(traceback.format_exc())
                #     # or
                #     # print(sys.exc_info()[0])
                #     logger.error("", exc_info=True)
                break
            else:
                buf += c
        print("good?", self.raw_text)
        return buf

    def remove_gdb_escapes(self) -> str:
        buf = ""
        c = self.read(1)
        while c:
            if c == GDB_ESCAPE_CHAR:
                c2 = self.read(1)
                buf += c2
            else:
                buf += c
            c = self.read(1)
        return buf
