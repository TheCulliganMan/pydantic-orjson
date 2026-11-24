# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Large-report contracts reject wrong sizes, missing rounds and swapped RSS probes."""

import hashlib
import json

import pyperf
import pytest
from matrix_suite import ENGINES, LABELS
from report_large import MIB, REQUIRED_METADATA, large_report, load_large


def write_json(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(directory):
    fixture_file = directory / "fixture.json"
    fixture_file.write_bytes(b'{"x":"' + b"x" * (MIB - 8) + b'"}')
    fixture = {
        "name": "records-1mib",
        "family": "records",
        "target_bytes": MIB,
        "actual_bytes": MIB,
        "items": 1,
        "path": fixture_file.name,
        "sha256": hashlib.sha256(fixture_file.read_bytes()).hexdigest(),
    }
    manifest = {
        "format": 1,
        "status": "complete",
        "labels": LABELS,
        "source_commit": "a" * 40,
        "rounds": 2,
        "operations": ["dumps", "loads"],
        "fixtures": [fixture],
        "entries": [],
        "memory": [],
    }
    for operation in manifest["operations"]:
        for engine_index, engine in enumerate(ENGINES, 1):
            metadata = dict.fromkeys(REQUIRED_METADATA, "test")
            metadata.update(
                {
                    "name": f"{operation}.{fixture['name']}",
                    "unit": "second",
                    "engine": engine,
                    "engine_label": LABELS[engine],
                    "engine_version": "test",
                    "native_sha256": engine * 8,
                    "source_commit": manifest["source_commit"],
                    "fixture_sha256": fixture["sha256"],
                    "fixture_bytes": MIB,
                }
            )
            for round_number in (1, 2):
                stem = f"{operation}-{engine}-{round_number}"
                report = directory / (stem + ".json")
                log = directory / (stem + ".log")
                runs = [
                    pyperf.Run(
                        [engine_index * 0.01] * 4,
                        metadata=metadata,
                        collect_metadata=False,
                    )
                    for _ in range(4)
                ]
                pyperf.BenchmarkSuite([pyperf.Benchmark(runs)]).dump(str(report))
                log.write_text("synthetic contract test; not benchmark evidence\n")
                manifest["entries"].append(
                    {
                        "fixture": fixture["name"],
                        "operation": operation,
                        "engine": engine,
                        "round": round_number,
                        "report": report.name,
                        "report_sha256": hashlib.sha256(
                            report.read_bytes()
                        ).hexdigest(),
                        "log": log.name,
                        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                    }
                )
            probe_file = directory / f"{operation}-{engine}-memory.json"
            probe = {
                "baseline_rss_bytes": 10 * MIB,
                "peak_rss_bytes": 12 * MIB,
                "incremental_peak_rss_bytes": 2 * MIB,
                "retained_result_rss_bytes": 11 * MIB,
                "samples": 4,
                "requested_interval_seconds": 0.001,
                "max_sample_gap_seconds": 0.002,
                "validated": True,
                "output_bytes": MIB,
                "method": "synthetic observed-RSS test",
                "native_sha256": metadata["native_sha256"],
                "fixture_sha256": fixture["sha256"],
                "fixture_bytes": MIB,
                "engine": engine,
                "operation": operation,
            }
            manifest["memory"].append(
                {
                    "fixture": fixture["name"],
                    "operation": operation,
                    "engine": engine,
                    "report": probe_file.name,
                    "report_sha256": write_json(probe_file, probe),
                }
            )
    write_json(directory / "manifest.json", manifest)
    return manifest


def test_reports_real_bytes_all_engines_and_observed_memory(tmp_path):
    evidence(tmp_path)
    manifest, rows, unavailable = load_large(tmp_path)
    result, markdown = large_report(manifest, rows, unavailable)
    assert not result["complete_1_10_100_mib_matrix"]
    assert not unavailable
    assert (
        result["cases"]["dumps.records-1mib"]["engines"]["candidate"][
            "throughput_mib_per_second"
        ]
        == 100
    )
    assert (
        "Pydantic ORJSON ms / MiB/s | ORJSON ms / MiB/s | json ms / MiB/s" in markdown
    )
    assert "1.000000" in markdown
    assert "12.00 / +2.00" in markdown
    assert "Sampling can miss transient peaks" in markdown
    assert "Partial large-document matrix" in markdown


@pytest.mark.parametrize(
    "problem",
    [
        "fixture",
        "missing_round",
        "swapped_memory",
        "unvalidated_memory",
        "changed_report",
    ],
)
def test_rejects_wrong_or_incomplete_measurements(tmp_path, problem):
    manifest = evidence(tmp_path)
    if problem == "fixture":
        (tmp_path / "fixture.json").write_bytes(b"{}")
    elif problem == "missing_round":
        manifest["entries"].pop()
    elif problem in ("swapped_memory", "unvalidated_memory"):
        entry = manifest["memory"][0]
        path = tmp_path / entry["report"]
        probe = json.loads(path.read_text())
        if problem == "swapped_memory":
            probe["fixture_sha256"] = "b" * 64
        else:
            probe["validated"] = False
        entry["report_sha256"] = write_json(path, probe)
    else:
        (tmp_path / manifest["entries"][0]["report"]).write_text("{}")
    write_json(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError):
        load_large(tmp_path)


def test_absent_retained_fixture_is_disclosed(tmp_path):
    evidence(tmp_path)
    (tmp_path / "fixture.json").unlink()
    manifest, rows, unavailable = load_large(tmp_path)
    result, markdown = large_report(manifest, rows, unavailable)
    assert result["fixture_files_unavailable"] == ["records-1mib"]
    assert "does not claim to have reverified the absent files" in markdown
