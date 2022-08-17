"""This module defines the `IoManager` class
which manages I/O for file objects connected to an existing gdb process
or pty.
"""
import logging
import os
import select
import time
from pprint import pformat
from typing import IO, Any, Dict, List, Optional, Tuple, Union

from pygdbmi import gdbmiparser
from pygdbmi.constants import (
    DEFAULT_GDB_TIMEOUT_SEC,
    DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
    USING_WINDOWS,
    GdbTimeoutError,
)


if USING_WINDOWS:
    import msvcrt
    from ctypes import POINTER, WinError, byref, windll, wintypes  # type: ignore
    from ctypes.wintypes import BOOL, DWORD, HANDLE
else:
    import fcntl


__all__ = ["IoManager"]


logger = logging.getLogger(__name__)


class IoManager:
    def __init__(
        self,
        stdin: IO[bytes],
        stdout: IO[bytes],
        stderr: Optional[IO[bytes]],
        time_to_check_for_additional_output_sec: float = DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
    ) -> None:
        """
        Manage I/O for file objects created before calling this class
        This can be useful if the gdb process is managed elsewhere, or if a
        pty is used.
        """

        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

        self.stdin_fileno = self.stdin.fileno()
        self.stdout_fileno = self.stdout.fileno()
        self.stderr_fileno = self.stderr.fileno() if self.stderr else -1

        self.read_list: List[int] = []
        if self.stdout:
            self.read_list.append(self.stdout_fileno)
        self.write_list = [self.stdin_fileno]

        self._incomplete_output: Dict[str, Any] = {"stdout": None, "stderr": None}
        self.time_to_check_for_additional_output_sec = (
            time_to_check_for_additional_output_sec
        )
        self._allow_overwrite_timeout_times = (
            self.time_to_check_for_additional_output_sec > 0
        )
        _make_non_blocking(self.stdout)
        if self.stderr:
            _make_non_blocking(self.stderr)

    def get_gdb_response(
        self,
        timeout_sec: float = DEFAULT_GDB_TIMEOUT_SEC,
        raise_error_on_timeout: bool = True,
    ) -> List[Dict]:
        """Get response from GDB, and block while doing so. If GDB does not have any response ready to be read
        by timeout_sec, an exception is raised.

        Args:
            timeout_sec: Maximum time to wait for reponse. Must be >= 0. Will return after
            raise_error_on_timeout: Whether an exception should be raised if no response was found after timeout_sec

        Returns:
            List of parsed GDB responses, returned from gdbmiparser.parse_response, with the
            additional key 'stream' which is either 'stdout' or 'stderr'

        Raises:
            GdbTimeoutError: if response is not received within timeout_sec
            ValueError: if select returned unexpected file number
        """

        if timeout_sec < 0:
            logger.warning("timeout_sec was negative, replacing with 0")
            timeout_sec = 0

        if USING_WINDOWS:
            retval = self._get_responses_windows(timeout_sec)
        else:
            retval = self._get_responses_unix(timeout_sec)

        if not retval and raise_error_on_timeout:
            raise GdbTimeoutError(
                "Did not get response from gdb after %s seconds" % timeout_sec
            )

        else:
            return retval

    def _get_responses_windows(self, timeout_sec: float) -> List[Dict]:
        """Get responses on windows. Assume no support for select and use a while loop."""
        timeout_time_sec = time.time() + timeout_sec
        responses = []
        while True:
            responses_list = []
            try:
                self.stdout.flush()
                raw_output = self.stdout.readline().replace(b"\r", b"\n")
                responses_list = self._get_responses_list(raw_output, "stdout")
            except OSError:
                pass

            if self.stderr is not None:
                try:
                    self.stderr.flush()
                    raw_output = self.stderr.readline().replace(b"\r", b"\n")
                    responses_list += self._get_responses_list(raw_output, "stderr")
                except OSError:
                    pass

            responses += responses_list
            if timeout_sec == 0:
                break
            elif responses_list and self._allow_overwrite_timeout_times:
                timeout_time_sec = min(
                    time.time() + self.time_to_check_for_additional_output_sec,
                    timeout_time_sec,
                )
            elif time.time() > timeout_time_sec:
                break

        return responses

    def _get_responses_unix(self, timeout_sec: float) -> List[Dict]:
        """Get responses on unix-like system. Use select to wait for output."""
        timeout_time_sec = time.time() + timeout_sec
        responses = []
        while True:
            select_timeout = timeout_time_sec - time.time()
            if select_timeout <= 0:
                select_timeout = 0
            events, _, _ = select.select(self.read_list, [], [], select_timeout)
            responses_list = None  # to avoid infinite loop if using Python 2
            for fileno in events:
                # new data is ready to read
                if fileno == self.stdout_fileno:
                    self.stdout.flush()
                    raw_output = self.stdout.read()
                    stream = "stdout"

                elif fileno == self.stderr_fileno:
                    assert self.stderr is not None
                    self.stderr.flush()
                    raw_output = self.stderr.read()
                    stream = "stderr"

                else:
                    raise ValueError(
                        "Developer error. Got unexpected file number %d" % fileno
                    )
                responses_list = self._get_responses_list(raw_output, stream)
                responses += responses_list

            if timeout_sec == 0:  # just exit immediately
                break

            elif responses_list and self._allow_overwrite_timeout_times:
                # update timeout time to potentially be closer to now to avoid lengthy wait times when nothing is being output by gdb
                timeout_time_sec = min(
                    time.time() + self.time_to_check_for_additional_output_sec,
                    timeout_time_sec,
                )

            elif time.time() > timeout_time_sec:
                break

        return responses

    def _get_responses_list(
        self, raw_output: bytes, stream: str
    ) -> List[Dict[Any, Any]]:
        """Get parsed response list from string output
        Args:
            raw_output (unicode): gdb output to parse
            stream (str): either stdout or stderr
        """
        responses: List[Dict[Any, Any]] = []

        (_new_output, self._incomplete_output[stream],) = _buffer_incomplete_responses(
            raw_output, self._incomplete_output.get(stream)
        )

        if not _new_output:
            return responses

        response_list = list(
            filter(lambda x: x, _new_output.decode(errors="replace").split("\n"))
        )  # remove blank lines

        # parse each response from gdb into a dict, and store in a list
        for response in response_list:
            if gdbmiparser.response_is_finished(response):
                pass
            else:
                parsed_response = gdbmiparser.parse_response(response)
                parsed_response["stream"] = stream

                logger.debug("%s", pformat(parsed_response))

                responses.append(parsed_response)

        return responses

    def write(
        self,
        mi_cmd_to_write: Union[str, List[str]],
        timeout_sec: float = DEFAULT_GDB_TIMEOUT_SEC,
        raise_error_on_timeout: bool = True,
        read_response: bool = True,
    ) -> List[Dict]:
        """Write to gdb process. Block while parsing responses from gdb for a maximum of timeout_sec.

        Args:
            mi_cmd_to_write: String to write to gdb. If list, it is joined by newlines.
            timeout_sec: Maximum number of seconds to wait for response before exiting. Must be >= 0.
            raise_error_on_timeout: If read_response is True, raise error if no response is received
            read_response: Block and read response. If there is a separate thread running, this can be false, and the reading thread read the output.
        Returns:
            List of parsed gdb responses if read_response is True, otherwise []
        Raises:
            TypeError: if mi_cmd_to_write is not valid
        """
        # self.verify_valid_gdb_subprocess()
        if timeout_sec < 0:
            logger.warning("timeout_sec was negative, replacing with 0")
            timeout_sec = 0

        # Ensure proper type of the mi command
        if isinstance(mi_cmd_to_write, str):
            mi_cmd_to_write_str = mi_cmd_to_write
        elif isinstance(mi_cmd_to_write, list):
            mi_cmd_to_write_str = "\n".join(mi_cmd_to_write)
        else:
            raise TypeError(
                "The gdb mi command must a be str or list. Got "
                + str(type(mi_cmd_to_write))
            )

        logger.debug("writing: %s", mi_cmd_to_write)

        if not mi_cmd_to_write_str.endswith("\n"):
            mi_cmd_to_write_nl = mi_cmd_to_write_str + "\n"
        else:
            mi_cmd_to_write_nl = mi_cmd_to_write_str

        if USING_WINDOWS:
            # select not implemented in windows for pipes
            # assume it's always ready
            outputready = [self.stdin_fileno]
        else:
            _, outputready, _ = select.select([], self.write_list, [], timeout_sec)
        for fileno in outputready:
            if fileno == self.stdin_fileno:
                # ready to write
                self.stdin.write(mi_cmd_to_write_nl.encode())  # type: ignore
                # must flush, otherwise gdb won't realize there is data
                # to evaluate, and we won't get a response
                self.stdin.flush()  # type: ignore
            else:
                logger.error("got unexpected fileno %d" % fileno)

        if read_response is True:
            return self.get_gdb_response(
                timeout_sec=timeout_sec, raise_error_on_timeout=raise_error_on_timeout
            )

        else:
            return []


