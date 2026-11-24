# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Root integer shortcuts must retain JSON grammar and numeric overflow types."""

import json

import pytest

import orjson


def inputs(text):
    encoded = text.encode()
    return text, encoded, bytearray(encoded), memoryview(encoded)


@pytest.mark.parametrize(
    "value",
    [
        -(2**63),
        -(2**63) + 1,
        -(2**31),
        -257,
        -256,
        -5,
        -1,
        0,
        1,
        255,
        256,
        257,
        2**31,
        2**63 - 1,
        2**63,
        2**64 - 2,
        2**64 - 1,
    ],
)
def test_root_integer_full_supported_ranges(value):
    for raw in inputs(str(value)):
        actual = orjson.loads(raw)
        assert type(actual) is int
        assert actual == value


@pytest.mark.parametrize("text", ["0", "-0"])
def test_integer_zero_is_an_integer(text):
    for raw in inputs(text):
        actual = orjson.loads(raw)
        assert type(actual) is int
        assert actual == 0


@pytest.mark.parametrize(
    "value", [-(2**63) - 1, -(2**64), -(2**64) - 1, 2**64, 2**64 + 1, 10**30]
)
def test_out_of_range_integers_keep_yyjson_float_conversion(value):
    for raw in inputs(str(value)):
        actual = orjson.loads(raw)
        assert type(actual) is float
        assert actual.hex() == float(str(value)).hex()


@pytest.mark.parametrize(
    "text", [" 7", "7 ", "\t-7\r\n", "1.0", "1e0", "1E+2", "-0.0", "-0e0", "0e0"]
)
def test_whitespace_fraction_and_exponent_keep_parser_semantics(text):
    expected = json.loads(text)
    for raw in inputs(text):
        actual = orjson.loads(raw)
        assert type(actual) is type(expected)
        if type(expected) is float:
            assert actual.hex() == expected.hex()
        else:
            assert actual == expected


@pytest.mark.parametrize(
    "text",
    [
        "00",
        "01",
        "-00",
        "-01",
        "+1",
        "-",
        "--1",
        "1-",
        "1+",
        "1x",
        "1 2",
        "1,",
        "1]",
        "1e",
        "1.",
        "\u0661",
        "\uff11",
        "1雪",
        "-\uff11",
    ],
)
def test_non_integer_json_grammar_remains_rejected(text):
    for raw in inputs(text):
        with pytest.raises(orjson.JSONDecodeError) as caught:
            orjson.loads(raw)
        assert caught.value.doc == text
        assert 0 <= caught.value.pos <= len(text)


@pytest.mark.parametrize("raw", [b"12\xff", b"-\xed\xa0\x80", b"\xf0\x80\x80\x80"])
def test_invalid_utf8_is_rejected_before_numeric_shortcuts(raw):
    for value in (raw, bytearray(raw), memoryview(raw)):
        with pytest.raises(orjson.JSONDecodeError) as caught:
            orjson.loads(value)
        assert caught.value.msg == "str is not valid UTF-8: surrogates not allowed"
        assert caught.value.pos == 0


def test_unbounded_integer_overflow_still_raises_json_error():
    for text in ("9" * 400, "-" + "9" * 400):
        with pytest.raises(orjson.JSONDecodeError) as caught:
            orjson.loads(text)
        assert caught.value.msg == "number is infinity when parsed as double"
        assert caught.value.doc == text
