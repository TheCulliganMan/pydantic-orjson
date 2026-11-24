# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Retain a completed large-JSON run without copying its large fixture payloads.

Run through UV after timing has finished. Originals are never modified. The
archive retains timings, warmups, RSS observations, warnings and fixture receipts;
only host/interpreter identities, log home prefixes and fixture paths change.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
import tempfile
from pathlib import Path

from report_large import load_large

HASHED_SUITE_FILES = ("large_suite.py", "large_fixtures.py", "matrix_suite.py")
HARNESS_FILES = (
    *HASHED_SUITE_FILES,
    "run_large.py",
    "report_large.py",
    "run_matrix.py",
    "report_matrix.py",
    "retain_large.py",
)
FIXTURE_FIELDS = (
    "name",
    "family",
    "target_bytes",
    "actual_bytes",
    "sha256",
    "items",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def sanitize_json(value: object) -> object:
    if isinstance(value, dict):
        cleaned = {
            key: sanitize_json(item)
            for key, item in value.items()
            if key not in ("hostname", "python_executable")
        }
        if "path" in cleaned and all(field in cleaned for field in FIXTURE_FIELDS):
            cleaned["path"] = f"../fixtures/{cleaned['name']}.json"
        return cleaned
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    return value


def sanitize_log(data: bytes) -> bytes:
    text = data.decode("utf-8")
    text = re.sub(r"/(?:Users|home)/[^/\s\"'<>]+", "<home>", text)
    text = re.sub(r"[A-Za-z]:\\Users\\[^\\\s\"'<>]+", "<home>", text)
    return text.encode("utf-8")


def relative_file(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Evidence must stay inside its directory: {name}")
    return path


def sanitized_file(path: Path) -> bytes:
    original = path.read_bytes()
    if path.suffix == ".json":
        before = json.loads(original)
        after = sanitize_json(before)
        if isinstance(before, dict) and "benchmarks" in before:
            # Keep every measured value and warmup, including calibration runs.
            for old_benchmark, new_benchmark in zip(
                before["benchmarks"], after["benchmarks"], strict=True
            ):
                for old_run, new_run in zip(
                    old_benchmark["runs"], new_benchmark["runs"], strict=True
                ):
                    if old_run.get("values") != new_run.get("values") or old_run.get(
                        "warmups"
                    ) != new_run.get("warmups"):
                        raise ValueError(
                            f"Timing values changed while sanitizing {path.name}"
                        )
        return encode_json(after)
    if path.suffix == ".log":
        return sanitize_log(original)
    return original


def deterministic_archive(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, data in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue(), mtime=0)


def prepare_retention(source: Path, fixtures: Path) -> tuple[dict, dict]:  # noqa: PLR0912, PLR0915
    manifest, _, unavailable = load_large(source)
    if unavailable:
        raise ValueError(
            "Original fixtures must be available for verification before retention"
        )
    if manifest.get("partial"):
        raise ValueError(
            "This retention command expects the completed full large-document run"
        )
    selected = {
        (fixture["family"], fixture["target_bytes"]) for fixture in manifest["fixtures"]
    }
    expected = {
        (family, size * 1024 * 1024)
        for family in ("records", "numeric", "nested_unicode")
        for size in (1, 10, 100)
    }
    if selected != expected or set(manifest["operations"]) != {"dumps", "loads"}:
        raise ValueError("Expected all nine 1/10/100 MiB fixtures and both operations")

    receipt = {
        "format": 1,
        "source_commit": manifest["source_commit"],
        "suite_sha256": manifest["suite_sha256"],
        "removed_json_fields": ["hostname", "python_executable"],
        "log_replacements": "Absolute user home prefixes replaced by <home>; remaining log text preserved",
        "fixture_paths": "Rewritten to ../fixtures/<name>.json; payloads deliberately absent",
        "manifest_rewrites": ["report_sha256", "log_sha256", "fixtures[].path"],
        "memory_log_hashes": "Added to retained manifest; original runner records only the memory JSON hash",
        "files": [],
        "harness_sources": [],
        "excluded_fixture_payloads": [],
    }
    members: dict[str, bytes] = {}
    records = {}

    def retain(path: Path, original_name: str, member: str) -> None:
        if member in members:
            raise ValueError(f"Duplicate retained member: {member}")
        original = path.read_bytes()
        sanitized = sanitized_file(path)
        members[member] = sanitized
        record = {
            "original_file": original_name,
            "original_sha256": digest(original),
            "original_bytes": len(original),
            "sanitized_sha256": digest(sanitized),
            "sanitized_bytes": len(sanitized),
            "member": member,
        }
        records[member] = record
        receipt["files"].append(record)

    timing_files = {
        entry[kind] for entry in manifest["entries"] for kind in ("report", "log")
    }
    memory_files = set()
    for entry in manifest["memory"]:
        report_path = relative_file(entry["report"])
        memory_files.add(report_path.as_posix())
        memory_files.add(report_path.with_suffix(".log").as_posix())
    for name in sorted(
        timing_files
        | memory_files
        | {"manifest.json", "comparison.json", "comparison.md"}
    ):
        path = relative_file(name)
        retain(source / path, "input/" + path.as_posix(), "matrix/" + path.as_posix())

    for fixture in manifest["fixtures"]:
        filename = fixture["name"] + ".json.manifest.json"
        path = fixtures / filename
        sidecar = json.loads(path.read_text())
        for field in FIXTURE_FIELDS:
            if sidecar[field] != fixture[field]:
                raise ValueError(
                    f"Fixture receipt mismatch: {fixture['name']}: {field}"
                )
        retain(path, "fixtures/" + filename, "fixtures/" + filename)
        receipt["excluded_fixture_payloads"].append(
            {field: fixture[field] for field in FIXTURE_FIELDS}
        )

    directory = Path(__file__).parent
    worker_digest = hashlib.sha256()
    for name in HASHED_SUITE_FILES:
        worker_digest.update(name.encode())
        worker_digest.update((directory / name).read_bytes())
    if worker_digest.hexdigest() != manifest["suite_sha256"]:
        raise ValueError(
            "Current worker/fixture sources differ from the measured suite; retain the exact measured sources"
        )
    for name in HARNESS_FILES:
        path = directory / name
        retain(path, "benchmarks/" + name, "source/" + name)
        receipt["harness_sources"].append(
            {
                "file": name,
                "sha256": digest(path.read_bytes()),
                "worker_suite_hash_input": name in HASHED_SUITE_FILES,
                "scope": "measured worker hash"
                if name in HASHED_SUITE_FILES
                else "supporting source at retention",
            }
        )

    original_manifest = members["matrix/manifest.json"]
    members["matrix/manifest.original-sanitized.json"] = original_manifest
    receipt["original_sanitized_manifest"] = {
        "member": "matrix/manifest.original-sanitized.json",
        "sha256": digest(original_manifest),
    }
    retained_manifest = json.loads(original_manifest)
    for entry in retained_manifest["entries"]:
        for kind in ("report", "log"):
            entry[kind + "_sha256"] = digest(members["matrix/" + entry[kind]])
    for entry in retained_manifest["memory"]:
        entry["report_sha256"] = digest(members["matrix/" + entry["report"]])
        entry["log"] = Path(entry["report"]).with_suffix(".log").as_posix()
        entry["log_sha256"] = digest(members["matrix/" + entry["log"]])
    members["matrix/manifest.json"] = encode_json(retained_manifest)
    for name, record in records.items():
        record["stored_sha256"] = digest(members[name])
        record["stored_bytes"] = len(members[name])
    receipt["counts"] = {
        "timing_reports": len(manifest["entries"]),
        "timing_logs": len(timing_files) - len(manifest["entries"]),
        "memory_reports": len(manifest["memory"]),
        "memory_logs": len(memory_files) - len(manifest["memory"]),
        "fixture_receipts": len(manifest["fixtures"]),
        "archive_members": len(members),
    }
    return receipt, members


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(
            "Output directory must be empty; existing evidence is never replaced"
        )
    receipt, members = prepare_retention(args.input, args.fixtures)
    archive = deterministic_archive(members)
    receipt["archive"] = {
        "file": "raw-evidence.tar.gz",
        "sha256": digest(archive),
        "bytes": len(archive),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".retain-large-", dir=args.output.parent
    ) as temporary:
        staging = Path(temporary) / "result"
        staging.mkdir()
        (staging / "raw-evidence.tar.gz").write_bytes(archive)
        for filename in ("comparison.md", "comparison.json"):
            data = members["matrix/" + filename]
            (staging / filename).write_bytes(data)
        (staging / "fixtures").mkdir()
        for name, data in members.items():
            if name.startswith("fixtures/"):
                (staging / name).write_bytes(data)
        receipt["readable_files"] = [
            {
                "file": path.relative_to(staging).as_posix(),
                "sha256": digest(path.read_bytes()),
                "bytes": path.stat().st_size,
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "raw-evidence.tar.gz"
        ]
        (staging / "retention.json").write_bytes(encode_json(receipt))
        # Verify the retained manifest against the sanitized reports before
        # publication. The deliberately absent payloads are disclosed by loader.
        check = Path(temporary) / "check"
        for name, data in members.items():
            path = check / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        _, _, unavailable = load_large(check / "matrix")
        if len(unavailable) != receipt["counts"]["fixture_receipts"]:
            raise ValueError("Retained fixture payload omission was not confirmed")
        if args.output.exists():
            args.output.rmdir()  # Only an empty destination can reach publication.
        staging.rename(args.output)
    print(f"Retained {args.output}: {receipt['counts']}")
    print(f"raw-evidence.tar.gz SHA-256: {receipt['archive']['sha256']}")


if __name__ == "__main__":
    main()
