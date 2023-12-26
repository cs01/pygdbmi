#!/usr/bin/env python3
"""
Unit tests

Run from top level directory: ./tests/test_app.py
"""

import os
import random
import shutil
import subprocess
import time

import pytest

from pygdbmi.constants import USING_WINDOWS, GdbTimeoutError
from pygdbmi.gdbcontroller import GdbController


if USING_WINDOWS:
    MAKE_CMD = "mingw32-make.exe"
else:
    MAKE_CMD = "make"


def _get_c_program(makefile_target_name: str, binary_name: str) -> str:
    """build c program and return path to binary"""
    if not shutil.which(MAKE_CMD):
        raise AssertionError(
            'Could not find executable "%s". Ensure it is installed and on your $PATH.'
            % MAKE_CMD
        )

    SAMPLE_C_CODE_DIR = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "sample_c_app"
    )
    binary_path = os.path.join(SAMPLE_C_CODE_DIR, binary_name)
    # Build C program
    subprocess.check_output(
        [MAKE_CMD, makefile_target_name, "-C", SAMPLE_C_CODE_DIR, "--quiet"]
    )
    return binary_path


def test_controller() -> None:
    """Build a simple C program, then run it with GdbController and verify the output is parsed
    as expected"""

    # Initialize object that manages gdb subprocess
    gdbmi = GdbController()

    c_hello_world_binary = _get_c_program("hello", "pygdbmiapp.a")

    if USING_WINDOWS:
        c_hello_world_binary = c_hello_world_binary.replace("\\", "/")
    # Load the binary and its symbols in the gdb subprocess
    responses = gdbmi.write(
        "-file-exec-and-symbols %s" % c_hello_world_binary, timeout_sec=1
    )

    # Verify output was parsed into a list of responses
    assert len(responses) != 0
    response = responses[0]
    assert set(response.keys()) == {"message", "type", "payload", "stream", "token"}

    assert response["message"] == "thread-group-added"
    assert response["type"] == "notify"
    assert response["payload"] == {"id": "i1"}
    assert response["stream"] == "stdout"
    assert response["token"] is None

    # Verify exits quickly if return_on_result is True
    t0 = time.monotonic()
    responses = gdbmi.write(["-rubbish"], return_on_result=True)
    t1 = time.monotonic()
    duration = t1 - t0
    assert len(responses) != 0
    assert duration < 0.01

    responses = gdbmi.write(["-file-list-exec-source-files", "-break-insert main"])
    assert len(responses) != 0

    responses = gdbmi.write(["-exec-run", "-exec-continue"], timeout_sec=3)

    # Test GdbTimeoutError exception
    with pytest.raises(GdbTimeoutError):
        gdbmi.get_gdb_response(timeout_sec=0)

    # Close gdb subprocess
    gdbmi.exit()
    assert gdbmi.gdb_process is None

    # Test NoGdbProcessError exception
    got_no_process_exception = False
    try:
        responses = gdbmi.write("-file-exec-and-symbols %s" % c_hello_world_binary)
    except OSError:
        got_no_process_exception = True
    assert got_no_process_exception is True

    # Respawn and test signal handling
    gdbmi.spawn_new_gdb_subprocess()
    responses = gdbmi.write(
        "-file-exec-and-symbols %s" % c_hello_world_binary, timeout_sec=1
    )
    responses = gdbmi.write(["-break-insert main", "-exec-run"])


@pytest.mark.skip()
def test_controller_buffer_randomized() -> None:
    """
    The following code reads a sample gdb mi stream randomly to ensure partial
    output is read and that the buffer is working as expected on all streams.
    """
    # Note that this code, since it was written, broke even furthere. For instance, some of the
    # attributes accessed by this test don't exist any more (see the `type: ignore[attr-defined]`
    # comments).

    test_directory = os.path.dirname(os.path.abspath(__file__))
    datafile_path = "%s/response_samples.txt" % (test_directory)

    gdbmi = GdbController()
    for stream in gdbmi._incomplete_output.keys():  # type: ignore[attr-defined]
        responses = []
        with open(datafile_path, "rb") as f:
            while True:
                n = random.randint(1, 100)
                # read random number of bytes to simulate incomplete responses
                gdb_mi_simulated_output = f.read(n)
                if gdb_mi_simulated_output == b"":
                    break  # EOF

                # let the controller try to parse this additional raw gdb output
                responses += gdbmi._get_responses_list(gdb_mi_simulated_output, stream)  # type: ignore[attr-defined]
        assert len(responses) == 141

        # spot check a few
        assert responses[0] == {
            "message": None,
            "type": "console",
            "payload": "0x00007fe2c5c58920 in __nanosleep_nocancel () at ../sysdeps/unix/syscall-template.S:81\\n",
            "stream": stream,
        }
        if not USING_WINDOWS:
            # can't get this to pass in windows
            assert responses[71] == {
                "stream": stream,
                "message": "done",
                "type": "result",
                "payload": None,
                "token": None,
            }
            assert responses[82] == {
                "message": None,
                "type": "output",
                "payload": "The inferior program printed this! Can you still parse it?",
                "stream": stream,
            }
        assert responses[137] == {
            "stream": stream,
            "message": "thread-group-exited",
            "type": "notify",
            "payload": {"exit-code": "0", "id": "i1"},
            "token": None,
        }
        assert responses[138] == {
            "stream": stream,
            "message": "thread-group-started",
            "type": "notify",
            "payload": {"pid": "48337", "id": "i1"},
            "token": None,
        }
        assert responses[139] == {
            "stream": stream,
            "message": "tsv-created",
            "type": "notify",
            "payload": {"name": "trace_timestamp", "initial": "0"},
            "token": None,
        }
        assert responses[140] == {
            "stream": stream,
            "message": "tsv-created",
            "type": "notify",
            "payload": {"name": "trace_timestamp", "initial": "0"},
            "token": None,
        }

        for stream in gdbmi._incomplete_output.keys():  # type: ignore[attr-defined]
            assert gdbmi._incomplete_output[stream] is None  # type: ignore[attr-defined]
