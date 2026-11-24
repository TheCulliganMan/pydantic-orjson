# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Capacity boundaries for the exact top-level string serializer."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import orjson

OPTIONS = [
    0,
    orjson.OPT_INDENT_2,
    orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
    4095,
]


def expected_bytes(value, option):
    encoded = json.dumps(value, ensure_ascii=False).encode()
    return encoded + (b"\n" if option & orjson.OPT_APPEND_NEWLINE else b"")


@pytest.mark.parametrize("length", [36, 37, 38])
@pytest.mark.parametrize("option", OPTIONS)
def test_every_escape_at_short_string_boundary(length, option):
    for escape in [chr(value) for value in range(32)] + ['"', "\\"]:
        for position in range(length):
            value = "a" * position + escape + "z" * (length - position - 1)
            assert orjson.dumps(value, option=option) == expected_bytes(value, option)
        # All six-byte escapes exercise the maximum expansion, including the
        # AVX tail's final zero-length masked load and 32-byte store.
        value = escape * length
        assert orjson.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("length", [36, 37, 38])
@pytest.mark.parametrize("prefix", ["", "é", "雪", "📦"])
@pytest.mark.parametrize("option", OPTIONS)
def test_cutoff_counts_utf8_bytes_and_preserves_multibyte_sequences(
    length, prefix, option
):
    padding = length - len(prefix.encode())
    for value in (prefix + "x" * padding, "\x00" * padding + prefix):
        assert len(value.encode()) == length
        assert orjson.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("value", ["", "a", "\x00", '"', "\\", "📦"])
@pytest.mark.parametrize("option", OPTIONS)
def test_short_strings_ignore_default_and_return_bytes(value, option):
    def reject_default(item):
        pytest.fail(f"exact string reached default: {item!r}")

    expected = expected_bytes(value, option)
    result = orjson.dumps(value, default=reject_default, option=option)
    assert type(result) is bytes
    assert result == expected
    assert orjson.dumps(value, default=object(), option=option) == expected


@pytest.mark.parametrize("length", [38, 39, 64, 4096, 65536])
@pytest.mark.parametrize("prefix", ["", "é", "雪", "📦"])
@pytest.mark.parametrize("option", OPTIONS)
def test_long_exact_string_options_and_growth(length, prefix, option):
    def reject_default(item):
        pytest.fail("exact string reached default")

    padding = length - len(prefix.encode())
    for value in (prefix + "x" * padding, "\x00" * padding + prefix):
        assert len(value.encode()) == length
        expected = expected_bytes(value, option)
        result = orjson.dumps(value, default=reject_default, option=option)
        assert type(result) is bytes
        assert result == expected
        assert orjson.dumps(value, default=object(), option=option) == expected


@pytest.mark.parametrize("length", [36, 37, 38])
@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"])
@pytest.mark.parametrize("option", OPTIONS)
def test_surrogate_errors_preserve_native_message_and_skip_default(
    length, surrogate, option
):
    calls = []

    def convert(value):
        calls.append(value)
        return "converted"

    for position in (0, 17, length - 1):
        value = "a" * position + surrogate + "z" * (length - position - 1)
        with pytest.raises(orjson.JSONEncodeError) as caught:
            orjson.dumps(value, default=convert, option=option)
        assert str(caught.value) == "str is not valid UTF-8: surrogates not allowed"
    assert calls == []


@pytest.mark.parametrize("length", [36, 37, 38])
def test_string_subclasses_keep_original_dispatch(length):
    class String(str):
        def __str__(self):
            raise AssertionError("native str serialization must not invoke __str__")

    raw = "雪" + "x" * (length - 3)
    value = String(raw)
    calls = []

    def convert(item):
        assert item is value
        calls.append(item)
        return "converted"

    assert orjson.dumps(value, default=convert) == expected_bytes(raw, 0)
    assert calls == []
    assert (
        orjson.dumps(
            value,
            default=convert,
            option=orjson.OPT_PASSTHROUGH_SUBCLASS | orjson.OPT_APPEND_NEWLINE,
        )
        == b'"converted"\n'
    )
    assert calls == [value]
    with pytest.raises(orjson.JSONEncodeError):
        orjson.dumps(value, option=orjson.OPT_PASSTHROUGH_SUBCLASS)


def test_shared_exact_unicode_string_across_threads():
    value = "".join(["雪" * 12, "x"])
    expected = b'"' + b"\xe9\x9b\xaa" * 12 + b'x"'
    start = threading.Barrier(8, timeout=15)

    def encode(_):
        start.wait()
        for option in OPTIONS * 16:
            suffix = b"\n" if option & orjson.OPT_APPEND_NEWLINE else b""
            assert orjson.dumps(value, option=option) == expected + suffix

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(encode, range(8)))
