"""Scalar shortcuts must keep yyjson validation and position semantics."""

import json

import pytest

import orjson


@pytest.mark.parametrize("text", ["null", "true", "false", '"hello"', '"雪🙂"'])
def test_scalar_shortcuts_and_whitespace(text):
    for raw in (text, " " + text, text + "\n", "\t" + text + "\r"):
        for value in (
            raw,
            raw.encode(),
            bytearray(raw.encode()),
            memoryview(raw.encode()),
        ):
            assert orjson.loads(value) == json.loads(text)


@pytest.mark.parametrize("length", [1, 2, 3, 4, 5, 15, 16, 31, 32, 62, 63, 64, 65])
def test_short_string_controls_and_delimiters(length):
    for special in ('"', "\\", "\n", "\x00", "\x1f", "é", "雪", "🙂"):
        value = "a" * length + special
        raw = json.dumps(value, ensure_ascii=False).encode()
        assert orjson.loads(raw) == value
        with pytest.raises(orjson.JSONDecodeError):
            orjson.loads(raw + b'"')
    for byte in range(32):
        with pytest.raises(orjson.JSONDecodeError):
            orjson.loads(b'"' + b"x" * length + bytes([byte]) + b'"')
