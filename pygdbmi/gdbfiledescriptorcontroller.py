import logging
import os
import select
import time
from pprint import pformat
from typing import IO, Any, Dict, List, Optional, Tuple, Union

from pygdbmi import gdbmiparser
from pygdbmi.constants import DEFAULT_GDB_TIMEOUT_SEC, USING_WINDOWS, GdbTimeoutError


class GdbFileDescriptorController:
    """Parses gdb mi objects from existing File Descriptors.

    The file descriptors read from and written to are managed externally
    from this class. This class can be used to parse from/write to a
    subprocess or pty, for example.
    """

    def __init__(self, stdin: int, stdout: int):
        # self.stdin = stdin
        # self.stdout = stdout
        self.stdin_fileno = stdin
        self.stdout_fileno = stdout
        self._raw_buffer = None  # type: Optional[bytes]
        self.attach_logger()

    def attach_logger(self):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        unique_number = time.time()
        self.logger = logging.getLogger(__name__ + "." + str(unique_number))
        self.logger.addHandler(handler)

    def write(
        self,
        mi_cmd_to_write: Union[str, List[str]],
        timeout_sec=DEFAULT_GDB_TIMEOUT_SEC,
        raise_error_on_timeout: bool = False,
        read_response: bool = True,
    ):
        """Write to gdb process. Block while parsing responses from gdb for a maximum of timeout_sec.

        Args:
            mi_cmd_to_write (str or list): String to write to gdb. If list, it is joined by newlines.
            timeout_sec (float): Maximum number of seconds to wait for response before exiting. Must be >= 0.
            raise_error_on_timeout (bool): If read_response is True, raise error if no response is received
            read_response (bool): Block and read response. If there is a separate thread running,
            this can be false, and the reading thread will read the output.
        Returns:
            List of parsed gdb responses if read_response is True, otherwise []
        Raises:
            NoGdbProcessError if there is no gdb subprocess running
            TypeError if mi_cmd_to_write is not valid
        """
        if timeout_sec < 0:
            self.logger.warning("timeout_sec was negative, replacing with 0")
            timeout_sec = 0

        if isinstance(mi_cmd_to_write, str):
            mi_cmd_to_write_list = [mi_cmd_to_write]
        elif isinstance(mi_cmd_to_write, list):
            mi_cmd_to_write_list = mi_cmd_to_write
        else:
            raise TypeError(
                "The gdb mi command must a be str or list. Got "
                + str(type(mi_cmd_to_write))
            )

        if USING_WINDOWS:
            # select not implemented in windows for pipes
            # assume it's always ready
            ready_to_write = [self.stdin_fileno]
        else:
            _, ready_to_write, _ = select.select(
                [], [self.stdin_fileno], [], timeout_sec
            )

        for fileno in ready_to_write:
            if fileno == self.stdin_fileno:
                for cmd in mi_cmd_to_write_list:
                    self.logger.debug("writing: %s", cmd)
                    os.write(self.stdin_fileno, (cmd + "\n").encode())
            else:
                self.logger.error("got unexpected fileno %s" % str(fileno))

        if read_response is True:
            return self.get_gdb_response(
                timeout_sec=timeout_sec, raise_error_on_timeout=raise_error_on_timeout
            )
        else:
            return []

    def get_gdb_response(
        self, timeout_sec: float = DEFAULT_GDB_TIMEOUT_SEC, raise_error_on_timeout=True
    ) -> List[str]:
        """Get response from GDB, and block while doing so. If GDB does not have any response ready to be read
        by timeout_sec, an exception is raised.

        Args:
            timeout_sec (float): Maximum time to wait for reponse. Must be >= 0. Will return after
            raise_error_on_timeout (bool): Whether an exception should be raised if no response was found after timeout_sec

        Returns:
            List of parsed GDB responses, returned from gdbmiparser.parse_response

        Raises:
            GdbTimeoutError if response is not received within timeout_sec
            OSError if file descriptor is no longer valid
            NoGdbProcessError if there is no gdb subprocess running
        """

        if timeout_sec < 0:
            self.logger.warning("timeout_sec was negative, replacing with 0")
            timeout_sec = 0

        responses = self._get_responses(timeout_sec)

        if not responses and raise_error_on_timeout:
            raise GdbTimeoutError(
                "Did not get response from gdb after %s seconds" % timeout_sec
            )

        else:
            return responses

    def _get_new_output_windows(self) -> bytes:
        try:
            return self.stdout.readline().replace(b"\r", b"\n")
        except IOError:
            return b""

    def _get_new_output_unix(self, timeout_time_sec: int) -> bytes:
        select_timeout = timeout_time_sec - time.time()
        if select_timeout <= 0:
            select_timeout = 0

        events, _, _ = select.select([self.stdout_fileno], [], [], select_timeout)
        for fileno in events:
            # new data is ready to be read!
            if fileno == self.stdout_fileno:
                return os.read(self.stdout_fileno, 1024)

            else:
                raise ValueError(
                    "Developer error. Got unexpected file number %d" % fileno
                )
        return b""

    def _get_responses(self, timeout_sec):
        """Get responses on unix-like system. Use select to wait for output."""
        timeout_time_sec = time.time() + timeout_sec
        responses = []

        while True:
            if USING_WINDOWS:
                new_output = self._get_new_output_windows()
            else:
                new_output = self._get_new_output_unix(timeout_time_sec)
            new_responses = self._get_responses_list(new_output)
            responses += new_responses

            if timeout_sec == 0:
                # time's up!
                break
            elif new_responses:
                # update timeout time to potentially be closer to now to
                # avoid lengthy wait times when nothing is being output by gdb
                timeout_time_sec = min(time.time() + 0.1, timeout_time_sec)

            elif time.time() > timeout_time_sec:
                break

        return responses

    def _get_responses_list(self, new_output: bytes) -> List[Dict]:
        """Get parsed response list from string output"""
        responses = []  # type: List[Dict]
        new_output_processed = None  # type: Optional[bytes]
        new_output_processed, self._raw_buffer = _buffer_incomplete_responses(
            new_output, self._raw_buffer
        )

        if not new_output_processed:
            return responses

        response_list = [
            line
            for line in new_output_processed.decode(errors="replace").split("\n")
            if line
        ]

        for response in response_list:
            if gdbmiparser.response_is_finished(response):
                pass
            else:
                parsed_response = gdbmiparser.parse_response(response)
                self.logger.debug("%s", pformat(parsed_response))
                responses.append(parsed_response)

        return responses


