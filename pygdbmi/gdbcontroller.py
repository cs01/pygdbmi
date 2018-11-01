"""GdbController class to programatically run gdb and get structured output"""

from distutils.spawn import find_executable
import logging
import os
from pprint import pformat
from pygdbmi import gdbmiparser
import signal
import select
import subprocess
import sys
import time

try:  # py3
    from shlex import quote
except ImportError:  # py2
    from pipes import quote

PYTHON3 = sys.version_info.major == 3
DEFAULT_GDB_TIMEOUT_SEC = 1
DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC = 0.2
USING_WINDOWS = os.name == "nt"
if USING_WINDOWS:
    import msvcrt
    from ctypes import windll, byref, wintypes, WinError, POINTER
    from ctypes.wintypes import HANDLE, DWORD, BOOL
else:
    import fcntl

SIGNAL_NAME_TO_NUM = {}
for n in dir(signal):
    if n.startswith("SIG") and "_" not in n:
        SIGNAL_NAME_TO_NUM[n.upper()] = getattr(signal, n)

unicode = str if PYTHON3 else unicode  # noqa: F821


class NoGdbProcessError(ValueError):
    """Raise when trying to interact with gdb subprocess, but it does not exist.
    It may have been killed and removed, or failed to initialize for some reason."""

    pass


class GdbTimeoutError(ValueError):
    """Raised when no response is recieved from gdb after the timeout has been triggered"""

    pass


