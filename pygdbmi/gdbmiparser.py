"""
Python parser for gdb's machine interface interpreter.

Parses string output from gdb with the "--interpreter=mi2" flag into
structured objects.

See more at https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html#GDB_002fMI

"""

import re
from pygdbmi.printcolor import print_cyan, print_green
from pprint import pprint

# Print text to console as it's being parsed to help debug
_DEBUG = False


class StringStream:
    def __init__(self, data):
        self.data = data
        self.index = 0
        self.len = len(data)

    def read(self, count):
        newIndex = self.index + count
        char = None
        if newIndex > self.len:
            char = ''
        elif count == 1:
            char = self.data[self.index]
        else:
            char = self.data[self.index:newIndex]
        self.index = newIndex

        return char

    def seek(self, offset):
        self.index = self.index + offset

    def advance_to_after(self, char):
        return self.advance_to_after_any([char])

    def advance_to_after_any(self, chars):
        start_index = self.index
        while True:
            chunk = self.data[self.index]
            self.index += 1
            if chunk in chars:
                break
            elif self.index == self.len:
                break
        return self.data[start_index:self.index - 1]

    def advance_to_after_with_gdb_escapes(self, char):
        # characters that gdb escapes that should not be
        # escaped by this parser
        CHARS_TO_REMOVE_GDB_ESCAPE = ['"']

        buf = ''
        while True:
            c = self.data[self.index]
            self.index += 1
            if _DEBUG:
                print_cyan(c)

            if c == '\\':
                # We are on a backslash and there is another character after the backslash
                # to parse. Handle this case specially since gdb escaped it for us

                # Get the next char that is being escaped
                c2 = self.data[self.index]
                self.index += 1
                if c2 in CHARS_TO_REMOVE_GDB_ESCAPE:
                    # only store the escaped character in the buffer; don't store the backslash
                    # (don't leave it escaped)
                    buf += c2
                else:
                    # store the backslash and the following character in the buffer (leave it escaped)
                    buf += c + c2
            else:
                # Quote is closed. Exit (and don't include the end quote).
                if c == '"':
                    break
                buf += c
        return buf


def parse_response(gdb_mi_text):
    """Parse gdb mi text and turn it into a dictionary.

    See https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
    for details on types of gdb mi output.

    Args:
        gdb_mi_text (str): String output from gdb

    Returns:
        dict with the following keys:
        type (either 'notify', 'result', 'console', 'log', 'target', 'done'),
        message (str or None),
        payload (str, list, dict, or None)
    """
    stream = StringStream(gdb_mi_text)

    if _GDB_MI_NOTIFY_RE.match(gdb_mi_text):
        token, message, payload = _get_notify_msg_and_payload(gdb_mi_text, stream)
        return {'type': 'notify',
                'message': message,
                'payload': payload,
                'token': token}

    elif _GDB_MI_RESULT_RE.match(gdb_mi_text):
        token, message, payload = _get_result_msg_and_paylod(gdb_mi_text, stream)
        return {'type': 'result',
                'message': message,
                'payload': payload,
                'token': token}

    elif _GDB_MI_CONSOLE_RE.match(gdb_mi_text):
        return {'type': 'console',
                'message': None,
                'payload': _GDB_MI_CONSOLE_RE.match(gdb_mi_text).groups()[0]}

    elif _GDB_MI_LOG_RE.match(gdb_mi_text):
        return {'type': 'log',
                'message': None,
                'payload': _GDB_MI_LOG_RE.match(gdb_mi_text).groups()[0]}

    elif _GDB_MI_TARGET_OUTPUT_RE.match(gdb_mi_text):
        return {'type': 'target',
                'message': None,
                'payload': _GDB_MI_TARGET_OUTPUT_RE.match(gdb_mi_text).groups()[0]}

    elif response_is_finished(gdb_mi_text):
        return {'type': 'done',
                'message': None,
                'payload': None}

    else:
        # This was not gdb mi output, so it must have just been printed by
        # the inferior program that's being debugged
        return {'type': 'output',
                'message': None,
                'payload': gdb_mi_text}


def response_is_finished(gdb_mi_text):
    """Return true if the gdb mi response is ending
    Returns: True if gdb response is finished"""
    if _GDB_MI_RESPONSE_FINISHED_RE.match(gdb_mi_text):
        return True
    else:
        return False


def assert_match(actual_char_or_str, expected_char_or_str):
    """If values don't match, print them and raise a ValueError, otherwise,
    continue
    Raises: ValueError if argumetns do not match"""
    if expected_char_or_str != actual_char_or_str:
        print('Expected')
        pprint(expected_char_or_str)
        print('')
        print('Got')
        pprint(actual_char_or_str)
        raise ValueError()


# ========================================================================
# All functions and variables below are used internally to parse mi output
# ========================================================================


