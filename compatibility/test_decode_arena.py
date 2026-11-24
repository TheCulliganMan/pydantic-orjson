# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Lifetime and boundary checks for the decoder's small-message scratch arena."""

import json
import subprocess
import sys
import sysconfig

import pytest

import orjson

# Retain the original 321/322 boundary and exercise the current 610/611 one.
SIZES = (318, 319, 320, 321, 322, 323, 324, 607, 608, 609, 610, 611, 612, 613, 614)
FACTORIES = (
    pytest.param(lambda raw: raw.decode("utf-8"), id="str"),
    pytest.param(bytes, id="bytes"),
    pytest.param(bytearray, id="bytearray"),
    pytest.param(memoryview, id="memoryview"),
)


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("unicode_text", [False, True], ids=["ascii", "unicode"])
def test_boundary_documents_copy_strings_and_preserve_values(
    factory, size, unicode_text
):
    prefix = b'{"message":"'
    suffix = b'","values":[true,null,-7,1.25]}'
    available = size - len(prefix) - len(suffix)
    unit = "雪🌊".encode() if unicode_text else b"a"
    message = unit * (available // len(unit)) + b"x" * (available % len(unit))
    raw = prefix + message + suffix
    assert len(raw) == size
    expected = json.loads(raw)
    decoded = orjson.loads(factory(raw))

    # Further parses overwrite any reusable stack area. Previously returned
    # strings and containers must own their contents, including escaped data.
    for _ in range(20):
        assert orjson.loads(b'{"message":"\\u96ea\\nreplacement"}') == {
            "message": "雪\nreplacement"
        }
    assert decoded == expected


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("size", SIZES)
def test_invalid_value_positions_at_byte_boundaries(factory, size):
    raw = b'{"items":' + b" " * (size - 11) + b"]}"
    assert len(raw) == size
    with pytest.raises(orjson.JSONDecodeError) as caught:
        orjson.loads(factory(raw))
    error = caught.value
    assert error.msg == "unexpected character, expected a JSON value"
    assert error.doc == raw.decode()
    assert (error.pos, error.lineno, error.colno) == (size - 2, 1, size - 1)


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("size", SIZES)
def test_json_whitespace_at_boundaries_is_accepted(factory, size):
    raw = b"\t\r\n true" + b" " * (size - 8)
    assert len(raw) == size
    assert orjson.loads(factory(raw)) is True
    with pytest.raises(orjson.JSONDecodeError):
        orjson.loads(factory(raw[:-1] + b"\x0b"))


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("depth", [158, 159, 160, 161, 162, 303, 304, 305, 306, 307])
def test_nested_documents_crossing_arena_boundary(factory, depth):
    raw = b"[" * depth + b"0" + b"]" * depth
    value = orjson.loads(factory(raw))
    for _ in range(depth):
        assert type(value) is list
        assert len(value) == 1
        value = value[0]
    assert value == 0
    with pytest.raises(orjson.JSONDecodeError):
        orjson.loads(factory(raw[:-1]))


@pytest.mark.parametrize("size", SIZES)
def test_invalid_utf8_is_rejected_before_parsing(size):
    raw = b'"' + b"x" * (size - 3) + b'\xff"'
    assert len(raw) == size
    for factory in (bytes, bytearray, memoryview):
        with pytest.raises(orjson.JSONDecodeError) as caught:
            orjson.loads(factory(raw))
        assert caught.value.pos == 0
        assert caught.value.msg == "str is not valid UTF-8: surrogates not allowed"


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("count", [938, 939, 940, 1000, 4096, 16384])
def test_dense_pretty_arrays_have_capacity_for_input_and_growing_tape(factory, count):
    # Two spaces select yyjson's pretty-size estimate. Inherited arena sizing
    # omitted the input copy and rejected the valid count=939 document.
    raw = b"[  " + b"0," * (count - 1) + b"0]"
    assert orjson.loads(factory(raw)) == [0] * count


@pytest.mark.parametrize("prefix", [b"[", b"[  ", b" \n[  "])
def test_dense_array_tape_growth_at_each_small_size(prefix):
    # Exercise successive 1.5x tape growth thresholds in stack and heap arenas.
    for count in range(1, 4097):
        raw = prefix + b"0," * (count - 1) + b"0]"
        decoded = orjson.loads(raw)
        assert len(decoded) == count
        assert decoded == [0] * count


@pytest.mark.parametrize("count", [939, 4096])
def test_error_positions_after_dense_tape_growth(count):
    raw = b"[  " + b"0," * count + b"]"
    with pytest.raises(orjson.JSONDecodeError) as caught:
        orjson.loads(raw)
    assert caught.value.msg == "trailing comma is not allowed"
    assert caught.value.doc == raw.decode()
    assert caught.value.pos == len(raw) - 2


@pytest.mark.skipif(
    bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
    reason="free-threaded GC does not trigger this in-call allocation-threshold callback",
)
@pytest.mark.parametrize("array_length", [200, 210], ids=["stack", "heap"])
def test_gc_callback_can_reenter_decoder_without_corrupting_outer_document(
    array_length,
):
    # Isolate forced GC thresholds and callbacks from pytest and other tests.
    # Allocating many inner lists triggers GC while the outer tape is in use.
    source = """
import gc
import sys
import orjson

nested = []
active = False
def on_gc(phase, info):
    if phase == 'start' and active:
        nested.append(orjson.loads(b'{"inside":[1,true,"snow"]}'))

gc.collect()
gc.callbacks.append(on_gc)
gc.set_threshold(1, 1, 1)
count = int(sys.argv[1])
raw = b'[' + b','.join([b'[]'] * count) + b']'
outputs = []
try:
    for _ in range(40):
        active = True
        value = orjson.loads(raw)
        active = False
        outputs.append(value)
finally:
    active = False
    gc.callbacks.remove(on_gc)
assert nested, 'the test must actually reenter loads during collection'
assert all(value == {'inside': [1, True, 'snow']} for value in nested)
assert all(value == [[] for _ in range(count)] for value in outputs)
assert len({id(inner) for value in outputs for inner in value}) == 40 * count
"""
    subprocess.run(
        [sys.executable, "-I", "-X", "dev", "-c", source, str(array_length)],
        check=True,
        capture_output=True,
        timeout=20,
    )
