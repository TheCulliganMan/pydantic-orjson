# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Top-level primitives retain formatting, errors, and dispatch semantics."""

import pytest

import orjson

ALL_OPTIONS = 4095


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, b"null"),
        (False, b"false"),
        (True, b"true"),
        (0, b"0"),
        (-1, b"-1"),
        (2**53 - 1, b"9007199254740991"),
        (-(2**53) + 1, b"-9007199254740991"),
        (1.25, b"1.25"),
        (-0.0, b"-0.0"),
        (1.7976931348623157e308, b"1.7976931348623157e+308"),
        (5e-324, b"5e-324"),
        (float("inf"), b"null"),
        (float("-inf"), b"null"),
        (float("nan"), b"null"),
    ],
)
@pytest.mark.parametrize(
    "option",
    [0, orjson.OPT_INDENT_2, orjson.OPT_APPEND_NEWLINE, ALL_OPTIONS],
)
def test_primitive_formatting_and_ignored_default(value, expected, option):
    def reject_default(item):
        pytest.fail(f"exact primitive reached default: {item!r}")

    if option & orjson.OPT_APPEND_NEWLINE:
        expected += b"\n"
    result = orjson.dumps(value, default=reject_default, option=option)
    assert type(result) is bytes
    assert result == expected
    # A noncallable default is ignored for supported native types, too.
    assert orjson.dumps(value, default=object(), option=option) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-(2**63), b"-9223372036854775808"), (2**64 - 1, b"18446744073709551615")],
)
def test_full_width_integer_with_other_options(value, expected):
    assert (
        orjson.dumps(value, option=ALL_OPTIONS & ~orjson.OPT_STRICT_INTEGER)
        == expected + b"\n"
    )


@pytest.mark.parametrize(
    ("value", "option", "message"),
    [
        (2**64, 0, "Integer exceeds 64-bit range"),
        (-(2**63) - 1, 0, "Integer exceeds 64-bit range"),
        (2**53, orjson.OPT_STRICT_INTEGER, "Integer exceeds 53-bit range"),
        (-(2**53), ALL_OPTIONS, "Integer exceeds 53-bit range"),
    ],
)
def test_primitive_integer_errors_do_not_call_default(value, option, message):
    calls = []

    def convert(item):
        calls.append(item)
        return "converted"

    with pytest.raises(orjson.JSONEncodeError) as caught:
        orjson.dumps(value, default=convert, option=option)
    assert str(caught.value) == message
    assert calls == []


def test_numeric_subclasses_use_original_dispatch():
    class Integer(int):
        pass

    class Float(float):
        pass

    integer = Integer(7)
    floating = Float(1.25)
    calls = []

    def convert(item):
        calls.append(item)
        return "converted"

    assert orjson.dumps(integer, default=convert) == b"7"
    assert calls == []
    assert (
        orjson.dumps(
            integer,
            default=convert,
            option=orjson.OPT_PASSTHROUGH_SUBCLASS | orjson.OPT_APPEND_NEWLINE,
        )
        == b'"converted"\n'
    )
    assert orjson.dumps(floating, default=convert) == b'"converted"'
    assert calls == [integer, floating]
