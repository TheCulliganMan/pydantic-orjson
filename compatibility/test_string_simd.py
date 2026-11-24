# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""String escaping across native vector boundaries and scalar fallbacks."""

import json

import pytest

import orjson


def reference(value, option=0):
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if option & orjson.OPT_INDENT_2 else None,
        separators=(",", ": ") if option & orjson.OPT_INDENT_2 else (",", ":"),
        sort_keys=bool(option & orjson.OPT_SORT_KEYS),
    ).encode() + (b"\n" if option & orjson.OPT_APPEND_NEWLINE else b"")


@pytest.mark.parametrize("length", [*range(65), 127, 128, 129, 255, 256, 257])
def test_ascii_lengths_and_exact_vector_tails(length):
    value = "a" * length
    assert orjson.dumps(value) == reference(value)


@pytest.mark.parametrize("escape", [*(chr(i) for i in range(32)), '"', "\\"])
def test_every_escape_at_every_vector_lane_and_tail(escape):
    for length in (15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64, 65, 127, 128, 129):
        for position in range(length):
            value = "x" * position + escape + "y" * (length - position - 1)
            assert orjson.dumps(value) == reference(value), (length, position)


@pytest.mark.parametrize("character", ["é", "雪", "📦", "\u2028", "\u2029"])
def test_utf8_codepoints_cross_vector_boundaries(character):
    for padding in range(32):
        for count in (1, 3, 9, 32):
            value = "a" * padding + character * count + '"\\\n' + character
            assert orjson.dumps(value) == reference(value), (padding, count)


@pytest.mark.parametrize(
    "option",
    [
        0,
        orjson.OPT_INDENT_2,
        orjson.OPT_SORT_KEYS,
        orjson.OPT_NON_STR_KEYS,
        orjson.OPT_APPEND_NEWLINE,
        orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE,
    ],
)
def test_key_value_escaping_with_options(option):
    value = {
        "z" * 16: "long unescaped value " * 32,
        'escaped "key"\\\n': ["雪📦" * 17, '\x00\t\n\r\\"' * 32],
        "a" * 17: {"\b\f": "tail"},
    }
    assert orjson.dumps(value, option=option) == reference(value, option)


def test_escape_dense_input_and_output_buffer_growth():
    controls = "".join(chr(i) for i in range(32)) + '"\\'
    for value in (controls * 128, "a" * 16384, "雪" * 8192 + controls):
        encoded = orjson.dumps(value)
        assert encoded == reference(value)
        assert orjson.loads(encoded) == value


def test_scalar_tokens_follow_each_output_alignment():
    for padding in range(16):
        value = ["a" * padding, True, False, None, {"key": [None, True, False]}]
        assert orjson.dumps(value) == reference(value)
