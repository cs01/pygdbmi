"""This module defines the `GdbController` class
which runs gdb as a subprocess and can write to it and read from it to get
structured output.
"""

import logging
import shutil
import subprocess
from typing import Dict, List, Optional, Union

from pygdbmi.constants import (
    DEFAULT_GDB_TIMEOUT_SEC,
    DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
)
from pygdbmi.IoManager import IoManager


__all__ = ["GdbController"]


DEFAULT_GDB_LAUNCH_COMMAND = ["gdb", "--nx", "--quiet", "--interpreter=mi3"]
logger = logging.getLogger(__name__)


class GdbController:
    def __init__(
        self,
        command: Optional[List[str]] = None,
        time_to_check_for_additional_output_sec: float = DEFAULT_TIME_TO_CHECK_FOR_ADDITIONAL_OUTPUT_SEC,
    ) -> None:
        """
        Run gdb as a subprocess. Send commands and receive structured output.
        Create new object, along with a gdb subprocess

        Args:
            command: Command to run in shell to spawn new gdb subprocess
            time_to_check_for_additional_output_sec: When parsing responses, wait this amout of time before exiting (exits before timeout is reached to save time). If <= 0, full timeout time is used.
        Returns:
            New GdbController object
        """

        if command is None:
            command = DEFAULT_GDB_LAUNCH_COMMAND

        if not any([("--interpreter=mi" in c) for c in command]):
            logger.warning(
                "Adding `--interpreter=mi3` (or similar) is recommended to get structured output. "
                + "See https://sourceware.org/gdb/onlinedocs/gdb/Mode-Options.html#Mode-Options."
            )
        self.abs_gdb_path = None  # abs path to gdb executable
        self.command: List[str] = command
        self.time_to_check_for_additional_output_sec = (
            time_to_check_for_additional_output_sec
        )
        self.gdb_process: Optional[subprocess.Popen] = None
        self._allow_overwrite_timeout_times = (
            self.time_to_check_for_additional_output_sec > 0
        )
        gdb_path = command[0]
        if not gdb_path:
            raise ValueError("a valid path to gdb must be specified")

        else:
            abs_gdb_path = shutil.which(gdb_path)
            if abs_gdb_path is None:
                raise ValueError(
                    'gdb executable could not be resolved from "%s"' % gdb_path
                )

            else:
                self.abs_gdb_path = abs_gdb_path

        self.spawn_new_gdb_subprocess()

    def spawn_new_gdb_subprocess(self) -> int:
        """Spawn a new gdb subprocess with the arguments supplied to the object
        during initialization. If gdb subprocess already exists, terminate it before
        spanwing a new one.
        Return int: gdb process id
        """
        if self.gdb_process:
            logger.debug(
                "Killing current gdb subprocess (pid %d)" % self.gdb_process.pid
            )
            self.exit()

        logger.debug(f'Launching gdb: {" ".join(self.command)}')

        # Use pipes to the standard streams
        self.gdb_process = subprocess.Popen(
            self.command,
            shell=False,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        assert self.gdb_process.stdin is not None
        assert self.gdb_process.stdout is not None
        self.io_manager = IoManager(
            self.gdb_process.stdin,
            self.gdb_process.stdout,
            self.gdb_process.stderr,
            self.time_to_check_for_additional_output_sec,
        )
        return self.gdb_process.pid

    def get_gdb_response(
        self,
        timeout_sec: float = DEFAULT_GDB_TIMEOUT_SEC,
        raise_error_on_timeout: bool = True,
    ) -> List[Dict]:
        """Get gdb response. See IoManager.get_gdb_response() for details"""
        return self.io_manager.get_gdb_response(timeout_sec, raise_error_on_timeout)

    def write(
        self,
        mi_cmd_to_write: Union[str, List[str]],
        timeout_sec: float = DEFAULT_GDB_TIMEOUT_SEC,
        raise_error_on_timeout: bool = True,
        read_response: bool = True,
    ) -> List[Dict]:
        """Write command to gdb. See IoManager.write() for details"""
        return self.io_manager.write(
            mi_cmd_to_write, timeout_sec, raise_error_on_timeout, read_response
        )

    def exit(self) -> None:
        """Terminate gdb process"""
        if self.gdb_process:
            self.gdb_process.terminate()
            self.gdb_process.wait()
            self.gdb_process.communicate()
        self.gdb_process = None
        return None
