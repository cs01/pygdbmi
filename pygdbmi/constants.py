import os


__all__ = [
    "DEFAULT_GDB_TIMEOUT_SEC",
    "DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC",
    "GdbTimeoutError",
    "USING_WINDOWS",
]


DEFAULT_GDB_TIMEOUT_SEC = 1
DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC = 0.2
USING_WINDOWS = os.name == "nt"


class GdbTimeoutError(ValueError):
    """Raised when no response is recieved from gdb after the timeout has been triggered"""

    pass
