# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Report all three engines and optionally enforce an observed performance gate.

No aggregate average can hide a slower, unstable, missing or unsupported case.
Worker ranges are descriptive bounds, not statistical confidence intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

import pyperf
from matrix_suite import ENGINES, LABELS, cases

REQUIRED_MATCHES = (
    "suite_sha256",
    "profile",
    "matrix_contract",
    "platform",
    "cpu_count",
    "python_version",
    "python_implementation",
    "python_compiler",
    "python_executable_sha256",
    "python_gil_disabled_build",
    "python_gil_enabled",
    "pydantic",
    "pydantic_core",
    "python_hash_seed",
    "perf_version",
    "unit",
    "fixture_sha256",
    "fixture_bytes",
    "pipeline",
)
OPTIONAL_MATCHES = (
    "cpu_model_name",
    "cpu_model",
    "cpu_affinity",
    "python_cflags",
    "python_config_args",
    "python_gc",
    "timer",
    "macos_qos_requested",
    "cpu_config",
)


def load_reports(directory: Path) -> tuple[dict, dict]:  # noqa: PLR0912, PLR0915
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["format"] != 1 or manifest["status"] != "complete":
        raise ValueError("Incomplete or unknown matrix manifest")
    if manifest["labels"] != LABELS:
        raise ValueError("Engine labels differ from the declared comparison")
    if manifest["rounds"] < 2 or manifest["rounds"] % 2:
        raise ValueError("Missing balanced forward/reverse rounds")
    expected_names = [case.name for case in cases(manifest["profile"])]
    names = manifest["cases"]
    if not names or len(set(names)) != len(names):
        raise ValueError("Empty or duplicate case manifest")
    if not manifest["partial"] and names != expected_names:
        raise ValueError("Incomplete declared profile")
    if set(names) - set(expected_names):
        raise ValueError("Unknown cases in manifest")
    reports = {name: {engine: [] for engine in ENGINES} for name in names}
    seen = set()
    for entry in manifest["measurements"]:
        key = (entry["case"], entry["engine"], entry["round"])
        if key in seen:
            raise ValueError(f"Duplicate measurement: {key}")
        seen.add(key)
        if entry["returncode"]:
            raise ValueError(f"Failed measurement: {key}")
        if (
            key[0] not in reports
            or key[1] not in ENGINES
            or not 1 <= key[2] <= manifest["rounds"]
        ):
            raise ValueError(f"Unexpected measurement: {key}")
        for field in ("report", "log"):
            path = directory / entry[field]
            if (
                path.parent != directory
                or hashlib.sha256(path.read_bytes()).hexdigest()
                != entry[field + "_sha256"]
            ):
                raise ValueError(f"Changed or invalid evidence: {path}")
        suite = pyperf.BenchmarkSuite.load(str(directory / entry["report"]))
        if suite.get_benchmark_names() != [entry["case"]]:
            raise ValueError(f"Different case in {entry['report']}")
        benchmark = suite.get_benchmark(entry["case"])
        metadata = benchmark.get_metadata()
        if (
            metadata["engine"] != entry["engine"]
            or metadata["engine_label"] != LABELS[entry["engine"]]
        ):
            raise ValueError(f"Wrong engine: {entry['report']}")
        if metadata["suite_sha256"] != manifest["suite_sha256"]:
            raise ValueError("Suite changed during the run")
        if metadata["profile"] != manifest["profile"]:
            raise ValueError("Profile differs from manifest")
        if metadata["unit"] != "second":
            raise ValueError("Only latency measurements in seconds are supported")
        if not benchmark.get_values() or any(
            not math.isfinite(v) or v <= 0 for v in benchmark.get_values()
        ):
            raise ValueError(f"Invalid timing: {key}")
        reports[key[0]][key[1]].append((key[2], benchmark))
    for name, engines in reports.items():
        reference = None
        for engine, rounds in engines.items():
            rounds.sort(key=lambda item: item[0])
            if [item[0] for item in rounds] != list(range(1, manifest["rounds"] + 1)):
                raise ValueError(f"Missing rounds: {name}: {engine}")
            identity = None
            for _, benchmark in rounds:
                metadata = benchmark.get_metadata()
                current_identity = (
                    metadata["engine_version"],
                    metadata["native_sha256"],
                )
                if identity is not None and identity != current_identity:
                    raise ValueError(f"Engine changed between rounds: {name}: {engine}")
                identity = current_identity
                if reference is None:
                    reference = metadata
                for field in REQUIRED_MATCHES:
                    if (
                        field not in metadata
                        or field not in reference
                        or metadata[field] != reference[field]
                    ):
                        raise ValueError(
                            f"Different or missing metadata: {name}: {field}"
                        )
                for field in OPTIONAL_MATCHES:
                    if (field in reference) != (field in metadata) or reference.get(
                        field
                    ) != metadata.get(field):
                        raise ValueError(
                            f"Different optional metadata: {name}: {field}"
                        )
    # A different wheel halfway through the matrix must not be accepted simply
    # because each individual case happened to use a matching pair of rounds.
    for engine in ENGINES:
        identities = {
            (b.get_metadata()["engine_version"], b.get_metadata()["native_sha256"])
            for engines in reports.values()
            for _, b in engines[engine]
        }
        if len(identities) != 1:
            raise ValueError(f"Engine identity changed across cases: {engine}")
    return manifest, reports


