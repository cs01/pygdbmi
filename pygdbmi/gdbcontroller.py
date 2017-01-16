import subprocess
import os
import fcntl
from pprint import pprint
from pygdbmi import gdbmiparser
import sys
import select
from distutils.spawn import find_executable
from multiprocessing import Lock

PYTHON3 = sys.version_info.major == 3
GDB_TIMEOUT_SEC = 1
MUTEX_AQUIRE_WAIT_TIME_SEC = int(1)
unicode = str if PYTHON3 else unicode

SEC_TO_MSEC = 1000

EVENT_LOOKUP = {
    select.POLLIN: 'POLLIN',
    select.POLLPRI: 'POLLPRI',
    select.POLLOUT: 'POLLOUT',
    select.POLLERR: 'POLLERR',
    select.POLLHUP: 'POLLHUP',
    select.POLLNVAL: 'POLLNVAL',
}


class GdbController():
    """
    Run gdb as a subprocess. Send commands and recieve structured output.
    """

    def __init__(self, gdb_path='gdb', gdb_args=['--nx', '--quiet', '--interpreter=mi2'], verbose=False):
        self.verbose = verbose
        self.epoll = select.epoll()
        self.epoll_write = select.epoll()
        self.mutex = Lock()
        self.abs_gdb_path = None  # abs path to gdb executable
        self.cmd = []  # the shell command to run gdb

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
        self.gdb_process = subprocess.Popen(self.cmd, shell=False, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        # Set the file status flag (F_SETFL) on the pipes to be non-blocking
        # so we can attempt to read from a pipe with no new data without locking
        # the program up
        fcntl.fcntl(self.gdb_process.stdout, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.gdb_process.stderr, fcntl.F_SETFL, os.O_NONBLOCK)

        # save file numbers for use later
        self.stdout_fileno = self.gdb_process.stdout.fileno()
        self.stderr_fileno = self.gdb_process.stderr.fileno()
        self.stdin_fileno = self.gdb_process.stdin.fileno()

        # register stdout and stderr for epoll
        self.epoll.register(self.gdb_process.stdout.fileno(), select.EPOLLIN)  # There is data to read
        self.epoll.register(self.gdb_process.stderr.fileno(), select.EPOLLIN)  # There is data to read
        self.epoll_write.register(self.gdb_process.stdin.fileno(), select.POLLOUT)  # Ready for output: writing will not block


    def write(self, mi_cmd_to_write,
                                    timeout_sec=GDB_TIMEOUT_SEC,
                                    verbose=False,
                                    raise_error_on_timeout=True,
                                    read_response=False):
        """Write to gdb process. Block while parsing responses from gdb for a maximum of timeout_sec.

        A mutex is obtained before writing and released before returning

        Args:
            mi_cmd_to_write (str or list): String to write to gdb. If list, it is joined by newlines.
            timeout_sec (int): Maximum number of seconds to wait for response before exiting. Must be >= 0.
            verbose (bool): Be verbose in what is being written
            flush_child_output (bool): call fflush(0)
            read_response (bool): Block and read response. If there is a separate thread running,
                                    this can be false, and the reading thread can just pick up the output.
        Returns:
            List of parsed gdb responses if read_response is True, otherwise []
        """
        if not self.gdb_process:
            raise ValueError('gdb process is not attached')
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
            raise ValueError('The gdb mi command must a be str or list. Got ' + str(type(mi_cmd_to_write)))

        if verbose:
            print('\nwriting: %s' % mi_cmd_to_write)

        if not mi_cmd_to_write.endswith('\n'):
            mi_cmd_to_write_nl = mi_cmd_to_write + '\n'

        timeout_msec = timeout_sec * SEC_TO_MSEC
        events = self.epoll_write.poll(timeout_msec)
        for fileno, event in events:
            if event == select.EPOLLOUT and fileno == self.stdin_fileno:
                # ready to write
                # self.gdb_process.stdin.flush()
                self.gdb_process.stdin.write(mi_cmd_to_write_nl.encode())
                # line = self.gdb_process.stdout.read()
            else:
                raise ValueError('got fileno %d, event %d' % (fileno, event))

        if read_response is True:
            return self.get_gdb_response(timeout_sec=timeout_sec,
                    raise_error_on_timeout=raise_error_on_timeout,
                    verbose=verbose)
        else:
            return []

    def get_gdb_response(self, timeout_sec=GDB_TIMEOUT_SEC, raise_error_on_timeout=True, verbose=False):
        """Get response from GDB, and block while doing so. If GDB does not have any response ready to be read
        by timeout_sec, a ValueError is raised.

        A mutex is obtained before reading and released before returning

        Args:
            timeout_sec (float): Time to wait for reponse. Must be >= 0.
            raise_error_on_timeout (bool): Whether an exception should be raised if no response was found
                after timeout_sec
            verbose (bool): If true, more output it printed

        Returns:
            List of parsed GDB responses
            Raises ValueError if response is not recieved within timeout_sec
        """

        # validate inputs
        if not self.gdb_process:
            raise ValueError('gdb process is not attached')
        elif timeout_sec < 0:
            print('warning: timeout_sec was negative, replacing with 0')
            timeout_sec = 0

        verbose = self.verbose or verbose

        self.mutex.acquire(MUTEX_AQUIRE_WAIT_TIME_SEC)
        self.gdb_process.stdout.flush()


        retval = []
        timeout_msec = timeout_sec * SEC_TO_MSEC
        events = self.epoll.poll(timeout_msec)
        for fileno, event in events:
            if event == select.EPOLLIN:
                # new data is ready to read
                if fileno == self.stdout_fileno:
                    line = self.gdb_process.stdout.read()

                elif fileno == self.stderr_fileno:
                    line = self.gdb_process.stderr.read()

                else:
                    self.mutex.release()
                    raise ValueError('Developer error. Got unexpected file number %d' % fileno)
            else:
                # This is unexpected
                print('unexpected event ' + EVENT_LOOKUP[event])

            # Split output on newlines
            stripped_raw_response_list = [x.strip() for x in line.decode().split('\n')]

            # Remove empty responses
            raw_response_list = list(filter(lambda x: x, stripped_raw_response_list))

            # parse each response from gdb and put into a list
            for response in raw_response_list:
                if gdbmiparser.response_is_finished(response):
                    pass
                else:
                    parsed_response = gdbmiparser.parse_response(response)
                    retval.append(parsed_response)
                    if verbose:
                        pprint(parsed_response)

        self.mutex.release()

        if not retval and raise_error_on_timeout:
            raise ValueError('Did not get response from gdb after %s seconds' % GDB_TIMEOUT_SEC)
        else:
            return retval

    def exit(self):
        """Terminate gdb process"""
        if self.gdb_process:
            self.gdb_process.terminate()
        self.gdb_process = None
        return None
