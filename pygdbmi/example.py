#!/usr/bin/env python3
from pygdbmi.gdbcontroller import GdbController
import subprocess
import os

SAMPLE_C_CODE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tests/sample_c_app')
SAMPLE_C_BINARY = os.path.join(SAMPLE_C_CODE_DIR, 'a.out')

def main(verbose=True):
    # Build C program
    subprocess.check_output(["make", "-C", SAMPLE_C_CODE_DIR, '--quiet'])

    # Initialize gdb with C binary
    gdbmi = GdbController(verbose=verbose)
    # Send gdb machine interface commands, and get responses. Responses are
    # automatically printed as they are received if verbose is True
    response = gdbmi.write('-file-exec-and-symbols %s' % SAMPLE_C_BINARY)
    response = gdbmi.write('-file-list-exec-source-files')
    response = gdbmi.write('-break-insert main')
    response = gdbmi.write('-exec-run')
    response = gdbmi.write('next')
    response = gdbmi.write('next')
    response = gdbmi.write('whatis i')
    response = gdbmi.write('continue')
    response = gdbmi.exit()

if __name__ == '__main__':
    main()
