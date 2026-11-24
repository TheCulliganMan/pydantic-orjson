# Fork changelog

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