class GdbController:
    """
    Run gdb as a subprocess. Send commands and receive structured output.
    Create new object, along with a gdb subprocess

    Args:
        gdb_path (str): Command to run in shell to spawn new gdb subprocess
        gdb_args (list): Arguments to pass to shell when spawning new gdb subprocess
        time_to_check_for_additional_output_sec (float): When parsing responses, wait this amout of time before exiting (exits before timeout is reached to save time). If <= 0, full timeout time is used.
        rr (bool): Use the `rr replay` command instead of `gdb`. See rr-project.org for more info.
        verbose (bool): Print verbose output if True
    Returns:
        New GdbController object
    """

    def __init__(
        self,
        gdb_path="gdb",
        gdb_args=None,
        time_to_check_for_additional_output_sec=DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
        rr=False,
        verbose=False,
    ):
        if gdb_args is None:
            default_gdb_args = ["--nx", "--quiet", "--interpreter=mi2"]
            gdb_args = default_gdb_args

        self.verbose = verbose
        self.abs_gdb_path = None  # abs path to gdb executable
        self.cmd = []  # the shell command to run gdb
        self.time_to_check_for_additional_output_sec = (
            time_to_check_for_additional_output_sec
        )
        self.gdb_process = None
        self._allow_overwrite_timeout_times = (
            self.time_to_check_for_additional_output_sec > 0
        )

        if rr:
            self.cmd = ["rr", "replay"] + gdb_args

        else:
            if not gdb_path:
                raise ValueError("a valid path to gdb must be specified")

            else:
                abs_gdb_path = find_executable(gdb_path)
                if abs_gdb_path is None:
                    raise ValueError(
                        'gdb executable could not be resolved from "%s"' % gdb_path
                    )

                else:
                    self.abs_gdb_path = abs_gdb_path
            self.cmd = [self.abs_gdb_path] + gdb_args

        self._attach_logger(verbose)
        self.spawn_new_gdb_subprocess()

    def _attach_logger(self, verbose):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        unique_number = time.time()
        self.logger = logging.getLogger(__name__ + "." + str(unique_number))
        self.logger.propagate = False
        if verbose:
            level = logging.DEBUG
        else:
            level = logging.ERROR
        self.logger.setLevel(level)
        self.logger.addHandler(handler)

    def get_subprocess_cmd(self):
        """Returns the shell-escaped string used to invoke the gdb subprocess.
        This is a string that can be executed directly in a shell.
        """
        return " ".join(quote(c) for c in self.cmd)

    def spawn_new_gdb_subprocess(self):
        """Spawn a new gdb subprocess with the arguments supplied to the object
        during initialization. If gdb subprocess already exists, terminate it before
        spanwing a new one.
        Return int: gdb process id
        """
        if self.gdb_process:
            self.logger.debug(
                "Killing current gdb subprocess (pid %d)" % self.gdb_process.pid
            )
            self.exit()

        self.logger.debug('Launching gdb: "%s"' % " ".join(self.cmd))

        # Use pipes to the standard streams
        self.gdb_process = subprocess.Popen(
            self.cmd,
            shell=False,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        _make_non_blocking(self.gdb_process.stdout)
        _make_non_blocking(self.gdb_process.stderr)

        # save file numbers for use later
        self.stdout_fileno = self.gdb_process.stdout.fileno()
        self.stderr_fileno = self.gdb_process.stderr.fileno()
        self.stdin_fileno = self.gdb_process.stdin.fileno()

        self.read_list = [self.stdout_fileno, self.stderr_fileno]
        self.write_list = [self.stdin_fileno]

        # string buffers for unifinished gdb output
        self._incomplete_output = {"stdout": None, "stderr": None}
        return self.gdb_process.pid

    def verify_valid_gdb_subprocess(self):
        """Verify there is a process object, and that it is still running.
        Raise NoGdbProcessError if either of the above are not true."""
        if not self.gdb_process:
            raise NoGdbProcessError("gdb process is not attached")

        elif self.gdb_process.poll() is not None:
            raise NoGdbProcessError(
                "gdb process has already finished with return code: %s"
                % str(self.gdb_process.poll())
            )

    def write(
        self,
        mi_cmd_to_write,
        timeout_sec=DEFAULT_GDB_TIMEOUT_SEC,
        raise_error_on_timeout=True,
        read_response=True,
    ):
        """Write to gdb process. Block while parsing responses from gdb for a maximum of timeout_sec.

        Args:
            mi_cmd_to_write (str or list): String to write to gdb. If list, it is joined by newlines.
            timeout_sec (float): Maximum number of seconds to wait for response before exiting. Must be >= 0.
            raise_error_on_timeout (bool): If read_response is True, raise error if no response is received
            read_response (bool): Block and read response. If there is a separate thread running,
            this can be false, and the reading thread read the output.
        Returns:
            List of parsed gdb responses if read_response is True, otherwise []
        Raises:
            NoGdbProcessError if there is no gdb subprocess running
            TypeError if mi_cmd_to_write is not valid
        """
        self.verify_valid_gdb_subprocess()
        if timeout_sec < 0:
            self.logger.warning("timeout_sec was negative, replacing with 0")
            timeout_sec = 0

        # Ensure proper type of the mi command
        if type(mi_cmd_to_write) in [str, unicode]:
            pass
        elif type(mi_cmd_to_write) == list:
            mi_cmd_to_write = "\n".join(mi_cmd_to_write)
        else:
            raise TypeError(
                "The gdb mi command must a be str or list. Got "
                + str(type(mi_cmd_to_write))
            )

        self.logger.debug("writing: %s", mi_cmd_to_write)

        if not mi_cmd_to_write.endswith("\n"):
            mi_cmd_to_write_nl = mi_cmd_to_write + "\n"
        else:
            mi_cmd_to_write_nl = mi_cmd_to_write

        if USING_WINDOWS:
            # select not implemented in windows for pipes
            # assume it's always ready
            outputready = [self.stdin_fileno]
        else:
            _, outputready, _ = select.select([], self.write_list, [], timeout_sec)
        for fileno in outputready:
            if fileno == self.stdin_fileno:
                # ready to write
                self.gdb_process.stdin.write(mi_cmd_to_write_nl.encode())
                # don't forget to flush for Python3, otherwise gdb won't realize there is data
                # to evaluate, and we won't get a response
                self.gdb_process.stdin.flush()
            else:
                self.logger.error("got unexpected fileno %d" % fileno)

        if read_response is True:
            return self.get_gdb_response(
                timeout_sec=timeout_sec, raise_error_on_timeout=raise_error_on_timeout
            )

        else:
            return []

    def get_gdb_response(
        self, timeout_sec=DEFAULT_GDB_TIMEOUT_SEC, raise_error_on_timeout=True
    ):
        """Get response from GDB, and block while doing so. If GDB does not have any response ready to be read
        by timeout_sec, an exception is raised.

        Args:
            timeout_sec (float): Maximum time to wait for reponse. Must be >= 0. Will return after
            raise_error_on_timeout (bool): Whether an exception should be raised if no response was found
            after timeout_sec

        Returns:
            List of parsed GDB responses, returned from gdbmiparser.parse_response, with the
            additional key 'stream' which is either 'stdout' or 'stderr'

        Raises:
            GdbTimeoutError if response is not received within timeout_sec
            ValueError if select returned unexpected file number
            NoGdbProcessError if there is no gdb subprocess running
        """

        self.verify_valid_gdb_subprocess()
        if timeout_sec < 0:
            self.logger.warning("timeout_sec was negative, replacing with 0")
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

    def _get_responses_windows(self, timeout_sec):
        """Get responses on windows. Assume no support for select and use a while loop."""
        timeout_time_sec = time.time() + timeout_sec
        responses = []
        while True:
            try:
                self.gdb_process.stdout.flush()
                if PYTHON3:
                    raw_output = self.gdb_process.stdout.readline().replace(
                        b"\r", b"\n"
                    )
                else:
                    raw_output = self.gdb_process.stdout.read().replace(b"\r", b"\n")
                responses += self._get_responses_list(raw_output, "stdout")
            except IOError:
                pass

            try:
                self.gdb_process.stderr.flush()
                if PYTHON3:
                    raw_output = self.gdb_process.stderr.readline().replace(
                        b"\r", b"\n"
                    )
                else:
                    raw_output = self.gdb_process.stderr.read().replace(b"\r", b"\n")
                responses += self._get_responses_list(raw_output, "stderr")
            except IOError:
                pass

            if time.time() > timeout_time_sec:
                break

        return responses

    def _get_responses_unix(self, timeout_sec):
        """Get responses on unix-like system. Use select to wait for output."""
        timeout_time_sec = time.time() + timeout_sec
        responses = []
        while True:
            select_timeout = timeout_time_sec - time.time()
            # I prefer to not pass a negative value to select
            if select_timeout <= 0:
                select_timeout = 0
            events, _, _ = select.select(self.read_list, [], [], select_timeout)
            responses_list = None  # to avoid infinite loop if using Python 2
            try:
                for fileno in events:
                    # new data is ready to read
                    if fileno == self.stdout_fileno:
                        self.gdb_process.stdout.flush()
                        raw_output = self.gdb_process.stdout.read()
                        stream = "stdout"

                    elif fileno == self.stderr_fileno:
                        self.gdb_process.stderr.flush()
                        raw_output = self.gdb_process.stderr.read()
                        stream = "stderr"

                    else:
                        raise ValueError(
                            "Developer error. Got unexpected file number %d" % fileno
                        )

                    responses_list = self._get_responses_list(raw_output, stream)
                    responses += responses_list

            except IOError:  # only occurs in python 2.7
                pass

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

    def _get_responses_list(self, raw_output, stream):
        """Get parsed response list from string output
        Args:
            raw_output (unicode): gdb output to parse
            stream (str): either stdout or stderr
        """
        responses = []

        raw_output, self._incomplete_output[stream] = _buffer_incomplete_responses(
            raw_output, self._incomplete_output.get(stream)
        )

        if not raw_output:
            return responses

        response_list = list(
            filter(lambda x: x, raw_output.decode(errors="replace").split("\n"))
        )  # remove blank lines

        # parse each response from gdb into a dict, and store in a list
        for response in response_list:
            if gdbmiparser.response_is_finished(response):
                pass
            else:
                parsed_response = gdbmiparser.parse_response(response)
                parsed_response["stream"] = stream

                self.logger.debug("%s", pformat(parsed_response))

                responses.append(parsed_response)

        return responses

    def send_signal_to_gdb(self, signal_input):
        """Send signal name (case insensitive) or number to gdb subprocess
        gdbmi.send_signal_to_gdb(2)  # valid
        gdbmi.send_signal_to_gdb('sigint')  # also valid
        gdbmi.send_signal_to_gdb('SIGINT')  # also valid

        raises ValueError if signal_input is invalie
        raises NoGdbProcessError if there is no gdb process to send a signal to
        """
        try:
            signal = int(signal_input)
        except Exception:
            signal = SIGNAL_NAME_TO_NUM.get(signal_input.upper())

        if not signal:
            raise ValueError(
                'Could not find signal corresponding to "%s"' % str(signal)
            )

        if self.gdb_process:
            os.kill(self.gdb_process.pid, signal)
        else:
            raise NoGdbProcessError(
                "Cannot send signal to gdb process because no process exists."
            )

    def interrupt_gdb(self):
        """Send SIGINT (interrupt signal) to the gdb subprocess"""
        self.send_signal_to_gdb("SIGINT")

    def exit(self):
        """Terminate gdb process
        Returns: None"""
        if self.gdb_process:
            self.gdb_process.terminate()
            self.gdb_process.communicate()
        self.gdb_process = None
        return None


def _buffer_incomplete_responses(raw_output, buf):
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


def _make_non_blocking(file_obj):
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

        h = msvcrt.get_osfhandle(file_obj.fileno())

        res = windll.kernel32.SetNamedPipeHandleState(h, byref(PIPE_NOWAIT), None, None)
        if res == 0:
            raise ValueError(WinError())

    else:
        # Set the file status flag (F_SETFL) on the pipes to be non-blocking
        # so we can attempt to read from a pipe with no new data without locking
        # the program up
        fcntl.fcntl(file_obj, fcntl.F_SETFL, os.O_NONBLOCK)
