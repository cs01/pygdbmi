from pygdbmi.StringStream import StringStream


def test_string_stream_index():
    raw_text = "abc"
    stream = StringStream(raw_text)
    assert stream.index == 0
    assert stream.len == len(raw_text)

    assert stream.read(1) == "a"
    assert stream.index == 1

    stream.seek(-1)
    assert stream.index == 0
    assert stream.read(1) == "a"


def test_string_stream_read():
    stream = StringStream("abcdefg")
    assert "a" == stream.read(1)
    assert "b" == stream.read(1)
    assert "cde" == stream.read(3)


def test_string_stream_advance():
    stream = StringStream("abcdefg")
    assert "abcd" == stream.advance_past_chars("e")
    assert "f" == stream.read(1)


def test_stream_advance_with_escapes():
    stream = StringStream('"mystream \\" quotes" "and another string"')
    assert stream.advance_past_string_with_gdb_escapes() == 'mystream " quotes'


def test_stream_advance_past_end():
    stream = StringStream("abc")
    assert "abc" == stream.read(50)
    assert "" == stream.read(50)


def test_advance_no_infinite_loop(caplog):
    stream = StringStream("no commas here!")
    assert "no commas here!" == stream.advance_past_chars([","])
    assert len(caplog.records) == 1
    assert "Unexpected end of stream" in caplog.records[0].message


def test_malformed_string(caplog):
    stream = StringStream('abc"')
    assert "" == stream.advance_past_string_with_gdb_escapes()
    assert len(caplog.records) == 1
    assert "Unexpected character a at start (expected" in caplog.records[0].message


def test_no_infinite_loop_with_gdb_escapes(caplog):
    stream = StringStream('"abc')
    assert "abc" == stream.advance_past_string_with_gdb_escapes()
    assert len(caplog.records) == 1
    assert "Unexpected end of stream" in caplog.records[0].message