def _buffer_incomplete_responses(
    raw_output: Optional[bytes], buf: Optional[bytes]
) -> Tuple[Optional[bytes], Optional[bytes]]:
    """It is possible for some of gdb's output to be read before it completely finished its response.
    In that case, a partial mi response was read, which cannot be parsed into structured data.
    We want to ALWAYS parse complete mi records. To do this, we store a buffer of gdb's
    output if the output did not end in a newline.

    Args:
        raw_output: Contents of the gdb mi output
        buf (str): Buffered gdb response from the past. This is incomplete and needs to be prepended to
        gdb's next output.

    Returns:
        (raw_output, buf)
    """

    if raw_output:
        if buf:
            # concatenate buffer and new output
            raw_output = b"".join([buf, raw_output])
            buf = None

        if b"\n" not in raw_output:
            # newline was not found, so assume output is incomplete and store in buffer
            buf = raw_output
            raw_output = None

        elif not raw_output.endswith(b"\n"):
            # raw output doesn't end in a newline, so store everything after the last newline (if anything)
            # in the buffer, and parse everything before it
            remainder_offset = raw_output.rindex(b"\n") + 1
            buf = raw_output[remainder_offset:]
            raw_output = raw_output[:remainder_offset]

    return (raw_output, buf)


def _make_non_blocking(file_obj: IO) -> None:
    """make file object non-blocking
    Windows doesn't have the fcntl module, but someone on
    stack overflow supplied this code as an answer, and it works
    http://stackoverflow.com/a/34504971/2893090"""

    if USING_WINDOWS:
        LPDWORD = POINTER(DWORD)
        PIPE_NOWAIT = wintypes.DWORD(0x00000001)

        SetNamedPipeHandleState = windll.kernel32.SetNamedPipeHandleState
        SetNamedPipeHandleState.argtypes = [HANDLE, LPDWORD, LPDWORD, LPDWORD]
        SetNamedPipeHandleState.restype = BOOL

        h = msvcrt.get_osfhandle(file_obj.fileno())  # type: ignore

        res = windll.kernel32.SetNamedPipeHandleState(h, byref(PIPE_NOWAIT), None, None)
        if res == 0:
            raise ValueError(WinError())

    else:
        # Set the file status flag (F_SETFL) on the pipes to be non-blocking
        # so we can attempt to read from a pipe with no new data without locking
        # the program up
        fcntl.fcntl(file_obj, fcntl.F_SETFL, os.O_NONBLOCK)
