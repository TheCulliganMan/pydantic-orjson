# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Measure one real large JSON fixture, without fixture construction in timing."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import sys
import sysconfig
import time
from pathlib import Path

import psutil
import pyperf
from matrix_suite import ENGINES, LABELS


def suite_hash() -> str:
    directory = Path(__file__).parent
    digest = hashlib.sha256()
    for name in ("large_suite.py", "large_fixtures.py", "matrix_suite.py"):
        digest.update(name.encode())
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    # Identifying a built-in stdlib accelerator can involve libpython itself.
    # Stream it so fingerprinting does not leave a library-sized freed buffer
    # in the prepared memory baseline for only one of the engines.
    with path.open("rb") as source:
        for block in iter(lambda: source.read(128 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(engine: str) -> dict:
    if engine == "stdlib":
        import _json  # noqa: PLC0415

        native = getattr(_json, "__file__", None)
        if native is None:
            native = str(
                Path(sysconfig.get_config_var("LIBDIR"))
                / sysconfig.get_config_var("LDLIBRARY")
            )
        version = sys.version.split()[0]
    else:
        import orjson.orjson as extension  # noqa: PLC0415

        native = extension.__file__
        version = importlib.metadata.version("orjson")
        if ("+pydantic" in version) != (engine == "candidate"):
            raise ValueError(f"Wrong installed library for {LABELS[engine]}: {version}")
    return {
        "engine": engine,
        "engine_label": LABELS[engine],
        "engine_version": version,
        "native_sha256": file_hash(Path(native)),
        "python_executable_sha256": file_hash(Path(sys.executable)),
        "python_gil_disabled_build": str(
            bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
        ),
        "python_gil_enabled": str(getattr(sys, "_is_gil_enabled", lambda: True)()),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "random"),
    }


def function(engine: str, operation: str):
    if engine != "stdlib":
        import orjson  # noqa: PLC0415

        return getattr(orjson, operation)
    if operation == "loads":
        return json.loads

    # UTF-8 conversion is part of the measured operation for the bytes contract.
    def encode(value):
        return json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")

    return encode


def prepare(path: Path, receipt: dict, operation: str):
    raw = path.read_bytes()
    if (
        len(raw) != receipt["actual_bytes"]
        or hashlib.sha256(raw).hexdigest() != receipt["sha256"]
    ):
        raise ValueError("Fixture bytes/hash do not match their receipt")
    if operation == "loads":
        return raw
    # Identical input-object construction for every encoding engine.
    return json.loads(raw)


def validate(fn, value, operation: str, path: Path) -> int:
    result = fn(value)
    if operation == "dumps":
        assert isinstance(result, bytes)
        assert json.loads(result) == value
        return len(result)
    expected = json.loads(path.read_bytes())
    assert result == expected
    return path.stat().st_size


def qos(enabled: bool) -> None:
    if not enabled:
        return
    if sys.platform != "darwin":
        raise ValueError("--macos-qos requires macOS")
    import ctypes  # noqa: PLC0415

    system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    set_qos = system.pthread_set_qos_class_self_np
    set_qos.argtypes, set_qos.restype = [ctypes.c_uint, ctypes.c_int], ctypes.c_int
    error = set_qos(0x19, 0)
    if error:
        raise OSError(error, "Unable to request benchmark thread QoS")


def add_arguments(parser):
    parser.add_argument("--engine", required=True, choices=ENGINES)
    parser.add_argument("--operation", required=True, choices=("dumps", "loads"))
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--macos-qos", action="store_true")


def worker_arguments(command, args):
    for name in ("engine", "operation", "fixture", "receipt", "source_commit"):
        command.extend(("--" + name.replace("_", "-"), str(getattr(args, name))))
    if args.macos_qos:
        command.append("--macos-qos")


def high_water() -> int:
    if sys.platform == "win32":
        return int(psutil.Process().memory_info().peak_wset)
    import resource  # noqa: PLC0415

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def memory_main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    qos(args.macos_qos)
    receipt = json.loads(args.receipt.read_text())
    fn = function(args.engine, args.operation)
    value = prepare(args.fixture, receipt, args.operation)
    gc.collect()
    process = psutil.Process()
    metadata = {
        **identity(args.engine),
        "operation": args.operation,
        "fixture_sha256": receipt["sha256"],
        "fixture_bytes": receipt["actual_bytes"],
        "source_commit": args.source_commit,
        "suite_sha256": suite_hash(),
        "preparation_high_water_rss_bytes": high_water(),
    }
    print(
        json.dumps(
            {
                "phase": "ready",
                "pid": os.getpid(),
                "baseline_rss_bytes": process.memory_info().rss,
                **metadata,
            }
        ),
        flush=True,
    )
    if sys.stdin.readline().strip() != "GO":
        raise RuntimeError("Missing memory measurement start handshake")
    started = time.perf_counter()
    result = fn(value)
    elapsed = time.perf_counter() - started
    output_bytes = len(result) if args.operation == "dumps" else receipt["actual_bytes"]
    print(
        json.dumps(
            {
                "phase": "complete",
                "elapsed_seconds": elapsed,
                "retained_result_rss_bytes": process.memory_info().rss,
                "output_bytes": output_bytes,
            }
        ),
        flush=True,
    )
    if sys.stdin.readline().strip() != "ACK":
        raise RuntimeError("Missing memory measurement end handshake")
    # Correctness checks run after the parent stops operation-window sampling.
    expected = (
        value if args.operation == "dumps" else json.loads(args.fixture.read_bytes())
    )
    actual = json.loads(result) if args.operation == "dumps" else result
    assert actual == expected
    print(
        json.dumps(
            {
                "phase": "validated",
                "validated": True,
                "process_high_water_rss_bytes": high_water(),
            }
        ),
        flush=True,
    )


def main():
    if "--memory" in sys.argv:
        memory_main()
        return
    runner = pyperf.Runner(add_cmdline_args=worker_arguments)
    add_arguments(runner.argparser)
    args = runner.parse_args()
    qos(args.macos_qos)
    receipt = json.loads(args.receipt.read_text())
    fn = function(args.engine, args.operation)
    value = prepare(args.fixture, receipt, args.operation)
    output_bytes = validate(fn, value, args.operation, args.fixture)
    gc.collect()
    runner.metadata.update(
        {
            **identity(args.engine),
            "source_commit": args.source_commit,
            "suite_sha256": suite_hash(),
            "fixture_sha256": receipt["sha256"],
            "fixture_bytes": receipt["actual_bytes"],
            "fixture_family": receipt["family"],
            "output_bytes": output_bytes,
            "contract": "UTF-8 bytes; fixture preparation excluded; call and result release included",
        }
    )
    if args.macos_qos:
        runner.metadata["macos_qos_requested"] = "user-initiated"
    runner.timeit(
        args.operation + "." + receipt["name"],
        "fn(value)",
        globals={"fn": fn, "value": value},
    )
    validate(fn, value, args.operation, args.fixture)


if __name__ == "__main__":
    main()
