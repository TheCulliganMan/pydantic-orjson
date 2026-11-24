#!/usr/bin/env bash
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
# Build on the oldest supported glibc, then smoke-test there. Full tests run
# on the CI host, where modern NumPy/pandas test wheels are available.
set -euo pipefail

phase=${1:-}
if [[ "$phase" == --in-container ]]; then
    shift
fi
requested=${1:?Usage: build_linux.sh PYTHON_VERSION}
build_profile=${ORJSON_LINUX_BUILD_PROFILE:-portable}
case "$build_profile" in
    portable|clang-lto) ;;
    *) printf 'Unsupported Linux build profile: %s\n' "$build_profile" >&2; exit 1 ;;
esac
case "$requested" in
    3.10|3.11|3.12|3.13|3.14|3.15|3.13t|3.14t|3.15t) ;;
    *) printf 'Unsupported Python ABI: %s\n' "$requested" >&2; exit 1 ;;
esac
architecture=$(uname -m)
case "$architecture" in
    x86_64)
        uv_sha256=58ccf5f1792b8a5a88d01bc910ea131a8b3db4a319a17ad5fad75e0845a3e271
        rustup_sha256=b1c8cb14e30889e7e2999e6b69e62d9e9b9ffc0f4df8180564d306d9680e6c55
        image_2014=quay.io/pypa/manylinux2014_x86_64@sha256:8a79ff36ce155d8f242dc8013d73c5e8bbe937defb15de7d7afb342c1ab537f4
        image_2_28=quay.io/pypa/manylinux_2_28_x86_64@sha256:55a36963bc0504cdf004011001c1072306402f0b8b83be5a5eba7068f93eec53
        ;;
    aarch64)
        uv_sha256=37fbb7c5bc66cf99c12aa881949d216181e201dec449772c4329e56487d61179
        rustup_sha256=9f608c142e0e38a78957d0661ba1dfaf0b6fb37184cfaa4b9a0aa57af6184282
        image_2014=quay.io/pypa/manylinux2014_aarch64@sha256:382236bfd11d86894d9792a6fa5286190b8dd3d075a7032284e123c288711e4f
        image_2_28=quay.io/pypa/manylinux_2_28_aarch64@sha256:126d9eea9d6b1717f3e17b2b3ac51da04ef159a5f935dac36fe92d621dc8f246
        ;;
    *) printf 'Unsupported native Linux architecture: %s\n' "$architecture" >&2; exit 1 ;;
esac
case "$requested" in
    3.15*) image=$image_2_28; compatibility=manylinux_2_28 ;;
    *) image=$image_2014; compatibility=manylinux_2_17 ;;
esac

if [[ "$phase" != --in-container ]]; then
    repo_dir=$(cd "$(dirname "$0")/.." && pwd)
    mkdir -p "$repo_dir/dist"
    if compgen -G "$repo_dir/dist/*.whl" >/dev/null; then
        printf 'dist already contains wheels; use a clean output directory.\n' >&2
        exit 1
    fi
    # The disposable container owns its caches and build environment. The
    # host checkout and its existing .venv are mounted read-only.
    docker run --rm --init \
        --volume "$repo_dir:/io:ro" \
        --volume "$repo_dir/dist:/dist" \
        --workdir /io \
        --env "OUTPUT_UID=$(id -u)" --env "OUTPUT_GID=$(id -g)" \
        --env "ORJSON_LINUX_BUILD_PROFILE=$build_profile" \
        "$image" bash /io/scripts/build_linux.sh --in-container "$requested"
    exit
fi

# Pins verified against official registry manifests/release checksums on
# 2026-11-24. Static uv also runs on the ARM64 glibc 2.17 image, unlike its
# GNU distribution. No pip/bootstrap Python environment is used.
export CARGO_HOME=/tmp/orjson-cargo RUSTUP_HOME=/tmp/orjson-rustup
export CARGO_TARGET_DIR=/tmp/orjson-target
export UV_CACHE_DIR=/tmp/orjson-uv-cache
export UV_PYTHON_INSTALL_DIR=/tmp/orjson-python
export UV_PROJECT_ENVIRONMENT=/tmp/orjson-smoke
export UV_MANAGED_PYTHON=1
export UV_PYTHON="$requested"
if [[ "$requested" != *t ]]; then
    UV_PYTHON="${requested}+gil"
