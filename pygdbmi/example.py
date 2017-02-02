#!/usr/bin/env python
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
    print(response)
    response = gdbmi.write('-file-list-exec-source-files')
    print(response)
    response = gdbmi.write('-break-insert main')
    print(response)
    response = gdbmi.write('-exec-run')
    print(response)
    response = gdbmi.write('next')
    print(response)
    response = gdbmi.write('next')
    print(response)
    print(response)
    response = gdbmi.write('whatis i')
    print(response)
    response = gdbmi.write('continue')
    print(response)
    response = gdbmi.exit()
    print(response)

if __name__ == '__main__':
    main()
