# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Diagnostic native JSON throughput with fixed total work across thread counts."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import sysconfig
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

ORDER_SEED = 24013
WARMUP_CALLS = 10


def gil_enabled() -> bool:
    return getattr(sys, "_is_gil_enabled", lambda: True)()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Case:
    name: str
    function: Callable[[Any], Any]
    argument: Any
    expected: Any
    fixture: bytes

    def check(self, result: Any) -> None:
        if type(result) is not type(self.expected) or result != self.expected:
            raise AssertionError(f"Incorrect output: {self.name}")


def cases(orjson: Any) -> list[Case]:
    event = {
        "id": 123,
        "event": "order.updated",
        "customer": {"name": "Zoë 森", "active": True, "note": None},
        "amount": 123.25,
        "tags": ["online", "priority", "📦"],
        "message": 'line one\nline two\t"quoted" \\ path',
    }
    fixtures = {
        "event": event,
        "records_128": [
            dict(event, id=index, amount=index / 4) for index in range(128)
        ],
    }
    result = []
    for name, value in fixtures.items():
        encoded = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
        result.extend(
            (
                Case(f"dumps.{name}", orjson.dumps, value, encoded, encoded),
                Case(f"loads.{name}", orjson.loads, encoded, value, encoded),
            )
        )
    return result


def worker(
    case: Case,
    count: int,
    start: threading.Barrier,
    finish: threading.Barrier,
) -> dict[str, int]:
    try:
        function, argument = case.function, case.argument
        for _ in range(WARMUP_CALLS):
            case.check(function(argument))
        start.wait()
        started = time.perf_counter_ns()
        cpu_started = time.thread_time_ns()
        # Every iteration invokes the native operation. Retain only its latest
        # output; all preceding outputs are released by normal assignment.
        for _ in range(count):
            result = function(argument)
        cpu_elapsed = time.thread_time_ns() - cpu_started
        stopped = time.perf_counter_ns()
        # No output checks run until every worker has left its timed loop.
        finish.wait()
        case.check(result)
        return {
            "operations": count,
            "started_ns": started,
            "stopped_ns": stopped,
            "loop_elapsed_ns": stopped - started,
            "thread_cpu_ns": cpu_elapsed,
        }
    except BaseException:
        start.abort()
        finish.abort()
        raise


def sample(case: Case, threads: int, iterations: int) -> dict[str, Any]:
    # Distribute the remainder too: total measured calls never depend on threads.
    quotient, remainder = divmod(iterations, threads)
    counts = [quotient + (index < remainder) for index in range(threads)]
    stamps = []
    start = threading.Barrier(
        threads + 1, action=lambda: stamps.append(time.perf_counter_ns())
    )
    finish = threading.Barrier(
        threads + 1, action=lambda: stamps.append(time.perf_counter_ns())
    )
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(worker, case, count, start, finish) for count in counts
        ]
        try:
            start.wait()
            finish.wait()
        except BaseException:
            start.abort()
            finish.abort()
            raise
        workers = [future.result() for future in futures]
    for measurement in workers:
        measurement["start_offset_ns"] = measurement.pop("started_ns") - stamps[0]
        measurement["stop_offset_ns"] = measurement.pop("stopped_ns") - stamps[0]
    elapsed = stamps[1] - stamps[0]
    assert sum(item["operations"] for item in workers) == iterations
    return {
        "threads": threads,
        "total_operations": iterations,
        "wall_elapsed_ns": elapsed,
        "operations_per_second": iterations * 1_000_000_000 / elapsed,
        "workers": workers,
        "correctness_checked": True,
    }


