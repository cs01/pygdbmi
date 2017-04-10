#!/usr/bin/env python3

"""
Unit tests

Run from top level directory: ./tests/test_app.py
"""

import os
import unittest
import subprocess
from pygdbmi.gdbmiparser import parse_response, assert_match
from pygdbmi.gdbcontroller import GdbController, NoGdbProcessError


class TestPyGdbMi(unittest.TestCase):

    def test_parser(self):
        """Test that the parser returns dictionaries from gdb mi strings as expected"""

        # Test basic types
        assert_match(parse_response('^done'), {'type': 'result', 'payload': None, 'message': 'done', "token": None})
        assert_match(parse_response('~"done"'), {'type': 'console', 'payload': 'done', 'message': None})
        assert_match(parse_response('@"done"'), {"type": 'target', "payload": 'done', 'message': None})
        assert_match(parse_response('&"done"'), {"type": 'log', "payload": 'done', 'message': None})
        assert_match(parse_response('done'), {'type': 'output', 'payload': 'done', 'message': None})

        # Test escape sequences
        assert_match(parse_response('~""'), {"type": "console", "payload": "", 'message': None})
        assert_match(parse_response('~"\b\f\n\r\t\""'), {"type": "console", "payload": '\b\f\n\r\t\"', 'message': None})
        assert_match(parse_response('@""'), {"type": "target", "payload": "", 'message': None})
        assert_match(parse_response('@"\b\f\n\r\t\""'), {"type": "target", "payload": '\b\f\n\r\t\"', 'message': None})
        assert_match(parse_response('&""'), {"type": "log", "payload": "", 'message': None})
        assert_match(parse_response('&"\b\f\n\r\t\""'), {"type": "log", "payload": '\b\f\n\r\t\"', 'message': None})

        # Test a real world Dictionary
        assert_match(parse_response('=breakpoint-modified,bkpt={number="1",empty_arr=[],type="breakpoint",disp="keep",enabled="y",addr="0x000000000040059c",func="main",file="hello.c",fullname="/home/git/pygdbmi/tests/sample_c_app/hello.c",line="9",thread-groups=["i1"],times="1",original-location="hello.c:9"}'),
                                    {'message': 'breakpoint-modified',
                                    'payload': {'bkpt': {'addr': '0x000000000040059c',
                                                         'disp': 'keep',
                                                         'enabled': 'y',
                                                         'file': 'hello.c',
                                                         'fullname': '/home/git/pygdbmi/tests/sample_c_app/hello.c',
                                                         'func': 'main',
                                                         'line': '9',
                                                         'number': '1',
                                                         'empty_arr': [],
                                                         'original-location': 'hello.c:9',
                                                         'thread-groups': ['i1'],
                                                         'times': '1',
                                                         'type': 'breakpoint'}},
                                     'type' : 'notify',
                                     'token': None})

        #Test records with token
        assert_match(parse_response('1342^done'), {'type': 'result', 'payload': None, 'message': 'done', "token": 1342})

    def test_controller(self):
        """Build a simple C program, then run it with GdbController and verify the output is parsed
        as expected"""
        SAMPLE_C_CODE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'sample_c_app')
        SAMPLE_C_BINARY = os.path.join(SAMPLE_C_CODE_DIR, 'a.out')
        # Build C program
        subprocess.check_output(["make", "-C", SAMPLE_C_CODE_DIR, '--quiet'])

        # Initialize object that manages gdb subprocess
        gdbmi = GdbController()

        # Load the binary and its symbols in the gdb subprocess
        responses = gdbmi.write('-file-exec-and-symbols %s' % SAMPLE_C_BINARY, timeout_sec=1)

        # Verify output was parsed into a list of responses
        assert(len(responses) != 0)
        response = responses[0]
        assert(set(response.keys()) == set(['message', 'type', 'payload', 'stream', 'token']))
        assert(response['message'] == 'thread-group-added')
        assert(response['type'] == 'notify')
        assert(response['payload'] == {'id': 'i1'})
        assert(response['stream'] == 'stdout')
        assert(response['token'] is None)

        responses = gdbmi.write(['-file-list-exec-source-files', '-break-insert main'])
        assert(len(responses) != 0)

        # Close gdb subprocess
        responses = gdbmi.exit()
        assert(responses is None)
        assert(gdbmi.gdb_process is None)

        # Test NoGdbProcessError exception
        got_no_process_exception = False
        try:
            responses = gdbmi.write('-file-exec-and-symbols %s' % SAMPLE_C_BINARY)
        except NoGdbProcessError:
            got_no_process_exception = True
        assert(got_no_process_exception is True)


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPyGdbMi))

    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    num_failures = len(result.errors) + len(result.failures)
    return num_failures


if __name__ == '__main__':
    main()
