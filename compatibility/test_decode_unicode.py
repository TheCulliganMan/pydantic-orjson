# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Wide Unicode construction across ASCII lanes and UTF-8 character boundaries."""

import json

import pytest

import orjson


@pytest.mark.parametrize("character", ["é", "雪", "🌊", "\U0010ffff"])
@pytest.mark.parametrize("escaped", [False, True], ids=["utf8", "escaped"])
def test_wide_strings_at_each_ascii_lane_and_tail(character, escaped):
    for prefix in range(33):
        for suffix in range(33):
            text = "a" * prefix + character + "b" * 64 + character + "c" * suffix
            raw = json.dumps(text, ensure_ascii=escaped).encode()
            assert orjson.loads(raw) == text
            assert orjson.loads(memoryview(raw)) == text


@pytest.mark.parametrize("character", ["é", "雪", "🌊", "\U0010ffff"])
@pytest.mark.parametrize("size", [31, 32, 33, 63, 64, 65, 127, 128, 129, 4096])
def test_dense_and_initial_non_ascii_strings(character, size):
    for text in (character * size, character + "a" * size, "a" + character * size):
        raw = json.dumps(text, ensure_ascii=False).encode()
        assert orjson.loads(raw) == text


@pytest.mark.parametrize("size", [63, 64, 65, 127, 128, 129])
def test_wide_string_lengths_and_embedded_nulls(size):
    for character in ("雪", "🌊"):
        text = ("abc\x00def" + character) * size
        raw = json.dumps({text: [text, text]}, ensure_ascii=False).encode()
        value = orjson.loads(raw)
        assert value == {text: [text, text]}
        assert len(next(iter(value))) == len(text)
        assert orjson.loads(orjson.dumps(value)) == value
