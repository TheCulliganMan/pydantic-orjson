#!/usr/bin/env python3
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Run an instrumented installed wheel with its matching ASan runtime."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform not in ("darwin", "linux"):
        parser.error("The sanitizer launcher supports macOS and Linux")
    runtime = str(args.runtime.resolve(strict=True))
    loader = "DYLD_INSERT_LIBRARIES" if sys.platform == "darwin" else "LD_PRELOAD"
    env = dict(os.environ)
    env.update(
        {
            loader: runtime,
            "ORJSON_ASAN_RUNTIME": runtime,
            "ORJSON_ASAN_LOADER": loader,
            "ASAN_OPTIONS": "detect_leaks=0:detect_stack_use_after_return=1:abort_on_error=1",
            "PYTHONMALLOC": "malloc",
        }
    )
    # dyld removes its injection variable after loading. Restore it for isolated
    # test subprocesses so they can load the same instrumented extension.
    bootstrap = """
import os
os.environ[os.environ['ORJSON_ASAN_LOADER']] = os.environ['ORJSON_ASAN_RUNTIME']
import pytest
raise SystemExit(pytest.main([
    '-q', '-rs', '--ignore=test/test_memory.py', 'test', 'compatibility',
    'integration_pydantic',
]))
"""
    # RSS growth assertions target the normal allocator; ASan's quarantine
    # intentionally retains freed memory. Run that suite with PYTHONMALLOC=debug
    # on the ordinary wheel separately. Leak detection is likewise excluded.
    result = subprocess.run(
        [str(args.python.absolute()), "-X", "faulthandler", "-c", bootstrap],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
