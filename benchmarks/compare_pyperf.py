# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Validate comparable pyperf reports, then show medians and pyperf statistics.

Successful execution verifies report compatibility, not a performance release
gate. Input files and all individual measurements are retained unchanged.
"""

from __future__ import annotations

import argparse
import math
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

import pyperf

REQUIRED_MATCHES = (
    "suite_sha256",
    "platform",
    "cpu_count",
    "python_version",
    "python_implementation",
    "python_compiler",
    "pydantic",
    "pydantic_core",
    "perf_version",
    "unit",
    "fixture_sha256",
    "fixture_bytes",
)
OPTIONAL_MATCHES = (
    "cpu_model_name",
    "cpu_model",
    "cpu_affinity",
    "python_cflags",
    "python_gc",
    "timer",
    "timeit_setup",
    "timeit_stmt",
    "timeit_teardown",
    "macos_qos_requested",
)


def select_benchmarks(suite: pyperf.BenchmarkSuite, *, native_only: bool):
    return {
        benchmark.get_name(): benchmark
        for benchmark in suite.get_benchmarks()
        if not native_only or benchmark.get_name().startswith(("dumps.", "loads."))
    }


def validate_reports(baseline, candidate) -> None:
    if not baseline or not candidate:
        raise ValueError("No benchmarks selected in one or both reports")
    if baseline.keys() != candidate.keys():
        raise ValueError(
            "Different selected case sets: "
            f"missing={sorted(baseline.keys() - candidate.keys())}, "
            f"added={sorted(candidate.keys() - baseline.keys())}"
        )
    for name, previous in baseline.items():
        before = previous.get_metadata()
        after = candidate[name].get_metadata()
        for field in REQUIRED_MATCHES:
            if field not in before or field not in after:
                raise ValueError(f"Missing required metadata: {name}: {field}")
            if before[field] != after[field]:
                raise ValueError(f"Different metadata: {name}: {field}")
        for field in OPTIONAL_MATCHES:
            if (field in before) != (field in after) or before.get(field) != after.get(
                field
            ):
                raise ValueError(f"Different metadata: {name}: {field}")
        if before["unit"] != "second":
            raise ValueError(f"Expected latency measurements in seconds: {name}")
        for report in (previous, candidate[name]):
            values = report.get_values()
            if not values or any(
                value <= 0 or not math.isfinite(value) for value in values
            ):
                raise ValueError(f"Missing or invalid timing values: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--native-only",
        action="store_true",
        help="Compare only dumps.* and loads.*; omit typed cases in both reports",
    )
    args = parser.parse_args()
    try:
        baseline = select_benchmarks(
            pyperf.BenchmarkSuite.load(str(args.baseline)), native_only=args.native_only
        )
        candidate = select_benchmarks(
            pyperf.BenchmarkSuite.load(str(args.candidate)),
            native_only=args.native_only,
        )
        validate_reports(baseline, candidate)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))

    print("Selected cases and recorded environment/fixture metadata match.")
    print("Median ratio = baseline / candidate; >1 favors the candidate.")
    print("Medians are descriptive; pyperf's statistical comparison follows.\n")
    print("| Case | Baseline median µs | Candidate median µs | Median ratio |")
    print("| --- | ---: | ---: | ---: |")
    for name, previous in baseline.items():
        old = statistics.median(previous.get_values())
        new = statistics.median(candidate[name].get_values())
        print(f"| {name} | {old * 1e6:.3f} | {new * 1e6:.3f} | {old / new:.3f}x |")
    print(
        "\nThe comparison does not certify stability, representative workload "
        "coverage, or a performance release gate.\n",
        flush=True,
    )

    # Public Suite APIs preserve each Run, including calibration, warmups,
    # metadata and timing samples. Only the selected case set is filtered.
    with tempfile.TemporaryDirectory(prefix="orjson-pyperf-compare-") as directory:
        previous_file = str(Path(directory) / "baseline.json")
        current_file = str(Path(directory) / "candidate.json")
        pyperf.BenchmarkSuite(list(baseline.values())).dump(previous_file)
        pyperf.BenchmarkSuite([candidate[name] for name in baseline]).dump(current_file)
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pyperf",
                "compare_to",
                previous_file,
                current_file,
                "--table",
                "--table-format",
                "md",
                "--verbose",
            ],
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
