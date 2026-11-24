# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Float-prefix tape decoding must preserve generic suffixes and scalar bits."""

import gc
import json
import math
from concurrent.futures import ThreadPoolExecutor

import pytest

import orjson


def assert_same(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is float:
        # Equality alone misses a lost negative zero sign.
        assert actual.hex() == expected.hex()
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            assert_same(left, right)
    elif type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_same(actual[key], expected[key])
    else:
        assert actual == expected


@pytest.mark.parametrize("size", [0, 1, 15, 16, 17, 128, 2048])
def test_homogeneous_floats_preserve_values_and_signed_zero(size):
    limits = [
        0.0,
        -0.0,
        5e-324,
        -5e-324,
        1.7976931348623157e308,
        -1.7976931348623157e308,
        1.25,
    ]
    values = [limits[i % len(limits)] for i in range(size)]
    encoded = json.dumps(values, separators=(",", ":")).encode()
    actual = orjson.loads(encoded)
    assert_same(actual, values)
    for _ in range(20):
        orjson.loads(b'[1.0,2.0,3.0,{"new":[true,null]}]')
    gc.collect()
    assert_same(actual, values)


@pytest.mark.parametrize("prefix", [0, 1, 15, 16, 17, 2047])
@pytest.mark.parametrize(
    "suffix",
    [
        0,
        -(2**63),
        2**64 - 1,
        True,
        False,
        None,
        "雪🌊",
        [],
        {},
        [7, {"inner": [1.5, -0.0]}],
        {"inner": [[], [1.5, -0.0]]},
    ],
)
@pytest.mark.parametrize("nested", [False, True])
def test_float_prefix_falls_through_without_skipping_container_tape(
    prefix, suffix, nested
):
    values = [0.25] * prefix + [suffix, -0.0, 0, 7.5, {"tail": [1, 2.0]}]
    # Keep the >=16 guard active even for a one-float prefix. The nested case
    # exercises outer container-offset skipping after the specialized child.
    values += [1.25] * 16
    if nested:
        values = {"before": [True], "numbers": values, "after": [9, {"end": False}]}
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
    assert_same(orjson.loads(encoded), values)


def test_integer_tokens_are_never_reinterpreted_as_float_bits():
    raw = (
        b"["
        + b",".join(
            [b"1.0"] * 16
            + [
                b"0",
                b"-0",
                b"-9223372036854775808",
                b"18446744073709551615",
                b"1e0",
                b"-0e0",
            ]
        )
        + b"]"
    )
    actual = orjson.loads(raw)
    expected = json.loads(raw)
    assert_same(actual, expected)
    assert math.copysign(1, actual[-1]) == -1


def test_numeric_results_belong_to_each_concurrent_decode():
    # Applicable to regular and no-GIL interpreters: immutable input is shared,
    # but each call must own its list/scalars and the nested mutable suffix.
    raw = b"[" + b"1.25," * 32 + b'{"nested":[1,-0.0]},2.5]'
    expected = json.loads(raw)
    with ThreadPoolExecutor(max_workers=4) as executor:
        outputs = list(executor.map(orjson.loads, [raw] * 256))
    for output in outputs:
        assert_same(output, expected)
    outputs[0][32]["nested"].append("changed")
    assert all(output[32]["nested"] == [1, -0.0] for output in outputs[1:])


@pytest.mark.parametrize(
    "suffix", [b"NaN", b"Infinity", b"1e999", b"[", b"{", b"true,"]
)
def test_invalid_json_after_float_prefix_is_still_rejected(suffix):
    raw = b"[" + b"1.25," * 16 + suffix + b"]"
    with pytest.raises(orjson.JSONDecodeError):
        orjson.loads(raw)
