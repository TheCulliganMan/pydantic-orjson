# Project changelog

## 3.13.0+pydantic.4 — development candidate

- Bound numeric-array output reservations and specialize exact integer/float
  runs, retaining generic dispatch for mixed suffixes and all options/errors.
- Encode exact scalar primitives directly into finished bytes; reuse the
  existing numeric formatter for range, nonfinite and strict-integer behavior.
- Encode exact strings through shared escaping, using bounded stack storage
  through 37 UTF-8 bytes and reusing the validated UTF-8 for longer strings.
- Retain immutable exact-string keys instead of allocating a Rust string for
  each `OPT_NON_STR_KEYS` field; preserve converted keys, sorting and callbacks.
- Replace yyjson's general pool with an invocation-local bounded bump arena.
  Include both input copy and geometric tape growth in its capacity bound,
  fixing valid dense pretty arrays rejected by the inherited allocation bound.
  The separate stack frame now handles documents through 610 UTF-8 bytes.
- Decode exact null/boolean literals and small unescaped strings directly;
  widen ASCII runs within long mixed Unicode strings in fixed-size blocks.
  Avoid widening when a bounded prefix probe finds no complete ASCII block.
  On ARM, combine long-string UTF-8 character counting and width detection
  with bounded NEON loads and checked accumulator folding.
- Decode exact-float array prefixes with a specialized loop, resuming ordinary
  mixed/container traversal at the first different tape tag.
- Parse complete root integer tokens directly with checked integer conversion;
  overflow, whitespace and other numeric grammar retain the parser fallback.
- Batch clean x86 string prefixes in 64/128-byte blocks. Keep dense Unicode
  construction on the original scalar loop when ASCII widening cannot help.
- Guard fixed-size output writes after unbounded values and correct NumPy
  float64 array reservations; preserve buffer growth and callback behavior.
- Consume x86 string escape masks once per block, avoiding repeated scans
  for dense escaped strings.
- Add a primary three-engine benchmark with identical inputs and UTF-8 bytes
  output: Pydantic ORJSON, published ORJSON and stdlib json. Retain balanced
  orders, raw process samples, hashes, instability checks and an explicit
  all-cases-wins gate. Typed pipelines are distinguished from native parsing.

These are candidates pending full performance acceptance, not a claim of
universal speed superiority. See [benchmark methodology](benchmarks/README.md)
and the [earlier timing audit](benchmarks/FORENSICS.md).

## 3.13.0+pydantic.3 — free-threaded and UV qualification

- Manage Python versions, environments, locking, builds and test execution
  through UV 0.13.9+, with `uv.lock` and explicit native/integration groups.
  UV invokes the pinned maturin backend for Rust/C compilation.
- Keep this as an independent personal repository, retain upstream provenance
  and licenses, and disable pushes to the fetch-only upstream remote.
- Replace superseded upstream CI definitions with three maintained UV workflows;
  preserve historical validation and timing artifacts as records of older builds.

- Add free-threaded CPython 3.13t, 3.14t and 3.15t build targets with no-GIL
  runtime checks; remove the inherited environment-variable build gate.
  Experimental 3.13t is carried with a targeted PyO3 version-check override;
  all other ABIs keep the normal dependency version checks. Use the separate
  `native313t` group for native-only 3.13t qualification; current Pydantic/AI
  free-threaded integration targets begin at 3.14t.
- Snapshot mutable Python containers under their critical sections and retain
  keys/values while serializing after the lock is released. Snapshots are
  shallow and do not promise atomic consistency across a nested object graph.
- Copy mutable JSON inputs before parsing, preserving owned document data for
  decode errors. Concurrent memoryview-alias writes and external native buffer
  writers still require caller synchronization. On 3.13t this also includes
  direct bytearray writes and external buffer operations; the port serializes
  its own export-counter access.
- Anchor source-package include rules at the repository root, exclude rough
  outputs and test the UV source-archive-to-wheel rebuild in CI.
- Use CPython allocation and public C API paths for affected free-threaded
  object layouts, Fragment ownership, string caches and NumPy capsules.
- Add concurrent native-call, callback, shared-container mutation, mutable-input,
  cross-thread Fragment lifetime and output-buffer regression tests.
- Add a manual 45-cell replacement-wheel matrix for regular Python 3.10–3.15
  and free-threaded 3.13t–3.15t on Linux x86-64/ARM64, macOS Intel/ARM64 and
  Windows x86-64. Successful jobs retain wheels, hashes and runtime/test evidence.
- Build Linux wheels in pinned official manylinux images, audited for glibc
  2.17 through Python 3.14 and 2.28 for Python 3.15. Verify import, no-GIL state
  and threaded calls on that baseline before the full host test suite.
- Clean intermediate free-threaded environments and Cargo output with the
  existing cleanup command; retain final wheels and published evidence.

All 45 declared wheel variants passed build/runtime qualification at source
commit `ec6b336`, with 43 main-run jobs plus two same-source fallback jobs after
GitHub macOS runner capacity cancellations. The release includes checksums,
raw test/ABI/GIL evidence and the source archive. Broader performance gates
remain open; this is an alpha. Python 3.13t is experimental and requires caller
synchronization for concurrent class/type metadata changes. See
[validation](VALIDATION.md) for exact coverage. NumPy
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
