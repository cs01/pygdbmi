"""
Python parser for gdb's machine interface interpreter.

Parses string output from gdb with the "--interpreter=mi2" flag into
structured objects.

See more at https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html#GDB_002fMI

"""


import re
from pygdbmi.printcolor import print_cyan, print_red, print_green
from pprint import pprint


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
    if _GDB_MI_NOTIFY_RE.match(gdb_mi_text):
        token, message, payload = _get_notify_msg_and_payload(gdb_mi_text)
        return {'type': 'notify',
                'message': message,
                'payload': payload,
                'token'  : token}

    elif _GDB_MI_RESULT_RE.match(gdb_mi_text):
        token, message, payload = _get_result_msg_and_paylod(gdb_mi_text)
        return {'type': 'result',
                'message': message,
                'payload': payload,
                'token'  : token}

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
        print ('Got')
        pprint(actual_char_or_str)
        raise ValueError()


# ========================================================================
# All functions and variables below are used internally to parse mi output
# ========================================================================


# Print text to console as it's being parsed to help debug
_DEBUG = False

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


def _get_notify_msg_and_payload(result):
    """Get notify message and payload dict"""
    groups = _GDB_MI_NOTIFY_RE.match(result).groups()
    token  = int(groups[0]) if groups[0] != '' else None
    message = groups[1].strip()
    result_of_status = groups[2].strip()
    _, payload = _parse_dict(result_of_status)
    return token, message, payload


def _get_result_msg_and_paylod(result):
    """Get result message and payload dict"""
    groups = _GDB_MI_RESULT_RE.match(result).groups()
    token  = int(groups[0]) if groups[0] != '' else None
    message = groups[1]
    if groups[2] is None:
        payload = None
    else:
        str_to_parse = groups[2].strip()
        i, payload = _parse_dict(str_to_parse)
    return token, message, payload


def _parse_dict(to_parse):
    """Parse dictionary, with optional starting character '{'
    return (tuple):
        Number of characters parsed from to_parse
        Parsed dictionary
    """
    if _DEBUG:
        print_red('obj')
        print_red(to_parse)
    i = 0
    obj = {}
    while i < len(to_parse):
        c = to_parse[i]
        if c in _WHITESPACE:
            pass
        elif c in ['{', ',']:
            pass
        elif c == '}':
            # end of object, exit loop
            break
        else:
            chars_used, key, val = _parse_key_val(to_parse[i:])
            i = i + chars_used
            obj[key] = val
        i += 1
    if _DEBUG:
        print_green(obj)
    return i, obj


def _parse_key_val(to_parse):
    """Parse key, value combination
    return (tuple):
        Number of characters parsed from to_parse
        Parsed key (string)
        Parsed value (either a string, array, or dict)
    """
    if _DEBUG:
        print_red('keyval')
        print_red(to_parse)

    i = 0
    size, key = _parse_key(to_parse[i:])
    i += size
    size, val = _parse_val(to_parse[i:])
    i += size
    if _DEBUG:
        print_green(key)
        print_green(val)
    return i, key, val


def _parse_key(to_parse):
    """Parse key, value combination
    return (tuple):
        Number of characters parsed from to_parse
        Parsed key (string)
    """
    if _DEBUG:
        print_red('key')
        print_red(to_parse)

    buf = ''
    i = 0
    key = ''
    while i < len(to_parse) - 1:
        c = to_parse[i]
        if c == '=':
            key = buf
            # consume '=' sign so caller doesn't get it again
            i += 1
            break
        buf += c
        i += 1
    if _DEBUG:
        print_green(key)
    return i, key


def _parse_val(to_parse):
    """Parse value from string
    return (tuple):
        Number of characters parsed from to_parse
        Parsed value (either a string, array, or dict)
    """
    if _DEBUG:
        print_red('val')
        print_red(to_parse)

    i = 0
    val = ''
    buf = ''
    while i < len(to_parse) - 1:
        c = to_parse[i]

        if c == '{':
            # Start object
            size, val = _parse_dict(to_parse[i:])
            i += size
            break
        elif c == '[':
            # Start of an array
            size, val = _parse_array(to_parse[i:])
            i += size
            break
        elif c == '"':
            # Start of a string
            size, val = _parse_str(to_parse[i:])
            i += size
            break
        else:
            buf += c
        i += 1

    if _DEBUG:
        print_green(val)
    return i, val


def _parse_array(to_parse):
    """Parse an array
    return (tuple):
        Number of characters parsed from to_parse
        Parsed array
    """
    if _DEBUG:
        print_red('array')
        print_red(to_parse)

    assert_match(_GDB_MI_CHAR_ARRAY_START, to_parse[0])

    # Skip first open bracket so we don't end up in an
    # endless loop trying to re-parse the array
    i = 1

    arr = []
    while i < len(to_parse) - 1:
        c = to_parse[i]

        if c in _GDB_MI_VALUE_START_CHARS:
            size, val = _parse_val(to_parse[i:])
            arr.append(val)
            i += size
        elif c in _WHITESPACE:
            pass
        elif c == ',':
            pass
        elif c == ']':
            # Stop when this array has finished. Note
            # that elements of this array can be also be arrays.
            break
        i += 1
    if _DEBUG:
        print_green(arr)
    return i, arr


def _parse_str(to_parse):
    """Parse a string
    return (tuple):
        Number of characters parsed from to_parse
        Parsed string, without surrounding quotes
    """

    # characters that gdb escapes that should not be
    # escaped by this parser
    CHARS_TO_REMOVE_GDB_ESCAPE = ['"']

    if _DEBUG:
        print_red('string')
        print_red(to_parse)

    assert_match(_GDB_MI_CHAR_STRING_START, to_parse[0])
    i = 1  # Skip the opening quote
    buf = ''
    while i < len(to_parse) - 1:
        c = to_parse[i]
        if _DEBUG:
            print_cyan(c)

        if c == '\\' and i < (len(to_parse) - 1):
            # We are on a backslash and there is another character after the backslash
            # to parse. Handle this case specially since gdb escaped it for us

            # Get the next char that is being escaped
            c2 = to_parse[i + 1]
            if c2 in CHARS_TO_REMOVE_GDB_ESCAPE:
                # only store the escaped character in the buffer; don't store the backslash
                # (don't leave it escaped)
                buf += to_parse[i + 1]
            else:
                # store the backslash and the following character in the buffer (leave it escaped)
                buf += c + to_parse[i + 1]

            # consume the backslash and the next character
            i += 2

        else:
            # Quote is closed. Exit (and don't include the end quote).
            if c == '"':
                break
            buf += c
            i += 1

    string = buf
    if _DEBUG:
        print_green(string)
    return i, string
