"""GdbController class to programatically run gdb and get structured output"""

import sys
import select
import subprocess
import os
from pprint import pprint
from pygdbmi import gdbmiparser
from distutils.spawn import find_executable
from multiprocessing import Lock

PYTHON3 = sys.version_info.major == 3
DEFAULT_GDB_TIMEOUT_SEC = 1
MUTEX_AQUIRE_WAIT_TIME_SEC = int(1)
USING_WINDOWS = os.name == 'nt'
unicode = str if PYTHON3 else unicode


class NoGdbProcessError(ValueError):
    """Raise when trying to interact with gdb subprocess, but it does not exist.
    It may have been killed and removed, or failed to initialize for some reason."""
    pass


class GdbTimeoutError(ValueError):
    """Raised when no response is recieved from gdb after the timeout has been triggered"""
    pass


class GdbController():
    """
    Run gdb as a subprocess. Send commands and receive structured output.
    Create new object, along with a gdb subprocess

    Args:
        gdb_path (str): Command to run in shell to spawn new gdb subprocess
        gdb_args (list): Arguments to pass to shell when spawning new gdb subprocess
        verbose (bool): Print verbose output if True
    Returns:
        New GdbController object
    """

    def __init__(self, gdb_path='gdb', gdb_args=['--nx', '--quiet', '--interpreter=mi2'], verbose=False):
        self.verbose = verbose
        self.mutex = Lock()
        self.abs_gdb_path = None  # abs path to gdb executable
        self.cmd = []  # the shell command to run gdb
        self._buffer = ''  # string buffer for unifinished gdb output

        if not gdb_path:
            raise ValueError('a valid path to gdb must be specified')
        else:
            abs_gdb_path = find_executable(gdb_path)
            if abs_gdb_path is None:
                raise ValueError('gdb executable could not be resolved from "%s"' % gdb_path)
            else:
                self.abs_gdb_path = abs_gdb_path

        self.cmd = [self.abs_gdb_path] + gdb_args

        if verbose:
            print('Launching gdb: "%s"' % ' '.join(self.cmd))

        # Use pipes to the standard streams
        # In UNIX a newline will typically only flush the buffer if stdout is a terminal.
        # If the output is being redirected to a file, a newline won't flush
        self.gdb_process = subprocess.Popen(self.cmd, shell=False, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        _make_non_blocking(self.gdb_process.stdout)
        _make_non_blocking(self.gdb_process.stderr)

        # save file numbers for use later
        self.stdout_fileno = self.gdb_process.stdout.fileno()
        self.stderr_fileno = self.gdb_process.stderr.fileno()
        self.stdin_fileno = self.gdb_process.stdin.fileno()

        self.read_list = [self.stdout_fileno, self.stderr_fileno]
        self.write_list = [self.stdin_fileno]

    def write(self, mi_cmd_to_write,
            timeout_sec=DEFAULT_GDB_TIMEOUT_SEC,
            verbose=False,
            raise_error_on_timeout=True,
            read_response=True):
        """Write to gdb process. Block while parsing responses from gdb for a maximum of timeout_sec.

        A mutex is obtained before writing and released before returning

        Args:
            mi_cmd_to_write (str or list): String to write to gdb. If list, it is joined by newlines.
            timeout_sec (int): Maximum number of seconds to wait for response before exiting. Must be >= 0.
            verbose (bool): Be verbose in what is being written
            raise_error_on_timeout (bool): If read_response is True, raise error if no response is received
            read_response (bool): Block and read response. If there is a separate thread running,
            this can be false, and the reading thread read the output.
        Returns:
            List of parsed gdb responses if read_response is True, otherwise []
        Raises:
            NoGdbProcessError if there is no gdb subprocess running
            TypeError if mi_cmd_to_write is not valid
        """
        if not self.gdb_process:
            raise NoGdbProcessError('gdb process is not attached')
        elif timeout_sec < 0:
            print('warning: timeout_sec was negative, replacing with 0')
            timeout_sec = 0

        verbose = self.verbose or verbose

        # Ensure proper type of the mi command
        if type(mi_cmd_to_write) in [str, unicode]:
            pass
        elif type(mi_cmd_to_write) == list:
            mi_cmd_to_write = '\n'.join(mi_cmd_to_write)
        else:
            raise TypeError('The gdb mi command must a be str or list. Got ' + str(type(mi_cmd_to_write)))

        if verbose:
            print('\nwriting: %s' % mi_cmd_to_write)

        if not mi_cmd_to_write.endswith('\n'):
            mi_cmd_to_write_nl = mi_cmd_to_write + '\n'
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
                print('developer error: got unexpected fileno %d, event %d' % fileno)

        if read_response is True:
            return self.get_gdb_response(timeout_sec=timeout_sec, raise_error_on_timeout=raise_error_on_timeout, verbose=verbose)
        else:
            return []

    def get_gdb_response(self, timeout_sec=DEFAULT_GDB_TIMEOUT_SEC, raise_error_on_timeout=True, verbose=False):
        """Get response from GDB, and block while doing so. If GDB does not have any response ready to be read
        by timeout_sec, an exception is raised.

        A lock (mutex) is obtained before reading and released before returning. If the lock cannot
        be obtained, no data is read and an empty list is returned.

        Args:
            timeout_sec (float): Time to wait for reponse. Must be >= 0.
            raise_error_on_timeout (bool): Whether an exception should be raised if no response was found
            after timeout_sec
            verbose (bool): If true, more output it printed

        Returns:
            List of parsed GDB responses, returned from gdbmiparser.parse_response, with the
            additional key 'stream' which is either 'stdout' or 'stderr'

        Raises:
            GdbTimeoutError if response is not received within timeout_sec
            ValueError if select returned unexpected file number
            NoGdbProcessError if there is no gdb subprocess running
        """

        # validate inputs
        if not self.gdb_process:
            raise NoGdbProcessError('gdb process is not attached')
        elif timeout_sec < 0:
            print('warning: timeout_sec was negative, replacing with 0')
            timeout_sec = 0

        verbose = self.verbose or verbose

        self.mutex.acquire(MUTEX_AQUIRE_WAIT_TIME_SEC)

        if USING_WINDOWS:
            retval = self._get_responses_windows(timeout_sec, verbose)
        else:
            retval = self._get_responses_unix(timeout_sec, verbose)

        self.mutex.release()

        if not retval and raise_error_on_timeout:
            raise GdbTimeoutError('Did not get response from gdb after %s seconds' % DEFAULT_GDB_TIMEOUT_SEC)
        else:
            return retval

    def _get_responses_windows(self, timeout_sec, verbose):
        """Get responses on windows. Assume no support for select and use a while loop."""
        import time
        timeout_time_sec = time.time() + timeout_sec
        responses = []
        while(True):
            try:
                self.gdb_process.stdout.flush()
                raw_output = self.gdb_process.stdout.read()
                responses += self._get_responses_list(raw_output, 'stdout', verbose)
            except IOError:
                pass

            try:
                self.gdb_process.stderr.flush()
                raw_output = self.gdb_process.stderr.read()
                responses += self._get_responses_list(raw_output, 'stderr', verbose)
            except IOError:
                pass

            if time.time() > timeout_time_sec:
                break
        return responses

    def _get_responses_unix(self, timeout_sec, verbose):
        """Get responses on unix-like system. Use select to wait for output."""
        events, _, _ = select.select(self.read_list, [], [], timeout_sec)

        responses = []
        for fileno in events:
            # new data is ready to read
            if fileno == self.stdout_fileno:
                self.gdb_process.stdout.flush()
                raw_output = self.gdb_process.stdout.read()
                stream = 'stdout'

            elif fileno == self.stderr_fileno:
                self.gdb_process.stderr.flush()
                raw_output = self.gdb_process.stderr.read()
                stream = 'stderr'

            else:
                self.mutex.release()
                raise ValueError('Developer error. Got unexpected file number %d' % fileno)

            responses += self._get_responses_list(raw_output, stream, verbose)
        return responses

    def _get_responses_list(self, raw_output, stream, verbose):
        """Get parsed response list from string output
        Args:
            raw_output (unicode): gdb output to parse
            stream (str): either stdout or stderr
            verbose (bool): add verbose output when true
        """
        responses = []
        if not raw_output:
            return responses

        stripped_raw_response_list = [x.strip() for x in raw_output.decode().split('\n')]
        raw_response_list = list(filter(lambda x: x, stripped_raw_response_list))
        raw_response_list, self._buffer = _buffer_incomplete_responses(raw_response_list, self._buffer)

        # parse each response from gdb and put into a list
        for response in raw_response_list:
            if gdbmiparser.response_is_finished(response):
                pass
            else:
                parsed_response = gdbmiparser.parse_response(response)
                parsed_response['stream'] = stream

                responses.append(parsed_response)
                if verbose:
                    pprint(parsed_response)
        return responses

    def exit(self):
        """Terminate gdb process
        Returns: None"""
        if self.gdb_process:
            self.gdb_process.terminate()
        self.gdb_process = None
        return None


def _buffer_incomplete_responses(raw_response_list, buf):
    """It is possible for some of gdb's output to be read before it completely finished its response.
    In that case, a partial mi response was read, which cannot be parsed into structured data.
    We want to ALWAYS parse complete mi records. To do this, we store a buffer of gdb's
    output if gdb did not tell us it finished.

    Args:
        raw_response_list: List of gdb responses
        buf (str): Buffered gdb response from the past. This is incomplete and needs to be prepended to
        gdb's next output.

    Returns:
        (buffered_response_list, buffer)
    """

    if buf:
        # We have a partial response in our buffer. Combine it with
        # this response to hopefully form a complete response.
        raw_response_list[0] = buf + raw_response_list[0]
        # Erase buffer since we put it back into the output to be parsed.
        # If it's still not complete, it will be set back in this buffer with the
        # new output.
        buf = ''

    num_responses = len(raw_response_list)
    for i, response in enumerate(raw_response_list):
        # i is zero indexed
        # num_responses is one indexed
        if response.startswith('^done'):
            # we got a response from gdb, but we need to make sure
            # gdb completed writing its response and there isn't some more
            # mi output that we need. Output is ready to be parsed ONLY when we get (gdb) in
            # the next response.
            if (i + 1) > (num_responses - 1):
                # This was the last response, but it's missing the "finished"
                # response. Therefore we got an incomplete result which won't be parsed
                # correctly.

                # Store the partial response in a buffer and combine it with the next
                # response
                buf = response
                # don't process this incomplete response
                raw_response_list = raw_response_list[1:-1]

    return (raw_response_list, buf)


def _make_non_blocking(file_obj):
    """make file object non-blocking
    Windows doesn't have the fcntl module, but someone on
    stack overflow supplied this code as an answer, and it works
    http://stackoverflow.com/a/34504971/2893090"""

    if USING_WINDOWS:
        import msvcrt
        from ctypes import windll, byref, wintypes, WinError
        from ctypes.wintypes import HANDLE, DWORD, POINTER, BOOL
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
        import fcntl
        # Set the file status flag (F_SETFL) on the pipes to be non-blocking
        # so we can attempt to read from a pipe with no new data without locking
        # the program up
        fcntl.fcntl(file_obj, fcntl.F_SETFL, os.O_NONBLOCK)
