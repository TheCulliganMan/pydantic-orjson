# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Generative contracts around the native parser and string writer."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import orjson

STRINGS = st.text(st.characters(exclude_categories=("Cs",)), max_size=4096)
JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers(-(2**63), 2**64 - 1) | STRINGS,
    lambda children: (
        st.lists(children, max_size=12)
        | st.dictionaries(STRINGS, children, max_size=12)
    ),
    max_leaves=40,
)


@settings(max_examples=1000, deadline=None, derandomize=True, database=None)
@given(JSON_VALUES)
def test_generated_values_match_standard_json(value):
    encoded = orjson.dumps(value)
    assert json.loads(encoded) == value
    assert orjson.loads(encoded) == value
    assert orjson.loads(json.dumps(value, ensure_ascii=False)) == value


@settings(max_examples=1000, deadline=None, derandomize=True, database=None)
@given(STRINGS)
def test_string_bytes_match_standard_escaping(value):
    assert orjson.dumps(value) == json.dumps(value, ensure_ascii=False).encode()


@settings(max_examples=1000, deadline=None, derandomize=True, database=None)
@given(st.binary(max_size=2048))
def test_arbitrary_bytes_either_parse_or_raise_decode_error(value):
    try:
        parsed = orjson.loads(value)
    except orjson.JSONDecodeError:
        return
    # Python accepts a superset (e.g. NaN), but every accepted orjson document
    # must also parse as the same standard JSON value.
    assert parsed == json.loads(value)


@settings(max_examples=1000, deadline=None, derandomize=True, database=None)
@given(STRINGS, st.integers(min_value=0, max_value=31))
def test_unescaped_control_bytes_are_always_rejected(text, control):
    encoded = orjson.dumps(text)
    malformed = encoded[:-1] + bytes([control]) + b'"'
    with pytest.raises(orjson.JSONDecodeError):
        orjson.loads(malformed)
