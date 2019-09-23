import os
import re

# GDB machine interface output patterns to match

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Result-Records.html#GDB_002fMI-Result-Records
# In addition to a number of out-of-band notifications,
# the response to a gdb/mi command includes one of the following result indications:
# done, running, connected, error, exit
GDB_MI_RESULT_RE = re.compile(r"^(\d*)\^(\S+?)(,(.*))?$")

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Async-Records.html#GDB_002fMI-Async-Records
# Async records are used to notify the gdb/mi client of additional
# changes that have occurred. Those changes can either be a consequence
# of gdb/mi commands (e.g., a breakpoint modified) or a result of target activity
# (e.g., target stopped).
GDB_MI_NOTIFY_RE = re.compile(r"^(\d*)[*=](\S+?),(.*)$")

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
# "~" string-output
# The console output stream contains text that should be displayed
# in the CLI console window. It contains the textual responses to CLI commands.
GDB_MI_CONSOLE_RE = re.compile(r'~"(.*)"', re.DOTALL)

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
# "&" string-output
# The log stream contains debugging messages being produced by gdb's internals.
GDB_MI_LOG_RE = re.compile(r'&"(.*)"', re.DOTALL)

# https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Stream-Records.html#GDB_002fMI-Stream-Records
# "@" string-output
# The target output stream contains any textual output from the
# running target. This is only present when GDB's event loop is truly asynchronous,
# which is currently only the case for remote targets.
GDB_MI_TARGET_OUTPUT_RE = re.compile(r'@"(.*)"', re.DOTALL)

# Response finished
GDB_MI_RESPONSE_FINISHED_RE = re.compile(r"^\(gdb\)\s*$")

WHITESPACE = [" ", "\t", "\r", "\n"]

GDB_MI_CHAR_DICT_START = "{"
GDB_MI_CHAR_ARRAY_START = "["
GDB_MI_CHAR_STRING_START = '"'
GDB_MI_VALUE_START_CHARS = [
    GDB_MI_CHAR_DICT_START,
    GDB_MI_CHAR_ARRAY_START,
    GDB_MI_CHAR_STRING_START,
]

DEFAULT_GDB_TIMEOUT_SEC = 1
DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC = 0.2
USING_WINDOWS = os.name == "nt"
GDB_ESCAPE_CHAR = "\\"


class GdbTimeoutError(ValueError):
    """Raised when no response is recieved from gdb after the timeout has been triggered"""

    pass
