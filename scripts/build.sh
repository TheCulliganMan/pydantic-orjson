#!/usr/bin/env bash
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
set -euo pipefail
cd "$(dirname "$0")/.."

python_spec="${1:-$(cat .python-version)}"
case "$python_spec" in
    *t|*+*) ;;
    3.*) python_spec="${python_spec}+gil" ;;
esac
uv python install "${python_spec%+gil}"
if [[ "$python_spec" == 3.13t || "$python_spec" == 3.13+freethreaded ]]; then
    uv sync --locked --python "$python_spec" --no-install-project --no-build --group native313t
else
    uv sync --locked --python "$python_spec" --no-install-project --group native --group integration
fi
uv run --no-sync --python "$python_spec" python script/check-version
build_python=$(uv run --no-sync --python "$python_spec" python -c 'import sys; print(sys.executable)')
mkdir -p .artifacts dist
build_dir=$(mktemp -d "$PWD/.artifacts/local-wheel.XXXXXX")

# PyO3 0.29 dropped experimental 3.13t; this fork carries and tests that ABI.
# Every other interpreter keeps PyO3's normal version checks.
if [[ "$python_spec" == 3.13t || "$python_spec" == 3.13+freethreaded ]]; then
    UNSAFE_PYO3_SKIP_VERSION_CHECK=1 uv build --wheel --python "$build_python" --no-sources \
        -C 'maturin.build-args=--locked --strip' --out-dir "$build_dir"
else
    uv build --wheel --python "$build_python" --no-sources \
        -C 'maturin.build-args=--locked --strip' --out-dir "$build_dir"
fi
wheels=("$build_dir"/*.whl)
[[ ${#wheels[@]} == 1 && -f "${wheels[0]}" ]]
uv pip install --python "$build_python" --no-deps --reinstall "${wheels[0]}"
cp "${wheels[0]}" dist/
minor=$(uv run --no-sync --python "$python_spec" python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$python_spec" == 3.13t || "$python_spec" == 3.13+freethreaded ]]; then
    PYTHON_GIL=0 uv run --no-sync --python "$python_spec" python -m pytest -q test compatibility --ignore=compatibility/test_drop_in.py
elif [[ "$minor" == 3.10 ]]; then
    uv run --no-sync --python "$python_spec" python -m pytest -q test compatibility --ignore=compatibility/test_drop_in.py integration_pydantic/test_codec.py integration_pydantic/test_semantics.py
else
    uv run --no-sync --python "$python_spec" python -m pytest -q test compatibility integration_pydantic
fi
uv run --no-sync --python "$python_spec" ruff check pysrc/orjson/pydantic.py pysrc/orjson/pydantic_ai.py compatibility integration_pydantic benchmarks scripts
uv run --no-sync --python "$python_spec" ruff format --check pysrc/orjson/pydantic.py pysrc/orjson/pydantic_ai.py compatibility integration_pydantic benchmarks scripts
uv pip check --python "$build_python"
if [[ "${ORJSON_KEEP_BUILD_ARTIFACTS:-0}" != 1 ]]; then
    uv run --no-sync --python "$python_spec" python scripts/clean.py --preserve-env "${UV_PROJECT_ENVIRONMENT:-.venv}"
fi
