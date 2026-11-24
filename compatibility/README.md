# Drop-in compatibility

The distribution and import remain `orjson`. Changing only the repository name
to `pydantic-orjson` lets existing code and dependency requirements keep working.
Installing a separate distribution that also writes an `orjson` directory is
not an acceptable release strategy: package managers cannot safely track those
overlapping files. Replace the installed distribution through an explicit wheel
or pinned source requirement, then run the application's own test suite and the
package manager's dependency check.

## Executable checks

Use UV 0.13.9+ to sync the locked `native` and `integration` groups, build the
wheel and install that exact artifact as described in [build and use](../README.md#build-and-use).
Then run without syncing over the installed wheel. The full integration example
below is for regular Python or 3.14t/3.15t; the separate native-only 3.13t path is
explained under [free-threaded builds](#free-threaded-builds-and-concurrency):

```sh
uv run --no-sync pytest -q test compatibility integration_pydantic
uv run --no-sync python compatibility/differential.py \
  --baseline /path/to/upstream-venv/bin/python \
  --candidate /path/to/candidate-venv/bin/python \
  --output /tmp/orjson-compatibility.json
```

The differential harness launches both interpreters with `-I`, preventing the
checkout or `PYTHONPATH` from silently replacing either installed package. It
compares exact encoded bytes, decoded types and dict order, floating-point
representations, option constants, function signatures, exception classes and
messages, and JSON error positions. Its deterministic generated inputs supplement
the upstream malformed-JSON fixtures and explicit callback, datetime, integer,
Unicode, recursion, and buffer cases. This bounded corpus is a regression check,
not proof for every possible input; run the complete upstream test suite as well.

| Consumer contract | Implemented verification | Release gate |
| --- | --- | --- |
| `import orjson` and `Requires-Dist: orjson` | Installed distribution identity, native function identity, no optional imports | Wheel install/upgrade/uninstall and dependency-resolution tests on each supported platform |
| Existing `dumps` / `loads` | Differential corpus and complete upstream tests | No unexplained byte, type, exception, flag, callback, or input-acceptance changes |
| FastAPI `ORJSONResponse` | Real TestClient route, NumPy arrays, non-string keys, headers, and observed call to candidate | Supported oldest/current FastAPI versions and dependency constraints |
| FastAPI response models | Alias, exclusion, field serializer, request validation, and error response checks | Preserve filtering and validation; benchmark the actual path used by that FastAPI version |
| Starlette custom JSON response | Existing subclass calling `orjson.dumps` | App-level checks without changing consumer code |
| Other orjson consumers | Native API unchanged; not individually certified | Add representative HTTP clients, logging, queues, and cache serializers before claiming tested ecosystem coverage |
| Pydantic / Pydantic AI | Additive opt-in API; core still rejects models by default | Separate semantic and performance contracts; no silent global monkeypatch |

## FastAPI integration boundary

In addition to current-framework CI, a [legacy installed-wheel comparison](results/legacy-fastapi.json)
checks FastAPI 0.99.1 with Pydantic 1.10.27 on Python 3.10.22 / macOS ARM64.
All 12 observation records match upstream, including five HTTP responses,
headers, native signatures/errors and absence of optional helper imports.
The standalone [probe](legacy_fastapi.py) runs in separate UV environments with
the same dependencies and different installed orjson wheels. It is outside the
regular pytest collection because that environment uses Pydantic 2.

FastAPI's current [`ORJSONResponse` implementation](https://github.com/fastapi/fastapi/blob/master/fastapi/responses.py)
imports `orjson` and passes `OPT_NON_STR_KEYS | OPT_SERIALIZE_NUMPY` to `dumps`.
That existing path uses the installed replacement automatically. Current
[FastAPI documentation](https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model)
also describes direct Pydantic serialization for response models and deprecates
`ORJSONResponse`. Replacing `orjson` does not intercept that independent path.
The tests exercise both routes; performance work must measure both rather than
attribute a framework result to a serializer the framework did not call.

`uv sync --locked --no-install-project --group native --group integration`
installs the complete applicable development dependencies, including Hypothesis.
`uv.lock` records versions and Python markers. Native/Pydantic checks support
regular Python 3.10+; AI/FastAPI integration requires 3.11+. For free-threaded
Python, current Pydantic/AI integration targets 3.14t/3.15t; 3.13t uses the
separate `native313t` group for native-only qualification. Exact tested versions
and completed platform coverage belong in the validation report. Do not infer cross-platform certification from a local run.

## Native and typed regression coverage

The added native tests cover every escape class across vector boundaries,
UTF-8 boundaries, output-buffer growth, boolean/null alignment, parser arena
sizes around 321 bytes, invalid-input error positions, input-buffer lifetimes,
GC reentry, non-string-key callback snapshots and reference release on errors.
Hypothesis exercises recursive values, string escaping and arbitrary input
bytes alongside the preserved upstream suite and differential corpus.

Run `uv run --no-sync python scripts/check_asan.py --help` for the
instrumented-extension test launcher.
Build both Rust and the C parser with AddressSanitizer and supply the matching
runtime. This is separate from a normal release build with `PYTHONMALLOC=debug`;
ASan allocator quarantine makes the upstream RSS-growth assertions unsuitable
for that instrumented run. The validation report records exactly which checks
ran and which were excluded.

Typed tests cover public `TypeAdapter` options and errors, custom serialization
and validation, warning origins/module filters, adapters overridden on an
instance or class, plugins and rebuilds. Encoding and decoding keep the public
adapter entry points so these observable behaviors remain active. AI tests use
the official message and conversation schemas, including binary/retry messages,
deferred tools, actual offline agent resume and final validation after streaming.
They require no live model calls or API credentials.


## Free-threaded builds and concurrency

Version `.3` targets free-threaded CPython 3.13t, 3.14t and 3.15t with the GIL
remaining disabled. The `t` identifies the interpreter ABI; runtime assertions
also check that importing orjson does not enable the GIL. This is distinct from
installing a `t` wheel that falls back to GIL-enabled execution. CPython documents
both the build flag and the runtime check in its
[free-threading guide](https://docs.python.org/3/howto/free-threading-python.html).

The [manual wheel workflow](../.github/workflows/wheels.yml) has `regular`,
`free-threaded` and `all` selectors. Its five platform targets are Linux
x86-64/ARM64, macOS Intel/ARM64 and Windows x86-64. Six regular Python versions
(3.10–3.15) plus three free-threaded versions produce 45 configured combinations.
Each job builds, installs and tests its exact wheel before uploading it with
its hash and runtime evidence. Linux wheels target `manylinux_2_17` through
Python 3.14 and `manylinux_2_28` for Python 3.15, with matching baseline-container
runtime checks. All 45 declared variants passed; see the
[per-wheel report](results/wheels-v3.json). Build details and scope are recorded
in [validation](../VALIDATION.md).

| Runtime | UV dependency groups | Qualification scope |
| --- | --- | --- |
| Regular CPython 3.10–3.15 | `native`, `integration` | Native and applicable typed/framework tests; current AI/FastAPI test stack requires 3.11+ |
| Experimental CPython 3.13t | `native313t` only | Native API, property and concurrency tests; no current Pydantic/AI integration qualification |
| CPython 3.14t–3.15t | `native`, `integration` | Native plus current Pydantic/AI/FastAPI integration targets; completed cells are recorded in validation |

The separate 3.13t group locks published compatible versions of its test
packages. Current Pydantic-core, NumPy and Hypothesis versions no longer
provide 3.13t wheels; unsupported dependency builds are not forced. Older
NumPy/Hypothesis packages in `native313t` provide native regression coverage.
This does not imply current optional Pydantic/AI support on 3.13t.

For a local free-threaded build, the script selects Python and preserves the
chosen UV environment after cleanup:

```sh
UV_PROJECT_ENVIRONMENT=.venv-freethreaded bash scripts/build.sh 3.14t
UV_PROJECT_ENVIRONMENT=.venv-freethreaded uv run --python 3.14t --no-sync python -I -c 'import sys, sysconfig; assert sysconfig.get_config_var("Py_GIL_DISABLED"); assert not sys._is_gil_enabled(); import orjson; assert not sys._is_gil_enabled()'
```

The manual POSIX equivalent keeps the same UV workflow:

```sh
UV_PROJECT_ENVIRONMENT=.venv-freethreaded uv sync --python 3.14t --locked --no-install-project --group native --group integration
UV_PROJECT_ENVIRONMENT=.venv-freethreaded CARGO_TARGET_DIR=.artifacts/freethreaded-target uv build --wheel --python 3.14t --no-sources --out-dir dist/freethreaded -C 'maturin.build-args=--locked --strip'
uv pip install --python .venv-freethreaded/bin/python --reinstall --no-deps dist/freethreaded/orjson-3.13.0+pydantic.3-cp314-cp314t-*.whl
PYTHON_GIL=0 PYTHONMALLOC=debug UV_PROJECT_ENVIRONMENT=.venv-freethreaded uv run --python 3.14t --no-sync pytest -q test compatibility integration_pydantic
uv pip check --python .venv-freethreaded/bin/python
```

For experimental 3.13t, use its own environment and native-only build path:

```sh
UV_PROJECT_ENVIRONMENT=.venv-313t bash scripts/build.sh 3.13t
UV_PROJECT_ENVIRONMENT=.venv-313t uv run --python 3.13t --no-sync python -I -c 'import sys; assert not sys._is_gil_enabled(); import orjson; assert not sys._is_gil_enabled()'
```

The script selects `native313t` with `--no-build` for test dependency sync.
Only the 3.13t extension build sets `UNSAFE_PYO3_SKIP_VERSION_CHECK=1`: current
PyO3 0.29 no longer officially supports that ABI, so this project carries
experimental compatibility. All other ABIs keep normal version checks.
A successful compilation alone does not qualify 3.13t.

For 3.15t use
`UV_PROJECT_ENVIRONMENT=.venv-freethreaded bash scripts/build.sh 3.15t`.
When invoking UV manually, set `UV_PROJECT_ENVIRONMENT` on **every** command
for an alternate project environment, and select the interpreter with `--python`
or a consistent `UV_PYTHON`. `uv run --no-sync --python <interpreter>` alone can
still use the default project `.venv`; it does not select the alternate environment.
If installing regular Python manually, use `uv python install 3.13`; the `+gil`
suffix is for subsequent discovery/selection such as `--python 3.13+gil`, not
for `uv python install`. The build script handles this distinction.

Wheel filenames must carry the corresponding ABI (`cp313t`, `cp314t` or
`cp315t`); a regular `cp314` wheel cannot substitute for `cp314t`. After retaining
results and the final wheel, clean while preserving the selected environment:

```sh
UV_PROJECT_ENVIRONMENT=.venv-freethreaded uv run --python 3.14t --no-sync python scripts/clean.py --preserve-env .venv-freethreaded
```

Use `.venv-313t` / `--python 3.13t` for that environment instead. Cleanup retains
the selected environment, `dist/`, the regular `.venv`, source and committed
evidence while removing known intermediate products.

The concurrency contract includes these limits:

- Dict/list encoding acquires owned shallow snapshots inside CPython critical
  sections, then releases the container lock before invoking Python callbacks.
  Objects remain alive while serialized. Nested containers are visited and
  snapshotted separately, so concurrent application updates can produce a
  document containing values from different moments. Lock application state
  when a consistent whole-document snapshot is required.
- Mutable JSON inputs are copied before parsing, and decode errors retain their
  document data. A buffer export pins storage; it does not lock every alias.
  On Python 3.14+, direct bytearray updates use its critical section, but writes
  through memoryview aliases can bypass that lock. Callers must synchronize
  concurrent memoryview-alias writes and all external native buffer writers
  with `loads`, including the initial copy. An immutable input or a caller-made
  snapshot taken under the writer's lock avoids this shared-buffer boundary.
- On Python 3.13t, callers must synchronize **all** mutable-input writers with
  `loads`, including direct bytearray updates and memoryview release or mutation.
  [CPython 3.13's bytearray assignment](https://github.com/python/cpython/blob/v3.13.18/Objects/bytearrayobject.c)
  does not acquire the exporter's object mutex. The fork serializes its own
  buffer-export acquisitions and releases because that version's bytearray and
  memoryview export counters are non-atomic. This protects concurrent calls to
  `loads`; it cannot make an unrelated writer participate in the same lock.
- Python 3.13t support is experimental. Callers must synchronize concurrent
  class/type renaming and metadata mutation with serialization and decoding.
  In particular, `type_set_name` in [CPython 3.13](https://github.com/python/cpython/blob/3.13/Objects/typeobject.c)
  replaces the stored name without the stop-the-world protection added to
  [CPython 3.14](https://github.com/python/cpython/blob/3.14/Objects/typeobject.c).
  The fork preserves exact type names in errors instead of replacing them with
  generic messages. Container snapshots do not make arbitrary mutable Python
  objects or concurrent class changes safe.
- Keep shared NumPy arrays read-only while serializing, or hold a lock used by
  every writer/resizer as well as the serializer. The fork does not add a mutex
  around NumPy storage. NumPy recommends read-only sharing or caller locking in
  its [thread-safety guidance](https://numpy.org/doc/stable/reference/thread_safety.html).

`compatibility/test_freethreading.py` checks default no-GIL import, parallel
native calls, callbacks, shared dict/list mutation, mutable-input copying and
error-document ownership. The mutable-input test uses a caller lock on 3.13t;
3.14+ also exercises bytearray writers without a caller lock. Separate tests
check concurrent export release and decoding through bounded, interleaved
garbage collections. `test/test_freethreaded_objects.py` adds cross-thread
Fragment lifetimes, shared Unicode caches, decoded hashes and output-buffer
allocation/error paths. Runtime state is asserted during concurrency checks;
passing with an enabled GIL does not satisfy these tests. These bounded tests
support the recorded scope, not arbitrary native exporters or all possible
concurrent application behavior.
