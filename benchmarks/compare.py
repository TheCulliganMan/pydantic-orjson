"""Compare matching local measurements without treating noise as a speed claim."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    candidate = json.loads(args.candidate.read_text())
    if baseline["schema_version"] != 1 or candidate["schema_version"] != 1:
        parser.error("Unsupported report schema")
    for field in (
        "python",
        "python_compiler",
        "platform",
        "machine",
        "cpu_model",
        "logical_cpus",
    ):
        if baseline["metadata"][field] != candidate["metadata"][field]:
            parser.error(f"Different environments: {field}")
    for package in ("pydantic", "pydantic-core"):
        if (
            baseline["metadata"]["packages"][package]
            != candidate["metadata"]["packages"][package]
        ):
            parser.error(f"Different dependency versions: {package}")
    for field in ("samples", "target_sample_ms", "order_seed", "gc", "warmup"):
        if baseline["method"][field] != candidate["method"][field]:
            parser.error(f"Different measurement settings: {field}")
    previous = {result["name"]: result for result in baseline["results"]}
    current = {result["name"]: result for result in candidate["results"]}
    if previous.keys() != current.keys():
        parser.error(
            "Different case sets: "
            f"missing={sorted(previous.keys() - current.keys())}, "
            f"added={sorted(current.keys() - previous.keys())}"
        )
    print(
        "Local diagnostic only: ratio = baseline median / candidate median; >1 favors candidate."
    )
    print(
        "MAD is within-process median absolute deviation, not a confidence interval.\n"
    )
    print("| Case | Baseline µs | Candidate µs | Ratio | Candidate MAD % |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for name, result in current.items():
        median = result["median_ns_per_op"]
        mad_pct = result["mad_ns_per_op"] / median * 100
        old = previous[name]
        if old["fixture_sha256"] != result["fixture_sha256"]:
            parser.error(f"Different fixtures: {name}")
        if not old["correctness_checked"] or not result["correctness_checked"]:
            parser.error(f"Unchecked correctness: {name}")
        before = old["median_ns_per_op"]
        print(
            f"| {name} | {before / 1000:.3f} | {median / 1000:.3f} | {before / median:.3f}x | {mad_pct:.2f} |"
        )


if __name__ == "__main__":
    main()
