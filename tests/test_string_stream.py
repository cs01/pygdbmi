from pygdbmi.StringStream import StringStream


def test_string_stream() -> None:
    """Tests the StringStream API"""
    raw_text = 'abc- "d" ""ef"" g'
    stream = StringStream(raw_text)
    assert stream.index == 0
    assert stream.len == len(raw_text)

    buf = stream.read(1)
    assert buf == "a"
    assert stream.index == 1

    stream.seek(-1)
    assert stream.index == 0

    buf = stream.advance_past_chars(['"'])
    buf = stream.advance_past_string_with_gdb_escapes()
    assert buf == "d"

    buf = stream.advance_past_chars(['"'])
    buf = stream.advance_past_chars(['"'])
    buf = stream.advance_past_string_with_gdb_escapes()
    assert buf == "ef"

    # read way past end to test it gracefully returns the
    # remainder of the string without failing
    buf = stream.read(50)
    assert buf == '" g'
