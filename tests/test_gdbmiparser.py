from time import time
from typing import Any, Dict

import pytest

from pygdbmi.gdbmiparser import parse_response


@pytest.mark.parametrize(
    "response, expected_dict",
    [
        # Test basic types.
        (
            "^done",
            {"type": "result", "payload": None, "message": "done", "token": None},
        ),
        (
            '~"done"',
            {"type": "console", "payload": "done", "message": None},
        ),
        (
            '@"done"',
            {"type": "target", "payload": "done", "message": None},
        ),
        (
            '&"done"',
            {"type": "log", "payload": "done", "message": None},
        ),
        (
            "done",
            {"type": "output", "payload": "done", "message": None},
        ),
        # Test escape sequences,
        (
            '~""',
            {"type": "console", "payload": "", "message": None},
        ),
        (
            r'~"\b\f\n\r\t\""',
            {"type": "console", "payload": '\b\f\n\r\t"', "message": None},
        ),
        (
            '@""',
            {"type": "target", "payload": "", "message": None},
        ),
        (
            r'@"\b\f\n\r\t\""',
            {"type": "target", "payload": '\b\f\n\r\t"', "message": None},
        ),
        ('&""', {"type": "log", "payload": "", "message": None}),
        (
            r'&"\b\f\n\r\t\""',
            {"type": "log", "payload": '\b\f\n\r\t"', "message": None},
        ),
        # Test that an escaped backslash gets captured.
        (
            r'&"\\"',
            {"type": "log", "payload": "\\", "message": None},
        ),
        # Test that a dictionary with repeated keys (a gdb bug) is gracefully worked-around  by pygdbmi
        # See https://sourceware.org/bugzilla/show_bug.cgi?id=22217
        # and https://github.com/cs01/pygdbmi/issues/19
        (
            '^done,thread-ids={thread-id="3",thread-id="2",thread-id="1"}, current-thread-id="1",number-of-threads="3"',
            {
                "type": "result",
                "payload": {
                    "thread-ids": {"thread-id": ["3", "2", "1"]},
                    "current-thread-id": "1",
                    "number-of-threads": "3",
                },
                "message": "done",
                "token": None,
            },
        ),
        # Test errors.
        (
            r'^error,msg="some message"',
            {
                "type": "result",
                "message": "error",
                "payload": {"msg": "some message"},
                "token": None,
            },
        ),
        (
            r'^error,msg="some message",code="undefined-command"',
            {
                "type": "result",
                "message": "error",
                "payload": {"msg": "some message", "code": "undefined-command"},
                "token": None,
            },
        ),
        (
            r'^error,msg="message\twith\nescapes"',
            {
                "type": "result",
                "message": "error",
                "payload": {"msg": "message\twith\nescapes"},
                "token": None,
            },
        ),
        (
            r'^error,msg="This is a double quote: <\">"',
            {
                "type": "result",
                "message": "error",
                "payload": {"msg": 'This is a double quote: <">'},
                "token": None,
            },
        ),
        (
            r'^error,msg="This is a double quote: <\">",code="undefined-command"',
            {
                "type": "result",
                "message": "error",
                "payload": {
                    "msg": 'This is a double quote: <">',
                    "code": "undefined-command",
                },
                "token": None,
            },
        ),
        # Test a real world dictionary.
        (
            '=breakpoint-modified,bkpt={number="1",empty_arr=[],type="breakpoint",disp="keep",enabled="y",addr="0x000000000040059c",func="main",file="hello.c",fullname="/home/git/pygdbmi/tests/sample_c_app/hello.c",line="9",thread-groups=["i1"],times="1",original-location="hello.c:9"}',
            {
                "message": "breakpoint-modified",
                "payload": {
                    "bkpt": {
                        "addr": "0x000000000040059c",
                        "disp": "keep",
                        "enabled": "y",
                        "file": "hello.c",
                        "fullname": "/home/git/pygdbmi/tests/sample_c_app/hello.c",
                        "func": "main",
                        "line": "9",
                        "number": "1",
                        "empty_arr": [],
                        "original-location": "hello.c:9",
                        "thread-groups": ["i1"],
                        "times": "1",
                        "type": "breakpoint",
                    }
                },
                "type": "notify",
                "token": None,
            },
        ),
        # Test records with token.
        (
            "1342^done",
            {"type": "result", "payload": None, "message": "done", "token": 1342},
        ),
        # Test extra characters at end of dictionary are discarded (issue #30).
        (
            '=event,name="gdb"discardme',
            {
                "type": "notify",
                "payload": {"name": "gdb"},
                "message": "event",
                "token": None,
            },
        ),
        # Test async records status changes.
        (
            '*running,thread-id="all"',
            {
                "type": "notify",
                "payload": {"thread-id": "all"},
                "message": "running",
                "token": None,
            },
        ),
        (
            "*stopped",
            {
                "type": "notify",
                "payload": None,
                "message": "stopped",
                "token": None,
            },
        ),
    ],
)
def test_parser(response: str, expected_dict: Dict[str, Any]) -> None:
    """Test that the parser returns dictionaries from gdb mi strings as expected"""
    assert parse_response(response) == expected_dict


def _get_test_input(n_repetitions: int) -> str:
    data = ", ".join(
        ['"/a/path/to/parse/' + str(i) + '"' for i in range(n_repetitions)]
    )
    return "=test-message,test-data=[" + data + "]"


def _get_avg_time_to_parse(input_str: str, num_runs: int) -> float:
    avg_time = 0.0
    for _ in range(num_runs):
        t0 = time()
        parse_response(input_str)
        t1 = time()
        time_to_run = t1 - t0
        avg_time += time_to_run / num_runs
    return avg_time


def test_performance_big_o() -> None:
    num_runs = 2

    large_input_len = 100000

    single_input = _get_test_input(1)
    large_input = _get_test_input(large_input_len)

    t_small = _get_avg_time_to_parse(single_input, num_runs) or 0.0001
    t_large = _get_avg_time_to_parse(large_input, num_runs)
    bigo_n = (t_large / large_input_len) / t_small
    assert bigo_n < 1  # with old parser, this was over 3