def summarize(rounds: list, max_spread: float) -> dict:
    workers = []
    round_medians = []
    sample_spreads = []
    adequate = True
    for _, benchmark in rounds:
        runs = [run for run in benchmark.get_runs() if run.values]
        adequate &= len(runs) >= 4 and all(len(run.values) >= 4 for run in runs)
        medians = [statistics.median(run.values) for run in runs]
        workers.extend(medians)
        round_medians.append(statistics.median(medians))
        sample_spreads.extend(max(run.values) / min(run.values) - 1 for run in runs)
    spread = max(workers) / min(workers) - 1
    drift = max(round_medians) / min(round_medians) - 1
    return {
        "median_seconds": statistics.median(workers),
        "worker_medians_seconds": workers,
        "round_medians_seconds": round_medians,
        "worker_spread": spread,
        "round_drift": drift,
        "max_within_worker_spread": max(sample_spreads),
        "adequate_sampling": adequate,
        "stable": max(spread, drift, *sample_spreads) <= max_spread,
    }


def classify(
    candidate: dict, baseline: dict, *, min_win: float, tolerance: float
) -> dict:
    ratios = [
        before / after
        for before, after in zip(
            baseline["round_medians_seconds"],
            candidate["round_medians_seconds"],
            strict=True,
        )
    ]
    # Conservative separation across all observed process medians, not a ratio
    # of pooled samples that lets a lucky process outweigh a slow process.
    lower = min(baseline["worker_medians_seconds"]) / max(
        candidate["worker_medians_seconds"]
    )
    upper = max(baseline["worker_medians_seconds"]) / min(
        candidate["worker_medians_seconds"]
    )
    if not candidate["adequate_sampling"] or not baseline["adequate_sampling"]:
        status = "insufficient samples"
    elif not candidate["stable"] or not baseline["stable"]:
        status = "unstable"
    elif lower > 1 + min_win:
        status = "win"
    elif upper < 1 / (1 + tolerance):
        status = "regression"
    elif lower >= 1 / (1 + tolerance) and upper <= 1 + tolerance:
        status = "within tolerance"
    else:
        status = "inconclusive"
    return {
        "status": status,
        "ratios_by_round": ratios,
        "observed_ratio_bounds": [lower, upper],
        "no_regression": candidate["adequate_sampling"]
        and baseline["adequate_sampling"]
        and candidate["stable"]
        and baseline["stable"]
        and lower >= 1 / (1 + tolerance),
    }


