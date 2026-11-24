# Pydantic orjson implementation plan

Status: free-threaded implementation and qualification, November 24, 2026.
Version `.2` introduced the native and integration changes; `.3` adds the
free-threaded CPython port and replacement-wheel matrix. This document separates
implemented work from the remaining qualification needed for
a production compatibility and speed claim. See [validation](VALIDATION.md) for
actual build, test and measurement results.

## UV workflow and repository ownership

This is an independent personal GitHub repository, retaining orjson's source
history and licenses. Publishing means commits and tested artifacts in
`TheCulliganMan/pydantic-orjson`; no upstream pull request is part of the work.
Upstream remains a fetch-only source of provenance and future comparisons.

All current Python environment, dependency, build and execution commands use
UV 0.13.9+. `uv.lock` and the explicit `native`/`integration` dependency groups
replace the old flat development requirements file. `dev` includes both groups;
no groups are installed by default. Experimental 3.13t uses the mutually
exclusive `native313t` group with compatible published native-test packages;
current Pydantic/AI qualification on free-threaded Python begins at 3.14t.
`uv sync --locked --no-install-project` prepares the selected dependencies, `uv build --wheel --no-sources` invokes the
pinned maturin backend, and `uv pip install` installs the exact built wheel.
Run checks with `uv run --no-sync` to preserve that installed artifact. Alternate
environments require `UV_PROJECT_ENVIRONMENT` on each command; `--python` alone
does not select the project environment. Rust/C compilation still requires the native toolchain; `uv_build` cannot compile this
extension. Qualification must check the UV lock, clean sync, isolated wheel
build, installed-wheel tests and all maintained workflows. Historical evidence
retains its original toolchain records without implying migration completion.

## Free-threaded implementation and qualification

The target is actual no-GIL execution on CPython 3.13t, 3.14t and 3.15t, alongside
regular CPython 3.10–3.15. A `t` wheel that enables the GIL on import does not
meet that target. Runtime checks verify the interpreter configuration and
`sys._is_gil_enabled()` before and after import; concurrency tests explicitly
use `PYTHON_GIL=0`.

The port uses owned shallow snapshots of dict/list entries acquired within
CPython critical sections, then serializes outside the lock so user callbacks
can run. Mutable bytearray/memoryview JSON input is copied with the exporter
held alive, and decode-error documents retain their contents. Affected object
headers, allocation, string-cache and capsule access use CPython's C API paths.
Nested containers are snapshotted when visited; there is no claim that the
whole graph reflects one instant. Callers own application-level consistency.

