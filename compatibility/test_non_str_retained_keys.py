# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Retained exact string keys survive callbacks and release on every exit."""

import gc
import json
import sys
import weakref

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
@pytest.mark.parametrize("text", ["ascii", "Café", "雪の街", "📦🙂"])
def test_exact_string_keys_survive_source_clear_and_heap_reuse(option, text):
    marker = object()
    key = "z-" + text * 256
    expected = json.dumps(
        {"a-trigger": "converted", key: "value"},
        ensure_ascii=False,
        sort_keys=bool(option & orjson.OPT_SORT_KEYS),
        indent=2 if option & orjson.OPT_INDENT_2 else None,
        separators=(",", ": ") if option & orjson.OPT_INDENT_2 else (",", ":"),
    ).encode()
    if option & orjson.OPT_APPEND_NEWLINE:
        expected += b"\n"
    payload = {"a-trigger": marker, key: "value"}
    del key

    def convert(value):
        assert value is marker
        payload.clear()
        # Reuse similarly sized Unicode and UTF-8 allocations after removing
        # the source mapping's sole reference to the dynamically created key.
        churn = [("replacement-" + str(i) + text * 256).encode() for i in range(64)]
        payload["replacement"] = churn
        gc.collect()
        return "converted"

    assert orjson.dumps(payload, default=convert, option=option) == expected


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("exit_kind", ["success", "default_error", "key_error"])
def test_exact_string_key_references_release_on_all_exits(option, exit_kind):
    key = "".join(["dynamic-key-", "雪" * 256])
    marker = object()
    payload = {key: marker}
    if exit_kind == "key_error":
        payload["\ud800"] = 1
    initial_references = sys.getrefcount(key)
    calls = []

    def convert(value):
        assert value is marker
        calls.append(value)
        if exit_kind == "default_error":
            raise ValueError("conversion failed")
        return "converted"

    for _ in range(16):
        if exit_kind == "success":
            assert orjson.loads(
                orjson.dumps(payload, default=convert, option=option)
            ) == {key: "converted"}
        else:
            with pytest.raises(orjson.JSONEncodeError):
                orjson.dumps(payload, default=convert, option=option)
        assert sys.getrefcount(key) == initial_references
    assert len(calls) == (0 if exit_kind == "key_error" else 16)


@pytest.mark.parametrize("option", OPTIONS)
def test_string_subclass_keys_keep_original_conversion_lifetime(option):
    class Key(str):
        pass

    key = Key("z-subclass-key")
    key_ref = weakref.ref(key)
    marker = object()
    payload = {"a-trigger": marker, key: "value"}
    del key

    def convert(value):
        assert value is marker
        payload.clear()
        gc.collect()
        # Only exact strings are borrowed. Subclasses retain the previous
        # converted-string snapshot, without extending the source lifetime.
        assert key_ref() is None
        return "converted"

    result = orjson.dumps(payload, default=convert, option=option)
    assert orjson.loads(result) == {
        "a-trigger": "converted",
        "z-subclass-key": "value",
    }
