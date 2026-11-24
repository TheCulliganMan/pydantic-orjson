"""Correctness-checked local measurements; not a release-grade speed claim."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, TypeAdapter

import orjson
import orjson.orjson as extension

if TYPE_CHECKING:
    from collections.abc import Callable


class Item(BaseModel):
    id: int
    title: str
    price: float
    available: bool
    tags: list[str]
    created_at: datetime


class Batch(BaseModel):
    request_id: str
    items: list[Item]


@dataclass
class Case:
    name: str
    operation: Callable[[], Any]
    fixture: bytes
    check: Callable[[Any], bool]


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fixtures() -> dict[str, Any]:
    event = {
        "id": 123,
        "type": "order.updated",
        "customer": {"name": "Zoë 森", "active": True, "note": None},
        "amount": 123.45,
        "tags": ["online", "priority", "📦"],
    }
    return {
        "event": event,
        "records_64": [dict(event, id=i, amount=i / 4) for i in range(64)],
        "records_1024": [dict(event, id=i, amount=i / 4) for i in range(1024)],
    }


def cases(include_codec: bool) -> list[Case]:
    result: list[Case] = []
    for name, value in fixtures().items():
        encoded = orjson.dumps(value)
        result.extend(
            [
                Case(
                    f"untyped.dumps.{name}",
                    lambda v=value: orjson.dumps(v),
                    encoded,
                    lambda actual, expected=encoded: actual == expected,
                ),
                Case(
                    f"untyped.loads.{name}",
                    lambda data=encoded: orjson.loads(data),
                    encoded,
                    lambda actual, expected=value: actual == expected,
                ),
            ]
        )

    # Fixed schema and reusable adapter: construction is intentionally outside timing.
    model = Batch(
        request_id="benchmark-0001",
        items=[
            Item(
                id=i,
                title=f"Item {i} — café",
                price=i / 4,
                available=i % 2 == 0,
                tags=["warehouse", "sale"],
                created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            )
            for i in range(128)
        ],
    )
    adapter = TypeAdapter(Batch)
    model_bytes = adapter.dump_json(model)
    model_json = orjson.loads(model_bytes)

    def check_dump(actual: Any) -> bool:
        return isinstance(actual, bytes) and orjson.loads(actual) == model_json

    def check_load(actual: Any) -> bool:
        return isinstance(actual, Batch) and actual == model

    result.extend(
        [
            Case(
                "typed.adapter.dumps",
                lambda: adapter.dump_json(model),
                model_bytes,
                check_dump,
            ),
            Case(
                "typed.model_dump_then_orjson.dumps",
                lambda: orjson.dumps(model.model_dump(mode="json")),
                model_bytes,
                check_dump,
            ),
            Case(
                "typed.adapter.loads",
                lambda: adapter.validate_json(model_bytes, strict=False),
                model_bytes,
                check_load,
            ),
            Case(
                "typed.orjson_then_validate_python.loads",
                lambda: adapter.validate_python(
                    orjson.loads(model_bytes), strict=False
                ),
                model_bytes,
                check_load,
            ),
        ]
    )
    if include_codec:
        from orjson.pydantic import Codec  # noqa: PLC0415 - unavailable in upstream

        codec = Codec(adapter)
        result.extend(
            [
                Case(
                    "typed.codec.dumps",
                    lambda: codec.dumps(model),
                    model_bytes,
                    check_dump,
                ),
                Case(
                    "typed.codec.loads",
                    lambda: codec.loads(model_bytes, strict=False),
                    model_bytes,
                    check_load,
                ),
            ]
        )
    return result


def time_batch(operation: Callable[[], Any], loops: int) -> int:
    enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        for _ in range(loops):
            operation()
        return time.perf_counter_ns() - start
    finally:
        if enabled:
            gc.enable()


def command(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            args, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def metadata() -> dict[str, Any]:
    extension_path = Path(extension.__file__)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_compiler": platform.python_compiler(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_model": command("sysctl", "-n", "machdep.cpu.brand_string")
        if sys.platform == "darwin"
        else platform.processor(),
        "logical_cpus": os.cpu_count(),
        "packages": {
            name: version(name) for name in ("orjson", "pydantic", "pydantic-core")
        },
        "extension_filename": extension_path.name,
        "extension_sha256": digest(extension_path.read_bytes()),
        "rustc_available_at_measurement": command("rustc", "--version"),
        "git_head": command("git", "rev-parse", "HEAD"),
        "git_dirty": bool(command("git", "status", "--porcelain")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label", required=True, help="For example upstream or candidate"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=11)
    parser.add_argument("--sample-ms", type=float, default=50.0)
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--include-codec", action="store_true")
    args = parser.parse_args()
    if args.samples < 3 or args.sample_ms <= 0:
        parser.error("Use at least three samples and a positive sample duration")

    measurements = cases(args.include_codec)
    loops: dict[str, int] = {}
    samples: dict[str, list[float]] = {case.name: [] for case in measurements}
    target_ns = args.sample_ms * 1_000_000
    for case in measurements:
        if not case.check(case.operation()):
            raise AssertionError(f"Correctness check failed: {case.name}")
        # Autoranging also warms each operation. Keep timed calls free of validation.
        count = 1
        while True:
            elapsed = time_batch(case.operation, count)
            if elapsed >= target_ns or count >= 1_000_000:
                break
            count = min(
                1_000_000,
                max(count + 1, int(count * target_ns / max(elapsed, 1) * 1.1)),
            )
        loops[case.name] = count

    rng = random.Random(args.seed)
    for _ in range(args.samples):
        order = measurements.copy()
        rng.shuffle(order)
        for case in order:
            count = loops[case.name]
            samples[case.name].append(time_batch(case.operation, count) / count)

    results = []
    for case in measurements:
        if not case.check(case.operation()):
            raise AssertionError(
                f"Post-measurement correctness check failed: {case.name}"
            )
        values = samples[case.name]
        median = statistics.median(values)
        results.append(
            {
                "name": case.name,
                "fixture_bytes": len(case.fixture),
                "fixture_sha256": digest(case.fixture),
                "loops_per_sample": loops[case.name],
                "samples_ns_per_op": values,
                "median_ns_per_op": median,
                "mad_ns_per_op": statistics.median(
                    abs(value - median) for value in values
                ),
                "min_ns_per_op": min(values),
                "max_ns_per_op": max(values),
                "operations_per_second": 1_000_000_000 / median,
                "correctness_checked": True,
            }
        )
    report = {
        "schema_version": 1,
        "label": args.label,
        "metadata": metadata(),
        "method": {
            "timer": "perf_counter_ns",
            "samples": args.samples,
            "target_sample_ms": args.sample_ms,
            "order_seed": args.seed,
            "gc": "disabled within each timed batch; original state restored",
            "warmup": "adaptive autoranging to target sample duration per case",
            "scope": "single-process local diagnostic; no confidence or speed guarantee",
            "typed_decode_semantics": "non-strict fixed schema; Python and JSON outputs checked equal",
        },
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {len(results)} correctness-checked measurements to {args.output}")


if __name__ == "__main__":
    main()
