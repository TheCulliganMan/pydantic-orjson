"""Fixture integrity, determinism, representative shapes, and safe file lifecycle."""

import hashlib
import json
import math

import pytest

from benchmarks import large_fixtures
from benchmarks.large_fixtures import FixtureSpec, generate, manifest_path, specs


@pytest.mark.parametrize("family", ["records", "numeric", "nested_unicode"])
@pytest.mark.parametrize("target_bytes", [1024, 8192])
def test_json_shape_size_integrity_and_reproducibility(tmp_path, family, target_bytes):
    spec = FixtureSpec(family, target_bytes)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    receipt = generate(spec, first)
    duplicate = generate(spec, second)
    payload = first.read_bytes()
    decoded = json.loads(payload)

    assert payload == second.read_bytes()
    assert receipt == duplicate
    assert receipt == json.loads(manifest_path(first).read_text())
    assert receipt["actual_bytes"] == len(payload) == first.stat().st_size
    assert receipt["sha256"] == hashlib.sha256(payload).hexdigest()
    assert (
        target_bytes <= len(payload) <= target_bytes + receipt["last_record_bytes"] + 2
    )
    assert len(decoded) == receipt["items"] > 0
    assert receipt["overshoot_bytes"] == len(payload) - target_bytes
    assert isinstance(decoded, list)
    if family == "records":
        assert all(isinstance(row, dict) and len(row) >= 8 for row in decoded)
        assert len({row["id"] for row in decoded}) == len(decoded)
        assert all(isinstance(row["customer"], dict) for row in decoded)
    elif family == "numeric":
        assert all(
            type(value) in (int, float) and math.isfinite(value) for value in decoded
        )
        assert {type(value) for value in decoded} == {int, float}
        assert min(decoded) < 0 < max(decoded)
    else:
        assert any(byte >= 128 for byte in payload)
        assert b"\\n" in payload and b"\\t" in payload and b'\\"' in payload
        assert all(isinstance(row["sections"], list) for row in decoded)
        assert all(isinstance(row["owner"]["profile"], dict) for row in decoded)
        assert 1024 <= receipt["max_record_bytes"] <= 4096


def test_specs_are_lightweight_descriptions_of_required_sizes():
    descriptions = specs()
    assert len(descriptions) == 9
    assert {spec.family for spec in descriptions} == {
        "records",
        "numeric",
        "nested_unicode",
    }
    assert {spec.target_bytes for spec in descriptions} == {
        1024**2,
        10 * 1024**2,
        100 * 1024**2,
    }
    assert len({spec.name for spec in descriptions}) == 9


def test_matching_existing_fixture_is_verified_and_reused(tmp_path):
    path = tmp_path / "numeric.json"
    spec = FixtureSpec("numeric", 1024)
    receipt = generate(spec, path)
    data_time = path.stat().st_mtime_ns
    manifest_time = manifest_path(path).stat().st_mtime_ns
    assert generate(spec, path) == receipt
    assert path.stat().st_mtime_ns == data_time
    assert manifest_path(path).stat().st_mtime_ns == manifest_time
    assert not list(tmp_path.glob("*.partial"))


def test_existing_unrelated_file_is_preserved(tmp_path):
    path = tmp_path / "fixture.json"
    original = b'{"existing":true}'
    path.write_bytes(original)
    with pytest.raises(FileExistsError):
        generate(FixtureSpec("records", 1024), path)
    assert path.read_bytes() == original
    assert not manifest_path(path).exists()


def test_existing_fixture_with_other_spec_is_preserved(tmp_path):
    path = tmp_path / "fixture.json"
    generate(FixtureSpec("records", 1024), path)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        generate(FixtureSpec("numeric", 1024), path)
    assert path.read_bytes() == original


def test_corrupted_fixture_is_not_silently_reused_or_replaced(tmp_path):
    path = tmp_path / "fixture.json"
    spec = FixtureSpec("records", 1024)
    generate(spec, path)
    corrupted = path.read_bytes().replace(b"created", b"altered", 1)
    path.write_bytes(corrupted)
    with pytest.raises(FileExistsError):
        generate(spec, path)
    assert path.read_bytes() == corrupted


def test_interruption_removes_owned_temporary_files(tmp_path, monkeypatch):
    original_row = large_fixtures._row

    def interrupted_row(family, index):
        if index == 5:
            raise KeyboardInterrupt
        return original_row(family, index)

    monkeypatch.setattr(large_fixtures, "_row", interrupted_row)
    path = tmp_path / "fixture.json"
    with pytest.raises(KeyboardInterrupt):
        generate(FixtureSpec("numeric", 8192), path)
    assert list(tmp_path.iterdir()) == []


def test_failed_manifest_publication_removes_only_owned_data(tmp_path, monkeypatch):
    original_link = large_fixtures.os.link
    path = tmp_path / "fixture.json"

    def link_with_manifest_collision(source, destination):
        if destination == manifest_path(path):
            destination.write_text("existing manifest")
        original_link(source, destination)

    monkeypatch.setattr(large_fixtures.os, "link", link_with_manifest_collision)
    with pytest.raises(FileExistsError):
        generate(FixtureSpec("numeric", 1024), path)
    assert not path.exists()
    assert manifest_path(path).read_text() == "existing manifest"
    assert list(tmp_path.iterdir()) == [manifest_path(path)]


@pytest.mark.parametrize("target_bytes", [0, -1])
def test_nonpositive_targets_are_rejected(target_bytes):
    with pytest.raises(ValueError, match="positive"):
        FixtureSpec("numeric", target_bytes)


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError, match="family"):
        FixtureSpec("unknown", 1024)
