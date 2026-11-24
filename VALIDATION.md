# Initial build validation

Validated locally on November 24, 2026, on Apple M5 / macOS 27.2.1 ARM64,
CPython 3.13.12, rustc 1.99.0, and maturin 1.16.0. Exact Python dependencies
are pinned in `requirements-fork.txt` (Pydantic 2.14.4, pydantic-core 2.50.5,
Pydantic AI slim 2.73.0, FastAPI 0.165.0, NumPy 2.5.5).

## Installed artifact

`dist/orjson-3.13.0+pydantic.1-cp313-cp313-macosx_11_0_arm64.whl`

SHA-256: `c2eb711acabb63f7a7c63c0487f3bf34246cbc22bdc73308038636f1f67e5d5f`

Built with `maturin build --release --strip --locked`, CPython 3.13, the checked-in
Cargo.lock, and default macOS deployment target 11.0. No CPU-specific RUSTFLAGS
or benchmark-only native changes were introduced. The upstream baseline was
built from `bd00937c5c46ab20eb5d7fe1cfc034b906c4578f` with the same toolchain and
options. Both initially installed native extensions have SHA-256:

`1d05a468f0e7fa547635cc29ca5f5578de1860fa51a58dcabe666ea788b3b769`

The identical native binaries are intentional. This build adds integration
modules and packaging, not an optimized native encoder/decoder. The wheel is
retained locally, ignored by Git, and rebuildable from source; it is not a
PyPI release. A new build may have different wheel archive metadata/digests.

## Checks completed

| Check | Result |
| --- | --- |
| Full upstream suite plus compatibility and typed/AI tests against installed wheel | **1,642 passed; 32 skipped; 3 expected FastAPI deprecation warnings**, 8.18 seconds |
| Differential baseline/candidate comparison | **756 cases + 7 API contracts; zero mismatches**; [machine-readable result](compatibility/results/local.json) |
| FastAPI / Starlette | TestClient requests, NumPy/non-string keys, headers, aliases, field serializer, response filtering, request validation/errors passed |
| Pydantic | Strict JSON date/tuple semantics, aliases, exclusion, serializer/validator context, root model, discriminated union, error parity and explicit partial mode passed |
| Pydantic AI | Offline official-adapter message/tool-call/tool-result round trip and invalid discriminator checks passed |
| Minimal install with no optional dependencies | Fresh temporary environment imports/uses native orjson without importing Pydantic |
| Installed dependency consistency | `uv pip check` passed for 36 packages |
| Wheel/source archive contents | Helpers, typing marker/stubs, source/test/build files and retained wheel licenses inspected |
| Added Python code quality | Ruff lint and formatting checks passed |
| Upstream preservation | Rust source, Cargo.toml/lock, original Python API/stubs and upstream tests unchanged |

Skipped upstream tests include unavailable optional packages (pandas, pendulum,
psutil), Python-version-dependent features, and upstream's explicitly skipped
NumPy case. These skips are not counted as passes. No native fuzz/sanitizer,
full downstream ecosystem, or production load-test qualification is claimed.
The source archive was inspected, not independently rebuilt offline.

## Benchmark interpretation

Four initial diagnostic reports are retained under [benchmarks/results](benchmarks/results):
upstream then candidate, followed by candidate then upstream. Each checks
correctness and collects 11 timed samples per case. Candidate reports also
contain two typed Codec cases; these change the randomized case schedule,
so the first reports are exploratory rather than a controlled paired trial.

The first comparison appeared to favor the candidate by roughly 1.26–1.45x
even for unchanged Pydantic operations. Reversing the run order produced
substantial dispersion (some median absolute deviations above 20%) and
unstable control ratios. Since the native binaries are identical and the
Pydantic versions are identical, these numbers do **not** establish a fork
speed improvement. They show the need for controlled worker processes,
matched schedules, repeated trials and dedicated hardware. The reports retain
raw samples and this limitation rather than promoting the favorable ratios.

After detecting the schedule mismatch, the comparator was tightened to reject
different case sets or seeds. Four additional `*-matched*.json` reports use
the same ten cases and order seed in each environment, with both run orders.
For these runs upstream was rebuilt from an isolated archive of the same base
commit, with the same build flags; its extension digest is recorded in those
reports (`fb96a0295d4be56aee205013a82f4841c0dee6af3574435bf36c239f413209b2`).
The first matched comparison's six raw encode/decode ratios range from
0.965x to 1.034x (baseline median / candidate median). The reversed comparison
ranges from 0.889x to 1.049x for raw cases, while unchanged direct Pydantic
controls also move to 0.828x and 0.862x. These results establish neither a
speed gain nor performance acceptance. Matched runs remain noisy
single-process diagnostics, not release-quality evidence.

Benchmark metadata records the upstream Git HEAD plus a dirty working tree:
measurements were made before the initial fork commit. Installed distribution
versions, native binary hashes, fixture hashes and dependency versions identify
the measured artifacts. The integration source measured is committed alongside
the reports. See [benchmark methodology](benchmarks/README.md) and the
[performance plan](PLAN.md) for release-quality measurement gates.

## Scope and cleanup

Local verification covers one macOS ARM64 / Python 3.13 environment. Automated
CI is configured for Linux 3.10/3.13/3.14 and macOS/Windows 3.13. A configured
job is not a passed result; consult the repository's Actions runs for current
remote status. Broader upstream wheel support remains a release gate.

Temporary baseline and clean-install environments, Cargo target output,
intermediate source/wheel archives and test/lint caches are removed with
`scripts/clean.py`. The final wheel, usable `.venv`, source checkout, and compact
JSON evidence are retained. Reproduce with `bash scripts/build.sh`.
