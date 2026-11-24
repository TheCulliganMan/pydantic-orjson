#!/usr/bin/env bash
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
set -euo pipefail
cd "$(dirname "$0")/.."

# A local environment only; leave system Python untouched.
uv venv --python 3.13 --allow-existing .venv
uv pip install --python .venv/bin/python -r requirements-fork.txt
.venv/bin/python script/check-version
.venv/bin/maturin build --release --strip --locked --out dist -i .venv/bin/python
distribution_version=$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
uv pip install --python .venv/bin/python --reinstall "dist/orjson-${distribution_version}-"*.whl
.venv/bin/python -m pytest -q test compatibility integration_pydantic
.venv/bin/ruff check pysrc/orjson/pydantic.py pysrc/orjson/pydantic_ai.py compatibility integration_pydantic benchmarks scripts
.venv/bin/ruff format --check pysrc/orjson/pydantic.py pysrc/orjson/pydantic_ai.py compatibility integration_pydantic benchmarks scripts
.venv/bin/python scripts/clean.py
