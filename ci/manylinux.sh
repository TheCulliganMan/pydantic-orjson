#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Run inside the desired manylinux build image; uv retains maturin's ABI audit.
exec bash scripts/build.sh "${UV_PYTHON:-3.13}"
