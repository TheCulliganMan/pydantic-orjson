# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""No-GIL import, concurrent calls, and shared-container lifetime contracts."""

import gc
import json
import os
import subprocess
import sys
import sysconfig
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, Event

import pytest

import orjson

FREE_THREADED = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
pytestmark = pytest.mark.skipif(not FREE_THREADED, reason="free-threaded CPython only")


def test_import_does_not_enable_gil():
    environment = dict(os.environ)
    environment.pop("PYTHON_GIL", None)
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys; assert not sys._is_gil_enabled(); "
                "import orjson; assert not sys._is_gil_enabled(); "
                "assert orjson.loads(orjson.dumps({'ok': True})) == {'ok': True}"
            ),
        ],
        env=environment,
        check=True,
        timeout=30,
    )


def test_parallel_native_calls_fragments_and_callbacks():
    assert not sys._is_gil_enabled()
    barrier = Barrier(8)
    shared_fragment = orjson.Fragment(b'{"shared":true}')

    @dataclass
    class Record:
        number: int
        title: str

    class Custom:
        pass

    def default(value):
        assert isinstance(value, Custom)
        return orjson.loads(orjson.dumps({"nested": "雪"}))

    def worker(index):
        barrier.wait(timeout=15)
        for i in range(500):
            payload = {
                "record": Record(i, "thread " + str(index)),
                "fragment": shared_fragment,
                "custom": Custom(),
                "fresh": orjson.Fragment(b"[1,2,3]"),
            }
            parsed = orjson.loads(orjson.dumps(payload, default=default))
            assert parsed == {
                "record": {"number": i, "title": "thread " + str(index)},
                "fragment": {"shared": True},
                "custom": {"nested": "雪"},
                "fresh": [1, 2, 3],
            }

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(8)))
    assert not sys._is_gil_enabled()


@pytest.mark.parametrize(
    "option",
    [
        0,
        orjson.OPT_SORT_KEYS,
        orjson.OPT_NON_STR_KEYS,
        orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
    ],
)
def test_shared_mapping_mutation_uses_owned_snapshots(option):
    shared = {"initial": list(range(8))}
    barrier = Barrier(4)
    finished = Event()

    def mutate():
        barrier.wait(timeout=15)
        i = 0
        while not finished.is_set():
            shared.clear()
            shared.update({f"key {i % 10}": [i, "雪" * 16]})
            i += 1

    def read():
        barrier.wait(timeout=15)
        for _ in range(1000):
            parsed = json.loads(orjson.dumps(shared, option=option))
            assert isinstance(parsed, dict)
            assert all(isinstance(value, list) for value in parsed.values())

    with ThreadPoolExecutor(max_workers=4) as executor:
        writer = executor.submit(mutate)
        readers = [executor.submit(read) for _ in range(3)]
        try:
            for result in readers:
                result.result(timeout=30)
        finally:
            finished.set()
        writer.result(timeout=15)


def test_shared_list_resize_uses_owned_snapshot():
    shared = list(range(32))
    barrier = Barrier(4)
    finished = Event()

    def mutate():
        barrier.wait(timeout=15)
        while not finished.is_set():
            shared.clear()
            shared.extend(range(64))
            shared[:] = [1, 2, 3]

    def read():
        barrier.wait(timeout=15)
        for _ in range(1000):
            parsed = json.loads(orjson.dumps(shared))
            assert isinstance(parsed, list)
            assert all(type(value) is int for value in parsed)

    with ThreadPoolExecutor(max_workers=4) as executor:
        writer = executor.submit(mutate)
        readers = [executor.submit(read) for _ in range(3)]
        try:
            for result in readers:
                result.result(timeout=30)
        finally:
            finished.set()
        writer.result(timeout=15)


@pytest.mark.parametrize("view", [False, True])
def test_mutable_json_input_is_copied_before_parsing(view):
    shared = bytearray(b'{"value":11111111}')
    payload = memoryview(shared) if view else shared
    barrier = Barrier(4)
    finished = Event()

    def mutate():
        barrier.wait(timeout=15)
        while not finished.is_set():
            shared[:] = b'{"value":22222222}'
            shared[:] = b'{"value":11111111}'

    def read():
        barrier.wait(timeout=15)
        for _ in range(1000):
            assert orjson.loads(payload) in ({"value": 11111111}, {"value": 22222222})

    with ThreadPoolExecutor(max_workers=4) as executor:
        writer = executor.submit(mutate)
        readers = [executor.submit(read) for _ in range(3)]
        try:
            for result in readers:
                result.result(timeout=30)
        finally:
            finished.set()
        writer.result(timeout=15)


@pytest.mark.parametrize("factory", [bytearray, memoryview])
def test_mutable_input_error_owns_original_document(factory):
    source = b'{"message":"' + ("雪" * 200).encode() + b'", "bad":]}'
    with pytest.raises(orjson.JSONDecodeError) as caught:
        orjson.loads(factory(source))
    gc.collect()
    assert caught.value.doc == source.decode()
    assert caught.value.pos == len('{"message":"' + "雪" * 200 + '", "bad":')


def test_decode_while_another_thread_collects():
    finished = Event()
    barrier = Barrier(4)
    encoded = orjson.dumps([{str(i): [i, "雪"]} for i in range(100)])
    expected = orjson.loads(encoded)

    def collect():
        barrier.wait(timeout=15)
        while not finished.is_set():
            gc.collect()

    def read():
        barrier.wait(timeout=15)
        for _ in range(250):
            assert orjson.loads(encoded) == expected

    with ThreadPoolExecutor(max_workers=4) as executor:
        collector = executor.submit(collect)
        readers = [executor.submit(read) for _ in range(3)]
        try:
            for result in readers:
                result.result(timeout=30)
        finally:
            finished.set()
        collector.result(timeout=15)
