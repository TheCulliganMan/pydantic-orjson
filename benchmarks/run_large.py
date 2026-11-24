# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Run serial 1/10/100 MiB JSON comparisons with separate external RSS probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import psutil
from large_fixtures import generate, specs
from large_suite import suite_hash
from matrix_suite import ENGINES, LABELS
from run_matrix import machine_state, write_manifest


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def memory_probe(command, destination: Path, environment: dict) -> dict:
    log = destination.with_suffix(".log")
    with log.open("w") as stderr:
        process = subprocess.Popen(
            [*command, "--memory"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            env=environment,
        )
        try:
            ready = json.loads(process.stdout.readline())
            if ready.get("phase") != "ready":
                raise RuntimeError(f"Invalid memory handshake: {ready}")
            observed = psutil.Process(ready["pid"])
            samples = [observed.memory_info().rss, ready["baseline_rss_bytes"]]
            gaps = []
            completed = []
            done = threading.Event()

            def read_result():
                completed.append(process.stdout.readline())
                done.set()

            reader = threading.Thread(target=read_result, daemon=True)
            reader.start()
            previous = time.perf_counter()
            process.stdin.write("GO\n")
            process.stdin.flush()
            deadline = previous + 300
            while not done.wait(0.001):
                now = time.perf_counter()
                if now > deadline:
                    raise TimeoutError("Memory operation exceeded 300 seconds")
                samples.append(observed.memory_info().rss)
                gaps.append(now - previous)
                previous = now
            gaps.append(time.perf_counter() - previous)
            samples.append(observed.memory_info().rss)
            result = json.loads(completed[0])
            if result.get("phase") != "complete":
                raise RuntimeError(f"Invalid memory completion: {result}")
            samples.append(result["retained_result_rss_bytes"])
            # Stop measuring before validation allocates any reference graph.
            process.stdin.write("ACK\n")
            process.stdin.flush()
            validated = json.loads(process.stdout.readline())
            code = process.wait(timeout=300)
            if code or not validated.get("validated"):
                raise RuntimeError(f"Memory worker failed: {log}")
            peak = max(samples)
            result = {
                **ready,
                **result,
                **validated,
                "baseline_rss_bytes": ready["baseline_rss_bytes"],
                "peak_rss_bytes": peak,
                "incremental_peak_rss_bytes": max(
                    0, peak - ready["baseline_rss_bytes"]
                ),
                "samples": len(samples),
                "requested_interval_seconds": 0.001,
                "max_sample_gap_seconds": max(gaps, default=0.0),
                "method": "external psutil RSS samples from GO through retained result; validation excluded; observed peak, not exact allocation peak",
            }
            result.pop("pid", None)
            result.pop("phase", None)
            destination.write_text(json.dumps(result, indent=2) + "\n")
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def main():  # noqa: PLR0912, PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-python", required=True, type=Path)
    parser.add_argument("--orjson-python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--sizes", default="1,10,100", help="MiB sizes; a subset is labeled partial"
    )
    parser.add_argument("--families", default="records,numeric,nested_unicode")
    parser.add_argument("--operations", default="dumps,loads")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--processes", type=int, default=4)
    parser.add_argument("--values", type=int, default=4)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--affinity")
    parser.add_argument("--macos-qos", action="store_true")
    args = parser.parse_args()
    if args.rounds < 2 or args.rounds % 2:
        parser.error("Use an even number of rounds >=2 for balanced orders")
    if min(args.processes, args.values, args.warmups) < 1:
        parser.error("Sampling values must be positive")
    sizes = {int(value) * 1024 * 1024 for value in args.sizes.split(",")}
    families = set(args.families.split(","))
    operations = args.operations.split(",")
    if not set(operations) <= {"dumps", "loads"} or len(set(operations)) != len(
        operations
    ):
        parser.error("Operations must be unique dumps and/or loads")
    available = specs()
    if not sizes <= {s.target_bytes for s in available} or not families <= {
        s.family for s in available
    }:
        parser.error("Unknown size or family")
    selected = [
        s for s in available if s.target_bytes in sizes and s.family in families
    ]
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(
            "Output directory must be empty; retained runs are never overwritten"
        )
    uv = shutil.which("uv")
    if not uv:
        parser.error("UV is required")
    interpreters = {
        "candidate": args.candidate_python.absolute(),
        "upstream": args.orjson_python.absolute(),
        "stdlib": args.candidate_python.absolute(),
    }
    if any(not p.is_file() for p in interpreters.values()):
        parser.error("An exact installed interpreter is missing")
    args.output.mkdir(parents=True, exist_ok=True)
    args.fixtures.mkdir(parents=True, exist_ok=True)
    suite = Path(__file__).with_name("large_suite.py").resolve()
    environment = dict(os.environ, PYTHONHASHSEED="0")
    manifest = {
        "format": 1,
        "status": "running",
        "labels": LABELS,
        "source_commit": args.source_commit,
        "suite_sha256": suite_hash(),
        "harness_sha256": {
            name: sha(suite.with_name(name))
            for name in (
                "large_suite.py",
                "run_large.py",
                "large_fixtures.py",
                "report_large.py",
            )
        },
        "operations": operations,
        "rounds": args.rounds,
        "processes": args.processes,
        "values": args.values,
        "warmups": args.warmups,
        "partial": len(selected) != len(available) or len(operations) != 2,
        "fixtures": [],
        "entries": [],
        "memory": [],
        "uv": subprocess.check_output([uv, "--version"], text=True).strip(),
        "machine_before": machine_state(),
        "latency_contract": "Fixture construction and file IO excluded; UTF-8 bytes output; call and result release included",
        "memory_contract": "One fresh-process external RSS probe per fixture/operation/engine, separate from latency; observed operation-window RSS peak",
    }
    manifest_path = args.output / "manifest.json"
    try:
        for spec in selected:
            print(f"Preparing {spec.name}", flush=True)
            path = (args.fixtures / (spec.name + ".json")).absolute()
            receipt = generate(spec, path)
            receipt["path"] = os.path.relpath(path, args.output)
            manifest["fixtures"].append(receipt)
            write_manifest(manifest_path, manifest)
        case_index = 0
        for fixture in manifest["fixtures"]:
            path = (args.output / fixture["path"]).absolute()
            receipt = Path(str(path) + ".manifest.json")
            loops = max(1, (16 * 1024 * 1024) // fixture["target_bytes"])
            for operation in operations:
                order = ENGINES[case_index % 3 :] + ENGINES[: case_index % 3]
                for round_index in range(args.rounds):
                    for engine in order if round_index % 2 == 0 else reversed(order):
                        stem = (
                            f"{operation}.{fixture['name']}-{engine}-r{round_index + 1}"
                        )
                        report, log = (
                            args.output / (stem + ".json"),
                            args.output / (stem + ".log"),
                        )
                        base = [
                            uv,
                            "run",
                            "--no-project",
                            "--python",
                            str(interpreters[engine]),
                            "python",
                            str(suite),
                            "--engine",
                            engine,
                            "--operation",
                            operation,
                            "--fixture",
                            str(path),
                            "--receipt",
                            str(receipt),
                            "--source-commit",
                            args.source_commit,
                        ]
                        command = [
                            *base,
                            "--inherit-environ",
                            "PYTHONHASHSEED",
                            "-p",
                            str(args.processes),
                            "-n",
                            str(args.values),
                            "-w",
                            str(args.warmups),
                            "--loops",
                            str(loops),
                            "-o",
                            str(report),
                        ]
                        if args.affinity:
                            command.extend(("--affinity", args.affinity))
                        if args.macos_qos:
                            command.append("--macos-qos")
                        print(
                            f"{fixture['name']} {operation} | {LABELS[engine]} | round {round_index + 1}/{args.rounds}",
                            flush=True,
                        )
                        with log.open("w") as output:
                            completed = subprocess.run(
                                command,
                                env=environment,
                                stdout=output,
                                stderr=subprocess.STDOUT,
                                check=False,
                            )
                        entry = {
                            "fixture": fixture["name"],
                            "operation": operation,
                            "engine": engine,
                            "round": round_index + 1,
                            "report": report.name,
                            "report_sha256": sha(report) if report.exists() else None,
                            "log": log.name,
                            "log_sha256": sha(log),
                            "returncode": completed.returncode,
                        }
                        manifest["entries"].append(entry)
                        write_manifest(manifest_path, manifest)
                        if completed.returncode:
                            raise RuntimeError(
                                f"Measurement failed: {log}\n{log.read_text()}"
                            )
                for engine in order:
                    stem = f"memory.{operation}.{fixture['name']}-{engine}"
                    report = args.output / (stem + ".json")
                    command = [
                        uv,
                        "run",
                        "--no-project",
                        "--python",
                        str(interpreters[engine]),
                        "python",
                        str(suite),
                        "--engine",
                        engine,
                        "--operation",
                        operation,
                        "--fixture",
                        str(path),
                        "--receipt",
                        str(receipt),
                        "--source-commit",
                        args.source_commit,
                    ]
                    if args.macos_qos:
                        command.append("--macos-qos")
                    print(
                        f"RSS {fixture['name']} {operation} | {LABELS[engine]}",
                        flush=True,
                    )
                    memory_probe(command, report, environment)
                    manifest["memory"].append(
                        {
                            "fixture": fixture["name"],
                            "operation": operation,
                            "engine": engine,
                            "report": report.name,
                            "report_sha256": sha(report),
                        }
                    )
                    write_manifest(manifest_path, manifest)
                case_index += 1
        manifest["status"] = "complete"
    finally:
        manifest["machine_after"] = machine_state()
        if manifest["status"] != "complete":
            manifest["status"] = "incomplete"
        write_manifest(manifest_path, manifest)
    print(f"Large JSON evidence: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