fi
export PATH="/tmp/orjson-tools:$CARGO_HOME/bin:$PATH"
unset PYTHON_GIL PYTHONPATH VIRTUAL_ENV UNSAFE_PYO3_SKIP_VERSION_CHECK
mkdir -p /tmp/orjson-tools
curl --fail --show-error --silent --location --retry 3 \
    "https://github.com/astral-sh/uv/releases/download/0.13.9/uv-${architecture}-unknown-linux-musl.tar.gz" \
    --output /tmp/orjson-uv.tar.gz
printf '%s  %s\n' "$uv_sha256" /tmp/orjson-uv.tar.gz | sha256sum --check --strict
tar -xzf /tmp/orjson-uv.tar.gz --directory /tmp/orjson-tools --strip-components=1
curl --fail --show-error --silent --location --retry 3 \
    "https://static.rust-lang.org/rustup/archive/1.29.3/${architecture}-unknown-linux-gnu/rustup-init" \
    --output /tmp/orjson-tools/rustup-init
printf '%s  %s\n' "$rustup_sha256" /tmp/orjson-tools/rustup-init | sha256sum --check --strict
chmod +x /tmp/orjson-tools/rustup-init
/tmp/orjson-tools/rustup-init -y --no-modify-path --profile minimal --default-toolchain 1.99.0
uv --version
rustc --version
uv python install "${UV_PYTHON%+gil}"

# The optional experiment uses the official manylinux installer, which retains
# the image's GCC sysroot/runtime and baseline architecture. Toolchain release:
# https://github.com/mayeut/static-clang-images/releases/tag/v23.1.5.0
# The checksum-file and archive digests were checked against release metadata
# on 2026-11-24; the installer verifies both before extraction.
build_args="--locked --strip --compatibility $compatibility --auditwheel check"
export BUILD_PROFILE="$build_profile" BUILD_EXPLICIT_TARGET=
export BUILD_CLANG_RELEASE= BUILD_CLANG_CHECKSUM_FILE_SHA256= BUILD_CLANG_ARCHIVE_SHA256=
if [[ "$build_profile" == clang-lto ]]; then
    export BUILD_CLANG_RELEASE=23.1.5.0
    export BUILD_CLANG_CHECKSUM_FILE_SHA256=80bf99b6afe83420a648a6d0eae0e0cfd6472cdb26577b1c12964fe29884dc06
    case "$architecture" in
        x86_64) export BUILD_CLANG_ARCHIVE_SHA256=98e4329235d8ffec368c2bf60fe760a3d68fab802852921ba92c31324efa5da9 ;;
        aarch64) export BUILD_CLANG_ARCHIVE_SHA256=c39dd96082249a831c05e9d860964d55a2987a89ba695db2451a91c5a1f222b8 ;;
    esac
    manylinux-install-clang -v "$BUILD_CLANG_RELEASE" -c "$BUILD_CLANG_CHECKSUM_FILE_SHA256"
    export CC=/opt/clang/bin/clang AR=/opt/clang/bin/llvm-ar
    export CFLAGS='-O2 -fstrict-aliasing -flto=full'
    # Match full LTO in C and Rust. Rust 1.99 uses LLVM 23.1.1; the LLVM
    # 23.1.5 linker shares its major version. Qualification checks compatibility.
    # https://doc.rust-lang.org/rustc/linker-plugin-lto.html
    export RUSTFLAGS='-C linker=/opt/clang/bin/clang -C link-arg=-fuse-ld=lld -C linker-plugin-lto -C lto=fat'
    export BUILD_EXPLICIT_TARGET="${architecture}-unknown-linux-gnu"
    # An explicit target keeps target LTO flags off host build scripts.
    build_args+=" --target $BUILD_EXPLICIT_TARGET"
fi
export BUILD_CC="${CC:-cc}" BUILD_AR="${AR:-ar}"
export BUILD_LINKER=ld
if [[ "$build_profile" == clang-lto ]]; then
    export BUILD_LINKER=/opt/clang/bin/ld.lld
fi
export BUILD_CFLAGS="${CFLAGS:-}" BUILD_RUSTFLAGS="${RUSTFLAGS:-}"

