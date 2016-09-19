#!/usr/bin/env python3

"""
Unit tests

Run from top level directory: ./tests/test_app.py
"""

import unittest
from pygdbmi import example
from pygdbmi.gdbmiparser import parse_response, assert_match


class TestPyGdbMi(unittest.TestCase):

    def test_example(self):
        example.main(verbose=False)

    def test_parser(self):
        # Basic types
        assert_match(parse_response('^done'), {'type': 'result', 'payload': None, 'message': 'done'})
        assert_match(parse_response('~"done"'), {'type': 'console', 'payload': 'done', 'message': None})
        assert_match(parse_response('@"done"'), {"type": 'target', "payload": 'done', 'message': None})
        assert_match(parse_response('&"done"'), {"type": 'log', "payload": 'done', 'message': None})
        assert_match(parse_response('done'), {'type': 'output', 'payload': 'done', 'message': None})

        # escape sequences
        assert_match(parse_response('~""'), {"type": "console", "payload": "", 'message': None})
        assert_match(parse_response('~"\b\f\n\r\t\""'), {"type": "console", "payload": '\b\f\n\r\t\"', 'message': None})
        assert_match(parse_response('@""'), {"type": "target", "payload": "", 'message': None})
        assert_match(parse_response('@"\b\f\n\r\t\""'), {"type": "target", "payload": '\b\f\n\r\t\"', 'message': None})
        assert_match(parse_response('&""'), {"type": "log", "payload": "", 'message': None})
        assert_match(parse_response('&"\b\f\n\r\t\""'), {"type": "log", "payload": '\b\f\n\r\t\"', 'message': None})

        # Real world Dictionary
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
                                    'type': 'notify'})

def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPyGdbMi))

    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    return len(result.errors) + len(result.failures)


if __name__ == '__main__':
    main()