# GDB machine interface output patterns to match
# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Result-Records.html#GDB_002fMI-Result-Records
# In addition to a number of out-of-band notifications,
# the response to a gdb/mi command includes one of the following result indications:
# done, running, connected, error, exit
_GDB_MI_RESULT_RE = re.compile('^(\d*)\^(\S+?)(,(.*))?$')

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Async-Records.html#GDB_002fMI-Async-Records
# Async records are used to notify the gdb/mi client of additional
# changes that have occurred. Those changes can either be a consequence
# of gdb/mi commands (e.g., a breakpoint modified) or a result of target activity
# (e.g., target stopped).
_GDB_MI_NOTIFY_RE = re.compile('^(\d*)[*=](\S+?),(.*)$')

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
# "~" string-output
# The console output stream contains text that should be displayed
# in the CLI console window. It contains the textual responses to CLI commands.
_GDB_MI_CONSOLE_RE = re.compile('~"(.*)"', re.DOTALL)

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
# "&" string-output
# The log stream contains debugging messages being produced by gdb's internals.
_GDB_MI_LOG_RE = re.compile('&"(.*)"', re.DOTALL)

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
# "@" string-output
# The target output stream contains any textual output from the
# running target. This is only present when GDB's event loop is truly asynchronous,
# which is currently only the case for remote targets.
_GDB_MI_TARGET_OUTPUT_RE = re.compile('@"(.*)"', re.DOTALL)

# Response finished
_GDB_MI_RESPONSE_FINISHED_RE = re.compile('^\(gdb\)\s*$')

_WHITESPACE = [' ', '\t', '\r', '\n']

_GDB_MI_CHAR_DICT_START = '{'
_GDB_MI_CHAR_ARRAY_START = '['
_GDB_MI_CHAR_STRING_START = '"'
_GDB_MI_VALUE_START_CHARS = [_GDB_MI_CHAR_DICT_START, _GDB_MI_CHAR_ARRAY_START, _GDB_MI_CHAR_STRING_START]


def _get_notify_msg_and_payload(result, stream):
    """Get notify message and payload dict"""
    token = stream.advance_to_after_any(['=', '*'])
    token = int(token) if token != '' else None
    message = stream.advance_to_after(',')

    payload = _parse_dict(stream)
    return token, message.strip(), payload


def _get_result_msg_and_paylod(result, stream):
    """Get result message and payload dict"""

    groups = _GDB_MI_RESULT_RE.match(result).groups()
    token = int(groups[0]) if groups[0] != '' else None
    message = groups[1]

    if groups[2] is None:
        payload = None
    else:
        stream.advance_to_after(',')
        payload = _parse_dict(stream)

    return token, message, payload


def _parse_dict(stream):
    """Parse dictionary, with optional starting character '{'
    return (tuple):
        Number of characters parsed from to_parse
        Parsed dictionary
    """
    obj = {}

    while True:
        c = stream.read(1)
        if c in _WHITESPACE:
            pass
        elif c in ['{', ',']:
            pass
        elif c in ['}', '']:
            # end of object, exit loop
            break
        else:
            stream.seek(-1)
            key, val = _parse_key_val(stream)
            if key in obj:
                # This is a gdb bug. We should never get repeated keys in a dict!
                # See https://sourceware.org/bugzilla/show_bug.cgi?id=22217
                # and https://github.com/cs01/pygdbmi/issues/19
                # Example:
                #   thread-ids={thread-id="1",thread-id="2"}
                # Results in:
                #   thread-ids: {{'thread-id': ['1', '2']}}
                # Rather than the lossy
                #   thread-ids: {'thread-id': 2}  # '1' got overwritten!
                if isinstance(obj[key], list):
                    obj[key].append(val)
                else:
                    obj[key] = [obj[key], val]
            else:
                obj[key] = val

    if _DEBUG:
        print_green(obj)
    return obj


def _parse_key_val(stream):
    """Parse key, value combination
    return (tuple):
        Parsed key (string)
        Parsed value (either a string, array, or dict)
    """

    key = _parse_key(stream)
    val = _parse_val(stream)

    if _DEBUG:
        print_green(key)
        print_green(val)
    return key, val


def _parse_key(stream):
    """Parse key, value combination
    returns :
        Parsed key (string)
    """
    key = stream.advance_to_after('=')
    if _DEBUG:
        print_green(key)
    return key


def _parse_val(stream):
    """Parse value from string
    returns:
        Parsed value (either a string, array, or dict)
    """

    while True:
        c = stream.read(1)

        if c == '{':
            # Start object
            val = _parse_dict(stream)
            break
        elif c == '[':
            # Start of an array
            val = _parse_array(stream)
            break
        elif c == '"':
            # Start of a string
            val = stream.advance_to_after_with_gdb_escapes('"')
            break
        else:
            raise ValueError()

    if _DEBUG:
        print_green(val)

    return val


def _parse_array(stream):
    """Parse an array, stream should be passed the initial [
    returns:
        Parsed array
    """

    arr = []
    while True:
        c = stream.read(1)

        if c in _GDB_MI_VALUE_START_CHARS:
            stream.seek(-1)
            val = _parse_val(stream)
            arr.append(val)
        elif c in _WHITESPACE:
            pass
        elif c == ',':
            pass
        elif c == ']':
            # Stop when this array has finished. Note
            # that elements of this array can be also be arrays.
            break

    if _DEBUG:
        print_green(arr)
    return arr
