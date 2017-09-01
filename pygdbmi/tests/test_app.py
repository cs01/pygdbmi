#!/usr/bin/env python3

"""
Unit tests

Run from top level directory: ./tests/test_app.py
"""

import math
import os
import random
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
                                     'type': 'notify',
                                     'token': None})

        # Test records with token
        assert_match(parse_response('1342^done'), {'type': 'result', 'payload': None, 'message': 'done', "token": 1342})

    def _get_c_program(self):
        """build c program and return path to binary"""
        FILENAME = 'pygdbmiapp.a'
        SAMPLE_C_CODE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'sample_c_app')
        SAMPLE_C_BINARY = os.path.join(SAMPLE_C_CODE_DIR, FILENAME)
        # Build C program
        subprocess.check_output(["make", "-C", SAMPLE_C_CODE_DIR, '--quiet'])
        return SAMPLE_C_BINARY

    def test_controller(self):
        """Build a simple C program, then run it with GdbController and verify the output is parsed
        as expected"""

        # Initialize object that manages gdb subprocess
        gdbmi = GdbController()

        c_binary_path = self._get_c_program()
        # Load the binary and its symbols in the gdb subprocess
        responses = gdbmi.write('-file-exec-and-symbols %s' % c_binary_path, timeout_sec=1)

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

        responses = gdbmi.write(['-exec-run', '-exec-continue'], timeout_sec=3)
        found_match = False
        for r in responses:
            if r.get('payload', '') == '  leading spaces should be preserved. So should trailing spaces.  ':
                found_match = True
        assert(found_match is True)

        # Close gdb subprocess
        responses = gdbmi.exit()
        assert(responses is None)
        assert(gdbmi.gdb_process is None)

        # Test NoGdbProcessError exception
        got_no_process_exception = False
        try:
            responses = gdbmi.write('-file-exec-and-symbols %s' % c_binary_path)
        except NoGdbProcessError:
            got_no_process_exception = True
        assert(got_no_process_exception is True)

    def test_controller_buffer(self):
        """test that a partial response gets successfully buffered
        by the controller, then fully read when more data arrives"""
        gdbmi = GdbController()
        to_be_buffered = b'^done,BreakpointTable={nr_rows="1",nr_'

        stream = 'teststream'
        verbose = False
        response = gdbmi._get_responses_list(to_be_buffered, stream, verbose)
        # Nothing should have been parsed yet
        assert(len(response) == 0)
        assert(gdbmi.incomplete_packet[stream] == to_be_buffered)

        remaining_gdb_output = b'cols="6"}\n(gdb) \n'
        response = gdbmi._get_responses_list(remaining_gdb_output, stream, verbose)

        # Should have parsed response at this point
        assert(len(response) == 1)
        r = response[0]
        assert(r['stream'] == 'teststream')
        assert(r['type'] == 'result')
        assert(r['payload'] == {'BreakpointTable': {'nr_cols': '6', 'nr_rows': '1'}})

        """
        The following code loads the sample corpus, extracts a random set of
        responses and for each one it parses them both as a single packet
        and a series of randomly split packets. 

        Each packet size will range between 25% and 50% of the complete packet.
        """
        test_directory = os.path.dirname(os.path.abspath(__file__))
        datafile_path = '%s/response_samples.txt' % (test_directory)

        with open(datafile_path, 'rb') as datafile:
            samples = datafile.read()
            samples = samples.strip()

        samples = samples.splitlines()
        samples = [b''.join([sample, b'\n']) for sample in samples]

        random.shuffle(samples)

        samples = [[sample, None, None] for sample in samples[:10]]

        for sample in samples:
            gdbmi.discard_incomplete_packets()

            sample[1] = gdbmi._get_responses_list(sample[0], stream, False)

        for sample in samples:
            sample_data = sample[0]
            packet_chunks = []
            packet_chunk_count = random.randint(1, 10)
            maximum_chunk_length = len(sample_data) * random.uniform(0.25, 0.50)
            maximum_chunk_length = math.ceil(maximum_chunk_length)

            for packet_chunk_index in range(packet_chunk_count):
                packet_chunk_length = random.randint(1, maximum_chunk_length)
                packet_chunk = sample_data[:packet_chunk_length]
                packet_chunks.append(packet_chunk)

                sample_data = sample_data[len(packet_chunk):]

                if packet_chunk_length != len(packet_chunk):
                    break

            if sample_data:  # Append the remainder
                packet_chunks.append(sample_data)

            gdbmi.discard_incomplete_packets()

            sample[1] = gdbmi._get_responses_list(sample[0], stream, False)

            gdbmi.discard_incomplete_packets()

            for packet_chunk in packet_chunks:
                sample[2] = gdbmi._get_responses_list(packet_chunk, stream, False)

            assert(sample[1] == sample[2])

        samples = None



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
