# Pydantic orjson implementation plan

Status: buildable integration baseline, November 24, 2026. This document describes
work required to earn a production compatibility and speed claim. The initial
fork has no native performance changes and does not claim to beat upstream.

## Product contract

An application already using orjson must keep its imports and calls. Preserve
`import orjson`, the distribution name `orjson`, the native `orjson.orjson`
extension, bytes output, positional/keyword behavior, constants, `Fragment`,
errors, options, typing information, and CPython support. Do not make Pydantic
mandatory or automatically start accepting models in ordinary `dumps`.

The GitHub project is named `pydantic-orjson`; its replacement wheel is named
`orjson`. A separate distribution named `pydantic-orjson` exporting the same
package would not satisfy dependencies on `orjson` and would create overlapping
file ownership. Install exactly one provider using an explicit wheel/direct
source requirement. Retain upstream's engine version in `orjson.__version__`;
identify this build with distribution version `3.13.0+pydantic.1`, source SHA,
and artifact digest. Local versions must be pinned in lockfiles; an ordinary
upgrade from PyPI can replace this build. Publishing on GitHub does not grant
ownership of the upstream PyPI name. Public PyPI publication is not part of
this bootstrap.

## Architecture

1. **Compatibility engine:** retain upstream Rust encode/decode paths. No
   additional type checks, imports, dispatch, or flags on the normal hot path.
2. **Typed API:** `orjson.pydantic.Codec(type_or_adapter)` holds one reusable
   `TypeAdapter`. `dumps` delegates to `dump_json`; `loads` delegates to
   `validate_json`. Callers can supply an adapter with their own namespace and
   configuration. Each codec owns its adapter; there is no global type cache.
3. **AI boundary:** `orjson.pydantic_ai.dump_messages` and `load_messages`
   use Pydantic AI's `ModelMessagesTypeAdapter`. They support persistence at
   an explicit application boundary. They do not replace provider transports,
   output validation, retry logic, or every internal JSON operation.
4. **Future optimizations:** measured, guarded native specializations behind
   the typed API, with the Pydantic implementation as semantic fallback.

Pydantic already implements validation and serialization in Rust. Replacing
`validate_json` with `orjson.loads` followed by `validate_python` allocates an
intermediate object tree and changes strict-mode behavior for dates, UUIDs,
and tuples. It is not a valid general optimization. Likewise, reading a
model's `__dict__` bypasses serializers, exclusions, and schema-directed
subclass filtering. Neither shortcut is permitted.

Typed APIs retain Pydantic options and errors; they do not pretend to implement
orjson's option bitmask. Raw `loads` stays complete-document JSON only. Partial
typed validation is explicit and experimental, with final complete validation
required before treating a streamed output as complete.

## Ecosystem compatibility

| Consumer | Contract | Bootstrap evidence / remaining work |
| --- | --- | --- |
| Existing Python imports | Existing API and native symbols unchanged | Full upstream tests, installed-wheel smoke test, differential corpus |
| FastAPI `ORJSONResponse` | Non-string keys and NumPy option combination; status, headers and response filtering | Real TestClient tests; current FastAPI deprecates this response class |
| FastAPI default typed responses | Pydantic validation/serialization behavior unchanged | Test separately; replacing orjson cannot accelerate a path that does not call it |
| Pydantic v2 | Aliases, defaults/exclusions, serializers, validators, strict JSON semantics, context and errors | Optional Codec baseline; broaden version and schema matrix before stable release |
| Pydantic AI | Official message schema, discriminator tags, tools, timestamps and validation | Offline synthetic message round trips; add streaming, multimodal, retry and full conversation persistence cases |
| Other frameworks | Same module/distribution identity, signatures, options, error contract | Add real Litestar, Django integrations, HTTPX serializers and task/cache clients selected from downstream usage |
| Packaging | Single file owner, same dependency identity, reproducible wheels | Local macOS ARM64 wheel built; cross-platform CI configured, results must be checked |

“Anywhere orjson is used” is the release goal, not a claim established by a
few framework tests. Maintain a published supported-version matrix and allow
downstream fixtures to become permanent regression tests. Pydantic v1 remains
an existing-orjson consumer; the new typed API targets v2. Current optional
AI/FastAPI test dependencies require Python 3.11+, while the native library
continues to target upstream's Python 3.10+ range.

## Performance research, in order

**A. Establish equivalent work.** Build upstream and fork from the recorded
source on the same machine/compiler/options. Measure compact/pretty/sorted
encoding and decoding separately: small API objects, nested records, long
ASCII and escaped Unicode strings, integer/float arrays, datetimes, UUIDs,
NumPy, invalid input, and large payloads. Separate cold import/schema creation
from warm operations. Capture correctness, byte sizes, time distributions,
memory, and versions. Include Pydantic's native methods as competitors.

**B. Profile the native engine before changing it.** Inspect
`src/serialize/writer/`, `src/serialize/obtype.rs`, `src/deserialize/backend/`,
`src/deserialize/pyobject.rs`, and `src/deserialize/cache.rs`. Use allocation
and CPU profiles to select buffer growth, Python object allocation, key-cache
behavior, string escaping, and SIMD dispatch experiments. Test ARM64 and
x86-64 independently. Keep one hypothesis per branch and delete failed build
outputs after recording measurements. No claim that these areas necessarily
contain a win over already optimized upstream code.

