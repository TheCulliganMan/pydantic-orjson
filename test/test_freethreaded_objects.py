# SPDX-License-Identifier: (Apache-2.0 OR MIT)

"""Object lifetime and cache regression tests, also run on GIL-enabled Python."""

import gc
import json
import queue
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

import pytest

import orjson


def test_fragment_cross_thread_lifetime():
    """A Fragment retains its contents and releases them on another thread."""

    class Contents:
        pass

    handoff = queue.Queue()

    def produce():
        for _ in range(32):
            contents = Contents()
            handoff.put((orjson.Fragment(contents), weakref.ref(contents)))

    producer = threading.Thread(target=produce)
    producer.start()
    producer.join(timeout=10)
    assert not producer.is_alive()

    references = []
    while not handoff.empty():
        fragment, reference = handoff.get_nowait()
        assert reference() is not None
        # Invalid contents still participate in the normal lifetime contract.
        with pytest.raises(orjson.JSONEncodeError):
            orjson.dumps(fragment)
        references.append(reference)
        del fragment

    gc.collect()
    assert all(reference() is None for reference in references)


def test_shared_fragment_unicode_cache():
    """Threads may initialize the same immutable string's UTF-8 cache."""
    workers = 6
    barrier = threading.Barrier(workers)
    # Joining creates fresh strings whose UTF-8 caches have not been populated.
    texts = ['"' + "".join([char, "xyz"] * 97) + '"' for char in ("é", "中", "🐈")]
    fragments = [orjson.Fragment(text) for text in texts]

    def encode(_):
        barrier.wait(timeout=10)
        results = []
        for _ in range(24):
            for fragment in fragments:
                results.append(orjson.dumps(fragment))
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(encode, range(workers)))

    expected = [text.encode() for text in texts] * 24
    assert all(result == expected for result in results)


def test_threaded_decoded_string_hashes():
    """Decoded key ownership and the shared empty string hash remain valid."""
    workers = 6
    barrier = threading.Barrier(workers)
    payload = '{"":0,"é":1,"中":2,"🐈":3,"repeated":4,"repeated":5}'
    expected = json.loads(payload)

    def decode(_):
        barrier.wait(timeout=10)
        for _ in range(100):
            result = orjson.loads(payload)
            assert result == expected
            assert {key: hash(key) for key in result} == {
                key: hash(key) for key in expected
            }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(decode, range(workers)))


def test_threaded_output_buffers_and_abort():
    """Growing and failed writers cannot corrupt another thread's output."""
    workers = 6
    barrier = threading.Barrier(workers)
    sizes = (0, 1, 4095, 4096, 4097, 65536)

    def encode(index):
        barrier.wait(timeout=10)
        for size in sizes:
            value = (str(index) + "é\\\n") * size
            expected = json.dumps(value, ensure_ascii=False).encode() + b"\n"
            assert orjson.dumps(value, option=orjson.OPT_APPEND_NEWLINE) == expected
            # Fail after reserving/growing output, then immediately allocate again.
            with pytest.raises(orjson.JSONEncodeError):
                orjson.dumps([value, object()])
            assert orjson.dumps(orjson.Fragment(b"")) == b""
            assert orjson.dumps(index) == str(index).encode()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(encode, range(workers)))
