#!/usr/bin/env python3
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Remove this checkout's rough outputs; keep dist, .venv and committed reports."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for name in (
        "target",
        "build",
        ".artifacts",
        ".venv-baseline",
        ".venv-install-check",
        ".venv-asan",
        ".venv-published",
        ".hypothesis",
        ".pytest_cache",
        ".ruff_cache",
    ):
        path = ROOT / name
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
