# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""The NON_STR_KEYS path snapshots converted keys before serializing values."""

import sys

import pytest

import orjson

OPTIONS = [
    orjson.OPT_NON_STR_KEYS,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_INDENT_2,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2,
]


@pytest.mark.parametrize("option", OPTIONS)
def test_default_callback_keeps_original_owned_key_snapshot(option):
    marker = object()
    key = "".join(["z-original ", "key " * 32, "雪"])
    # Retain values independently: this checks key snapshot behavior, not the
    # existing borrowed-value lifetime contract during arbitrary dict mutation.
    values = ["".join(["value", str(i)]) for i in range(3)]
    expected = orjson.dumps(
        {"trigger": "converted", key: values[0], "1": values[1], 1: values[2]},
        option=option,
    )
    payload = {"trigger": marker, key: values[0], "1": values[1], 1: values[2]}
    del key

    def convert(value):
        assert value is marker
        payload.clear()
        payload["replacement"] = "added during callback"
        return "converted"

    assert orjson.dumps(payload, default=convert, option=option) == expected
    assert payload == {"replacement": "added during callback"}


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("bad_key", [("unsupported",), "\ud800"])
def test_all_key_errors_precede_value_callbacks(option, bad_key):
    calls = []

    def convert(value):
        calls.append(value)
        return "converted"

    with pytest.raises(orjson.JSONEncodeError):
        orjson.dumps({"first": object(), bad_key: 1}, default=convert, option=option)
    assert calls == []


def test_unsorted_duplicate_keys_retain_insertion_order():
    assert (
        orjson.dumps(
            {"1": "string", 1: "integer", "null": "string-null", None: "none"},
            option=orjson.OPT_NON_STR_KEYS,
        )
        == b'{"1":"string","1":"integer","null":"string-null","null":"none"}'
    )


def test_nested_snapshots_and_default_returned_mapping():
    marker = object()
    calls = []

    def convert(value):
        calls.append(value)
        return {3: "third", "3": "string-third"}

    payload = {1: {2: marker}, "1": []}
    assert orjson.dumps(payload, default=convert, option=orjson.OPT_NON_STR_KEYS) == (
        b'{"1":{"2":{"3":"third","3":"string-third"}},"1":[]}'
    )
    assert calls == [marker]


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("fail", [False, True])
def test_snapshot_value_references_are_released_on_success_and_error(option, fail):
    class Value:
        pass

    marker = Value()
    value = Value()
    payload = {"first": marker, "second": value}
    initial = sys.getrefcount(value)

    def convert(item):
        # The native snapshot owns a reference independent of the mapping.
        assert sys.getrefcount(value) > initial
        if fail:
            raise ValueError("conversion failed")
        return "converted"

    if fail:
        with pytest.raises(orjson.JSONEncodeError):
            orjson.dumps(payload, default=convert, option=option)
    else:
        assert orjson.loads(orjson.dumps(payload, default=convert, option=option)) == {
            "first": "converted",
            "second": "converted",
        }
    assert sys.getrefcount(value) == initial
