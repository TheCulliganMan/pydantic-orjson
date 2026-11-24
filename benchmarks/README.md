# Performance evidence

Version `.2` adds native string encoding, small-document parsing and dictionary
snapshot changes; `.3` adds the free-threaded port. Their performance must be
measured against both a matched upstream source build and the published wheel. The published wheel
can use different compiler/SIMD settings; it is the relevant baseline for users
replacing a downloaded wheel. A matched source build isolates our code changes.

The optional `Codec` reuses Pydantic's public `TypeAdapter`. It preserves custom
callbacks, instrumentation, warning filters and rebuild behavior. Typed cases
measure wrapper overhead and provide unchanged-engine controls; they are not a
new typed encoder or validator. See [validation](../VALIDATION.md) for measured
results and limitations rather than inferring gains from these design changes.

## Recorded results

- [Version `.2`, commit `66c0d035`](results/v2/README.md): regular CPython CI
  comparisons against matched source and the published wheel, with complete
  forward/reverse results and regressions.
- [Version `.3`, commit `655e430e`](results/v3/README.md): regular CPython 3.13.18
  comparisons before the UV migration. This is evidence for that exact source
  and build, not the final UV artifact or no-GIL throughput. All four jobs
  completed; timing instability and regressions prevent a universal speed claim.
- [Local 3.14t threaded diagnostic](results/threaded-314t.json): a separate
  Apple M5 no-GIL measurement, interpreted below. It is not an upstream-wheel
  comparison and does not qualify every free-threaded platform.

## Process-isolated suite

Build baseline and candidate release wheels in separate environments with the
same Python, dependencies, compiler and flags. Install the published
`orjson==3.13.0` wheel in a third environment with the same Python dependencies.
Current commands use UV 0.13.9+ and the project lock. Prepare each environment
with the same selected Python and groups using `UV_PROJECT_ENVIRONMENT=<env>
uv sync --locked --no-install-project --group native --group integration`, then
install its exact wheel with `uv pip install --python <env>/bin/python`.
Keep `UV_PROJECT_ENVIRONMENT` explicit on every baseline/published `uv run`;
`--python` alone does not move execution out of the default project environment.
The current candidate is built with `uv build --wheel --no-sources`; historical
source baselines retain their source/toolchain identity. The maintained workflow
contains the complete preparation recipe. From the repository root:

```sh
UV_PROJECT_ENVIRONMENT=.venv-baseline uv run --no-sync python benchmarks/pyperf_suite.py -p 4 -n 4 -w 2 --min-time 0.07 -o /tmp/source-baseline.json
uv run --no-sync python benchmarks/pyperf_suite.py -p 4 -n 4 -w 2 --min-time 0.07 -o /tmp/candidate.json
uv run --no-sync python benchmarks/compare_pyperf.py /tmp/source-baseline.json /tmp/candidate.json
UV_PROJECT_ENVIRONMENT=.venv-published uv run --no-sync python benchmarks/pyperf_suite.py --group dumps.,loads. -p 4 -n 4 -w 2 --min-time 0.07 -o /tmp/published.json
uv run --no-sync python benchmarks/compare_pyperf.py /tmp/published.json /tmp/candidate.json --native-only
```

Run each pair again in reverse order, using new output paths. Use the same
selected workload set for a pair when generating final comparison evidence.
The command above reuses the full candidate report for a convenient native-only
comparison; the comparator filters both sides explicitly. Published upstream
has no `Codec`, so its native comparison must exclude typed cases on both sides.

`pyperf_suite.py` uses separate worker processes, calibration, warmups and
`timeit` expressions around prepared inputs. It checks outputs before and after
timing and records the suite hash, fixture hash and byte size, native extension
hash, distribution and Pydantic versions, plus pyperf's environment metadata.
Cases include compact records, FastAPI option combinations, sorted and pretty
output, ASCII/Unicode/escaped strings, dense escapes, integer/float arrays,
datetimes, and parser sizes around the stack-arena boundary. Typed cases compare
small and batch schemas with direct Pydantic calls, including explicit warning
options. Adapter/schema construction is outside the timed warm operations.

`compare_pyperf.py` rejects different selected cases, fixture/suite hashes and
recorded Python/dependency/platform metadata. It prints per-case medians and
runs pyperf's statistical comparison while retaining each measurement run.
A ratio above 1 means baseline latency divided by candidate latency favored the
candidate. Passing metadata validation does not establish benchmark stability,
representative coverage or a release gate. Inspect pyperf warnings, unchanged
Pydantic controls, both run orders and all regressions before making a claim.

