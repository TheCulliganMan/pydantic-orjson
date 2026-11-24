# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""UTF-8 width/count boundaries and long continuation-count accumulation."""

import json

import pytest

import orjson


@pytest.mark.parametrize(
    "character", ["é", "ÿ", "Ā", "雪", "\uffff", "\U00010000", "\U0010ffff"]
)
@pytest.mark.parametrize("prefix", [0, 1, 15, 16, 63, 64, 65, 127, 128, 129])
def test_unicode_width_and_character_count_across_lanes(character, prefix):
    for tail in range(65):
        text = "a" * prefix + character + "b" * 128 + character + "c" * tail
        raw = json.dumps(text, ensure_ascii=False).encode()
        decoded = orjson.loads(raw)
        assert decoded == text
        assert len(decoded) == len(text)


@pytest.mark.parametrize("character", ["é", "雪", "🌊"])
@pytest.mark.parametrize(
    "size",
    [
        16255,
        16256,
        16257,
        16319,
        16320,
        16321,
        16383,
        16384,
        16385,
        32639,
        32640,
        32641,
    ],
)
def test_continuation_accumulators_fold_without_wrapping(character, size):
    width = len(character.encode())
    text = "a" + character * ((size - 1) // width) + "b" * ((size - 1) % width)
    assert len(text.encode()) == size
    for escaped in (False, True):
        raw = json.dumps(text, ensure_ascii=escaped).encode()
        assert orjson.loads(raw) == text
        assert orjson.loads(memoryview(raw)) == text


@pytest.mark.parametrize(
    "size",
    [0, 1, 15, 16, 17, 63, 64, 65, 127, 128, 129, 255, 256, 257, 16319, 16320, 16321],
)
def test_ascii_prefix_and_final_unicode_width(size):
    for suffix in ("", "é", "Ā", "雪", "🌊", "\U0010ffff"):
        text = "a" * size + suffix
        raw = json.dumps({text: text}, ensure_ascii=False).encode()
        assert orjson.loads(raw) == {text: text}


@pytest.mark.parametrize("character", ["é", "雪", "🌊"])
@pytest.mark.parametrize("size", [63, 64, 65, 127, 128, 129])
def test_exact_utf8_byte_lengths_at_classifier_transition(character, size):
    available = size - len(character.encode())
    for prefix in sorted({0, 1, 15, 16, 31, 32, available}):
        text = "a" * prefix + character + "b" * (available - prefix)
        assert len(text.encode()) == size
        raw = json.dumps(text, ensure_ascii=False).encode()
        assert orjson.loads(raw) == text
