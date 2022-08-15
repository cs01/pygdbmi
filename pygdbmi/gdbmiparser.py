"""
Python parser for gdb's machine interface interpreter.

Parses string output from gdb with the `--interpreter=mi2` flag into
structured objects.

See more at https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html#GDB_002fMI
"""

import functools
import logging
import re
from typing import Any, Callable, Dict, List, Match, Optional, Pattern, Tuple, Union

from pygdbmi.gdbescapes import unescape
from pygdbmi.printcolor import fmt_green
from pygdbmi.StringStream import StringStream


__all__ = [
    "parse_response",
    "response_is_finished",
]


_DEBUG = False
logger = logging.getLogger(__name__)


def _setup_logger(logger: logging.Logger, debug: bool) -> None:
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s")
    )
    if debug:
        level = logging.DEBUG
    else:
        level = logging.ERROR

    logger.setLevel(level)
    logger.addHandler(handler)


_setup_logger(logger, _DEBUG)


def parse_response(gdb_mi_text: str) -> Dict:
    """Parse gdb mi text and turn it into a dictionary.

    See https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
    for details on types of gdb mi output.

    Args:
        gdb_mi_text: String output from gdb

    Returns:
        dictionary with keys "type", "message", "payload", "token"
    """
    stream = StringStream(gdb_mi_text, debug=_DEBUG)

    for pattern, parser in _GDB_MI_PATTERNS_AND_PARSERS:
        match = pattern.match(gdb_mi_text)
        if match is not None:
            return parser(match, stream)

    # This was not gdb mi output, so it must have just been printed by
    # the inferior program that's being debugged
    return {
        "type": "output",
        "message": None,
        "payload": gdb_mi_text,
    }


def response_is_finished(gdb_mi_text: str) -> bool:
    """Return true if the gdb mi response is ending

    Args:
        gdb_mi_text: String output from gdb

    Returns:
        True if gdb response is finished
    """
    return _GDB_MI_RESPONSE_FINISHED_RE.match(gdb_mi_text) is not None


# ========================================================================
# All functions and variables below are used internally to parse mi output
# ========================================================================


def _parse_mi_notify(match: Match, stream: StringStream) -> Dict:
    """Parser function for matches against a notify record.

    See _GDB_MI_PATTERNS_AND_PARSERS for details."""
    message = match["message"]
    logger.debug("parsed message")
    logger.debug("%s", fmt_green(message))

    return {
        "type": "notify",
        "message": message.strip(),
        "payload": _extract_payload(match, stream),
        "token": _extract_token(match),
    }


def _parse_mi_result(match: Match, stream: StringStream) -> Dict:
    """Parser function for matches against a result record.

    See _GDB_MI_PATTERNS_AND_PARSERS for details."""
    return {
        "type": "result",
        "message": match["message"],
        "payload": _extract_payload(match, stream),
        "token": _extract_token(match),
    }


def _parse_mi_output(match: Match, stream: StringStream, output_type: str) -> Dict:
    """Parser function for matches against a console, log or target record.

    The record type must be specified in output_type.

    See _GDB_MI_PATTERNS_AND_PARSERS for details."""
    return {
        "type": output_type,
        "message": None,
        "payload": unescape(match["payload"]),
    }


def _parse_mi_finished(match: Match, stream: StringStream) -> Dict:
    """Parser function for matches against a finished record.

    See _GDB_MI_PATTERNS_AND_PARSERS for details."""
    return {
        "type": "done",
        "message": None,
        "payload": None,
    }


def _extract_token(match: Match) -> Optional[int]:
    """Extract a token from a match against a regular expression which included
    _GDB_MI_COMPONENT_TOKEN."""
    token = match["token"]
    return int(token) if token is not None else None


def _extract_payload(match: Match, stream: StringStream) -> Optional[Dict]:
    """Extract a token from a match against a regular expression which included
    _GDB_MI_COMPONENT_PAYLOAD."""
    if match["payload"] is None:
        return None

    stream.advance_past_chars([","])
    return _parse_dict(stream)


# A regular expression matching a response finished record.
_GDB_MI_RESPONSE_FINISHED_RE = re.compile(r"^\(gdb\)\s*$")

# Regular expression identifying a token in a MI record.
_GDB_MI_COMPONENT_TOKEN = r"(?P<token>\d+)?"
# Regular expression identifying a payload in a MI record.
_GDB_MI_COMPONENT_PAYLOAD = r"(?P<payload>,.*)?"

# The type of the functions which parse MI records as used by
# _GDB_MI_PATTERNS_AND_PARSERS.
_PARSER_FUNCTION = Callable[[Match, StringStream], Dict]

