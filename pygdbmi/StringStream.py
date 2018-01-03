from pygdbmi.printcolor import print_cyan


class StringStream:
    """A simple class to hold text so that when passed
    between functions, the object is passed by reference
    and memory does not need to be repeatedly allocated for the string.

    This class was written here to avoid adding a dependency
    to the project rather than using.
    """

    def __init__(self, raw_text, debug=False):
        self.raw_text = raw_text
        self.index = 0
        self.len = len(raw_text)
        self.debug = debug

    def read(self, count):
        """Read count characters starting at self.index,
        and return those characters as a string
        """
        new_index = self.index + count
        if new_index > self.len:
            buf = self.raw_text[self.index:]  # return to the end, don't fail
        else:
            buf = self.raw_text[self.index:new_index]
        self.index = new_index

        return buf

    def seek(self, offset):
        """Advance the index of this StringStream by offset characters"""
        self.index = self.index + offset

    def advance_past_chars(self, chars):
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
        return self.raw_text[start_index:self.index - 1]

    def advance_past_string_with_gdb_escapes(self, chars_to_remove_gdb_escape=['"']):
        """characters that gdb escapes that should not be
        escaped by this parser
        """

        buf = ''
        while True:
            c = self.raw_text[self.index]
            self.index += 1
            if self.debug:
                print_cyan(c)

            if c == '\\':
                # We are on a backslash and there is another character after the backslash
                # to parse. Handle this case specially since gdb escaped it for us

                # Get the next char that is being escaped
                c2 = self.raw_text[self.index]
                self.index += 1
                # only store the escaped character in the buffer; don't store the backslash
                # (don't leave it escaped)
                buf += c2

            elif c == '"':
                # Quote is closed. Exit (and don't include the end quote).
                break

            else:
                # capture this character, and keep capturing
                buf += c
        return buf
