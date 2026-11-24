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
python -m pytest -q compatibility/test_drop_in.py
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

| Consumer contract | Initial verification | Release gate |
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

The initial checks require `pytest`, `fastapi`, `httpx`, `pydantic>=2`, and `numpy`.
Exact tested versions and supported platform coverage belong in the validation
report. Do not infer cross-platform certification from a local passing run.
