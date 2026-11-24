"""Owned container snapshots must survive callbacks without retaining locks."""

from __future__ import annotations

import dataclasses
import sys
import sysconfig
import threading
from typing import TYPE_CHECKING

import pytest

import orjson

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"),
    reason="free-threaded container snapshot contract",
)


class Marker:
    def __init__(self, value: str) -> None:
        self.value = value


def dumps_during_mutation(
    payload: object, mutate: Callable[[], None], *, option: int = 0
) -> bytes:
    """The callback cannot return until a different thread mutates its parent."""
    assert not sys._is_gil_enabled()
    requested = threading.Event()
    finished = threading.Event()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            if not requested.wait(timeout=5):
                raise AssertionError("serialization never requested mutation")
            mutate()
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def default(value: object) -> str:
        assert isinstance(value, Marker)
        requested.set()
        assert finished.wait(timeout=5), (
            "parent container stayed locked across callback"
        )
        if errors:
            raise errors[0]
        return value.value

    try:
        return orjson.dumps(payload, default=default, option=option)
    finally:
        requested.set()
        thread.join(timeout=5)
        assert not thread.is_alive(), "mutation thread did not finish"
        if errors:
            raise errors[0]
        assert not sys._is_gil_enabled()


@pytest.mark.parametrize("option", [0, orjson.OPT_INDENT_2])
def test_list_snapshot_survives_cross_thread_callback_mutation(option: int) -> None:
    payload = [Marker("first"), {"keep": [1, 2, 3]}, Marker("last")]

    def mutate() -> None:
        payload.clear()
        payload.extend(["replacement"] * 257)

    actual = dumps_during_mutation(payload, mutate, option=option)
    expected = ["first", {"keep": [1, 2, 3]}, "last"]
    assert actual == orjson.dumps(expected, option=option)


@pytest.mark.parametrize(
    "option",
    [
        0,
        orjson.OPT_SORT_KEYS,
        orjson.OPT_NON_STR_KEYS,
        orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
    ],
)
@pytest.mark.parametrize("pretty", [0, orjson.OPT_INDENT_2])
def test_dict_snapshot_survives_cross_thread_callback_mutation(
    option: int, pretty: int
) -> None:
    payload = {"first": Marker("first"), "keep": [1, 2, 3], "last": Marker("last")}

    def mutate() -> None:
        payload.clear()
        payload.update({f"replacement-{index}": index for index in range(257)})

    actual = dumps_during_mutation(payload, mutate, option=option | pretty)
    expected = {"first": "first", "keep": [1, 2, 3], "last": "last"}
    assert actual == orjson.dumps(expected, option=option | pretty)


@pytest.mark.parametrize("pretty", [0, orjson.OPT_INDENT_2])
def test_non_str_keys_snapshot_survives_cross_thread_callback_mutation(
    pretty: int,
) -> None:
    payload = {1: Marker("first"), "keep": [1, 2], 3: Marker("last")}

    def mutate() -> None:
        payload.clear()
        payload.update({False: "replacement"})

    option = orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS | pretty
    actual = dumps_during_mutation(payload, mutate, option=option)
    assert actual == orjson.dumps(
        {1: "first", "keep": [1, 2], 3: "last"}, option=option
    )


@pytest.mark.parametrize("pretty", [0, orjson.OPT_INDENT_2])
def test_dataclass_dict_snapshot_survives_cross_thread_callback_mutation(
    pretty: int,
) -> None:
    @dataclasses.dataclass
    class Record:
        first: object
        keep: list[int]
        last: object

    payload = Record(Marker("first"), [1, 2, 3], Marker("last"))

    def mutate() -> None:
        payload.__dict__.clear()
        payload.__dict__["replacement"] = True

    actual = dumps_during_mutation(payload, mutate, option=pretty)
    expected = {"first": "first", "keep": [1, 2, 3], "last": "last"}
    assert actual == orjson.dumps(expected, option=pretty)


@pytest.mark.parametrize("pretty", [0, orjson.OPT_INDENT_2])
def test_slotted_dataclass_retains_field_metadata_across_callback(pretty: int) -> None:
    @dataclasses.dataclass(slots=True)
    class Record:
        first: object
        last: object

    payload = Record(Marker("first"), Marker("last"))

    def mutate() -> None:
        Record.__dataclass_fields__.clear()
        payload.first = Marker("replacement-first")
        payload.last = Marker("replacement-last")

    actual = dumps_during_mutation(payload, mutate, option=pretty)
    # Field names are snapshotted; attributes are read as each field is visited.
    expected = {"first": "first", "last": "replacement-last"}
    assert actual == orjson.dumps(expected, option=pretty)


@pytest.mark.parametrize("payload", [[], {}, dataclasses.make_dataclass("Empty", [])()])
def test_empty_containers_keep_compact_empty_spelling(payload: object) -> None:
    expected = b"[]" if isinstance(payload, list) else b"{}"
    assert (
        orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        == expected
    )
