"""Deterministic JSON fixtures streamed to disk without a whole-payload object."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
GENERATOR_VERSION = 1
FAMILIES = ("records", "numeric", "nested_unicode")
SHAPES = {
    "records": "array of varied event records with identifiers, amounts, flags, customer objects, and tags",
    "numeric": "array of finite integer and floating-point scalars with varied signs and magnitudes",
    "nested_unicode": "array of nested document objects with lists, multilingual text, and escaped prose",
}


@dataclass(frozen=True)
class FixtureSpec:
    family: str
    target_bytes: int

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"Unknown fixture family: {self.family!r}")
        if isinstance(self.target_bytes, bool) or not isinstance(
            self.target_bytes, int
        ):
            raise TypeError("target_bytes must be an integer")
        if self.target_bytes <= 0:
            raise ValueError("target_bytes must be positive")

    @property
    def name(self) -> str:
        size = (
            f"{self.target_bytes // MIB}mib"
            if self.target_bytes % MIB == 0
            else f"{self.target_bytes}b"
        )
        return f"{self.family}-{size}"


def specs() -> tuple[FixtureSpec, ...]:
    """Return lightweight descriptions; do not generate or load any payload."""
    return tuple(
        FixtureSpec(family, size * MIB) for family in FAMILIES for size in (1, 10, 100)
    )


def manifest_path(path: Path | str) -> Path:
    path = Path(path)
    return path.with_name(f"{path.name}.manifest.json")


def _row(family: str, index: int) -> Any:  # noqa: PLR0911 - explicit numeric distributions
    if family == "records":
        return {
            "id": index,
            "event": ("created", "updated", "fulfilled", "returned")[index % 4],
            "account_id": 1_000_000 + index % 19_997,
            "customer": {
                "name": f"Customer {index % 19_997}",
                "region": ("north", "south", "east", "west")[index % 4],
                "verified": index % 7 != 0,
            },
            "amount": ((index * 7_919) % 1_000_003) / 100,
            "currency": ("USD", "EUR", "GBP")[index % 3],
            "quantity": index % 23 + 1,
            "priority": index % 11 == 0,
            "note": None if index % 5 == 0 else f"Shipment reference {index:09d}",
            "tags": [f"batch-{index // 100}", f"channel-{index % 8}"],
            "timestamp": 1_767_225_600 + index * 17,
        }
    if family == "numeric":
        kind = index % 8
        if kind == 0:
            return index
        if kind == 1:
            return -((index * 104_729) % 2_147_483_647)
        if kind == 2:
            return 9_000_000_000_000_000 + index
        if kind == 3:
            return (index % 200_001 - 100_000) / 1_000
        if kind == 4:
            return (index % 10_000 + 1) * 1e-12
        if kind == 5:
            return (index % 10_000 + 1) * 1e12
        if kind == 6:
            return (index % 100_000) / 7.0
        return -0.0 if index % 64 == 7 else -(index % 100_003 + 1) / 13

    # About 1-3 KiB per record: variation remains distributed across small values.
    languages = (
        "café déjà vu",
        "森林と湖",
        "مرحبا بالعالم",
        "γειά σου κόσμε",  # noqa: RUF001 - intentional Greek text
        "📦 🌲 🦭",
    )
    return {
        "document_id": f"doc-{index:09d}",
        "title": f"Field report {index}: {languages[index % len(languages)]}",
        "owner": {
            "id": index % 4_093,
            "profile": {
                "name": f"Zoë {index % 997}",
                "locales": ["en-US", "ja-JP", "ar"],
                "preferences": {"alerts": index % 3 != 0, "theme": "forest"},
            },
        },
        "sections": [
            {
                "heading": f"Section {section}: {languages[(index + section) % len(languages)]}",
                "paragraphs": [
                    (
                        f'Observation {index}/{section}: "The water is clear," she said.\n'
                        "Trail markers: north\\ridge\tthen lake; café, 森林, مرحبا, 🦭. "
                        f"Samples {index % 97}, {(index + section) % 89} remain available."
                    ),
                    (
                        f"Review {index * 3 + section}: naïve façades and coöperation; "
                        "Καλημέρα κόσμε. Measurements are recorded beside the shoreline."
                    ),
                ],
                "observations": [
                    {
                        "site": f"site-{index % 101}",
                        "depth_m": (index % 300 + section) / 10,
                    },
                    {
                        "labels": ["lake", languages[section]],
                        "verified": index % 2 == 0,
                    },
                ],
            }
            for section in range(3)
        ],
        "links": [{"rel": "source", "path": f"/reports/{index % 2_003}/{index}"}],
        "revision": index % 17,
    }


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing(spec: FixtureSpec, path: Path, manifest: Path) -> dict[str, Any] | None:
    if not path.exists() and not manifest.exists():
        return None
    error = f"Refusing to replace an existing fixture or manifest: {path}"
    if not path.is_file() or not manifest.is_file():
        raise FileExistsError(error)
    try:
        receipt = json.loads(manifest.read_text(encoding="utf-8"))
        expected = {
            "generator_version": GENERATOR_VERSION,
            "family": spec.family,
            "name": spec.name,
            "target_bytes": spec.target_bytes,
            "shape": SHAPES[spec.family],
        }
        valid = (
            all(receipt.get(key) == value for key, value in expected.items())
            and receipt["actual_bytes"] >= spec.target_bytes
            and receipt["items"] > 0
            and receipt["actual_bytes"] == path.stat().st_size
            and receipt["sha256"] == _file_digest(path)
        )
    except (AttributeError, KeyError, TypeError, ValueError, OSError) as exc:
        raise FileExistsError(error) from exc
    if not valid:
        raise FileExistsError(error)
    return receipt


def generate(spec: FixtureSpec, path: Path | str) -> dict[str, Any]:  # noqa: PLR0915 - one atomic publication lifecycle
    """Stream one JSON array, reaching the target only at a complete item boundary.

    Returns a deterministic receipt and writes it beside the JSON file. Existing
    files are reused only when their manifest matches the specification and their
    size and hash still match. New files are published with no-overwrite hard
    links after their contents are complete; owned temporary files are removed on
    normal completion or exceptions. Memory is bounded by one row and a 64 KiB
    output buffer. Targets are binary bytes (1 MiB = 1,048,576 bytes).
    """
    path = Path(path)
    manifest = manifest_path(path)
    existing = _existing(spec, path, manifest)
    if existing is not None:
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    encode = json.JSONEncoder(
        ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode
    digest = hashlib.sha256()
    temporary_paths: list[Path] = []
    published_data = False
    data_temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".partial",
            delete=False,
        ) as output:
            data_temp = Path(output.name)
            temporary_paths.append(data_temp)
            buffer = bytearray(b"[")
            actual_bytes = 1
            items = 0
            max_record_bytes = 0
            last_record_bytes = 0
            while items == 0 or actual_bytes + 1 < spec.target_bytes:
                record = encode(_row(spec.family, items)).encode("utf-8")
                if items:
                    buffer.extend(b",")
                    actual_bytes += 1
                buffer.extend(record)
                last_record_bytes = len(record)
                max_record_bytes = max(max_record_bytes, last_record_bytes)
                actual_bytes += last_record_bytes
                items += 1
                if len(buffer) >= 64 * 1024:
                    output.write(buffer)
                    digest.update(buffer)
                    buffer.clear()
            buffer.extend(b"]")
            actual_bytes += 1
            output.write(buffer)
            digest.update(buffer)
            output.flush()
            os.fsync(output.fileno())

        receipt = {
            "generator_version": GENERATOR_VERSION,
            "name": spec.name,
            "family": spec.family,
            "target_bytes": spec.target_bytes,
            "actual_bytes": actual_bytes,
            "sha256": digest.hexdigest(),
            "items": items,
            "shape": SHAPES[spec.family],
            "encoding": "utf-8",
            "size_policy": "at least target bytes, stopping at a complete array item",
            "overshoot_bytes": actual_bytes - spec.target_bytes,
            "max_record_bytes": max_record_bytes,
            "last_record_bytes": last_record_bytes,
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{manifest.name}.",
            suffix=".partial",
            delete=False,
        ) as output:
            manifest_temp = Path(output.name)
            temporary_paths.append(manifest_temp)
            json.dump(receipt, output, sort_keys=True, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())

        # Unlike replace(), link() fails atomically if another writer owns the path.
        os.link(data_temp, path)
        published_data = True
        os.link(manifest_temp, manifest)
        return receipt
    except BaseException:
        if published_data and data_temp is not None:
            try:
                if path.samefile(data_temp):
                    path.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
