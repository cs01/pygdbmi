import logging
import os
import random
import subprocess
from distutils.spawn import find_executable

import pytest  # type: ignore
from pygdbmi.constants import GdbTimeoutError
from pygdbmi.gdbcontroller import GdbController

USING_WINDOWS = os.name == "nt"

if USING_WINDOWS:
    MAKE_CMD = "mingw32-make.exe"
else:
    MAKE_CMD = "make"


def _get_c_program(makefile_target_name, binary_name):
    """build c program and return path to binary"""
    find_executable(MAKE_CMD)
    if not find_executable(MAKE_CMD):
        print(
            'Could not find executable "%s". Ensure it is installed and on your $PATH.'
            % MAKE_CMD
        )
        exit(1)

    SAMPLE_C_CODE_DIR = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "sample_c_app"
    )
    binary_path = os.path.join(SAMPLE_C_CODE_DIR, binary_name)
    subprocess.call(["rm", "pygdbmi.a*"], cwd=SAMPLE_C_CODE_DIR)
    # Build C program
    subprocess.check_output(
        [MAKE_CMD, makefile_target_name, "-C", SAMPLE_C_CODE_DIR, "--quiet"]
    )
    return binary_path


def test_load_binary():
    """Build a simple C program, then run it with GdbController and verify the output is parsed
    as expected"""

    gdbmi = GdbController()
    c_hello_world_binary = _get_c_program("hello", "pygdbmiapp.a")
    responses = gdbmi.write(
        "-file-exec-and-symbols %s" % c_hello_world_binary, timeout_sec=1
    )

    # Verify output was parsed into a list of responses
    assert len(responses) != 0
    response = responses[0]
    assert set(response.keys()) == {"message", "type", "payload", "token"}

    assert response["message"] == "thread-group-added"
    assert response["type"] == "notify"
    assert response["payload"] == {"id": "i1"}
    assert response["token"] is None


def test_write_no_read():
    gdbmi = GdbController()
    gdbmi.write("", read_response=False)


def test_write_negative_timeout():
    gdbmi = GdbController()
    with pytest.raises(GdbTimeoutError):
        gdbmi.write("", timeout_sec=-1, raise_error_on_timeout=True)


def test_write_list():
    gdbmi = GdbController()
    gdbmi.write(["asdf", "jkl"])


def test_write_unknown_type():
    gdbmi = GdbController()
    with pytest.raises(TypeError):
        gdbmi.write(b"a bytestring")


def test_bad_gdb_path():
    with pytest.raises(ValueError):
        GdbController(gdb_path="invalid path!")


def test_write_invalid_command():
    logging.basicConfig(level=logging.DEBUG)
    gdbmi = GdbController()
    responses = gdbmi.write("asdf", timeout_sec=1)
    assert responses[2]["type"] == "log"
    assert 'Undefined command: "asdf"' in responses[2]["payload"]


def test_timeout():
    gdbmi = GdbController()
    got_timeout_exception = False
    try:
        gdbmi.get_gdb_response(timeout_sec=0)
    except GdbTimeoutError:
        got_timeout_exception = True
    assert got_timeout_exception is True


def test_close_subprocess():
    gdbmi = GdbController()
    if not USING_WINDOWS:
        # access denied on windows
        gdbmi.send_signal_to_gdb("SIGINT")
        gdbmi.send_signal_to_gdb(2)
        gdbmi.interrupt_gdb()
    responses = gdbmi.terminate()
    assert responses is None
    assert gdbmi.gdb_process is None

    with pytest.raises(OSError):
        responses = gdbmi.write("break main")


def test_signal_handling():
    gdbmi = GdbController()
    if not USING_WINDOWS:
        gdbmi.interrupt_gdb()
        gdbmi.send_signal_to_gdb(2)
        gdbmi.send_signal_to_gdb("sigTeRm")
        with pytest.raises(ValueError):
            gdbmi.send_signal_to_gdb("invalid_signal_name")
        gdbmi.send_signal_to_gdb("sigstop")


def test_controller_buffer():
    """test that a partial response gets successfully buffered
    by the controller, then fully read when more data arrives
    """
    gdbmi = GdbController()
    to_be_buffered = b'^done,BreakpointTable={nr_rows="1",nr_'

    response = gdbmi._get_responses_list(to_be_buffered)
    # Nothing should have been parsed yet
    assert len(response) == 0
    assert gdbmi._raw_buffer == to_be_buffered

    remaining_gdb_output = b'cols="6"}\n(gdb) \n'
    response = gdbmi._get_responses_list(remaining_gdb_output)

    # Should have parsed response at this point
    assert len(response) == 1
    r = response[0]
    assert r["type"] == "result"
    assert r["payload"] == {"BreakpointTable": {"nr_cols": "6", "nr_rows": "1"}}


def test_controller_buffer_randomized():
    """Reads a sample gdb mi stream randomly

    This ensures partial output is read and that the buffer
    is working as expected on all streams.
    """
    test_directory = os.path.dirname(os.path.abspath(__file__))
    datafile_path = "%s/response_samples.txt" % (test_directory)

    gdbmi = GdbController()
    responses = []
    with open(datafile_path, "rb") as f:
        gdb_mi_simulated_output = True
        while gdb_mi_simulated_output:
            n = random.randint(1, 100)
            # read random number of bytes to simulate incomplete responses
            gdb_mi_simulated_output = f.read(n)
            if gdb_mi_simulated_output == b"":
                break  # EOF

            # let the controller try to parse this additional raw gdb output
            responses += gdbmi._get_responses_list(gdb_mi_simulated_output)
        assert len(responses) == 141

        # spot check a few
        responses[0] == {
            "message": None,
            "type": "console",
            "payload": u"0x00007fe2c5c58920 in __nanosleep_nocancel () at ../sysdeps/unix/syscall-template.S:81\\n",
        }

        assert responses[139] == {
            "message": u"tsv-created",
            "type": "notify",
            "payload": {u"name": "trace_timestamp", u"initial": "0"},
            "token": None,
        }

        assert responses[140] == {
            "message": u"tsv-created",
            "type": "notify",
            "payload": {u"name": "trace_timestamp", u"initial": "0"},
            "token": None,
        }

        if not USING_WINDOWS:
            # can't get this to pass in windows
            assert responses[71] == {
                "message": u"done",
                "type": "result",
                "payload": None,
                "token": None,
            }

            assert responses[82] == {
                "message": None,
                "type": "output",
                "payload": u"The inferior program printed this! Can you still parse it?",
            }

            assert responses[137] == {
                "message": u"thread-group-exited",
                "type": "notify",
                "payload": {u"exit-code": u"0", u"id": u"i1"},
                "token": None,
            }

            assert responses[138] == {
                "message": u"thread-group-started",
                "type": "notify",
                "payload": {u"pid": u"48337", u"id": u"i1"},
                "token": None,
            }

        assert gdbmi._raw_buffer is None
