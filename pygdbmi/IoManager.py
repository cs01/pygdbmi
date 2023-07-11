"""This module defines the `IoManager` class
which manages I/O for file objects connected to an existing gdb process
or pty.
"""
import logging
import queue
import select
import threading
from typing import IO, Dict, List, Optional, Union

from . import gdbmiparser
from .constants import USING_WINDOWS


__all__ = ["IoManager"]


logger = logging.getLogger(__name__)


def write_thread(stdin, in_queue):
    while True:
        command = in_queue.get()
        # if we put a None in the command queue the thread needs to stop
        if command is None:
            break

        if USING_WINDOWS:
            # select not implemented in windows for pipes
            # assume it's always ready
            outputready = [stdin.fileno()]
        else:
            # The timeout for the select is hardcoded to 1s because it is not a public interface.
            _, outputready, _ = select.select([], [stdin.fileno()], [], 1)
        for fileno in outputready:
            if fileno == stdin.fileno():
                # ready to write

                if not command.endswith("\n"):
                    command += "\n"
                stdin.write(command)  # type: ignore
                # must flush, otherwise gdb won't realize there is data
                # to evaluate, and we won't get a response
                stdin.flush()  # type: ignore
            else:
                logger.error("got unexpected fileno %d" % fileno)


def read_thread(stream, stream_name, out_queue):
    while True:
        try:
            stream.flush()
            line = stream.readline()
        except ValueError:
            break

        if USING_WINDOWS:
            line = line.replace(b"\r", b"\n")
        parsed_response = gdbmiparser.parse_response(line)
        parsed_response["stream"] = stream_name

        out_queue.put(parsed_response)


class IoManager:
    def __init__(
        self,
        stdin: IO[str],
        stdout: IO[str],
        stderr: Optional[IO[str]],
    ) -> None:
        """
        Manage I/O for file objects created before calling this class
        This can be useful if the gdb process is managed elsewhere, or if a
        pty is used.
        """

        self.in_queue = queue.Queue()
        self.out_queue = queue.Queue()

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

        self.write_tread = threading.Thread(
            target=write_thread, args=(self.stdin, self.in_queue), daemon=True
        )

        self.read_stdout_thread = threading.Thread(
            target=read_thread, args=(self.stdout, "stdout", self.out_queue)
        )
        self.read_stderr_thread = threading.Thread(
            target=read_thread, args=(self.stderr, "stderr", self.out_queue)
        )

        self.write_tread.start()
        self.read_stderr_thread.start()
        self.read_stdout_thread.start()

    def get_gdb_response(
        self,
    ) -> List[Dict]:
        """Get response from GDB without blocking. If GDB does not have any response ready to be read
        it returns an empty list

        Returns:
            List of parsed GDB responses, returned from gdbmiparser.parse_response, with the
            additional key 'stream' which is either 'stdout' or 'stderr'
        """

        responses = []
        # read all the elements of the queue
        while True:
            try:
                res = self.out_queue.get_nowait()
                responses.append(res)
            except queue.Empty:
                break

        return responses

    def write(
        self,
        mi_cmd_to_write: Union[str, List[str]],
    ):
        """Write to gdb process.

        Args:
            mi_cmd_to_write: String to write to gdb. If list, it is joined by newlines.
        Returns:
            None
        Raises:
            TypeError: if mi_cmd_to_write is not valid
        """
        # self.verify_valid_gdb_subprocess()

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

        self.in_queue.put_nowait(mi_cmd_to_write_nl)

    def terminate(self):
        # ends the read/write threads when the iomanager is destroyed
        self.in_queue.put(None)

        self.write_tread.join()
        self.read_stdout_thread.join()
        self.read_stderr_thread.join()

    def __del__(self):
        self.terminate()
