# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Large valid documents exercise dense tapes without spare arena pages."""

import pytest

import orjson


@pytest.mark.parametrize("count", [32768, 65536, 131072])
def test_large_dense_pretty_arrays_are_accepted(count):
    # Whitespace selects yyjson's smaller initial tape estimate; short integer
    # tokens then require repeated growth to represent the complete document.
    raw = b"[  " + b"0," * (count - 1) + b"0]"
    value = orjson.loads(raw)
    assert value == [0] * count
    assert orjson.loads(memoryview(raw)) == value


@pytest.mark.parametrize("count", [16384, 32768, 65536])
def test_large_dense_pretty_objects_preserve_last_duplicate_key(count):
    # Duplicate empty keys keep the final Python dictionary small while the
    # parser must still represent every key/value pair in its intermediate tape.
    raw = b"{  " + b'"":0,' * (count - 1) + b'"":7}'
    assert orjson.loads(raw) == {"": 7}
    assert orjson.loads(bytearray(raw)) == {"": 7}