def _buffer_incomplete_responses(
    new_output: Optional[bytes], unparseable_buffer: Optional[bytes]
) -> Tuple[Optional[bytes], Optional[bytes]]:
    """It is possible for some of gdb's output to be read before it completely finished its response.
    In that case, a partial mi response was read, which cannot be parsed into structured data.
    We want to ALWAYS parse complete mi records. To do this, we store a buffer of gdb's
    output if the output did not end in a newline.

    Args:
        new_output: Contents of the gdb mi output
        unparseable_buffer (str): Buffered gdb response from the past.
        This is incomplete and needs to be prepended to gdb's next output.

    Returns:
        (new_output, unparseable_buffer)
    """

    def is_incomplete(output: bytes) -> bool:
        return b"\n" not in output

    def has_trailing_incomplete_output(output: bytes) -> bool:
        return not output.endswith(b"\n")

    if new_output:
        if unparseable_buffer:
            # concatenate buffer and new output
            new_output = b"".join([unparseable_buffer, new_output])
            unparseable_buffer = None

        if is_incomplete(new_output):
            unparseable_buffer = new_output
            new_output = None

        elif has_trailing_incomplete_output(new_output):
            # store incomplete output (everything after the last newline)
            # in the unparseable_buffer, and parse everything before it
            remainder_offset = new_output.rindex(b"\n") + 1
            unparseable_buffer = new_output[remainder_offset:]
            new_output = new_output[:remainder_offset]

    return (new_output, unparseable_buffer)
