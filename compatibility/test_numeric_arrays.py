# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Numeric array allocation and dispatch must preserve the scalar contract."""

import json

import pytest

import orjson


@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("size", [3, 4, 5, 7, 8, 9, 15, 16, 17, 255, 2048, 16384])
@pytest.mark.parametrize("pretty", [False, True])
def test_numeric_array_sizes_and_integer_limits(container, size, pretty):
    limits = [-(2**63), 2**64 - 1, -(2**31), 2**32 - 1, 0]
    values = [limits[index % len(limits)] for index in range(size)]
    option = orjson.OPT_APPEND_NEWLINE
    if pretty:
        option |= orjson.OPT_INDENT_2
    expected = (
        json.dumps(
            values,
            indent=2 if pretty else None,
            separators=(",", ": ") if pretty else (",", ":"),
        ).encode()
        + b"\n"
    )
    assert orjson.dumps(container(values), option=option) == expected


@pytest.mark.parametrize("container", [list, tuple])
def test_numeric_array_float_limits_and_nonfinite_values(container):
    values = [1.7976931348623157e308, 5e-324, -0.0, float("inf"), float("nan")]
    expected = b"1.7976931348623157e+308,5e-324,-0.0,null,null"
    assert (
        orjson.dumps(container(values * 2048))
        == b"[" + b",".join([expected] * 2048) + b"]"
    )


@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("prefix", [1, 3, 4, 5, 15, 16, 2047])
@pytest.mark.parametrize("numeric", [1, 1.0])
def test_numeric_array_mixed_suffix_and_output_growth(container, prefix, numeric):
    # The suffix exceeds the initial numeric reservation and exercises every
    # formatter's reserve path after the first nonnumeric item.
    values = [numeric] * prefix + [True, None, "雪" * 4096, {"b": 2, "a": 1}]
    values += [2**64 - 1] * 2048
    for pretty in (False, True):
        expected = json.dumps(
            values,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if pretty else None,
            separators=(",", ": ") if pretty else (",", ":"),
        ).encode()
        option = orjson.OPT_SORT_KEYS | (orjson.OPT_INDENT_2 if pretty else 0)
        assert orjson.dumps(container(values), option=option) == expected


@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("position", [0, 1, 15, 16, 2047])
@pytest.mark.parametrize(
    ("value", "option", "message"),
    [
        (2**64, 0, "Integer exceeds 64-bit range"),
        (-(2**63) - 1, 0, "Integer exceeds 64-bit range"),
        (2**53, orjson.OPT_STRICT_INTEGER, "Integer exceeds 53-bit range"),
        (-(2**53), orjson.OPT_STRICT_INTEGER, "Integer exceeds 53-bit range"),
    ],
)
def test_numeric_array_integer_errors(container, position, value, option, message):
    values = [0] * 2048
    values[position] = value
    with pytest.raises(orjson.JSONEncodeError, match=message):
        orjson.dumps(container(values), option=option)


@pytest.mark.parametrize("container", [list, tuple])
def test_numeric_array_subclass_passthrough_and_default_order(container):
    class Integer(int):
        pass

    calls = []

    def default(value):
        calls.append(value)
        return {"converted": int(value)}

    subclass = Integer(7)
    values = [1] * 16 + [subclass, True, 1.0] + [1] * 16
    expected = [1] * 16 + [{"converted": 7}, True, 1.0] + [1] * 16
    assert (
        orjson.dumps(
            container(values), default=default, option=orjson.OPT_PASSTHROUGH_SUBCLASS
        )
        == json.dumps(expected, separators=(",", ":")).encode()
    )
    assert calls == [subclass]
    calls.clear()
    assert (
        orjson.dumps(container(values), default=default)
        == json.dumps(values, separators=(",", ":")).encode()
    )
    assert calls == []
