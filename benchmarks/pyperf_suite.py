# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Process-isolated, correctness-checked native and typed JSON benchmarks."""

from __future__ import annotations

import hashlib
import importlib.metadata
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyperf
from pydantic import BaseModel, TypeAdapter

import orjson
import orjson.orjson as extension

try:
    from orjson.pydantic import Codec
except ImportError:  # Published upstream has no typed integration module.
    Codec = None


class Item(BaseModel):
    id: int
    name: str
    active: bool


@dataclass
class Workload:
    name: str
    function: Any
    value: Any
    options: dict[str, Any]
    expected: Any
    fixture: bytes


def workloads() -> list[Workload]:
    event = {"id": 123, "name": "example", "active": True, "tags": ["api", "json"]}
    records = [dict(event, id=i) for i in range(128)]
    text = (
        "The service returns validated structured output with stable field names. "
        "Each response contains a result and the context needed to interpret it. "
    )
    fixtures = {
        "event": event,
        "records": records,
        "ascii_text": {"role": "assistant", "content": text * 32},
        "unicode_text": {"content": ("Café 雪の街 — 📦 " + text) * 32},
        "escaped_text": {
            "content": ('line one\nline two\t"quoted" \\ path ' + text) * 32
        },
        "dense_escapes": '\n\t"\\' * 256,
        "numbers": list(range(2048)),
        "floats": [i / 7 for i in range(2048)],
        "datetimes": [datetime(2026, 11, 24, tzinfo=timezone.utc)] * 32,
    }
    result = []
    for name, value in fixtures.items():
        encoded = orjson.dumps(value)
        result.append(
            Workload("dumps." + name, orjson.dumps, value, {}, encoded, encoded)
        )
        result.append(
            Workload(
                "loads." + name,
                orjson.loads,
                encoded,
                {},
                orjson.loads(encoded),
                encoded,
            )
        )
    for name, option in (
        ("fastapi", orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY),
        ("sorted", orjson.OPT_SORT_KEYS),
        ("pretty", orjson.OPT_INDENT_2),
    ):
        encoded = orjson.dumps(records, option=option)
        result.append(
            Workload(
                "dumps.records_" + name,
                orjson.dumps,
                records,
                {"option": option},
                encoded,
                encoded,
            )
        )
    for size in (64, 256, 321, 322, 512):
        encoded = b'{"message":"' + b"x" * (size - 14) + b'"}'
        assert len(encoded) == size
        result.append(
            Workload(
                f"loads.bytes_{size}",
                orjson.loads,
                encoded,
                {},
                {"message": "x" * (size - 14)},
                encoded,
            )
        )
    for name, schema, value in (
        ("small", Item, Item(id=1, name="example", active=True)),
        (
            "batch",
            list[Item],
            [Item(id=i, name=f"item {i}", active=True) for i in range(128)],
        ),
    ):
        adapter = TypeAdapter(schema)
        encoded = adapter.dump_json(value)
        engines = [("adapter", adapter.dump_json, adapter.validate_json)]
        if Codec is not None:
            codec = Codec(adapter)
            engines.append(("codec", codec.dumps, codec.loads))
        for engine, encoder, decoder in engines:
            result.append(
                Workload(
                    f"typed.{engine}.dumps_{name}", encoder, value, {}, encoded, encoded
                )
            )
            result.append(
                Workload(
                    f"typed.{engine}.loads_{name}", decoder, encoded, {}, value, encoded
                )
            )
        if Codec is not None:
            result.append(
                Workload(
                    f"typed.codec.dumps_quiet_{name}",
                    codec.dumps,
                    value,
                    {"warnings": False},
                    encoded,
                    encoded,
                )
            )
        result.append(
            Workload(
                f"typed.adapter.dumps_quiet_{name}",
                adapter.dump_json,
                value,
                {"warnings": False},
                encoded,
                encoded,
            )
        )
    return result


def add_worker_args(command: list[str], args: Any) -> None:
    if args.group:
        command.extend(("--group", args.group))
    if args.macos_qos:
        command.append("--macos-qos")


def main() -> None:
    runner = pyperf.Runner(add_cmdline_args=add_worker_args)
    runner.argparser.add_argument(
        "--group", help="Comma-separated name prefixes to select"
    )
    runner.argparser.add_argument(
        "--macos-qos",
        action="store_true",
        help="Request user-initiated QoS on macOS (not CPU affinity)",
    )
    args = runner.parse_args()
    if args.macos_qos:
        import ctypes  # noqa: PLC0415

        if sys.platform != "darwin":
            raise RuntimeError("--macos-qos requires macOS")
        system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        set_qos = system.pthread_set_qos_class_self_np
        set_qos.argtypes = [ctypes.c_uint, ctypes.c_int]
        set_qos.restype = ctypes.c_int
        error = set_qos(0x19, 0)  # QOS_CLASS_USER_INITIATED, relative priority 0
        if error:
            raise OSError(error, "Unable to request benchmark thread QoS")
        runner.metadata["macos_qos_requested"] = "user-initiated"
    runner.metadata.update(
        {
            "orjson_distribution": importlib.metadata.version("orjson"),
            "pydantic": importlib.metadata.version("pydantic"),
            "pydantic_core": importlib.metadata.version("pydantic-core"),
            "native_sha256": hashlib.sha256(
                Path(extension.__file__).read_bytes()
            ).hexdigest(),
            "suite_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    )
    for case in workloads():
        if args.group and not case.name.startswith(tuple(args.group.split(","))):
            continue
        assert case.function(case.value, **case.options) == case.expected, case.name
        # timeit avoids an extra Python callback per operation. The same prepared
        # values, schema, keyword arguments and expression are used in both wheels.
        expression = "function(value"
        expression += "".join(f", {key}={key}" for key in case.options)
        expression += ")"
        namespace = {"function": case.function, "value": case.value, **case.options}
        runner.timeit(
            case.name,
            expression,
            globals=namespace,
            metadata={
                "fixture_sha256": hashlib.sha256(case.fixture).hexdigest(),
                "fixture_bytes": len(case.fixture),
            },
        )
        assert case.function(case.value, **case.options) == case.expected, case.name


if __name__ == "__main__":
    main()
