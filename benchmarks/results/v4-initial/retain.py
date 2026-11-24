# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Reproduce these historical archives from downloaded GitHub artifacts using UV.

Only runner identities/home paths are removed. Timing samples, warnings, cases,
orders and build/test results are retained; matrix evidence hashes are updated.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def scrub_text(value: str) -> str:
    value = re.sub(r'\s+hostname="[^"]*"', "", value)
    return value.replace(
        "/home/runner/work/pydantic-orjson/pydantic-orjson", "<checkout>"
    ).replace("/home/runner", "<runner-home>")


def scrub(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: scrub(item)
            for key, item in value.items()
            if key not in ("hostname", "python_executable")
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def main() -> None:  # noqa: PLR0912, PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("--profile", choices=("portable", "clang-lto"), required=True)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    if any(args.destination.iterdir()):
        parser.error("Destination must be empty")
    receipt = {
        "format": 1,
        "workflow_run": f"https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/{args.run}",
        "artifact": args.artifact.name,
        "source_commit": (args.artifact / "results/source-commit.txt")
        .read_text()
        .strip(),
        "build_profile": args.profile,
        "removed_metadata_fields": ["hostname", "python_executable"],
        "removed_xml_attributes": ["hostname"],
        "path_replacements": {
            "GitHub runner checkout": "<checkout>",
            "GitHub runner home": "<runner-home>",
        },
        "matrix_manifest_rewrites": ["report_sha256", "log_sha256"],
        "files": [],
        "wheel_archives_not_duplicated_in_git": [],
    }
    members: dict[str, bytes] = {}
    entries = {}
    for path in sorted(args.artifact.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(args.artifact).as_posix()
        original = path.read_bytes()
        if path.suffix == ".whl":
            receipt["wheel_archives_not_duplicated_in_git"].append(
                {
                    "original_file": relative,
                    "sha256": digest(original),
                    "bytes": len(original),
                }
            )
            continue
        sanitized = (
            json_bytes(scrub(json.loads(original)))
            if path.suffix == ".json"
            else scrub_text(original.decode()).encode()
        )
        if path.suffix == ".xml":
            sanitized = sanitized.replace(b"<checkout>", b"&lt;checkout&gt;").replace(
                b"<runner-home>", b"&lt;runner-home&gt;"
            )
        entry = {
            "original_file": relative,
            "original_sha256": digest(original),
            "original_bytes": len(original),
            "sanitized_sha256": digest(sanitized),
            "sanitized_bytes": len(sanitized),
        }
        entries[relative] = entry
        receipt["files"].append(entry)
        if relative.startswith("results/matrix/"):
            member = relative.removeprefix("results/")
            members[member] = sanitized
            entry.update({"archive": "measurements.tar.gz", "member": member})
        else:
            filename = "provenance/" + path.name
            if path.suffix == ".xml" or len(sanitized) > 10_000:
                filename += ".gz"
                retained = gzip.compress(sanitized, mtime=0)
            else:
                retained = sanitized
            destination = args.destination / filename
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(retained)
            entry.update(
                {
                    "file": filename,
                    "retained_sha256": digest(retained),
                    "retained_bytes": len(retained),
                }
            )

    manifest = json.loads(members["matrix/manifest.json"])
    # Preserve the sanitized original manifest too, so its original evidence
    # hashes remain available alongside the retained archive's updated hashes.
    members["matrix/manifest.original-sanitized.json"] = members["matrix/manifest.json"]
    receipt["original_sanitized_manifest"] = {
        "member": "matrix/manifest.original-sanitized.json",
        "sha256": digest(members["matrix/manifest.original-sanitized.json"]),
    }
    for measurement in manifest["measurements"]:
        for kind in ("report", "log"):
            measurement[kind + "_sha256"] = digest(
                members["matrix/" + measurement[kind]]
            )
    members["matrix/manifest.json"] = json_bytes(manifest)
    entry = entries["results/matrix/manifest.json"]
    entry["retained_manifest_sha256"] = digest(members["matrix/manifest.json"])
    for entry in receipt["files"]:
        if "member" in entry:
            data = members[entry["member"]]
            entry.update({"retained_sha256": digest(data), "retained_bytes": len(data)})
    tar_buffer = io.BytesIO()
    with tarfile.open(
        fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT
    ) as archive:
        for name, data in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            info.uid, info.gid, info.uname, info.gname = 0, 0, "", ""
            archive.addfile(info, io.BytesIO(data))
    compressed = gzip.compress(tar_buffer.getvalue(), mtime=0)
    (args.destination / "measurements.tar.gz").write_bytes(compressed)
    (args.destination / "comparison.md").write_bytes(members["matrix/comparison.md"])
    receipt["archive"] = {
        "file": "measurements.tar.gz",
        "sha256": digest(compressed),
        "bytes": len(compressed),
        "members": len(members),
    }
    receipt["comparison_markdown_sha256"] = digest(members["matrix/comparison.md"])
    (args.destination / "retention.json.gz").write_bytes(
        gzip.compress(json_bytes(receipt), mtime=0)
    )
    print(
        f"Retained {args.destination}: {len(members)} archive members, {len(compressed)} bytes"
    )


if __name__ == "__main__":
    main()
