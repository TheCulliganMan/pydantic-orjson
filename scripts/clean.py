#!/usr/bin/env -S uv run --no-sync python
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Remove this checkout's rough outputs; keep dist, .venv and committed reports."""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preserve-env", type=Path, default=ROOT / ".venv")
    args = parser.parse_args()
    preserved = args.preserve_env.resolve()
    for name in (
        "target",
        "build",
        ".artifacts",
        ".venv-baseline",
        ".venv-install-check",
        ".venv-asan",
        ".venv-asan-ft",
        ".venv-published",
        ".venv-freethreaded",
        ".venv-313t",
        ".hypothesis",
        ".pytest_cache",
        ".ruff_cache",
    ):
        path = ROOT / name
        if path.resolve() == preserved:
            continue
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        print(f"Cleaned {name}")
    for directory in (
        "pysrc",
        "test",
        "compatibility",
        "integration_pydantic",
        "benchmarks",
        "scripts",
    ):
        for path in (ROOT / directory).rglob("__pycache__"):
            if path.is_symlink():
                path.unlink()
            else:
                shutil.rmtree(path)


if __name__ == "__main__":
    main()
