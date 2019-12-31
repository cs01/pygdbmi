from pygdbmi.gdbmiparser import (
    parse_array,
    parse_dict,
    parse_key,
    parse_key_val,
    parse_response,
    parse_val,
    response_is_finished,
)
from pygdbmi.StringStream import StringStream
import logging


def test_parse_key():
    assert parse_key(StringStream('a_key="a val"')) == "a_key"


def test_parse_val():
    assert parse_val(StringStream('"a val"')) == "a val"
    assert parse_val(StringStream('["1", "2"]')) == ["1", "2"]
    assert parse_val(StringStream('{thread-id="1", breakpoint="main"}')) == {
        "thread-id": "1",
        "breakpoint": "main",
    }
    assert parse_val(StringStream('"a string"')) == "a string"
    assert parse_val(StringStream('"a \\"string\\""')) == 'a "string"'
    assert parse_val(StringStream('"a "string"')) != "a s"


def test_parse_dict():
    assert parse_dict(StringStream('{thread-id="1", breakpoint="main"}')) == {
        "thread-id": "1",
        "breakpoint": "main",
    }


def test_parse_key_val():
    assert parse_key_val(StringStream('a_key="a val"')) == ("a_key", "a val")
    assert parse_key_val(StringStream('str_key="test string"')) == (
        "str_key",
        "test string",
    )
    assert parse_key_val(StringStream('arr_key=["val"]}')) == ("arr_key", ["val"])


def test_parse_array():
    assert parse_array(StringStream('["1", "2"]')) == ["1", "2"]


def test_parse_bad_array(caplog):
    caplog.set_level(logging.DEBUG)
    assert parse_array(StringStream('["1", "2"')) == ["1", "2"]
    assert "Unexpected end of stream. Got ['1', '2']" in caplog.messages


def test_parse_weird_array(caplog):
    caplog.set_level(logging.DEBUG)
    assert parse_array(StringStream('["1",; "2"]')) == ["1", "2"]
    assert "Unrecognized character when parsing array" in caplog.messages


def test_non_array(caplog):
    caplog.set_level(logging.DEBUG)
    assert parse_array(StringStream('"1", "2"]')) == []
    assert "Unexpected character at start of array" in caplog.messages


def test_basic_responses():
    assert parse_response("^done") == {
        "type": "result",
        "payload": None,
        "message": "done",
        "token": None,
    }

    assert parse_response('~"done"') == {
        "type": "console",
        "payload": "done",
        "message": None,
    }

    assert parse_response('@"done"') == {
        "type": "target",
        "payload": "done",
        "message": None,
    }

    assert parse_response('&"done"') == {
        "type": "log",
        "payload": "done",
        "message": None,
    }

    assert parse_response("done") == {
        "type": "output",
        "payload": "done",
        "message": None,
    }


def test_finished_response():
    assert response_is_finished("(gdb)")
    assert parse_response("(gdb)") == {"type": "done", "message": None, "payload": None}
    assert parse_response("(gdb)\n") == {
        "type": "done",
        "message": None,
        "payload": None,
    }


def test_escape_sequences():
    assert parse_response('~""') == {"type": "console", "payload": "", "message": None}

    assert parse_response('~"\b\f\n\r\t""') == {
        "type": "console",
        "payload": '\b\f\n\r\t"',
        "message": None,
    }

    assert parse_response('@""') == {"type": "target", "payload": "", "message": None}

    assert parse_response('@"\b\f\n\r\t""') == {
        "type": "target",
        "payload": '\b\f\n\r\t"',
        "message": None,
    }

    assert parse_response('&""') == {"type": "log", "payload": "", "message": None}

    assert parse_response('&"\b\f\n\r\t""') == {
        "type": "log",
        "payload": '\b\f\n\r\t"',
        "message": None,
    }


def test_escaped_backslash():
    assert parse_response('^done, key="some \\"value\\"",  count="3"') == {
        "type": "result",
        "payload": {"key": 'some "value"', "count": "3"},
        "message": "done",
        "token": None,
    }


def test_repeated_keys():
    # Test that a dictionary with repeated keys (a gdb bug) is gracefully worked-around  by pygdbmi
    # See https://sourceware.org/bugzilla/show_bug.cgi?id=22217
    # and https://github.com/cs01/pygdbmi/issues/19
    assert parse_response(
        '^done,thread-ids={thread-id="3",thread-id="2",thread-id="1"}, current-thread-id="1",number-of-threads="3"'
    ) == {
        "type": "result",
        "payload": {
            "thread-ids": {"thread-id": ["3", "2", "1"]},
            "current-thread-id": "1",
            "number-of-threads": "3",
        },
        "message": "done",
        "token": None,
    }


def test_real_world_dict():
    assert parse_response(
        '=breakpoint-modified,bkpt={number="1",empty_arr=[],type="breakpoint",disp="keep",enabled="y",addr="0x000000000040059c",func="main",file="hello.c",fullname="/home/git/pygdbmi/tests/sample_c_app/hello.c",line="9",thread-groups=["i1"],times="1",original-location="hello.c:9"}'
    ) == {
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
    }


def test_records():
    assert parse_response("1342^done") == {
        "type": "result",
        "payload": None,
        "message": "done",
        "token": 1342,
    }


def test_extra_chars_at_end_issue_30():
    assert parse_response('=event,name="gdb"discardme') == {
        "type": "notify",
        "payload": {"name": "gdb"},
        "message": "event",
        "token": None,
    }
