# Free-threaded implementation — 3.13.0+pydantic.3

The `.3` implementation adds actual GIL-disabled wheels for CPython 3.13t,
3.14t and 3.15t. Import must leave the GIL disabled; tests assert that state.
Regular CPython 3.10–3.15 remains supported. The wheel workflow covers five
platforms (Linux x86-64/ARM64, macOS x86-64/ARM64, Windows x86-64): 30 regular
and 15 free-threaded builds. The configured matrix is not itself a pass claim;
completed cross-platform results will be recorded below.

Local release-wheel checks on macOS ARM64:

| Interpreter | Result |
| --- | --- |
| CPython 3.13.12, regular GIL, debug allocator | **1,997 passed; 43 skipped; 4 expected warnings** |
| CPython 3.14.3t, `PYTHON_GIL=0`, debug allocator | **2,026 passed; 14 skipped; 4 expected warnings** |
| Differential, regular candidate vs published/source baselines | **2,425 cases + 7 API contracts; zero mismatches** |
| Differential, 3.14t candidate vs published 3.13.12 baseline | **2,425 cases + 7 API contracts; zero mismatches**; this corpus comparison crosses Python versions |

See [regular published](compatibility/results/v3-published.json),
[regular source](compatibility/results/v3-source.json), and
[free-threaded](compatibility/results/v3-freethreaded.json) reports. Normal
builds skip the 31 no-GIL-only checks. Free-threaded builds skip the two
allocation-threshold GC reentry tests because that mechanism does not trigger
in-call collection there; a separate concurrent collection test passes.
The remaining 12 skips match the resource/version/known-upstream exclusions
recorded for `.2` below. Skips are not passes.

The port uses owned list/dictionary snapshots under CPython critical sections,
ends locks before Python callbacks, retains dataclass/type/attribute references,
uses CPython-owned Fragment headers and synchronized string access, and copies
mutable JSON buffers while retaining their storage. Error documents own the
copied input after parsing fails. Decoded keys and NumPy capsule ownership are
corrected. Concurrent callbacks, parent mutation, fragments, shared Unicode,
output growth/errors and GC are exercised with real Python threads.

Concurrency limits are explicit in [compatibility](compatibility/README.md):
container snapshots are shallow; concurrent class/type mutation on experimental
3.13t requires caller synchronization; concurrent writes through memoryview
aliases, native buffer writers and NumPy array mutation also require caller
synchronization. No-GIL execution does not imply an atomic snapshot of an entire
mutable object graph or guaranteed linear speedup.

---

# Implementation validation — 3.13.0+pydantic.2

Validated locally on November 24, 2026, with CPython 3.13.12, Apple M5 /
macOS 27.2.1 ARM64, Rust 1.99.0 and maturin 1.16.0. Development dependencies
are pinned in `requirements-fork.txt`; installed dependency consistency passes.

## Current implementation

The native changes are bounded NEON string scans on stable ARM64, a stack
parser arena for documents up to 321 UTF-8 bytes, removal of a redundant
unsorted non-string-key vector, retained snapshot value references during
value callbacks, and explicitly unaligned escape/boolean/null stores.

The original import, distribution name, native functions, flags, signatures
and exception contracts are preserved. Typed encoding/decoding retain public
Pydantic TypeAdapter methods: direct-core shortcuts were rejected after
callback, dynamic model hook and warning-filter differences were demonstrated.
Pydantic AI helpers now persist full conversations with the official adapter.

| Check | Result |
| --- | --- |
| Installed release wheel, complete upstream + compatibility + typed/AI suites, `PYTHONMALLOC=debug` | **1,984 passed; 12 skipped; 4 expected deprecation warnings** |
| Differential against matched upstream source build | **2,418 cases + 7 API contracts; zero mismatches** ([report](compatibility/results/v2-source.json)) |
| Differential against official PyPI orjson 3.13.0 wheel | **2,418 cases + 7 API contracts; zero mismatches** ([report](compatibility/results/v2-published.json)) |
| Rust + C parser AddressSanitizer build | **1,972 passed; 12 skipped; 4 expected warnings; no ASan errors** |
| Property coverage | Four deterministic Hypothesis properties, 1,000 examples each; recursive JSON, escaping, arbitrary bytes, invalid controls |
| Native edge coverage | 16/64-byte vector boundaries, UTF-8/escape lanes, arena threshold, output growth, buffer lifetime, GC reentry, callback snapshot references and release on errors |
| Pydantic and AI integration | 45 tests, including actual offline agent resume, conversation/deferred-tool state, binary/retry history, streamed final validation, custom callbacks and warning filters |
| Quality/dependencies | Rust formatting, Ruff lint/format, diff whitespace and 43-package dependency check passed |

The 12 skips are the opt-in huge-buffer resource test, eight Python 3.15-only
cases, one upstream NumPy skip, and two opposite-support bytearray/memoryview
cases. The native memory tests run in the normal allocator suite.

ASan uses Rust nightly-2026-10-01 with `-Zsanitizer=address
-Zexternal-clangrt`, Homebrew LLVM 21 C instrumentation, and the matching Rust
ASan runtime through `scripts/check_asan.py`. The Python interpreter itself is
not instrumented. The 12 upstream RSS-growth checks are excluded from ASan
because allocator quarantine intentionally retains memory; leak detection is
disabled. They pass in the normal release/debug-allocator suite. These checks
are not a native fuzzing or ThreadSanitizer certification.

## Artifact and measurement status

Release wheel: `orjson-3.13.0+pydantic.2-cp313-cp313-macosx_11_0_arm64.whl`.
The final artifact digest and additional CI/benchmark results are recorded
when qualification completes. This is an alpha, not a PyPI publication.

The process-isolated pyperf suite measures 26 native cases and 12 typed/control
cases. It records raw worker samples, fixture and native hashes, Python and
Pydantic versions. The manual performance workflow compares both matched
source and official published-wheel baselines on Linux ARM64 and x86-64,
in both run orders on a pinned CPU. Passing the workflow checks comparability,
not a speed threshold. Laptop trial results were noisy, including substantial
movement in unchanged Pydantic controls; they do not establish universal gains.

Cross-platform qualification for this implementation is being run separately
from the historical baseline results below. Current native/typed validation
covers the stated environments, not every application consuming orjson.

---

# Historical .1 baseline evidence

The following records describe the original, unoptimized baseline only.

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

Local verification covers one macOS ARM64 / Python 3.13 environment.
[Cross-platform CI passed all five jobs](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45407937853)
for code commit `6f73c85af32731e427f80c18afebd5984a3050c0`:

- Ubuntu 24.04 / Python 3.10: native build and upstream tests.
- Ubuntu 24.04 / Python 3.13 and 3.14: wheel build, upstream and integration
  tests, lint and formatting.
- macOS 15 / Python 3.13: the same full checks.
- Windows Server 2025 / Python 3.13: the same full checks, using upstream's
  `PYO3_USE_RAW_DYLIB=0` import-library setting.

The initial Windows attempt failed at linking because that setting was missing
from the new workflow. The correction changed build configuration only.
Broader upstream wheel/platform/version support remains a release gate.

Temporary baseline and clean-install environments, Cargo target output,
intermediate source/wheel archives and test/lint caches are removed with
`scripts/clean.py`. The final wheel, usable `.venv`, source checkout, and compact
JSON evidence are retained. Reproduce with `bash scripts/build.sh`.