# Only our experimental 3.13t port bypasses PyO3's version guard.
if [[ "$requested" == 3.13t ]]; then
    export UNSAFE_PYO3_SKIP_VERSION_CHECK=1
fi
uv build --wheel --no-sources --python "$UV_PYTHON" \
    -C "maturin.build-args=$build_args" \
    --out-dir /dist
unset UNSAFE_PYO3_SKIP_VERSION_CHECK
wheels=(/dist/*.whl)
[[ ${#wheels[@]} == 1 && -f "${wheels[0]}" ]]
uv venv --python "$UV_PYTHON" "$UV_PROJECT_ENVIRONMENT"
uv pip install --python "$UV_PROJECT_ENVIRONMENT" --no-deps "${wheels[0]}"
export REQUESTED_PYTHON="$requested" BUILD_IMAGE="$image"
export BUILD_COMPATIBILITY="$compatibility" BUILD_WHEEL="${wheels[0]}"
# No project sync: current optional test dependencies need newer glibc.
# -I ensures imports come from the installed wheel in the temporary venv.
uv run --no-project --python "$UV_PROJECT_ENVIRONMENT/bin/python" python -I - <<'PY'
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import sysconfig
from concurrent.futures import ThreadPoolExecutor

requested = os.environ["REQUESTED_PYTHON"]
threaded = requested.endswith("t")
assert f"{sys.version_info.major}.{sys.version_info.minor}" == requested.removesuffix(
    "t"
)
assert bool(sysconfig.get_config_var("Py_GIL_DISABLED")) == threaded
before = getattr(sys, "_is_gil_enabled", lambda: True)()
import orjson

after = getattr(sys, "_is_gil_enabled", lambda: True)()
assert before is not threaded and after is not threaded, (before, after, threaded)
assert pathlib.Path(orjson.__file__).is_relative_to(pathlib.Path(sys.prefix))


def check(index):
    value = {
        "id": index,
        "text": "snow: 雪\\\n" * 32,
        "items": [True, None, list(range(32))],
    }
    assert orjson.loads(orjson.dumps(value)) == value
    assert orjson.dumps({"data": orjson.Fragment(b"[1,2]")}) == b'{"data":[1,2]}'


with ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(check, range(256)))
wheel = pathlib.Path(os.environ["BUILD_WHEEL"])
compatibility = os.environ["BUILD_COMPATIBILITY"]
assert compatibility in wheel.name, wheel.name
record = {
    "python": sys.version,
    "architecture": platform.machine(),
    "libc": platform.libc_ver(),
    "image": os.environ["BUILD_IMAGE"],
    "compatibility": compatibility,
    "uv": "0.13.9",
    "rustup": "1.29.3",
    "rust": "1.99.0",
    "build_profile": os.environ["BUILD_PROFILE"],
    "toolchain": {
        "rustc": subprocess.check_output(["rustc", "-vV"], text=True).strip(),
        "cc": os.environ["BUILD_CC"],
        "cc_version": subprocess.check_output(
            [os.environ["BUILD_CC"], "--version"], text=True
        ).strip(),
        "ar": os.environ["BUILD_AR"],
        "ar_version": subprocess.check_output(
            [os.environ["BUILD_AR"], "--version"], text=True
        ).strip(),
        "linker": os.environ["BUILD_LINKER"],
        "linker_version": subprocess.check_output(
            [os.environ["BUILD_LINKER"], "--version"], text=True
        ).strip(),
        "cflags": os.environ["BUILD_CFLAGS"],
        "rustflags": os.environ["BUILD_RUSTFLAGS"],
        "explicit_target": os.environ["BUILD_EXPLICIT_TARGET"] or None,
        "static_clang_release": os.environ["BUILD_CLANG_RELEASE"] or None,
        "static_clang_checksum_file_sha256": os.environ[
            "BUILD_CLANG_CHECKSUM_FILE_SHA256"
        ] or None,
        "static_clang_archive_sha256": os.environ["BUILD_CLANG_ARCHIVE_SHA256"] or None,
    },
    "wheel": wheel.name,
    "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    "gil_before_import": before,
    "gil_after_import": after,
    "threaded_roundtrips": 256,
}
pathlib.Path("/dist/linux-build.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
PY
chown "${OUTPUT_UID:?}:${OUTPUT_GID:?}" "${wheels[0]}" /dist/linux-build.json