def make_report(
    manifest: dict,
    reports: dict,
    *,
    max_spread: float,
    min_win: float,
    tolerance: float,
) -> tuple[dict, str]:
    result = {
        "labels": LABELS,
        "profile": manifest["profile"],
        "partial": manifest["partial"],
        "thresholds": {
            "max_spread": max_spread,
            "min_win": min_win,
            "tolerance": tolerance,
        },
        "cases": {},
    }
    lines = [
        "# Pydantic ORJSON / ORJSON / json",
        "",
        (
            "All durations are microseconds per operation; lower is better. Every encoder returns UTF-8 bytes. "
            "The json column includes UTF-8 encoding. Decode uses the same canonical bytes. "
            "Typed rows include model conversion/validation and are separate from native JSON performance."
        ),
        "",
        f"Profile: **{manifest['profile']}**; {len(reports)} cases; {manifest['rounds']} balanced rounds. "
        + (
            "**Partial diagnostic selection.**"
            if manifest["partial"]
            else "Complete declared profile."
        ),
        "",
        (
            f"A win requires every observed worker median to beat the baseline by >{min_win:.1%}, "
            f"with worker/sample spread and round drift ≤{max_spread:.1%}. "
            f"Tolerance is {tolerance:.1%}; within tolerance is not a win. "
            "These are conservative observed bounds, not confidence intervals or a guarantee on unmeasured workloads."
        ),
        "",
        "| Case | Pydantic ORJSON µs | ORJSON µs | json µs | Pydantic / ORJSON result | Pydantic / json result |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for name, engines in reports.items():
        stats = {
            engine: summarize(rounds, max_spread) for engine, rounds in engines.items()
        }
        comparisons = {
            engine: classify(
                stats["candidate"], stats[engine], min_win=min_win, tolerance=tolerance
            )
            for engine in ("upstream", "stdlib")
        }
        result["cases"][name] = {"engines": stats, "comparisons": comparisons}
        cells = [name] + [
            f"{stats[engine]['median_seconds'] * 1e6:.3f}" for engine in ENGINES
        ]
        for engine in ("upstream", "stdlib"):
            comparison = comparisons[engine]
            ratios = "/".join(
                f"{ratio:.3f}x" for ratio in comparison["ratios_by_round"]
            )
            cells.append(f"{comparison['status']} ({ratios})")
        lines.append("| " + " | ".join(cells) + " |")
    comparisons = [
        comparison
        for row in result["cases"].values()
        for comparison in row["comparisons"].values()
    ]
    qualified = not manifest["partial"] and manifest["profile"] != "smoke"
    result["all_cases_win"] = qualified and all(
        c["status"] == "win" for c in comparisons
    )
    result["no_observed_regressions"] = qualified and all(
        c["no_regression"] for c in comparisons
    )
    lines += [
        "",
        (
            "Ratios are baseline / Pydantic ORJSON for each round; >1 favors Pydantic ORJSON. "
            "Unstable ratios remain visible but are inconclusive evidence."
        ),
        "",
        (
            f"All tested cases beat both baselines: **{'PASS' if result['all_cases_win'] else 'NOT PROVEN'}**. "
            f"No observed regressions within tolerance: **{'PASS' if result['no_observed_regressions'] else 'NOT PROVEN'}**."
        ),
        "",
        "## Installed engine identities",
        "",
    ]
    for engine in ENGINES:
        metadata = next(iter(reports.values()))[engine][0][1].get_metadata()
        lines.append(
            f"- **{LABELS[engine]}** {metadata['engine_version']}; native SHA-256 `{metadata['native_sha256']}`."
        )
    lines += [
        "",
        "## Unsupported native capabilities",
        "",
        "These capabilities are not assigned fake timings or zeroes. They are outside the common-data matrix.",
        "",
    ]
    for name, engines in manifest["unsupported"].items():
        for engine, reason in engines.items():
            lines.append(f"- `{name}` — **{LABELS[engine]}: unsupported.** {reason}")
    lines += [
        "",
        (
            "FastAPI-flags rows measure serialization of ordinary record data with ORJSONResponse's flags. "
            "json produces equivalent JSON for those fixtures; it has no equivalent NumPy/non-string-key extension flags. "
            "These rows do not measure HTTP throughput."
        ),
        "",
    ]
    lines += [
        (
            "Typed rows compare Codec's direct TypeAdapter JSON calls with explicit "
            "dump_python + encoder / parser + validate_python pipelines. Every user "
            "can call that same direct TypeAdapter API without this package; these "
            "rows do not claim a faster Pydantic core or the best possible upstream "
            "typed workflow. See the separate source/adapter engineering controls."
        ),
        "",
    ]
    return result, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--gate", choices=("none", "no-regressions", "all-wins"), default="none"
    )
    parser.add_argument("--max-spread", type=float, default=0.10)
    parser.add_argument("--min-win", type=float, default=0.01)
    parser.add_argument("--tolerance", type=float, default=0.02)
    args = parser.parse_args()
    if any(
        not math.isfinite(value) or value < 0
        for value in (args.max_spread, args.min_win, args.tolerance)
    ):
        parser.error("Thresholds must be finite nonnegative fractions")
    try:
        manifest, reports = load_reports(args.directory)
        result, markdown = make_report(
            manifest,
            reports,
            max_spread=args.max_spread,
            min_win=args.min_win,
            tolerance=args.tolerance,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    (args.directory / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.directory / "comparison.md").write_text(markdown)
    print(markdown)
    if args.gate == "all-wins" and not result["all_cases_win"]:
        return 1
    if args.gate == "no-regressions" and not result["no_observed_regressions"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