def cpu_model() -> str:
    if sys.platform == "darwin":
        try:
            return subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                key, _, value = line.partition(":")
                if key.strip() in {"model name", "Hardware"}:
                    return value.strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def summaries(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault((result["case"], result["threads"]), []).append(result)
    output = []
    for (name, threads), measurements in sorted(grouped.items()):
        elapsed = [item["wall_elapsed_ns"] for item in measurements]
        median = statistics.median(elapsed)
        baseline = grouped.get((name, 1))
        speedup = (
            statistics.median(item["wall_elapsed_ns"] for item in baseline) / median
            if baseline
            else None
        )
        output.append(
            {
                "case": name,
                "threads": threads,
                "median_wall_ns": median,
                "min_wall_ns": min(elapsed),
                "max_wall_ns": max(elapsed),
                "mad_wall_ns": statistics.median(
                    abs(value - median) for value in elapsed
                ),
                "median_operations_per_second": statistics.median(
                    item["operations_per_second"] for item in measurements
                ),
                "speedup_vs_one_thread": speedup,
                "parallel_efficiency_vs_one_thread": speedup / threads
                if speedup
                else None,
            }
        )
    return output


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", nargs="+", type=positive_int, default=[1, 2, 4, 8])
    parser.add_argument(
        "--iterations",
        type=positive_int,
        default=10_000,
        help="total native calls per case/repeat, divided across threads (default: 10000)",
    )
    parser.add_argument("--repeats", type=positive_int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-gil",
        action="store_true",
        help="allow a GIL-enabled control; default requires a free-threaded build with GIL off",
    )
    args = parser.parse_args()
    if len(set(args.threads)) != len(args.threads) or args.iterations < max(
        args.threads
    ):
        parser.error("thread counts must be unique and cannot exceed --iterations")
    if args.output.exists():
        parser.error("output already exists; choose a new report filename")
    before_import = gil_enabled()
    orjson = importlib.import_module("orjson")
    extension = importlib.import_module("orjson.orjson")
    after_import = gil_enabled()
    free_threaded = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    if not args.allow_gil and (not free_threaded or before_import or after_import):
        parser.error(
            "requires GIL-disabled Python before/after import; use --allow-gil for a control"
        )
    workloads = cases(orjson)
    for case in workloads:
        case.check(case.function(case.argument))
    randomizer = random.Random(ORDER_SEED)
    results = []
    for repeat in range(args.repeats):
        order = [(case, threads) for case in workloads for threads in args.threads]
        randomizer.shuffle(order)
        for case, threads in order:
            measurement = sample(case, threads, args.iterations)
            measurement.update(
                case=case.name, repeat=repeat, execution_index=len(results)
            )
            results.append(measurement)
            if gil_enabled() != after_import:
                raise RuntimeError(
                    "GIL state changed during measurement; report rejected"
                )
    for case in workloads:
        case.check(case.function(case.argument))
    summary = summaries(results)
    report = {
        "schema_version": 1,
        "metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "python_compiler": platform.python_compiler(),
            "python_abi": sysconfig.get_config_var("SOABI"),
            "python_abiflags": getattr(sys, "abiflags", ""),
            "free_threaded_build": free_threaded,
            "gil_before_import": before_import,
            "gil_after_import": after_import,
            "gil_after_measurement": gil_enabled(),
            "platform": platform.system(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "distribution": {
                "name": "orjson",
                "version": importlib.metadata.version("orjson"),
            },
            "native_module_version": orjson.__version__,
            "native_extension_sha256": digest(Path(extension.__file__).read_bytes()),
            "harness_sha256": digest(Path(__file__).read_bytes()),
        },
        "method": {
            "work": "fixed total native calls per case and repeat, divided across threads",
            "iterations": args.iterations,
            "threads": args.threads,
            "repeats": args.repeats,
            "order_seed": ORDER_SEED,
            "warmup_calls_per_worker": WARMUP_CALLS,
            "input_sharing": "shared inputs, never mutated",
            "timing": "barrier release through all workers completing; thread creation excluded",
            "included_costs": "native calls, Python loops, prior output destruction, scheduling and barriers",
            "correctness": "stdlib JSON oracle; warmup and final output of every worker checked outside timing",
            "retained_outputs": "one final output per worker, released after timing and validation",
            "gc_enabled": gc.isenabled(),
            "gc_thresholds": gc.get_threshold(),
            "latency": "batch wall times only; no per-operation latency distribution",
            "scope": "one-process local diagnostic; no universal speed or scaling claim",
        },
        "fixtures": {
            case.name: {"json_bytes": len(case.fixture), "sha256": digest(case.fixture)}
            for case in workloads
        },
        "results": results,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(
        "Local diagnostic; fixed total work. Ratios compare with one thread in this run."
    )
    for item in summary:
        speedup = item["speedup_vs_one_thread"]
        ratio = f"{speedup:.3f}x" if speedup is not None else "n/a"
        print(
            f"{item['case']:20} {item['threads']:2} threads  "
            f"{item['median_operations_per_second']:12,.0f} ops/s  {ratio}"
        )


if __name__ == "__main__":
    main()
