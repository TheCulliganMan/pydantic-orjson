# Performance evidence

The initial fork retains upstream's native encoder and decoder. Its optional
`Codec` delegates to Pydantic's existing `TypeAdapter`; it is not a new faster
JSON engine. No performance improvement is claimed by this scaffold.

## Local reproducible check

Build upstream and the candidate with the same release compiler, flags, Python,
and dependency versions in separate environments. Do not compare an upstream
debug build with a release candidate, or a downloaded wheel with a locally
tuned build. From the repository root, run the environments sequentially:

```sh
.venv-baseline/bin/python benchmarks/run.py --label upstream-matched --output benchmarks/results/upstream-matched.json
.venv/bin/python benchmarks/run.py --label candidate-matched --output benchmarks/results/candidate-matched.json
.venv/bin/python benchmarks/compare.py benchmarks/results/upstream-matched.json benchmarks/results/candidate-matched.json
```

These runs use the same ten cases and ordering seed. Measure the optional Codec
separately, because adding cases changes the randomized order and workload:

```sh
.venv/bin/python benchmarks/run.py --label candidate-codec --include-codec --output benchmarks/results/candidate-codec.json
```

The twelve-case Codec report is a separate diagnostic and cannot be compared
against a ten-case baseline with `compare.py`.

The runner needs `orjson` and Pydantic v2. `--include-codec` additionally requires
the candidate wheel. It checks outputs before and after measurement, reuses a
compiled adapter, autoranges and warms each case, randomizes case ordering with
a recorded seed, and records eleven samples per case by default. Each timed
batch targets 50 ms; calibration does not guarantee every sample reaches that
duration. Garbage collection is disabled only inside timed
batches, and its prior state is restored afterward. Python loop/call overhead is
included, not estimated and subtracted. Reports retain raw timings, medians,
median absolute deviation (MAD), fixture sizes and SHA-256 hashes, imported
extension hash, Python/compiler/platform/dependency versions, and source state.
The reported Rust version is the toolchain available at measurement time; the
build log must separately establish which compiler and flags built each wheel.

Cases cover a small Unicode event, 64 nested records, 1,024 nested records, and a
128-item typed batch with datetimes. Typed encoding compares direct
`TypeAdapter.dump_json` with `model_dump(mode="json")` followed by
`orjson.dumps`. Typed decoding compares `TypeAdapter.validate_json` with
`orjson.loads` followed by `validate_python` on a fixed **non-strict** schema.
Both decode routes must produce equal validated models. This equivalence is
specific to the fixture: JSON-mode and Python-mode validation are not generally
interchangeable, especially under strict validation. Candidate `Codec` cases
measure wrapper overhead against the same native Pydantic operations. No
validator bypass, `model_construct`, or change to schema behavior is timed as an
optimization.

`compare.py` rejects mismatched platforms, Python/Pydantic versions, settings
(including the ordering seed), case sets, and fixtures. A ratio above 1 means the measured
candidate median was lower for that case. It does not establish statistical
significance. Results from one laptop and one process are diagnostics; thermal
state, scheduler activity, power mode, allocator state, and execution order can
change them. Run baseline/candidate again in the reverse order before interpreting
small differences. Do not aggregate raw JSON and typed validation into one
"faster JSON" number.

## Release evidence still required

Use `pyperf` process isolation and calibration on dedicated x86-64 and ARM64
runners. For example, after installing `pyperf` into both measurement environments:

```sh
.venv-baseline/bin/python -m pyperf timeit --rigorous -s 'import orjson; data={"items": list(range(1000))}' 'orjson.dumps(data)' -o upstream-dumps.json
.venv/bin/python -m pyperf timeit --rigorous -s 'import orjson; data={"items": list(range(1000))}' 'orjson.dumps(data)' -o candidate-dumps.json
.venv/bin/python -m pyperf compare_to upstream-dumps.json candidate-dumps.json --table
```

See the official [runner options](https://pyperf.readthedocs.io/en/latest/runner.html)
and [comparison commands](https://pyperf.readthedocs.io/en/latest/cli.html#pyperf-compare-to)
for process counts, calibration, metadata, and significance reporting.

That command is an example of the process-isolation mechanism, not a sufficient
workload. Port every checked fixture and include upstream `bench/` data, deep
nesting, numeric and Unicode distributions, options, NumPy, custom callbacks,
Pydantic serializers/validators, AI histories, concurrent server requests, and
large inputs. Measure allocations, peak RSS, import/startup time, latency tails,
and FastAPI throughput with response validation enabled. Report cold schema
construction separately from warm reuse. Keep complete JSON artifacts, build
logs, exact source/dependency locks, hardware and power settings, and significance
analysis. A suggested optimization gate is a repeatable >=10% gain in its named
target workload with <=3% regression in raw JSON geometric-mean latency and no
material per-case regression, subject to agreeing thresholds before tuning.
Compatibility gates must pass independently of performance gates.
