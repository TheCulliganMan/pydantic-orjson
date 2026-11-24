# Upstream provenance

- Source: https://github.com/ijl/orjson
- Base commit: `bd00937c5c46ab20eb5d7fe1cfc034b906c4578f`
- Base version: `3.13.0` (2026-10-07)
- Cloned: 2026-11-24
- Independent personal repository: https://github.com/TheCulliganMan/pydantic-orjson

This is a standalone GitHub repository (`isFork: false`, no parent repository),
with upstream source history retained for attribution and comparison. Work is
committed to the personal repository; no upstream pull request was opened.
The `upstream` remote is retained for fetching, with pushes disabled.

Git history and the upstream test suite are preserved. The initial `.1`
integration baseline retained the Rust engine unchanged. The `.2` implementation adds
bounded ARM64 string encoding, a small-document parser arena, non-string-key
snapshot improvements, and explicitly unaligned token writes. The `.3` port
adds free-threaded CPython object ownership, mutable-container snapshots,
mutable-input copies and public C API access for affected object layouts.
The top-level Python API remains unchanged. The upstream API reference follows
the project introduction in README.md, with active build/install/test commands
adapted to UV. Upstream license files and per-file notices are retained; this is an independent project, not an official Pydantic,
Pydantic AI, FastAPI, or orjson release.

The native engine reports `orjson.__version__ == '3.13.0'`. The replacement
distribution reports `importlib.metadata.version('orjson') ==
'3.13.0+pydantic.3'`. The local suffix identifies this experimental integration
build without changing the upstream version API. Preserve this distinction
in bug reports and lockfiles. The Cargo version remains the upstream API
version; it does not identify the fork patch set. Use the distribution version
and source SHA for that purpose.

Three maintained UV workflows handle compatibility, performance comparison and
replacement wheels. Superseded upstream build workflows have been removed.
Compatibility CI runs on push and pull requests to this personal repository.
No registry publication or release-upload workflow is enabled automatically. The manual replacement-wheel
workflow targets regular CPython 3.10–3.15 and free-threaded 3.13t–3.15t across
five platform/architecture pairs. It uploads each wheel only after that job's
runtime and test checks pass. This configuration is not evidence that all
45 combinations have completed successfully; consult `VALIDATION.md`.

The free-threaded port is a fork change beyond the inherited opt-in build path.
Its runtime contract requires `sys._is_gil_enabled()` to remain false after
import, including on Python 3.13t. The wheel's `t` ABI tag alone is insufficient
to establish that contract. Python 3.13t is experimental and carried by this
project despite the PyO3 0.29 support guard; only that build path sets
`UNSAFE_PYO3_SKIP_VERSION_CHECK=1`. The standard build script supplies the
version-specific setting. All other ABIs retain PyO3's normal version check.
The 3.13t path qualifies native orjson with the separate `native313t` test group;
current Pydantic-core/AI integration targets 3.14t and 3.15t, since those current
dependencies do not supply supported 3.13t builds. Standard Python/Pydantic
support remains unchanged.

Windows source builds must set `PYO3_USE_RAW_DYLIB=0`, matching upstream's
Windows workflow. orjson calls private CPython symbols that require the full
Python import library. This is also described by the
[PyO3 build guide](https://pyo3.rs/main/building-and-distribution.html#the-pyo3_use_raw_dylib-environment-variable).
The project CI includes this setting. UV invokes the pinned maturin backend
for the compiled extension; the developer-facing build command is `uv build`.

Current Python environment/build commands use UV 0.13.9+ and `uv.lock`.
Historical validation and benchmark artifacts retain the commands/tool versions
actually used for those older measurements. The UV migration's completed
checks are reported separately in `VALIDATION.md`.
