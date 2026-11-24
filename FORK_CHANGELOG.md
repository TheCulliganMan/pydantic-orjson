# Fork changelog

## 3.13.0+pydantic.3 — free-threaded qualification

- Add free-threaded CPython 3.13t, 3.14t and 3.15t build targets with no-GIL
  runtime checks; remove the inherited environment-variable build gate.
- Snapshot mutable Python containers under their critical sections and retain
  keys/values while serializing after the lock is released. Snapshots are
  shallow and do not promise atomic consistency across a nested object graph.
- Copy mutable JSON inputs before parsing, preserving owned document data for
  decode errors. Concurrent memoryview-alias writes and external native buffer
  writers still require caller synchronization.
- Use CPython allocation and public C API paths for affected free-threaded
  object layouts, Fragment ownership, string caches and NumPy capsules.
- Add concurrent native-call, callback, shared-container mutation, mutable-input,
  cross-thread Fragment lifetime and output-buffer regression tests.
- Add a manual 45-cell replacement-wheel matrix for regular Python 3.10–3.15
  and free-threaded 3.13t–3.15t on Linux x86-64/ARM64, macOS Intel/ARM64 and
  Windows x86-64. Successful jobs retain wheels, hashes and runtime/test evidence.
- Clean intermediate free-threaded environments and Cargo output with the
  existing cleanup command; retain final wheels and published evidence.

Qualification is in progress. Python 3.13t is experimental and requires caller
synchronization for concurrent class/type metadata changes. The configured
matrix does not imply that every build has passed. See [validation](VALIDATION.md) for completed checks. NumPy
arrays must remain read-only during encoding or use caller-managed locking,
consistent with [NumPy's thread-safety guidance](https://numpy.org/doc/stable/reference/thread_safety.html).

## 3.13.0+pydantic.2 — 2026-11-24

- Add bounded 64-byte and 16-byte NEON string encoding for stable ARM64 builds,
  with the existing scalar escape handling for escaped blocks and tails.
- Avoid the parser's heap arena allocation for documents up to 321 UTF-8 bytes;
  larger documents retain the existing allocation path.
- Remove a redundant borrowed-key vector for unsorted `OPT_NON_STR_KEYS`
  dictionaries and retain snapshot values through callbacks and error paths.
- Use explicitly unaligned stores for escape sequences and boolean/null tokens.
- Extend optional Pydantic AI integration to full conversation persistence,
  including deferred tools, and exercise real offline agent resume and streaming.
- Broaden Pydantic semantic checks for custom callbacks, serializers, warnings,
  plugins, adapter overrides and rebuilds.
- Add vector/arena boundary tests, property tests, callback reference checks,
  an AddressSanitizer launcher, process-isolated benchmarks and comparison CI.
- Expand the Python/platform CI matrix and clean intermediate benchmark and
  sanitizer builds with the existing cleanup command.

This remains an alpha. See [validation](VALIDATION.md) for the tested artifact,
compatibility evidence and performance scope; these changes do not establish
universal downstream coverage or a speed increase for every workload.

## 3.13.0+pydantic.1 — 2026-11-24

- Preserve orjson 3.13.0 native code, imports and existing API.
- Add optional reusable Pydantic codecs and Pydantic AI message persistence.
- Add framework compatibility tests, an upstream differential corpus, and
  correctness-checked benchmark tooling.
- Document the compatibility contract, phased performance research, release
  gates, source provenance and reproducible build/cleanup procedure.

This is an alpha integration baseline. Higher throughput and universal
downstream compatibility remain qualification targets, not release claims.
