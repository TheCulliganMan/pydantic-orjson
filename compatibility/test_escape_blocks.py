"""Escape masks must preserve every byte at vector and output boundaries."""

import json
import random

import pytest

import orjson


@pytest.mark.parametrize("length", [15, 16, 17, 31, 32, 33, 63, 64, 65, 255, 256, 257])
def test_every_escape_position(length):
    for escape in ('"', "\\", "\n", "\t", "\x00", "\x1f"):
        for position in range(length):
            value = "a" * position + escape + "z" * (length - position - 1)
            expected = json.dumps(value, ensure_ascii=False).encode()
            assert orjson.dumps(value) == expected
            assert orjson.loads(expected) == value


@pytest.mark.parametrize("length", [16, 17, 32, 33, 64, 65, 1024, 8192])
def test_dense_and_mixed_escape_blocks(length):
    generator = random.Random(4107 + length)
    alphabet = 'ab日本🙂é"\\\n\t\x00\x1f'
    for value in (
        ('\n\t"\\' * length)[:length],
        "".join(generator.choice(alphabet) for _ in range(length)),
    ):
        for payload in (value, {value: [value, value]}):
            expected = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode()
            assert orjson.dumps(payload) == expected
            assert orjson.loads(expected) == payload
