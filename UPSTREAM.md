# Upstream provenance

- Source: https://github.com/ijl/orjson
- Base commit: `bd00937c5c46ab20eb5d7fe1cfc034b906c4578f`
- Base version: `3.13.0` (2026-10-07)
- Cloned: 2026-11-24
- Fork repository: https://github.com/TheCulliganMan/pydantic-orjson

Git history and upstream tests are preserved. The initial fork does not modify
the Rust engine or the top-level Python API. The original README follows the
fork introduction in README.md. Upstream license files and per-file notices
are retained; this is an independent project, not an official Pydantic,
Pydantic AI, FastAPI, or orjson release.

The native engine reports `orjson.__version__ == '3.13.0'`. The replacement
distribution reports `importlib.metadata.version('orjson') ==
'3.13.0+pydantic.1'`. The local suffix identifies this experimental integration
build without changing the upstream version API. Preserve this distinction
in bug reports and lockfiles. The Cargo package continues to describe the
unmodified upstream engine.

Existing upstream workflows remain available via manual dispatch. A smaller
fork CI workflow runs on push and pull requests. No registry publication or
release-upload workflow is enabled automatically.

Windows source builds must set `PYO3_USE_RAW_DYLIB=0`, matching upstream's
Windows workflow. orjson calls private CPython symbols that require the full
Python import library. This is also described by the
[PyO3 build guide](https://pyo3.rs/main/building-and-distribution.html#the-pyo3_use_raw_dylib-environment-variable).
The fork CI includes this setting; no native code change is required.