Memoryview aliases and external native writers need independent coordination.
The buffer export pins storage, but writes through a memoryview alias can bypass
the exporter object's critical section. Callers must synchronize these writes
with decoding, including the initial copy. Shared NumPy arrays must remain
read-only during encoding or use a lock shared by every writer
and serializer, including resize operations. Python container critical sections
do not lock NumPy's storage or an arbitrary native exporter. See
[NumPy thread safety](https://numpy.org/doc/stable/reference/thread_safety.html).

Python 3.13t is experimental. PyO3 0.29 no longer officially supports that
free-threaded ABI, so only the 3.13t build path bypasses its version check with
`UNSAFE_PYO3_SKIP_VERSION_CHECK=1`. All other ABIs keep normal checks, and 3.13t
must pass build, import and full concurrency/compatibility qualification.
Callers must synchronize class/type renaming
and metadata mutation with codec calls. Its type-name setter lacks the
stop-the-world protection added in 3.14; exact type names in serialization
errors remain part of compatibility. See the [concurrency contract](compatibility/README.md#free-threaded-builds-and-concurrency)
for source references and the limits of container snapshots.

The manual wheel workflow contains 45 combinations across Linux x86-64/ARM64,
macOS Intel/ARM64 and Windows x86-64, with separate regular/free-threaded/all
selectors. Each successful job retains a wheel, digest, dependency snapshot and
runtime/test evidence. Linux builds target glibc 2.39+. The release gate is
completed build, install, native/property and concurrency checks in every cell,
plus applicable integration checks on regular Python and 3.14t/3.15t. Current
Pydantic-core/AI dependencies are not qualified on 3.13t; configuration alone
is not completion. Record actual outcomes in `VALIDATION.md` and retain failures until corrected or explicitly
removed from the supported matrix.

## Native and integration implementation from `.2`

- Stable ARM64 builds scan unescaped string prefixes in bounded 64-byte NEON
  blocks, then 16-byte blocks; escaped blocks and tails retain scalar handling.
  Nightly generic-SIMD builds retain their existing path.
- Decoding documents up to 321 UTF-8 bytes uses a 4 KiB aligned stack arena.
  Larger inputs use the existing heap arena, in a separate call frame.
- Unsorted `OPT_NON_STR_KEYS` encoding avoids a second vector allocation.
  Converted keys and retained value references survive default callbacks;
  sorted duplicate-key ordering keeps the existing sorting representation.
- Escape and boolean/null token writes explicitly permit unaligned addresses.
- Reusable Pydantic codecs preserve JSON validation semantics, options and
  extension hooks. AI helpers now persist both message histories and full
  conversations with the official adapters.
- Added differential/property tests, vector and parser boundary coverage,
  callback/reference tests, offline AI agent persistence/resume and streaming
  checks, an AddressSanitizer launcher, and process-isolated benchmark tooling.
- CI covers native and integration checks across additional Python versions,
  with separate matched-source and published-wheel performance comparisons.

The benchmark suite measures each operation separately. Compiler SIMD flags in
the published upstream wheel can differ from a stable source build; both are
necessary comparisons. A faster local source build alone does not establish an
improvement over the wheel users currently install.

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
identify this build with distribution version `3.13.0+pydantic.3`, source SHA,
and artifact digest. Local versions must be pinned in lockfiles; an ordinary
upgrade from PyPI can replace this build. Publishing on GitHub does not grant
ownership of the upstream PyPI name. Public PyPI publication is not part of
this implementation.

## Architecture

1. **Compatibility engine:** keep the existing native API and specialize only
   bounded internal encode/decode paths. No Pydantic imports, model detection or
   new option flags are added to ordinary `dumps` and `loads`.
2. **Typed API:** `orjson.pydantic.Codec(type_or_adapter)` holds one reusable
   `TypeAdapter`. `dumps` delegates to public `dump_json`; `loads` delegates to
   public `validate_json`. Direct-core forwarding experiments were rejected
   because custom callbacks and mutable models can change warning origins and
   filtering even without replacing the adapter's compiled schema. Callers can
   supply an adapter with their own namespace and configuration. Each codec owns its adapter; there is no global type cache.
3. **AI boundary:** `orjson.pydantic_ai.dump_messages` and `load_messages`
   use Pydantic AI's `ModelMessagesTypeAdapter`; `dump_conversation` and
   `load_conversation` use `ConversationTypeAdapter`. They support persistence
   at an explicit application boundary. They do not replace provider transports,
   output validation, retry logic, or every internal JSON operation.
4. **Typed optimization boundary:** retain Pydantic's engine and observable
   extension behavior. Removing public forwarding frames can change warning
   origins and instrumentation, even when returned values match. Any future
   shortcut must qualify these effects as well as bytes and validation errors.

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

| Consumer | Contract | Implementation evidence / remaining work |
| --- | --- | --- |
| Existing Python imports | Existing API and native symbols unchanged | Full upstream tests, installed-wheel smoke test, differential corpus |
| FastAPI `ORJSONResponse` | Non-string keys and NumPy option combination; status, headers and response filtering | Real TestClient tests; current FastAPI deprecates this response class |
| FastAPI default typed responses | Pydantic validation/serialization behavior unchanged | Test separately; replacing orjson cannot accelerate a path that does not call it |
| Pydantic v2 | Aliases, defaults/exclusions, serializers, validators, strict JSON semantics, context and errors | Reusable Codec with callback, warning, rebuild and plugin checks; broaden version/schema qualification before stable release |
| Pydantic AI | Official message schema, discriminator tags, tools, timestamps and validation | Offline agent persistence/resume, streaming completion, binary/retry messages and full conversation state tested; qualify provider-specific applications |
| Other frameworks | Same module/distribution identity, signatures, options, error contract | Add real Litestar, Django integrations, HTTPX serializers and task/cache clients selected from downstream usage |
| Packaging | Single file owner, same dependency identity, reproducible wheels | 45-cell replacement-wheel workflow; see validation for completed jobs and remaining platform coverage |
| Free-threaded CPython | No automatic GIL enabling; safe concurrent object ownership and input lifetimes | Native concurrency tests on 3.13t/3.14t/3.15t; current optional integrations target 3.14t/3.15t; each platform must pass before qualification |

“Anywhere orjson is used” is the release goal, not a claim established by a
few framework tests. Maintain a published supported-version matrix and allow
downstream fixtures to become permanent regression tests. Pydantic v1 remains
an existing-orjson consumer; the new typed API targets v2. Current optional
AI/FastAPI test dependencies require Python 3.11+, while the native library
continues to target upstream's Python 3.10+ range. Free-threaded variants begin
with Python 3.13; there are no 3.10t–3.12t builds.

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
| M0: baseline (completed in `.1`) | Upstream clone/history, release wheel, typed/AI helpers, tests, benchmark harness, public plan | Local verification recorded; no native speed claim |
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
The original lightweight harness remains a smoke baseline. The new pyperf
suite provides isolated workers, metadata checks and reversible run ordering;
shared CI still does not substitute for dedicated production qualification.

## Correctness and maintenance measures

- Preserve the complete upstream suite. Add differential tests for successful
  bytes/values and exception type/message/position, every option and meaningful
  combination, defaults and recursive callbacks, integer bounds, floats,
  UTF-8, cycles/depth, temporal types, NumPy and `Fragment`.
- Maintain the added Hypothesis valid/invalid inputs, sanitizer/debug allocator
  checks and callback reference tests. Extend native fuzzing and leak checks;
  the sanitizer run does not establish leak freedom or exhaustive input
  coverage. Never relax malformed-input handling for speed.
- Typed coverage must include `RootModel`, unions/discriminators, recursive
  models, dataclasses, generics, extras, computed fields, custom types,
  aliases, exclusions, serialization failures, context and strict errors.
- AI coverage must include tool calls/results, retries, usage metadata,
  binary/multimodal payloads, unknown tags, streaming completion and state
  beyond message history. Full conversation helpers require a Pydantic AI
  version exposing `ConversationTypeAdapter`; retain official schema ownership.
- Rebase/merge upstream regularly, record its SHA, rerun the differential
  suite, and keep native changes small. Preserve upstream attribution and
  per-file licenses, including MPL source distribution obligations.
- Retain only the installed working environment, final wheel and compact
  evidence reports locally. `scripts/clean.py` removes known rough outputs;
  source code and committed benchmark evidence are retained. This also removes
  temporary qualification environments unless explicitly retained with
  `--preserve-env`. The build script preserves its selected UV environment.

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
versions are captured in `uv.lock` and `VALIDATION.md`. Historical evidence
retains the dependency snapshots used for its measured artifacts.
