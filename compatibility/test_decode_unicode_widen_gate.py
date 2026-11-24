# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Wide-string decoding around a bounded ASCII-prefix probe."""

import json

import pytest

import orjson


@pytest.mark.parametrize("character", ["é", "雪", "🌊", "\U0010ffff"])
@pytest.mark.parametrize("ascii_length", [15, 16, 17, 31, 32])
def test_ascii_runs_straddling_probe_chunks_and_end(character, ascii_length):
    for prefix in range(145):
        text = "a" + character * prefix + "x" * ascii_length + character * 64
        raw = json.dumps(text, ensure_ascii=False).encode()
        assert orjson.loads(raw) == text
        assert orjson.loads(memoryview(raw)) == text


@pytest.mark.parametrize("length", [63, 64, 65, 127, 128, 129, 256, 4096])
def test_dense_mixed_unicode_with_no_ascii_run(length):
    unit = "Café 雪の街 — 📦 "
    text = (unit * (length // len(unit) + 1))[:length]
    for escaped in (False, True):
        raw = json.dumps({text: [text, text]}, ensure_ascii=escaped).encode()
        assert orjson.loads(raw) == {text: [text, text]}
