#!/usr/bin/env python

"""
Run with `python -m example`
"""
import os
import shutil
import subprocess
import sys

from pygdbmi.gdbcontroller import GdbController


SAMPLE_C_CODE_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "tests", "sample_c_app"
)
SAMPLE_C_BINARY = os.path.join(SAMPLE_C_CODE_DIR, "pygdbmiapp.a")
PYTHON3 = sys.version_info.major == 3
USING_WINDOWS = os.name == "nt"

if USING_WINDOWS:
    SAMPLE_C_BINARY = SAMPLE_C_BINARY.replace("\\", "/")
    MAKE_CMD = "mingw32-make.exe"
else:
    MAKE_CMD = "make"


def main() -> None:
    """Build and debug an application programatically

    For a list of GDB MI commands, see https://www.sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html
    """

    # Build C program
    if not shutil.which(MAKE_CMD):
        print(
            'Could not find executable "%s". Ensure it is installed and on your $PATH.'
            % MAKE_CMD
        )
        exit(1)
    subprocess.check_output([MAKE_CMD, "-C", SAMPLE_C_CODE_DIR, "--quiet"])

    # Initialize object that manages gdb subprocess
    gdbmi = GdbController()

    # Send gdb commands. Gdb machine interface commands are easier to script around,
    # hence the name "machine interface".
    # Responses are automatically printed as they are received if verbose is True.
    # Responses are returned after writing, by default.

    # Load the file
    responses = gdbmi.write("-file-exec-and-symbols %s" % SAMPLE_C_BINARY)
    # Get list of source files used to compile the binary
    responses = gdbmi.write("-file-list-exec-source-files")
    # Add breakpoint
    responses = gdbmi.write("-break-insert main")
    # Run
    responses = gdbmi.write("-exec-run")
    responses = gdbmi.write("-exec-next")
    responses = gdbmi.write("-exec-next")
    responses = gdbmi.write("-exec-continue")  # noqa: F841

    # gdbmi.gdb_process will be None because the gdb subprocess (and its inferior
    # program) will be terminated
    gdbmi.exit()


if __name__ == "__main__":
    main()
