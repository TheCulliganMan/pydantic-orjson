# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Run Pydantic ORJSON, published ORJSON and json serially in balanced case order.

Environments must already contain their exact wheels and the same locked test
dependencies. This command never builds or silently replaces installed wheels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from matrix_suite import ENGINES, LABELS, PROFILES, cases, unsupported


def read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def machine_state() -> dict:
    state = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
    }
    if hasattr(os, "sched_getaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        state["allowed_cpus"] = allowed
        state["cpu_policies"] = {
            str(cpu): {
                "governor": read(
                    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
                ),
                "frequency_khz": read(
                    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq"
                ),
                "thread_siblings": read(
                    f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
                ),
            }
            for cpu in allowed
        }
        state["proc_stat"] = read("/proc/stat")
        state["cpu_pressure"] = read("/proc/pressure/cpu")
    return state


def write_manifest(path: Path, manifest: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(path)


def main() -> int:  # noqa: PLR0912, PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-python", required=True, type=Path)
    parser.add_argument("--orjson-python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument(
        "--cases",
        help="Comma-separated exact names; marks report as a partial diagnostic",
    )
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--processes", type=int, default=4)
    parser.add_argument("--values", type=int, default=4)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--min-time", type=float, default=0.07)
    parser.add_argument(
        "--affinity", help="Same permitted logical CPU for every worker"
    )
    parser.add_argument("--macos-qos", action="store_true")
    args = parser.parse_args()
    if args.rounds < 2 or args.rounds % 2:
        parser.error("--rounds must be an even number >= 2 for forward/reverse pairs")
    if min(args.processes, args.values, args.warmups) < 1 or args.min_time <= 0:
        parser.error("Sampling settings must be positive")
    uv = shutil.which("uv")
    if not uv:
        parser.error("UV is required")
    # Resolving a venv interpreter symlink would erase the venv identity.
    candidate_python = args.candidate_python.absolute()
    upstream_python = args.orjson_python.absolute()
    for interpreter in (candidate_python, upstream_python):
        if not interpreter.is_file():
            parser.error(f"Missing interpreter: {interpreter}")
    chosen = cases(args.profile)
    if args.cases:
        names = args.cases.split(",")
        if set(names) - {case.name for case in chosen}:
            parser.error("--cases contains an unknown name")
        chosen = [case for case in chosen if case.name in names]
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(
            "Output directory must be empty; previous evidence is never overwritten"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    suite = Path(__file__).with_name("matrix_suite.py").resolve()
    manifest = {
        "format": 1,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "labels": LABELS,
        "profile": args.profile,
        "partial": bool(args.cases),
        "cases": [case.name for case in chosen],
        "unsupported": unsupported(),
        "rounds": args.rounds,
        "processes": args.processes,
        "values": args.values,
        "warmups": args.warmups,
        "min_time": args.min_time,
        "affinity": args.affinity,
        "macos_qos": args.macos_qos,
        "uv": subprocess.check_output([uv, "--version"], text=True).strip(),
        "suite_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
        "machine_before": machine_state(),
        "measurements": [],
        "status": "running",
    }
    manifest_path = args.output / "manifest.json"
    write_manifest(manifest_path, manifest)
    try:
        for case_index, case in enumerate(chosen):
            rotated = ENGINES[case_index % 3 :] + ENGINES[: case_index % 3]
            for round_index in range(args.rounds):
                order = rotated if round_index % 2 == 0 else tuple(reversed(rotated))
                for engine in order:
                    stem = f"{case_index:03d}-{case.name}-{engine}-r{round_index + 1}"
                    report = args.output / (stem + ".json")
                    log = args.output / (stem + ".log")
                    interpreter = (
                        upstream_python if engine == "upstream" else candidate_python
                    )
                    command = [
                        uv,
                        "run",
                        "--no-project",
                        "--python",
                        str(interpreter),
                        "python",
                        str(suite),
                        "--engine",
                        engine,
                        "--matrix-profile",
                        args.profile,
                        "--case",
                        case.name,
                        "-p",
                        str(args.processes),
                        "-n",
                        str(args.values),
                        "-w",
                        str(args.warmups),
                        "--min-time",
                        str(args.min_time),
                        "-o",
                        str(report),
                    ]
                    if args.affinity:
                        command.extend(("--affinity", args.affinity))
                    if args.macos_qos:
                        command.append("--macos-qos")
                    print(
                        f"{case_index + 1}/{len(chosen)} {case.name} | {LABELS[engine]} | round {round_index + 1}/{args.rounds}",
                        flush=True,
                    )
                    started = time.monotonic()
                    environment = dict(os.environ, PYTHONHASHSEED="0")
                    with log.open("w") as output:
                        completed = subprocess.run(
                            command,
                            env=environment,
                            stdout=output,
                            stderr=subprocess.STDOUT,
                            check=False,
                        )
                    entry = {
                        "case": case.name,
                        "engine": engine,
                        "round": round_index + 1,
                        "report": report.name,
                        "log": log.name,
                        "elapsed_seconds": time.monotonic() - started,
                        "returncode": completed.returncode,
                    }
                    if report.exists():
                        entry["report_sha256"] = hashlib.sha256(
                            report.read_bytes()
                        ).hexdigest()
                    entry["log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
                    manifest["measurements"].append(entry)
                    write_manifest(manifest_path, manifest)
                    if completed.returncode:
                        print(log.read_text(), flush=True)
                        raise RuntimeError(f"Benchmark failed: {stem}")
        manifest["status"] = "complete"
    finally:
        manifest["machine_after"] = machine_state()
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        if manifest["status"] != "complete":
            manifest["status"] = "incomplete"
        write_manifest(manifest_path, manifest)
    print(f"Raw evidence: {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