The manual [performance workflow](../.github/workflows/performance.yml) builds
and compares both baselines on Linux x86-64 and ARM64, and retains complete
reports as workflow artifacts. Shared runners and heterogeneous laptop cores
can still produce noise. Do not combine typed validation and raw JSON into one
"faster JSON" number, or present a favorable individual fixture as a universal
speedup. Preserve raw results when preparing a compact report; remove local
usernames, hostnames and checkout paths from metadata before public publication.

See the official [runner options](https://pyperf.readthedocs.io/en/latest/runner.html)
and [comparison commands](https://pyperf.readthedocs.io/en/latest/cli.html#pyperf-compare-to)
for process counts, calibration, metadata and significance reporting.

## Free-threaded performance qualification

Measure the regular and free-threaded ABIs separately. The `.3` container
snapshots and mutable-input copies have costs that the historical `.2` regular
CPython results do not measure. Record the wheel ABI, Python build,
`sysconfig.get_config_var("Py_GIL_DISABLED")` and `sys._is_gil_enabled()` before
and after loading every dependency. A `t` wheel with an enabled GIL is not a
no-GIL measurement. Current typed-codec no-GIL comparisons target 3.14t/3.15t.
Experimental 3.13t uses `native313t` and has native-only qualification; do not
install unsupported current Pydantic/AI dependencies to manufacture a typed
benchmark on that runtime.

The current pyperf suite measures single-thread latency. Concurrency regression
tests establish correctness within their tested scope; they do not establish
parallel speedup. For scaling measurements, use the same immutable or
worker-owned inputs at 1, 2, 4 and 8 threads, collect total throughput and latency
distributions, and include the synchronization cost for workloads that share
mutable application state. Keep NumPy arrays read-only or coordinate writers;
unsynchronized mutation changes the work and is not a valid benchmark input.
The 45-cell wheel workflow is a build/runtime compatibility matrix, not a
45-platform performance certification.

The retained [3.14t diagnostic](results/threaded-314t.json) reports CPython 3.14.3
on Apple M5 / ARM64, Darwin 27.2.0, with ten logical CPUs. The GIL was disabled
before import, after import and after measurement. Its source commit was not
recorded; native-extension and harness SHA-256 hashes identify the measured
artifacts. Do not assume it is the same binary as the Linux `.3` CI report or a
later UV build.

Each case performed a fixed total of 20,000 calls, split among 1, 2, 4 or 8
threads, with five repeats and randomized order in one process. Inputs were
shared and never mutated. Timing includes loops, output destruction, scheduling
and barriers, but excludes thread creation; results are batch wall times, not
per-operation latency distributions. Correctness was checked outside timing.
Median throughput ratios against the same artifact's one-thread run were:

| Case | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: |
| Encode small event | 0.626x | 0.839x | 0.445x |
| Encode 128 records | 0.960x | 0.907x | 0.940x |
| Decode small event | 1.204x | 2.905x | 1.509x |
| Decode 128 records | 2.046x | 3.752x | 5.503x |

Decoding scaled in these fixtures, while neither shared-input encoding fixture
improved with more threads. The small-event cases also showed substantial
variation; for example, two-thread event encoding ranged from 13.7 to 81.5 ms
across its five batches. Preserve both outcomes rather than advertising the
largest decode ratio as general scaling. This one-process laptop diagnostic
needs repeated isolated-process runs, varied ownership patterns and controlled
hardware before broader throughput conclusions.

## Historical lightweight diagnostic

The original single-process harness and `.1` reports remain available for
provenance. The commands below use current UV execution; dated reports retain
the toolchain commands that actually produced them. From the repository root,
run matched environments sequentially:

```sh
UV_PROJECT_ENVIRONMENT=.venv-baseline uv run --no-sync python benchmarks/run.py --label upstream-matched --output benchmarks/results/upstream-matched.json
uv run --no-sync python benchmarks/run.py --label candidate-matched --output benchmarks/results/candidate-matched.json
uv run --no-sync python benchmarks/compare.py benchmarks/results/upstream-matched.json benchmarks/results/candidate-matched.json
```

These runs use the same ten cases and ordering seed. Measure the optional Codec
separately, because adding cases changes the randomized order and workload:

```sh
uv run --no-sync python benchmarks/run.py --label candidate-codec --include-codec --output benchmarks/results/candidate-codec.json
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

Extend the process-isolated suite with upstream `bench/` datasets, deep nesting,
NumPy, custom callbacks, AI histories, concurrent server requests and large
inputs. Measure allocations, peak RSS, import/startup time, latency tails and
FastAPI throughput with response validation enabled. Report cold schema
construction separately from warm reuse. Keep complete JSON artifacts, build
logs, exact source/dependency locks, hardware and power settings, and significance
analysis. A suggested optimization gate is a repeatable >=10% gain in its named
target workload with <=3% regression in raw JSON geometric-mean latency and no
material per-case regression, subject to agreeing thresholds before tuning.
Compatibility gates must pass independently of performance gates.
