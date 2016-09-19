import subprocess
import os
import time
import fcntl
from pprint import pprint
from pygdbmi import gdbmiparser
import sys

PYTHON3 = sys.version_info.major == 3
GDB_TIMEOUT_SEC = 0.5
unicode = str if PYTHON3 else unicode


class GdbController():
    """
    Run gdb as a subprocess. Send commands and recieve structured output.
    """

    def __init__(self, c_binary_path=None, gdb_binary='gdb', gdb_args=['--nx', '--quiet', '--interpreter=mi2'], verbose=False):
        self.cmds_written = []
        self.gdb_io_thread = None
        self.verbose = verbose

        if c_binary_path:
            abs_c_binary = os.path.abspath(c_binary_path)

            if not os.path.isfile(abs_c_binary):
                raise ValueError('application does not exist at path "%s"' % abs_c_binary)

            cmd = [gdb_binary] + gdb_args + [abs_c_binary]
        else:
            cmd = [gdb_binary] + gdb_args

        if verbose:
            print('Launching gdb: "%s"' % ' '.join(cmd))

        self.gdb_process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        fcntl.fcntl(self.gdb_process.stdout, fcntl.F_SETFL, os.O_NONBLOCK)

    def write(self, mi_cmd_to_write,
                                    timeout_sec=GDB_TIMEOUT_SEC,
                                    verbose=False,
                                    raise_error_on_timeout=True,
                                    flush_child_stdout=False):
        """Write to gdb process. Block while parsing responses from gdb for a maximum of timeout_sec.
        Args:
            mi_cmd_to_write (str or list): String to write to gdb. If list, it is joined by newlines.
            timeout_sec (int): Maximum number of seconds to wait for response before exiting
            verbose (bool): Be verbose in what is being written
            flush_child_output (bool): call fflush(0)
        Returns:
            List of parsed gdb responses
        """
        if not self.gdb_process:
            raise ValueError('gdb process is not attached')

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

        mi_cmd_to_write_nl = mi_cmd_to_write + '\n'
        if flush_child_stdout:
            mi_cmd_to_write_nl += 'call fflush(0\n'

        self.cmds_written.append(mi_cmd_to_write_nl)
        self.gdb_process.stdin.write(mi_cmd_to_write_nl.encode())
        self.gdb_process.stdin.flush()

        return self.get_gdb_response(timeout_sec=timeout_sec,
                raise_error_on_timeout=raise_error_on_timeout,
                verbose=verbose)

    def get_gdb_response(self, timeout_sec=GDB_TIMEOUT_SEC, raise_error_on_timeout=True, verbose=False):
        """Get response from GDB, and block while doing so. If GDB does not complete its response in
        timeout_sec, a ValueError is raised.
        Returns:
            List of parsed GDB responses
            Rasies ValueError if response is not recieved within timeout_sec
        """
        verbose = self.verbose or verbose
        timeout_time = time.time() + timeout_sec
        self.gdb_process.stdout.flush()
        self.response = []
        while(True):

            line = None

            try:
                line = self.gdb_process.stdout.read()
            except IOError:
                pass

            if line:
                stripped_raw_response_list = [x.strip() for x in line.decode().split('\n')]
                # Remove empty responses
                raw_response_list = list(filter(lambda x: x, stripped_raw_response_list))
                for response in raw_response_list:
                    if gdbmiparser.response_is_finished(response):
                        timeout_time = time.time() + timeout_sec
                    else:
                        parsed_response = gdbmiparser.parse_response(response)
                        self.response.append(parsed_response)
                        if verbose:
                            pprint(parsed_response)

            elif time.time() > timeout_time:
                if not self.response and raise_error_on_timeout:
                    raise ValueError('Did not get response from gdb after %s seconds' % GDB_TIMEOUT_SEC)
                else:
                    return self.response

    def exit(self):
        """Exit gdb and terminate gdb process"""
        response = []
        if self.gdb_process:
            response += self.write('interrupt')
            response += self.write('-gdb-exit')
            self.gdb_process.terminate()
        self.gdb_process = None
        self.gdb_io_thread = None
        return response