# A list where each item is a tuple of:
# - A compiled regular expression matching a MI record.
# - A function which is called if the regex matched with the match and a StringStream.
#   It must return a dictionary with details on the MI record..
#
# For more details on the MI , see
# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
#
# The order matters as items are iterated in ordered and that stops once a match is
# found.
_GDB_MI_PATTERNS_AND_PARSERS: List[Tuple[Pattern, _PARSER_FUNCTION]] = [
    # https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Result-Records.html#GDB_002fMI-Result-Records
    # In addition to a number of out-of-band notifications,
    # the response to a gdb/mi command includes one of the following result indications:
    # done, running, connected, error, exit
    (
        re.compile(
            rf"^{_GDB_MI_COMPONENT_TOKEN}\^(?P<message>\S+?){_GDB_MI_COMPONENT_PAYLOAD}$"
        ),
        _parse_mi_result,
    ),
    # https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Async-Records.html#GDB_002fMI-Async-Records
    # Async records are used to notify the gdb/mi client of additional
    # changes that have occurred. Those changes can either be a consequence
    # of gdb/mi commands (e.g., a breakpoint modified) or a result of target activity
    # (e.g., target stopped).
    (
        re.compile(
            rf"^{_GDB_MI_COMPONENT_TOKEN}[*=](?P<message>\S+?){_GDB_MI_COMPONENT_PAYLOAD}$"
        ),
        _parse_mi_notify,
    ),
    # https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
    # "~" string-output
    # The console output stream contains text that should be displayed
    # in the CLI console window. It contains the textual responses to CLI commands.
    (
        re.compile(r'~"(?P<payload>.*)"', re.DOTALL),
        functools.partial(_parse_mi_output, output_type="console"),
    ),
    # https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
    # "&" string-output
    # The log stream contains debugging messages being produced by gdb's internals.
    (
        re.compile(r'&"(?P<payload>.*)"', re.DOTALL),
        functools.partial(_parse_mi_output, output_type="log"),
    ),
    # https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
    # "@" string-output
    # The target output stream contains any textual output from the
    # running target. This is only present when GDB's event loop is truly asynchronous,
    # which is currently only the case for remote targets.
    (
        re.compile(r'@"(?P<payload>.*)"', re.DOTALL),
        functools.partial(_parse_mi_output, output_type="target"),
    ),
    (
        _GDB_MI_RESPONSE_FINISHED_RE,
        _parse_mi_finished,
    ),
]


_WHITESPACE = [" ", "\t", "\r", "\n"]

_GDB_MI_CHAR_DICT_START = "{"
_GDB_MI_CHAR_ARRAY_START = "["
_GDB_MI_CHAR_STRING_START = '"'
_GDB_MI_VALUE_START_CHARS = [
    _GDB_MI_CHAR_DICT_START,
    _GDB_MI_CHAR_ARRAY_START,
    _GDB_MI_CHAR_STRING_START,
]


def _parse_dict(stream: StringStream) -> Dict:
    """Parse dictionary, with optional starting character '{'
    return (tuple):
        Number of characters parsed from to_parse
        Parsed dictionary
    """
    obj: Dict[str, Union[str, list, dict]] = {}

    logger.debug("%s", fmt_green("parsing dict"))

    while True:
        c = stream.read(1)
        if c in _WHITESPACE:
            pass
        elif c in ["{", ","]:
            pass
        elif c in ["}", ""]:
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
                    obj[key].append(val)  # type: ignore
                else:
                    obj[key] = [obj[key], val]
            else:
                obj[key] = val

            look_ahead_for_garbage = True
            c = stream.read(1)
            while look_ahead_for_garbage:
                if c in ["}", ",", ""]:
                    look_ahead_for_garbage = False
                else:
                    # got some garbage text, skip it. for example:
                    # name="gdb"gargage  # skip over 'garbage'
                    # name="gdb"\n  # skip over '\n'
                    logger.debug("skipping unexpected charcter: " + c)
                    c = stream.read(1)
            stream.seek(-1)

    logger.debug("parsed dict")
    logger.debug("%s", fmt_green(obj))
    return obj


def _parse_key_val(stream: StringStream) -> Tuple[str, Union[str, List, Dict]]:
    """Parse key, value combination
    return (tuple):
        Parsed key (string)
        Parsed value (either a string, array, or dict)
    """

    logger.debug("parsing key/val")
    key = _parse_key(stream)
    val = _parse_val(stream)

    logger.debug("parsed key/val")
    logger.debug("%s", fmt_green(key))
    logger.debug("%s", fmt_green(val))

    return key, val


def _parse_key(stream: StringStream) -> str:
    """Parse key, value combination
    returns :
        Parsed key (string)
    """
    logger.debug("parsing key")

    key = stream.advance_past_chars(["="])

    logger.debug("parsed key:")
    logger.debug("%s", fmt_green(key))
    return key


def _parse_val(stream: StringStream) -> Union[str, List, Dict]:
    """Parse value from string
    returns:
        Parsed value (either a string, array, or dict)
    """

    logger.debug("parsing value")

    val: Any

    while True:
        c = stream.read(1)

        if c == "{":
            # Start object
            val = _parse_dict(stream)
            break

        elif c == "[":
            # Start of an array
            val = _parse_array(stream)
            break

        elif c == '"':
            # Start of a string
            val = stream.advance_past_string_with_gdb_escapes()
            break

        elif _DEBUG:
            raise ValueError("unexpected character: %s" % c)

        else:
            logger.warn(f'unexpected character: "{c}" ({ord(c)}). Continuing.')
            val = ""  # this will be overwritten if there are more characters to be read

    logger.debug("parsed value:")
    logger.debug("%s", fmt_green(val))

    return val


def _parse_array(stream: StringStream) -> list:
    """Parse an array, stream should be passed the initial [
    returns:
        Parsed array
    """

    logger.debug("parsing array")
    arr = []
    while True:
        c = stream.read(1)

        if c in _GDB_MI_VALUE_START_CHARS:
            stream.seek(-1)
            val = _parse_val(stream)
            arr.append(val)
        elif c in _WHITESPACE:
            pass
        elif c == ",":
            pass
        elif c == "]":
            # Stop when this array has finished. Note
            # that elements of this array can be also be arrays.
            break

    logger.debug("parsed array:")
    logger.debug("%s", fmt_green(arr))
    return arr