**C. Typed encoding experiment.** Explore compiled schema dispatch for a small
subset of plain records/lists/scalars. Avoid Python dict materialization only
when all semantics are proven. Unsupported serializers, aliases/exclusions,
computed fields, subclass policies, recursive schemas, mutable/rebuilt models,
or contexts must use the reference implementation. Cache lifecycle and schema
invalidation are part of correctness. Reject a backend that cannot determine
eligibility before producing output.

**D. Typed decoding experiment.** First measure reuse and batch APIs around
Pydantic's native parser. A fused orjson parser plus validator requires a
supported Pydantic-core interface or a deliberately maintained dependency
fork. There is no assumed stable cross-extension Rust ABI. Prototype a
small supported schema subset only after agreeing the semantic contract;
preserve JSON-mode validation, errors, recursion limits, and validators.
Do not skip validation to produce an apparent benchmark improvement.

**E. Application workloads.** Measure FastAPI response latency/throughput
under controlled concurrency, with serialization time isolated and total
request time also reported. Measure AI message persistence/replay and growing
partial output snapshots without network model calls. Compare custom typed
serialization against default framework paths, not only against Python
intermediate-dict baselines. Repeated full-prefix parsing can be quadratic;
incremental parsing would be a separate feature and API.

## Milestones and acceptance gates

| Milestone | Deliverable | Exit condition |
| --- | --- | --- |
| M0: baseline (this commit) | Upstream clone/history, release wheel, typed/AI helpers, tests, benchmark harness, public plan | Local verification recorded; no native speed claim |
| M1: compatibility qualification | Differential/property tests, downstream matrix, wheel/install/upgrade/rollback tests | Full upstream suite passes; zero unexplained output/error diffs; all declared OS/Python versions green |
| M2: benchmark qualification | pyperf runs, CPU/allocation profiles, reference datasets and raw artifacts | Independent-process repeatability on ARM64 and x86-64; noise quantified; benchmark inputs audited |
| M3: first encoding win | One profiled native or typed specialization with fallback | Target >=10% median gain on declared representative encode suite; no statistically credible >3% regression on protected cases |
| M4: first decoding win | Separately profiled untyped or typed decoding change | Same gate for decoding; complete semantic parity; invalid/adversarial cases and memory bounds checked |
| M5: release candidate | CI wheels, source archive, provenance/SBOM, migration/rollback guide | M1-M4 evidence reviewed; downstream applications and installs exercised; public support matrix |

Thresholds are proposed acceptance criteria, not results. Reject cherry-picked
single-fixture wins and compare against both upstream orjson and direct
Pydantic where applicable. Prefer paired runs, multiple worker processes,
pyperf stability checks and confidence intervals; retain full results and
outliers. Do not enforce noisy microsecond timing thresholds on shared CI.
The included lightweight harness is a smoke baseline, not release evidence.

## Correctness and maintenance measures

- Preserve the complete upstream suite. Add differential tests for successful
  bytes/values and exception type/message/position, every option and meaningful
  combination, defaults and recursive callbacks, integer bounds, floats,
  UTF-8, cycles/depth, temporal types, NumPy and `Fragment`.
- Add Hypothesis-generated valid/invalid inputs, JSONTestSuite, native fuzzing,
  sanitizer/debug allocator runs, and reference-count/leak checks before
  shipping native changes. Never relax malformed-input handling for speed.
- Typed coverage must include `RootModel`, unions/discriminators, recursive
  models, dataclasses, generics, extras, computed fields, custom types,
  aliases, exclusions, serialization failures, context and strict errors.
- AI coverage must include tool calls/results, retries, usage metadata,
  binary/multimodal payloads, unknown tags, streaming completion and state
  beyond message history. Version-gate `ConversationTypeAdapter` if adopted.
- Rebase/merge upstream regularly, record its SHA, rerun the differential
  suite, and keep native changes small. Preserve upstream attribution and
  per-file licenses, including MPL source distribution obligations.
- Retain only the installed working environment, final wheel and compact
  evidence reports locally. `scripts/clean.py` removes known rough outputs;
  source code and committed benchmark evidence are retained.

## Primary references

- [orjson source and API](https://github.com/ijl/orjson/tree/bd00937c5c46ab20eb5d7fe1cfc034b906c4578f)
- [Pydantic architecture](https://pydantic.dev/docs/validation/latest/internals/architecture/)
- [Pydantic JSON semantics](https://pydantic.dev/docs/validation/latest/concepts/json/)
- [TypeAdapter](https://pydantic.dev/docs/validation/latest/api/pydantic/type_adapter/)
- [Serialization](https://pydantic.dev/docs/validation/latest/concepts/serialization/)
- [Performance](https://pydantic.dev/docs/validation/latest/concepts/performance/)
- [Partial validation limits](https://pydantic.dev/docs/validation/latest/concepts/experimental/)
- [Pydantic AI message history](https://pydantic.dev/docs/ai/core-concepts/message-history/)
- [Pydantic AI persistence](https://pydantic.dev/docs/ai/core-concepts/persistence/)
- [FastAPI responses](https://fastapi.tiangolo.com/advanced/custom-response/)

Documentation links track current upstream guidance. Exact locally tested
versions are captured in `requirements-fork.txt` and `VALIDATION.md`.
