"""
Python parser for gdb's machine interface interpreter.

Parses string output from gdb with the "--interpreter=mi2" flag into
structured objects.

See more at https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html#GDB_002fMI

"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from pygdbmi.constants import (
    GDB_MI_CHAR_ARRAY_START,
    GDB_MI_CONSOLE_RE,
    GDB_MI_LOG_RE,
    GDB_MI_NOTIFY_RE,
    GDB_MI_RESPONSE_FINISHED_RE,
    GDB_MI_RESULT_RE,
    GDB_MI_TARGET_OUTPUT_RE,
    GDB_MI_VALUE_START_CHARS,
    WHITESPACE,
)
from pygdbmi.printcolor import fmt_green
from pygdbmi.StringStream import StringStream

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s")
)
logger.addHandler(handler)


def parse_response(gdb_mi_text: str) -> Dict[str, Any]:
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

    payload = None  # type: Union[None, Dict, List, str]

    if GDB_MI_NOTIFY_RE.match(gdb_mi_text):
        stream = StringStream(gdb_mi_text)
        token, message, payload = _get_notify_msg_and_payload(gdb_mi_text, stream)
        return {
            "type": "notify",
            "message": message,
            "payload": payload,
            "token": token,
        }

    if GDB_MI_RESULT_RE.match(gdb_mi_text):
        stream = StringStream(gdb_mi_text)
        token, message, payload = _get_result_msg_and_payload(gdb_mi_text, stream)
        return {
            "type": "result",
            "message": message,
            "payload": payload,
            "token": token,
        }

    console_match = GDB_MI_CONSOLE_RE.match(gdb_mi_text)
    if console_match:
        payload = StringStream(console_match.groups()[0]).remove_gdb_escapes()
        return {"type": "console", "message": None, "payload": payload}

    log_match = GDB_MI_LOG_RE.match(gdb_mi_text)
    if log_match:
        payload = StringStream(log_match.groups()[0]).remove_gdb_escapes()
        return {"type": "log", "message": None, "payload": payload}

    target_output_match = GDB_MI_TARGET_OUTPUT_RE.match(gdb_mi_text)
    if target_output_match:
        payload = StringStream(target_output_match.groups()[0]).remove_gdb_escapes()
        return {"type": "target", "message": None, "payload": payload}

    if response_is_finished(gdb_mi_text):
        return {"type": "done", "message": None, "payload": None}

    # This was not gdb mi output, so it must have just been printed by
    # the inferior program that's being debugged
    return {"type": "output", "message": None, "payload": gdb_mi_text}


def response_is_finished(gdb_mi_text: str) -> bool:
    """Returns: True if gdb response is finished"""
    return bool(GDB_MI_RESPONSE_FINISHED_RE.match(gdb_mi_text))


def _get_notify_msg_and_payload(
    result: str, stream: StringStream
) -> Tuple[Optional[int], str, Dict]:
    """Get notify message and payload dict"""
    token_str = stream.advance_past_chars(["=", "*"])
    token = int(token_str) if token_str != "" else None
    logger.debug("%s", fmt_green("parsing message"))
    message = stream.advance_past_chars([","])

    logger.debug("parsed message")
    logger.debug("%s", fmt_green(message))

    payload = parse_dict(stream)
    return token, message.strip(), payload


def _get_result_msg_and_payload(
    result: str, stream: StringStream
) -> Tuple[Optional[int], str, Optional[Dict]]:
    """Get result message and payload dict"""

    match = GDB_MI_RESULT_RE.match(result)
    if not match:
        logger.error(
            "Expected result %s to match regular expression %s",
            result,
            GDB_MI_RESULT_RE,
        )
        return None, "", None

    groups = match.groups()
    token = int(groups[0]) if groups[0] != "" else None
    message = groups[1]

    if groups[2] is None:
        payload = None
    else:
        stream.advance_past_chars([","])
        payload = parse_dict(stream)

    return token, message, payload


def parse_dict(stream: StringStream) -> Dict[str, Any]:
    """Parse dictionary, with starting character '{' """
    obj = {}  # type: Dict[str, Any]

    logger.debug("%s", fmt_green("parsing dict"))

    while True:
        c = stream.read(1)
        if c in WHITESPACE:
            pass
        elif c in ["{", ","]:
            pass
        elif c in ["}", StringStream.stream_end]:
            # end of object, exit loop
            break
        else:
            stream.seek(-1)
            key, val = parse_key_val(stream)
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


def parse_key_val(stream: StringStream) -> Tuple[str, Union[Dict, List, str]]:
    """Parse key, value combination
    return (tuple):
        Parsed key (string)
        Parsed value (either a string, array, or dict)
    """

    logger.debug("parsing key/val")
    key = parse_key(stream)
    val = parse_val(stream)

    logger.debug("parsed key/val")
    logger.debug("%s", fmt_green(key))
    logger.debug("%s", fmt_green(val))

    return key, val


def parse_key(stream: StringStream) -> str:
    key = stream.advance_past_chars(["="])
    logger.debug("parsed key: %s", fmt_green(key))
    return key


def parse_val(stream: StringStream) -> Union[Dict, List, str]:
    """Parse value from string based on first identifiable character"""

    logger.debug("parsing value")
    val = ""  # type: Union[Dict, List, str]
    while True:
        c = stream.read(1)
        if c == "{":
            # Start object
            stream.seek(-1)
            return parse_dict(stream)
        elif c == "[":
            # Start of an array
            stream.seek(-1)
            return parse_array(stream)
        elif c == '"':
            stream.seek(-1)
            # Start of a string
            return stream.advance_past_string_with_gdb_escapes()
        elif c == "":
            return ""
        else:
            logger.warning('encountered unexpected character: "%s". Continuing.', c)
            break
    logger.error("Failed to parse value")
    return val


def parse_array(stream: StringStream) -> List[Any]:
    """Parse an array"""

    logger.debug("parsing array")
    arr = []  # type: List[Any]
    c = stream.read(1)

    if c != GDB_MI_CHAR_ARRAY_START:
        logger.debug("Unexpected character at start of array")
        return []

    while True:
        c = stream.read(1)

        if c in GDB_MI_VALUE_START_CHARS:
            stream.seek(-1)
            val = parse_val(stream)
            arr.append(val)
        elif c in WHITESPACE:
            pass
        elif c == ",":
            pass
        elif c == "]":
            # Stop when this array has finished. Note
            # that elements of this array can be also be arrays.
            break
        elif c == StringStream.stream_end:
            logger.debug("Unexpected end of stream. Got %s", arr)
            return arr
        else:
            logger.debug("Unrecognized character when parsing array")

    logger.debug("parsed array: %s", fmt_green(arr))
    return arr
