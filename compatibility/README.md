# Drop-in compatibility

The distribution and import remain `orjson`. Changing only the repository name
to `pydantic-orjson` lets existing code and dependency requirements keep working.
Installing a separate distribution that also writes an `orjson` directory is
not an acceptable release strategy: package managers cannot safely track those
overlapping files. Replace the installed distribution through an explicit wheel
or pinned source requirement, then run the application's own test suite and the
package manager's dependency check.

## Executable checks

Install a built candidate wheel with the development dependencies, then run:

```sh
python -m pytest -q test compatibility integration_pydantic
python compatibility/differential.py \
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

FastAPI's current [`ORJSONResponse` implementation](https://github.com/fastapi/fastapi/blob/master/fastapi/responses.py)
imports `orjson` and passes `OPT_NON_STR_KEYS | OPT_SERIALIZE_NUMPY` to `dumps`.
That existing path uses the installed replacement automatically. Current
[FastAPI documentation](https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model)
also describes direct Pydantic serialization for response models and deprecates
`ORJSONResponse`. Replacing `orjson` does not intercept that independent path.
The tests exercise both routes; performance work must measure both rather than
attribute a framework result to a serializer the framework did not call.

Install `requirements-fork.txt` for the complete development checks, including
Hypothesis. Exact tested versions and completed platform coverage belong in the
validation report. Do not infer cross-platform certification from a local run.

## Native and typed regression coverage

The added native tests cover every escape class across vector boundaries,
UTF-8 boundaries, output-buffer growth, boolean/null alignment, parser arena
sizes around 321 bytes, invalid-input error positions, input-buffer lifetimes,
GC reentry, non-string-key callback snapshots and reference release on errors.
Hypothesis exercises recursive values, string escaping and arbitrary input
bytes alongside the preserved upstream suite and differential corpus.

Run `scripts/check_asan.py --help` for the instrumented-extension test launcher.
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
its hash and runtime evidence. Linux wheels target `manylinux_2_39`, requiring
glibc 2.39 or newer. Configured cells are not certified passing builds; completed
results belong in [validation](../VALIDATION.md).

For a local POSIX build, first run the regular development build to create
`.venv` and install its build tools. Then select a free-threaded interpreter:

```sh
uv venv --python 3.14t --allow-existing .venv-freethreaded
uv pip install --python .venv-freethreaded/bin/python -r requirements-fork.txt
CARGO_TARGET_DIR=.artifacts/freethreaded-target .venv/bin/maturin build --release --strip --locked --out dist/freethreaded -i .venv-freethreaded/bin/python
uv pip install --python .venv-freethreaded/bin/python --reinstall dist/freethreaded/orjson-3.13.0+pydantic.3-*.whl
.venv-freethreaded/bin/python -I -c 'import sys, sysconfig; assert sysconfig.get_config_var("Py_GIL_DISABLED"); assert not sys._is_gil_enabled(); import orjson; assert not sys._is_gil_enabled()'
PYTHON_GIL=0 PYTHONMALLOC=debug .venv-freethreaded/bin/python -m pytest -q test compatibility integration_pydantic
uv pip check --python .venv-freethreaded/bin/python
```

Use `3.13t` or `3.15t` in a separate qualification run. Wheel filenames must
carry the corresponding ABI (`cp313t`, `cp314t` or `cp315t`); a regular `cp314`
wheel cannot substitute for `cp314t`. After retaining results and the final
wheel, `.venv/bin/python scripts/clean.py` removes `.venv-freethreaded`, its
intermediate Cargo target under `.artifacts`, and test caches. It preserves
`dist/`, the regular `.venv`, source and committed evidence.

The concurrency contract includes these limits:

- Dict/list encoding acquires owned shallow snapshots inside CPython critical
  sections, then releases the container lock before invoking Python callbacks.
  Objects remain alive while serialized. Nested containers are visited and
  snapshotted separately, so concurrent application updates can produce a
  document containing values from different moments. Lock application state
  when a consistent whole-document snapshot is required.
- Mutable JSON inputs are copied before parsing, and decode errors retain their
  document data. A buffer export pins storage; it does not lock every alias.
  Direct bytearray updates use the bytearray's critical section, but writes
  through memoryview aliases can bypass that lock. Callers must synchronize
  concurrent memoryview-alias writes and all external native buffer writers
  with `loads`, including the initial copy. An immutable input or a caller-made
  snapshot taken under the writer's lock avoids this shared-buffer boundary.
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
error-document ownership. `test/test_freethreaded_objects.py` adds cross-thread
Fragment lifetimes, shared Unicode caches, decoded hashes and output-buffer
allocation/error paths. Runtime state is asserted during concurrency checks;
passing with an enabled GIL does not satisfy these tests. These bounded tests
support the recorded scope, not arbitrary native exporters or all possible
concurrent application behavior.
