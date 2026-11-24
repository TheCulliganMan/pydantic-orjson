# Version .3 performance evidence with UV

These measurements belong to `orjson 3.13.0+pydantic.3`, exact commit
[`5db2adfe38696aeb658e3f68900227fa80b3948e`](https://github.com/TheCulliganMan/pydantic-orjson/commit/5db2adfe38696aeb658e3f68900227fa80b3948e),
from [successful workflow run 45426539830](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45426539830)
on November 24, 2026. All four jobs completed. There are targeted gains,
regressions and large unresolved changes between run orders. This record does
**not** establish a universal speedup or pass a broad performance acceptance gate.

**The measured wheels were local Linux builds on Ubuntu 26.04 with regular
CPython 3.13.18.** Their tags are `cp313-cp313-linux_aarch64` and
`cp313-cp313-linux_x86_64`. This verifies the UV benchmark workflow; it does not
measure no-GIL throughput, other Python versions or the separate portable
manylinux release-wheel pipeline. Later commits sharing the `.3` distribution
version need their own artifact identity and qualification.

## Baselines, build and method

- **Published:** the binary-only PyPI `orjson==3.13.0` wheel. The UV download log,
  installed wheel metadata and native-extension digest are retained as its
  provenance receipt. UV does not emit a pip-style installation report; this
  receipt does not claim an independently retained digest of the wheel archive.
- **Source:** commit `e56965ebcfdc1905318da14d37b8b07990130109`, distribution
  `3.13.0+pydantic.1`, retaining the recorded upstream native engine. The source
  baseline and candidate use the same stable compiler, release settings and
  Python dependency lock from the measured checkout. Published wheels may have
  different compiler/SIMD settings.
- UV **0.13.9** prepares both environments from `uv.lock` with the `native` and
  `integration` groups. `uv build --wheel --no-sources` invokes the pinned
  maturin **1.16.0** backend with `maturin.build-args=--locked --strip` and installs
  each exact wheel into its selected environment. The
  [measured workflow](https://github.com/TheCulliganMan/pydantic-orjson/blob/5db2adfe38696aeb658e3f68900227fa80b3948e/.github/workflows/performance.yml)
  records the complete commands.
- Each job runs baseline → candidate → candidate → baseline on one selected CPU.
  Each report has four worker processes, four values per worker, two warmups
  and a 70 ms minimum-time target: **16 timed values per case**, plus calibration
  and warmup records. Worker processes run serially.
- Published comparisons cover all **26 native cases**. Source comparisons add
  **12 typed controls**, for 38 cases. The typed implementation forwards to public
  TypeAdapter APIs; these cases measure wrapper overhead and unchanged-engine
  controls, not a new typed serialization engine.
- All four pairs passed **2,425 differential cases plus seven API contracts with
  zero mismatches**, and metadata/fixture comparison checks passed in both orders.
  Correctness and comparability checks do not establish stable timing.

Versions were UV-managed CPython 3.13.18, compiled with **Clang 23.1.3**;
Pydantic 2.14.4; pydantic-core 2.50.5; pyperf 2.11.0; and rustc 1.99.0
(LLVM 23.1.1). Linux reported 7.0.0-1020-azure / glibc 2.43. Dependency snapshots,
build logs, Python build settings and fixture hashes are retained.

| Pair | Recorded CPU | Allowed logical CPUs | Core representatives | Selected CPU |
| --- | --- | ---: | ---: | ---: |
| ARM64 published | Model not captured | 4 | 4 | 3 |
| ARM64 source | Model not captured | 4 | 4 | 3 |
| x86-64 published | AMD EPYC 7763 64-Core Processor | 4 | 2 | 2 |
| x86-64 source | AMD EPYC 9V74 80-Core Processor | 4 | 2 | 2 |

The x86-64 jobs used different CPU models. Compare baseline and candidate within
each pair; do not attribute differences between jobs only to the baseline type.
The candidate native-extension SHA-256 values were:

- ARM64: `b881b8d3f3bedd5a3d17550c31cf6d4a436bf58916571c97ceb71ec28917749e`
- x86-64: `02df2978575400aa293fbe0142e8cdfd60a14b1666224c868176c1405a81507c`

These native digests match the corresponding [pre-UV .3 builds](../v3/README.md).
The Python distribution and runner hardware differ, so that identity does not
make timing differences across workflow runs attributable solely to UV.

## Results and limitations

Against the published wheel, 64-byte decoding measured **1.338–1.341x on ARM64**
and **1.363–1.387x on x86-64** across both orders. ARM64 escaped-text encoding
measured **1.846–1.856x**, and the dense-escape fixture **8.553–8.575x**. These are
specific inputs, not general serialization gains. The records fixture using
FastAPI's option flags measured **1.088–1.089x on ARM64** and **1.090–1.091x on
x86-64**; it measures serialization with those flags, not HTTP throughput.

Regressions remain. Published ARM64 Unicode decoding measured **0.952–0.953x**,
about 5% higher latency. Published x86-64 escaped-text encoding measured
**0.877–0.882x** (about 13–14% higher latency), float decoding **0.917–0.919x**
(about 9% higher latency), and dense-escape decoding **0.959–0.961x** (about 4%
higher latency). x86-64 record decoding and sorted-record encoding were also
slower in both orders. Against matched source, x86-64 Unicode encoding measured
**0.845x → 0.672x**, roughly 18–49% higher latency, and integer-array encoding
**0.941–0.952x**. These are limitations of this evidence, not acceptable results
to omit from a speed claim.

Large order-dependent results remain unresolved. Published ARM64 integer-array
encoding changes **10.044x → 0.534x**, while source integer encoding changes
**1.025x → 9.479x**. Published float encoding changes **1.085x → 2.678x**;
source float encoding changes **0.963x → 0.402x**. Source ARM64 float decoding is
slower in both orders at **0.512x → 0.654x**. On published x86-64, escaped-text
decoding changes **1.280x → 0.974x**, and 321-byte decoding **1.488x → 1.192x**.
Do not average these effects away, select the favorable order, or assume a cause
from this run alone. Raw values and all original warnings remain available.

Every job emitted pyperf stability warnings, including insufficient samples for
its 1% variation criterion. A successful CI job establishes that the build and
comparison checks completed; it is not a speed acceptance gate. Profiling,
controlled-runner repetition and measurement of the intended release artifacts
remain necessary before broader claims.

## Complete native median ratios

Ratios are **baseline median / candidate median**: above 1 favors the candidate;
below 1 means higher candidate latency. `Forward / reverse` corresponds to
baseline → candidate and candidate → baseline. These descriptive median ratios
are distinct from pyperf's retained mean-based significance analysis. No native
case is omitted.

### Published upstream wheel

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `dumps.event` | 1.000 / 1.005 | 1.088 / 1.089 |
| `loads.event` | 1.176 / 1.170 | 1.173 / 1.172 |
| `dumps.records` | 1.022 / 1.018 | 0.995 / 0.996 |
| `loads.records` | 1.029 / 1.017 | 0.979 / 0.970 |
| `dumps.ascii_text` | 1.115 / 1.129 | 1.055 / 1.059 |
| `loads.ascii_text` | 1.100 / 1.114 | 0.994 / 0.997 |
| `dumps.unicode_text` | 1.124 / 1.117 | 1.027 / 1.027 |
| `loads.unicode_text` | 0.952 / 0.953 | 0.984 / 1.003 |
| `dumps.escaped_text` | 1.856 / 1.846 | 0.882 / 0.877 |
| `loads.escaped_text` | 1.063 / 1.066 | 1.280 / 0.974 |
| `dumps.dense_escapes` | 8.553 / 8.575 | 1.002 / 1.001 |
| `loads.dense_escapes` | 1.031 / 1.031 | 0.959 / 0.961 |
| `dumps.numbers` | 10.044 / 0.534 | 0.992 / 1.002 |
| `loads.numbers` | 1.029 / 1.039 | 0.991 / 0.983 |
| `dumps.floats` | 1.085 / 2.678 | 0.988 / 0.988 |
| `loads.floats` | 1.033 / 1.042 | 0.919 / 0.917 |
| `dumps.datetimes` | 1.025 / 1.031 | 1.005 / 1.018 |
| `loads.datetimes` | 1.051 / 1.061 | 1.068 / 1.034 |
| `dumps.records_fastapi` | 1.088 / 1.089 | 1.091 / 1.090 |
| `dumps.records_sorted` | 1.038 / 1.034 | 0.979 / 0.964 |
| `dumps.records_pretty` | 1.004 / 1.005 | 1.002 / 1.000 |
| `loads.bytes_64` | 1.338 / 1.341 | 1.387 / 1.363 |
| `loads.bytes_256` | 1.269 / 1.272 | 1.226 / 1.239 |
| `loads.bytes_321` | 1.240 / 1.263 | 1.488 / 1.192 |
| `loads.bytes_322` | 1.040 / 1.029 | 0.984 / 0.982 |
| `loads.bytes_512` | 1.055 / 1.055 | 1.018 / 1.003 |

### Matched stable source build

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `dumps.event` | 1.016 / 1.014 | 1.027 / 1.024 |
| `loads.event` | 1.203 / 1.208 | 1.197 / 1.199 |
| `dumps.records` | 0.990 / 0.974 | 1.033 / 0.992 |
| `loads.records` | 1.009 / 1.013 | 0.983 / 1.016 |
| `dumps.ascii_text` | 5.774 / 5.780 | 0.994 / 1.012 |
| `loads.ascii_text` | 1.003 / 0.995 | 0.994 / 0.990 |
| `dumps.unicode_text` | 6.204 / 6.269 | 0.845 / 0.672 |
| `loads.unicode_text` | 0.995 / 1.000 | 0.989 / 0.998 |
| `dumps.escaped_text` | 3.602 / 3.546 | 1.002 / 1.006 |
| `loads.escaped_text` | 1.007 / 0.999 | 1.013 / 1.009 |
| `dumps.dense_escapes` | 0.990 / 1.021 | 0.992 / 0.992 |
| `loads.dense_escapes` | 0.990 / 0.999 | 1.000 / 0.971 |
| `dumps.numbers` | 1.025 / 9.479 | 0.941 / 0.952 |
| `loads.numbers` | 0.996 / 1.000 | 0.981 / 1.005 |
| `dumps.floats` | 0.963 / 0.402 | 1.000 / 0.996 |
| `loads.floats` | 0.512 / 0.654 | 1.011 / 1.004 |
| `dumps.datetimes` | 0.988 / 0.987 | 0.972 / 0.979 |
| `loads.datetimes` | 1.007 / 1.004 | 1.001 / 1.022 |
| `dumps.records_fastapi` | 1.065 / 1.070 | 1.065 / 1.060 |
| `dumps.records_sorted` | 0.987 / 0.990 | 0.998 / 0.988 |
| `dumps.records_pretty` | 0.988 / 0.987 | 1.013 / 0.988 |
| `loads.bytes_64` | 1.375 / 1.382 | 1.314 / 1.313 |
| `loads.bytes_256` | 1.263 / 1.274 | 1.199 / 1.170 |
| `loads.bytes_321` | 1.243 / 1.223 | 1.162 / 1.150 |
| `loads.bytes_322` | 1.020 / 1.031 | 1.003 / 1.005 |
| `loads.bytes_512` | 0.998 / 0.997 | 1.014 / 0.987 |

### Typed controls in source comparisons

Both sides use the same Pydantic engine. Differences do not establish a new
typed-core optimization.

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `typed.adapter.dumps_small` | 1.009 / 1.003 | 0.984 / 1.005 |
| `typed.adapter.loads_small` | 1.006 / 0.977 | 1.003 / 1.016 |
| `typed.codec.dumps_small` | 0.989 / 1.003 | 0.998 / 1.046 |
| `typed.codec.loads_small` | 0.991 / 1.005 | 1.063 / 0.991 |
| `typed.codec.dumps_quiet_small` | 0.997 / 0.994 | 1.015 / 1.015 |
| `typed.adapter.dumps_quiet_small` | 0.987 / 1.003 | 1.016 / 1.000 |
| `typed.adapter.dumps_batch` | 1.004 / 1.005 | 1.008 / 0.991 |
| `typed.adapter.loads_batch` | 0.989 / 1.007 | 0.994 / 0.999 |
| `typed.codec.dumps_batch` | 1.000 / 1.016 | 1.010 / 0.998 |
| `typed.codec.loads_batch` | 1.007 / 0.997 | 0.989 / 0.992 |
| `typed.codec.dumps_quiet_batch` | 1.012 / 0.991 | 0.990 / 1.009 |
| `typed.adapter.dumps_quiet_batch` | 1.005 / 0.988 | 0.996 / 0.995 |

## Retained evidence

| Pair | Forward comparison | Reverse comparison | Warning counts: baseline / candidate / candidate-reverse / baseline-reverse |
| --- | --- | --- | --- |
| [arm64-published](arm64-published/) | [comparison](arm64-published/comparison.txt) | [reverse](arm64-published/comparison-reverse.txt) | 15 / 12 / 15 / 10 |
| [arm64-source](arm64-source/) | [comparison](arm64-source/comparison.txt) | [reverse](arm64-source/comparison-reverse.txt) | 19 / 28 / 23 / 25 |
| [x86_64-published](x86_64-published/) | [comparison](x86_64-published/comparison.txt) | [reverse](x86_64-published/comparison-reverse.txt) | 18 / 17 / 14 / 15 |
| [x86_64-source](x86_64-source/) | [comparison](x86_64-source/comparison.txt) | [reverse](x86_64-source/comparison-reverse.txt) | 32 / 33 / 28 / 24 |

The archive retains **80 evidence files**, including 16 complete pyperf reports
(`*.json.gz`), all measurement logs, eight comparison reports, build/dependency
records and differential results. All timing values, warmups and calibration
records are unchanged. Only `hostname` and `python_executable` were removed from
pyperf metadata; public CI configuration paths remain. Gzip has a fixed timestamp.
[manifest.json](manifest.json) records original artifact/file names and hashes,
sanitized JSON hashes and retained-file hashes. All retained hashes and sanitized
reports were checked against the download, and all eight comparisons were rerun
successfully from the archived data.

To inspect from the repository root using the current UV environment:

```sh
gzip -dc benchmarks/results/v3-uv/arm64-published/baseline.json.gz > /tmp/orjson-v3-uv-baseline.json
gzip -dc benchmarks/results/v3-uv/arm64-published/candidate.json.gz > /tmp/orjson-v3-uv-candidate.json
uv run --no-sync python benchmarks/compare_pyperf.py /tmp/orjson-v3-uv-baseline.json /tmp/orjson-v3-uv-candidate.json --native-only
```

Original comparisons retain pyperf's geometric-mean row; this report does not
promote it as an overall speed claim. The earlier failed setup run
`45426040453` produced no benchmarks and is not qualification evidence. The
separate [3.14t local diagnostic](../threaded-314t.json) measures no-GIL behavior
on different hardware; see [benchmark guidance](../../README.md#free-threaded-performance-qualification)
for its scope and limitations.
