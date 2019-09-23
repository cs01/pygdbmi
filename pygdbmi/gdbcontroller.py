"""GdbController class to programatically run gdb and get structured output"""

import logging
import os
import signal
import subprocess
import time
from distutils.spawn import find_executable
from shlex import quote
from typing import IO, Any, List, Optional, Tuple

from pygdbmi.constants import (
    DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
    USING_WINDOWS,
)
from pygdbmi.gdbfiledescriptorcontroller import GdbFileDescriptorController

if USING_WINDOWS:
    import msvcrt  # pragma: no cover
    from ctypes import windll, byref, wintypes, WinError, POINTER  # type: ignore
    from ctypes.wintypes import HANDLE, DWORD, BOOL
else:
    import fcntl

SIGNAL_NAME_TO_NUM = {}
for n in dir(signal):
    if n.startswith("SIG") and "_" not in n:
        SIGNAL_NAME_TO_NUM[n.upper()] = getattr(signal, n)


class NoGdbProcessError(ValueError):
    """Raise when trying to interact with gdb subprocess, but it does not exist.
    It may have been killed and removed, or failed to initialize for some reason.
    """

    pass


class GdbController(GdbFileDescriptorController):
    """
    Run gdb as a subprocess. Send commands and receive structured output.
    Create new object, along with a gdb subprocess

    Args:
        gdb_path (str): Command to run in shell to spawn new gdb subprocess
        gdb_args (list): Arguments to pass to shell when spawning new gdb subprocess
        time_to_check_for_additional_output_sec (float): When parsing responses, wait this amout of time before exiting (exits before timeout is reached to save time). If <= 0, full timeout time is used.
        verbose (bool): Print verbose output if True
    Returns:
        New GdbController object
    """

    default_gdb_args = ["--nx", "--quiet", "--interpreter=mi2"]

    def __init__(
        self,
        gdb_path: str = "gdb",
        gdb_args: Optional[List[str]] = None,
        time_to_check_for_additional_output_sec: float = DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
    ):
        self._attach_logger()
        self._terminated = False
        if gdb_args is None:
            gdb_args = self.default_gdb_args

        self.cmd = []  # type: List[str]
        self.time_to_check_for_additional_output_sec = (
            time_to_check_for_additional_output_sec
        )
        self.gdb_process = None  # type: Optional[subprocess.Popen]
        self._allow_overwrite_timeout_times = (
            self.time_to_check_for_additional_output_sec > 0
        )

        self.abs_gdb_path = find_executable(gdb_path)
        if self.abs_gdb_path is None:
            raise ValueError(
                'gdb executable could not be resolved from "%s"' % gdb_path
            )
        self.cmd = [self.abs_gdb_path] + gdb_args

        stdin, stdout = self._spawn_gdb_subprocess()
        super().__init__(stdin, stdout)

    def _attach_logger(self):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        unique_number = time.time()
        self.logger = logging.getLogger(__name__ + "." + str(unique_number))
        self.logger.propagate = False
        self.logger.addHandler(handler)

    def get_subprocess_cmd(self):
        """Returns the shell-escaped string used to invoke the gdb subprocess.
        This is a string that can be executed directly in a shell.
        """
        return " ".join(quote(c) for c in self.cmd)

    def _spawn_gdb_subprocess(self) -> Tuple[IO[Any], IO[Any]]:
        """Spawn a new gdb subprocess with the arguments supplied to the object
        during initialization. If gdb subprocess already exists, terminate it before
        spanwing a new one.
        Return int: gdb process id
        """
        if self.gdb_process or self._terminated:
            raise ValueError("Cannot restart new gdb subprocess")

        self.logger.debug('Launching gdb: "%s"' % " ".join(self.cmd))

        self.gdb_process = subprocess.Popen(
            self.cmd,
            shell=False,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            bufsize=0,
        )

        _make_non_blocking(self.gdb_process.stdout)
        return (self.gdb_process.stdin, self.gdb_process.stdout)

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

    def terminate(self) -> None:
        """Terminate gdb process """
        if self.gdb_process:
            self.gdb_process.terminate()
            self.gdb_process.communicate()
        else:
            self.logger.info("Process has already been terminated")
        self.gdb_process = None
        self._terminated = True
        return None


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
