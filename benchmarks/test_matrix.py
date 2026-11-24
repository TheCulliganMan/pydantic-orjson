# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Contract and gate tests: reject misleading or incomplete benchmark evidence."""

import hashlib
import json

import pyperf
import pytest
from matrix_suite import ENGINES, LABELS, cases, check, prepare, unsupported
from report_matrix import (
    REQUIRED_MATCHES,
    classify,
    load_reports,
    make_report,
    summarize,
)


@pytest.mark.parametrize("engine", ("candidate", "stdlib"))
def test_common_fixture_contract(engine):
    for case in cases():
        original = case.fixture
        expression, namespace, expected = prepare(case, engine)
        assert check(case, expression, namespace, expected) > 0
        assert case.fixture == original


def test_default_native_call_and_utf8_conversion_are_timed():
    case = next(case for case in cases() if case.name == "dumps.text.unicode.32_chars")
    expression, _, _ = prepare(case, "candidate")
    assert expression == "function(value)"
    expression, _, _ = prepare(case, "stdlib")
    assert "ensure_ascii=False" in expression
    assert expression.endswith(".encode('utf-8')")


def benchmark(values, name="dumps.scalar.null", metadata=None):
    return pyperf.Benchmark(
        [
            pyperf.Run(
                [value] * 4,
                metadata={"name": name, "unit": "second", **(metadata or {})},
                collect_metadata=False,
            )
            for value in values
        ]
    )


def stats(values, reverse=None):
    return summarize([(1, benchmark(values)), (2, benchmark(reverse or values))], 0.10)


def test_bimodal_worker_speedup_cannot_pass_gate():
    candidate = stats(
        [61.375e-6, 6.376e-6, 6.361e-6, 6.352e-6],
        [6.347e-6, 63.970e-6, 58.862e-6, 61.987e-6],
    )
    baseline = stats([60e-6] * 4)
    result = classify(candidate, baseline, min_win=0.01, tolerance=0.02)
    assert result["status"] == "unstable"
    assert not result["no_regression"]


def test_gate_distinguishes_win_regression_and_tolerance():
    baseline = stats([10e-6] * 4)
    assert (
        classify(stats([8e-6] * 4), baseline, min_win=0.01, tolerance=0.02)["status"]
        == "win"
    )
    assert (
        classify(stats([12e-6] * 4), baseline, min_win=0.01, tolerance=0.02)["status"]
        == "regression"
    )
    assert (
        classify(stats([10.1e-6] * 4), baseline, min_win=0.01, tolerance=0.02)["status"]
        == "within tolerance"
    )
    assert (
        classify(stats([8e-6]), baseline, min_win=0.01, tolerance=0.02)["status"]
        == "insufficient samples"
    )


def write_evidence(directory, *, bad_fixture=False, omitted=False):
    name = "dumps.scalar.null"
    manifest = {
        "format": 1,
        "status": "complete",
        "labels": LABELS,
        "profile": "smoke",
        "partial": True,
        "rounds": 2,
        "cases": [name],
        "suite_sha256": "a" * 64,
        "unsupported": unsupported(),
        "measurements": [],
    }
    for engine in ENGINES:
        for round_number in (1, 2):
            if omitted and engine == "stdlib" and round_number == 2:
                continue
            metadata = {field: "test" for field in REQUIRED_MATCHES}
            metadata.update(
                {
                    "engine": engine,
                    "engine_label": LABELS[engine],
                    "engine_version": "1",
                    "native_sha256": engine * 10,
                    "unit": "second",
                    "cpu_count": 4,
                    "fixture_bytes": 4,
                    "profile": "smoke",
                    "suite_sha256": "a" * 64,
                    "fixture_sha256": "changed"
                    if bad_fixture and engine == "stdlib"
                    else "b" * 64,
                    "timeit_stmt": "engine-specific expression: " + engine,
                }
            )
            stem = f"{engine}-{round_number}"
            report = directory / (stem + ".json")
            log = directory / (stem + ".log")
            pyperf.BenchmarkSuite(
                [
                    benchmark(
                        [1e-6 if engine == "candidate" else 2e-6] * 4, metadata=metadata
                    )
                ]
            ).dump(str(report))
            log.write_text("synthetic contract test, not performance evidence\n")
            manifest["measurements"].append(
                {
                    "case": name,
                    "engine": engine,
                    "round": round_number,
                    "returncode": 0,
                    "report": report.name,
                    "log": log.name,
                    "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                    "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                }
            )
    (directory / "manifest.json").write_text(json.dumps(manifest))


def test_three_engines_reported_but_partial_profile_cannot_qualify(tmp_path):
    write_evidence(tmp_path)
    manifest, reports = load_reports(tmp_path)
    result, markdown = make_report(
        manifest, reports, max_spread=0.10, min_win=0.01, tolerance=0.02
    )
    assert "Pydantic ORJSON µs | ORJSON µs | json µs" in markdown
    assert "unsupported" in markdown
    assert not result["all_cases_win"]
    assert not result["no_observed_regressions"]


@pytest.mark.parametrize("problem", ("bad_fixture", "omitted", "tampered"))
def test_incomparable_or_missing_evidence_is_rejected(tmp_path, problem):
    write_evidence(
        tmp_path, bad_fixture=problem == "bad_fixture", omitted=problem == "omitted"
    )
    if problem == "tampered":
        (tmp_path / "candidate-1.json").write_text("{}")
    with pytest.raises(ValueError):
        load_reports(tmp_path)
