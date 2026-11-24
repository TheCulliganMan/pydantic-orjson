# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Validate and report large-document latency, throughput and separate RSS probes.

All three engines remain visible. Observed worker ranges are descriptive, not
statistical confidence intervals or a claim about every JSON input.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

import pyperf
from matrix_suite import ENGINES, LABELS
from report_matrix import classify, summarize

MIB = 1024 * 1024
OPERATIONS = {"dumps": "Encode", "loads": "Decode"}
FAMILIES = {"records", "numeric", "nested_unicode"}
REQUIRED_METADATA = (
    "suite_sha256",
    "source_commit",
    "fixture_sha256",
    "fixture_bytes",
    "python_version",
    "python_implementation",
    "python_compiler",
    "python_executable_sha256",
    "perf_version",
    "unit",
)
OPTIONAL_METADATA = (
    "platform",
    "cpu_count",
    "cpu_model_name",
    "cpu_model",
    "cpu_affinity",
    "cpu_config",
    "timer",
    "python_cflags",
    "python_config_args",
    "python_gc",
    "python_gil_enabled",
    "python_gil_disabled_build",
    "python_hash_seed",
    "macos_qos_requested",
    "serialization_contract",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(MIB), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_path(directory: Path, entry: dict, key: str) -> Path:
    relative = Path(entry[key])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(
            f"Evidence path must stay inside the report directory: {relative}"
        )
    path = directory / relative
    if sha256_file(path) != entry[key + "_sha256"]:
        raise ValueError(f"Changed evidence: {relative}")
    return path


def require_matching_metadata(
    reference: dict, current: dict, name: str, *, same_fixture: bool = True
) -> None:
    for field in REQUIRED_METADATA:
        if not same_fixture and field in ("fixture_sha256", "fixture_bytes"):
            continue
        if (
            field not in reference
            or field not in current
            or reference[field] != current[field]
        ):
            raise ValueError(f"Different or missing metadata: {name}: {field}")
    for field in OPTIONAL_METADATA:
        if (field in reference) != (field in current) or reference.get(
            field
        ) != current.get(field):
            raise ValueError(f"Different optional metadata: {name}: {field}")


def validate_fixtures(directory: Path, fixtures: list) -> tuple[dict, list]:
    result = {}
    unavailable = []
    for fixture in fixtures:
        name = fixture["name"]
        if name in result or fixture["family"] not in FAMILIES:
            raise ValueError(f"Duplicate fixture or unknown family: {name}")
        for field in ("actual_bytes", "target_bytes", "items"):
            if type(fixture[field]) is not int or fixture[field] <= 0:
                raise ValueError(f"Invalid fixture {field}: {name}")
        if fixture["target_bytes"] not in (MIB, 10 * MIB, 100 * MIB):
            raise ValueError(f"Unsupported large-document target: {name}")
        if name != f"{fixture['family']}-{fixture['target_bytes'] // MIB}mib":
            raise ValueError(f"Fixture name disagrees with its family/target: {name}")
        path = Path(fixture["path"])
        if not path.is_absolute():
            path = directory / path
        if path.is_file():
            if (
                path.stat().st_size != fixture["actual_bytes"]
                or sha256_file(path) != fixture["sha256"]
            ):
                raise ValueError(f"Fixture bytes differ from receipt: {name}")
        else:
            unavailable.append(name)
        result[name] = fixture
    if not result:
        raise ValueError("No fixtures recorded")
    return result, unavailable


def validate_memory(  # noqa: PLR0912
    probe: dict, fixture: dict, operation: str, engine: str, native_sha256: str
) -> None:
    expected = {
        "fixture_sha256": fixture["sha256"],
        "fixture_bytes": fixture["actual_bytes"],
        "operation": operation,
        "engine": engine,
        "native_sha256": native_sha256,
    }
    for field, value in expected.items():
        if probe.get(field) != value:
            raise ValueError(
                f"Memory probe identity mismatch: {fixture['name']}: {engine}: {field}"
            )
    for field in (
        "baseline_rss_bytes",
        "peak_rss_bytes",
        "incremental_peak_rss_bytes",
        "output_bytes",
    ):
        if type(probe.get(field)) is not int or probe[field] < 0:
            raise ValueError(
                f"Invalid memory probe {field}: {fixture['name']}: {engine}"
            )
    if not isinstance(probe.get("method"), str) or not probe["method"]:
        raise ValueError("Memory probe must describe its measurement method")
    if probe["peak_rss_bytes"] < probe["baseline_rss_bytes"]:
        raise ValueError("Peak RSS cannot be below baseline RSS")
    if (
        probe["incremental_peak_rss_bytes"]
        != probe["peak_rss_bytes"] - probe["baseline_rss_bytes"]
    ):
        raise ValueError("Incremental peak RSS must equal peak minus baseline")
    if not probe["output_bytes"]:
        raise ValueError("Memory probe output size must be positive")
    if probe.get("validated") is not True:
        raise ValueError("Memory probe output was not validated")
    if (
        type(probe.get("retained_result_rss_bytes")) is not int
        or not 0 <= probe["retained_result_rss_bytes"] <= probe["peak_rss_bytes"]
    ):
        raise ValueError("Invalid retained-result RSS")
    if type(probe.get("samples")) is not int or probe["samples"] < 1:
        raise ValueError("Memory probe needs an observed RSS sample")
    for field in ("requested_interval_seconds", "max_sample_gap_seconds"):
        value = probe.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid memory sampling {field}")
    if not probe["requested_interval_seconds"]:
        raise ValueError("Memory sampling interval must be positive")


def load_large(directory: Path) -> tuple[dict, dict, list]:  # noqa: PLR0912, PLR0915
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("format") != 1 or manifest.get("status") != "complete":
        raise ValueError("Incomplete or unknown large-document manifest")
    if manifest["labels"] != LABELS:
        raise ValueError("Expected explicit Pydantic ORJSON / ORJSON / json labels")
    if (
        not isinstance(manifest["source_commit"], str)
        or len(manifest["source_commit"]) != 40
    ):
        raise ValueError("An exact source commit is required")
    rounds = manifest["rounds"]
    if type(rounds) is not int or rounds < 2 or rounds % 2:
        raise ValueError("At least two balanced forward/reverse rounds are required")
    operations = manifest["operations"]
    if (
        not operations
        or len(set(operations)) != len(operations)
        or set(operations) - OPERATIONS.keys()
    ):
        raise ValueError("Unknown or duplicate operations")
    fixtures, unavailable = validate_fixtures(directory, manifest["fixtures"])
    rows = {
        (name, operation): {engine: {"rounds": []} for engine in ENGINES}
        for name in fixtures
        for operation in operations
    }
    seen = set()
    global_reference = None
    for entry in manifest["entries"]:
        key = (entry["fixture"], entry["operation"], entry["engine"], entry["round"])
        row_key = key[:2]
        if (
            key in seen
            or row_key not in rows
            or key[2] not in ENGINES
            or not 1 <= key[3] <= rounds
        ):
            raise ValueError(f"Duplicate or unexpected timing entry: {key}")
        seen.add(key)
        report = evidence_path(directory, entry, "report")
        evidence_path(directory, entry, "log")
        suite = pyperf.BenchmarkSuite.load(str(report))
        name = f"{key[1]}.{key[0]}"
        if suite.get_benchmark_names() != [name]:
            raise ValueError(f"Wrong benchmark in {entry['report']}")
        benchmark = suite.get_benchmark(name)
        metadata = benchmark.get_metadata()
        fixture = fixtures[key[0]]
        expected = {
            "engine": key[2],
            "engine_label": LABELS[key[2]],
            "fixture_sha256": fixture["sha256"],
            "fixture_bytes": fixture["actual_bytes"],
            "source_commit": manifest["source_commit"],
            "unit": "second",
        }
        for field, value in expected.items():
            if metadata.get(field) != value:
                raise ValueError(f"Report/manifest mismatch: {name}: {field}")
        if global_reference is None:
            global_reference = metadata
        require_matching_metadata(global_reference, metadata, name, same_fixture=False)
        values = benchmark.get_values()
        if not values or any(
            value <= 0 or not math.isfinite(value) for value in values
        ):
            raise ValueError(f"Missing or invalid timings: {name}")
        rows[row_key][key[2]]["rounds"].append((key[3], benchmark))
    identities = {engine: set() for engine in ENGINES}
    for key, engines in rows.items():
        reference = None
        for engine, data in engines.items():
            data["rounds"].sort(key=lambda item: item[0])
            if [number for number, _ in data["rounds"]] != list(range(1, rounds + 1)):
                raise ValueError(f"Missing timing rounds: {key}: {engine}")
            for _, benchmark in data["rounds"]:
                metadata = benchmark.get_metadata()
                if reference is None:
                    reference = metadata
                require_matching_metadata(reference, metadata, str(key))
                identities[engine].add(
                    (metadata["engine_version"], metadata["native_sha256"])
                )
    if any(len(identity) != 1 for identity in identities.values()):
        raise ValueError("Installed engine changed during the measurements")
    memory_seen = set()
    for entry in manifest["memory"]:
        key = (entry["fixture"], entry["operation"], entry["engine"])
        if key in memory_seen or key[:2] not in rows or key[2] not in ENGINES:
            raise ValueError(f"Duplicate or unexpected memory probe: {key}")
        memory_seen.add(key)
        probe = json.loads(evidence_path(directory, entry, "report").read_text())
        native_sha256 = next(iter(identities[key[2]]))[1]
        validate_memory(probe, fixtures[key[0]], key[1], key[2], native_sha256)
        rows[key[:2]][key[2]]["memory"] = probe
    for key, engines in rows.items():
        if any("memory" not in data for data in engines.values()):
            raise ValueError(f"Missing memory probe: {key}")
        if len({data["memory"]["method"] for data in engines.values()}) != 1:
            raise ValueError(f"Different RSS probe methods: {key}")
    return manifest, rows, unavailable


def large_report(  # noqa: PLR0912
    manifest: dict, rows: dict, unavailable: list, *, max_spread: float = 0.10
) -> tuple[dict, str]:
    fixtures = {fixture["name"]: fixture for fixture in manifest["fixtures"]}
    complete_matrix = {(f["family"], f["target_bytes"]) for f in fixtures.values()} == {
        (family, size * MIB) for family in FAMILIES for size in (1, 10, 100)
    } and set(manifest["operations"]) == set(OPERATIONS)
    result = {
        "source_commit": manifest["source_commit"],
        "labels": LABELS,
        "complete_1_10_100_mib_matrix": complete_matrix,
        "fixture_files_unavailable": unavailable,
        "max_spread": max_spread,
        "cases": {},
    }
    lines = [
        "# Large JSON: Pydantic ORJSON / ORJSON / json",
        "",
        f"Source: `{manifest['source_commit']}`. "
        + (
            "Complete 1/10/100 MiB family matrix."
            if complete_matrix
            else "**Partial large-document matrix.**"
        ),
        "",
        (
            "Actual MiB uses the measured fixture byte count (1 MiB = 1,048,576 bytes). "
            "Throughput divides those same bytes by median latency, so extra output bytes do not inflate an engine's rate. "
            "Encoding produces UTF-8 bytes, including json's UTF-8 conversion; all decoders consume identical fixture bytes."
        ),
        "",
        (
            f"{manifest['rounds']} balanced rounds. Ratios are baseline / Pydantic ORJSON latency; >1 favors Pydantic ORJSON. "
            f">{max_spread:.0%} worker/sample spread or round drift is marked unstable. "
            "Fewer than four processes or four values per process is insufficient sampling. "
            "One loop per value is legitimate for a large document. Tags describe observed ranges, not statistical confidence or universal speed."
        ),
        "",
        "| Case | Actual MiB | Pydantic ORJSON ms / MiB/s | ORJSON ms / MiB/s | json ms / MiB/s | vs ORJSON (rounds) | vs json (rounds) |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    counts = {engine: collections.Counter() for engine in ("upstream", "stdlib")}
    for (fixture_name, operation), engines in rows.items():
        fixture = fixtures[fixture_name]
        mib = fixture["actual_bytes"] / MIB
        statistics = {}
        for engine, data in engines.items():
            stats = summarize(data["rounds"], max_spread)
            stats["throughput_mib_per_second"] = mib / stats["median_seconds"]
            stats["memory"] = data["memory"]
            statistics[engine] = stats
        comparisons = {
            engine: classify(
                statistics["candidate"],
                statistics[engine],
                min_win=0.01,
                tolerance=0.02,
            )
            for engine in ("upstream", "stdlib")
        }
        name = f"{operation}.{fixture_name}"
        result["cases"][name] = {
            "fixture": fixture,
            "actual_mib": mib,
            "engines": statistics,
            "comparisons": comparisons,
        }
        cells = [f"{OPERATIONS[operation]} {fixture_name}", f"{mib:.6f}"]
        for engine in ENGINES:
            stats = statistics[engine]
            cells.append(
                f"{stats['median_seconds'] * 1000:.3f} / {stats['throughput_mib_per_second']:.2f}"
            )
        for engine in ("upstream", "stdlib"):
            comparison = comparisons[engine]
            counts[engine][comparison["status"]] += 1
            ratios = " / ".join(
                f"{ratio:.3f}x" for ratio in comparison["ratios_by_round"]
            )
            cells.append(f"{comparison['status']}: {ratios}")
        lines.append("| " + " | ".join(cells) + " |")
    result["case_status_counts"] = {
        engine: dict(counter) for engine, counter in counts.items()
    }
    lines += [
        "",
        "## Separate memory probes",
        "",
        (
            "Each cell is **observed operation-window process RSS peak / incremental observed peak**, in MiB. "
            "Incremental peak is observed peak minus the prepared-input baseline. "
            "One fresh process per case/engine is sampled externally from READY/GO until DONE, with the result held until ACK; "
            "correctness validation occurs after sampling. These are separate memory probes, not latency-worker measurements. "
            "Input/prepared-value residency and interpreter imports contribute to the baseline. "
            "Sampling can miss transient peaks: these are observed RSS values, not exact maxima or allocated-byte counts. "
            "Latency timing includes output release on each iteration."
        ),
        "",
        "| Case | Pydantic ORJSON observed peak / +MiB | ORJSON observed peak / +MiB | json observed peak / +MiB |",
        "| --- | ---: | ---: | ---: |",
    ]
    methods = set()
    for (fixture_name, operation), engines in rows.items():
        cells = [f"{OPERATIONS[operation]} {fixture_name}"]
        for engine in ENGINES:
            probe = engines[engine]["memory"]
            methods.add(probe["method"])
            cells.append(
                f"{probe['peak_rss_bytes'] / MIB:.2f} / +{probe['incremental_peak_rss_bytes'] / MIB:.2f}"
            )
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "Memory method: " + "; ".join(sorted(methods)) + ".",
        "",
        "Each raw probe also retains prepared-input baseline RSS, retained-result RSS, sample count, requested interval and largest observed sample gap.",
        "",
        "## Memory sampling resolution",
        "",
        "Each cell shows sample count / largest sample gap in milliseconds; requested intervals are retained in comparison.json.",
        "",
        "| Case | Pydantic ORJSON | ORJSON | json |",
        "| --- | ---: | ---: | ---: |",
    ]
    for (fixture_name, operation), engines in rows.items():
        cells = [f"{OPERATIONS[operation]} {fixture_name}"]
        for engine in ENGINES:
            probe = engines[engine]["memory"]
            cells.append(
                f"{probe['samples']} / {probe['max_sample_gap_seconds'] * 1000:.3f} ms"
            )
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Stability details",
        "",
        "Each cell shows worker-median spread / largest within-worker sample spread / round-median drift.",
        "",
        "| Case | Pydantic ORJSON | ORJSON | json |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, row in result["cases"].items():
        cells = [name]
        for engine in ENGINES:
            stats = row["engines"][engine]
            cells.append(
                f"{stats['worker_spread']:.1%} / {stats['max_within_worker_spread']:.1%} / {stats['round_drift']:.1%}"
            )
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Artifact identities", ""]
    for engine, data in next(iter(rows.values())).items():
        metadata = data["rounds"][0][1].get_metadata()
        lines.append(
            f"- **{LABELS[engine]}** {metadata['engine_version']}; native SHA-256 `{metadata['native_sha256']}`."
        )
    if unavailable:
        lines += [
            "",
            "Fixture bytes were unavailable for local rehashing: "
            + ", ".join(f"`{name}`" for name in unavailable)
            + ". Their receipts agree with every timing and memory probe, but this report does not claim to have reverified the absent files.",
        ]
    else:
        lines += [
            "",
            "Every fixture file's actual length and SHA-256 were verified on disk.",
        ]
    lines += [
        "",
        (
            "All report, log and memory-probe hashes and the complete declared case/round set were verified. "
            "Every regression and unstable case remains visible; no aggregate statistic certifies this library as universally faster."
        ),
        "",
    ]
    return result, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--max-spread", type=float, default=0.10)
    args = parser.parse_args()
    if not math.isfinite(args.max_spread) or args.max_spread < 0:
        parser.error("--max-spread must be a finite nonnegative fraction")
    try:
        manifest, rows, unavailable = load_large(args.directory)
        result, markdown = large_report(
            manifest, rows, unavailable, max_spread=args.max_spread
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    (args.directory / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.directory / "comparison.md").write_text(markdown)
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
