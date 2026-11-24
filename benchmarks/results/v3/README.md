# Version .3 performance evidence before the UV migration

These measurements belong to `orjson 3.13.0+pydantic.3`, exact commit
[`655e430ed9e2c6260df2362d6b586a55cd44f8d3`](https://github.com/TheCulliganMan/pydantic-orjson/commit/655e430ed9e2c6260df2362d6b586a55cd44f8d3),
from [successful workflow run 45421088810](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45421088810)
on November 24, 2026. All four comparison jobs completed. The measured artifact
has targeted gains, repeatable regressions and large unexplained variations in
some numeric cases. This is **not** a universal speed claim or a passing broad
performance acceptance gate.

**This run used regular CPython 3.13.18, before the UV migration.** It does not
measure no-GIL execution, the subsequent UV build workflow or later changes
sharing the `.3` distribution version. Source commit and native binary digests
identify the artifact; the version suffix alone is insufficient. Preserve this
record separately from final-UV or free-threaded qualification.

## Baselines and method

- **Published:** the actual binary-only PyPI `orjson==3.13.0` wheel. Its install
  receipt retains the official download URL and wheel digest.
- **Source:** commit `e56965ebcfdc1905318da14d37b8b07990130109`, distribution
  `3.13.0+pydantic.1`, retaining the recorded upstream native engine. Source
  baseline and candidate use the same stable compiler and release flags.
  Published upstream wheels can have different compiler/SIMD settings.
- Every pair measured baseline → candidate → candidate → baseline. Each report
  has four worker processes, four values per worker, two warmups and a 70 ms
  minimum-time target: 16 timed values per case plus calibration/warmup records.
  Workers run serially, pinned to the same selected CPU within each job.
- Published comparisons include all 26 native cases. Source comparisons also
  contain 12 typed controls, for 38 total. Public TypeAdapter forwarding remains
  the typed implementation; these are controls and wrapper measurements.
- Each pair passed report metadata/fixture checks and a differential corpus of
  **2,425 cases plus seven API contracts, with zero mismatches**. Correctness
  results do not establish timing stability.

The historical workflow used `actions/setup-python`, isolated Python virtual
environments, package installation from `requirements-fork.txt`, and direct
`maturin build --release --strip --locked`. These are records of this measured
build, not current setup instructions; current development uses UV. Versions
were CPython 3.13.18, Pydantic 2.14.4, pydantic-core 2.50.5, pyperf 2.11.0,
maturin 1.16.0 and rustc 1.99.0 (LLVM 23.1.1). Python was compiled with
GCC 15.2.0. Runners reported Linux 7.0.0-1020-azure / glibc 2.43 on Ubuntu 26.04.

| Pair | Recorded CPU | Allowed logical CPUs | Core representatives | Selected CPU |
| --- | --- | ---: | ---: | ---: |
| ARM64 published | Model not captured | 4 | 4 | 3 |
| ARM64 source | Model not captured | 4 | 4 | 3 |
| x86-64 published | AMD EPYC 9V74 80-Core Processor | 4 | 2 | 2 |
| x86-64 source | Intel Xeon Platinum 8573C | 4 | 2 | 2 |

The x86-64 source and published jobs ran on **different CPU models**. Compare
candidate and baseline within each pair; do not interpret differences between
those two jobs as the effect of changing baseline alone. The Intel job recorded
the `schedutil` governor. All build logs, dependency snapshots, CPU selection,
fixture hashes and native extension hashes are retained.

## Results and limitations

Against the published wheel, 64-byte decoding measured **1.365–1.426x on ARM64**
and **1.264–1.287x on x86-64** across the two orders. ARM64 escaped-text encoding
measured **1.834–1.855x**, and the dense-escape fixture **8.544–9.143x**. These are
specific string distributions, not general serialization speedups. The records
fixture using FastAPI's option flags measured **1.096–1.099x on ARM64** and
**1.021–1.112x on x86-64**; it measures native serialization, not HTTP throughput.

Regressions remain. Published ARM64 Unicode decoding measured **0.948–0.951x**,
about 5.1–5.5% higher latency. Published x86-64 dense-escape decoding measured
**0.877–0.888x** (about 12.6–14.0% higher latency), float decoding
**0.917–0.932x** (about 7.3–9.0% higher latency), escaped-text decoding
**0.956–0.962x**, and pretty-record encoding **0.958–0.963x**. Matched-source
x86-64 sorted-record encoding measured **0.945–0.957x**. Smaller differences
and every native fixture appear below rather than being discarded.

ARM64 numeric results require investigation. Source integer-array encoding
moves from **1.013x forward to 0.127x reverse**; published integer encoding moves
**0.596x → 1.009x**. Source float decoding is slower in both orders, at
**0.726x → 0.515x**, but the magnitude changes sharply. Published float encoding
moves **1.065x → 0.838x**, and float decoding **1.463x → 1.029x**. These large,
order-dependent effects are unresolved; they must not be averaged away or
presented using only the favorable run. No cause is established by this record.

All four jobs emitted pyperf stability warnings, including insufficient samples
for its 1% variation criterion. Original logs and mean-based significance
comparisons are retained. A green job means the build and comparability checks
completed, not that every case is stable or a speed acceptance gate passed.
Dedicated-runner repetition, profiling of regressions and final-artifact
measurement remain necessary before broader claims.

## Complete native median ratios

Ratios are **baseline median / candidate median**: above 1 favors the candidate;
below 1 means candidate latency is higher. `Forward / reverse` corresponds to
baseline → candidate and candidate → baseline. These descriptive median ratios
are distinct from pyperf's mean-based significance analysis. No native case is
omitted.

### Published upstream wheel

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `dumps.event` | 1.059 / 0.972 | 0.966 / 0.984 |
| `loads.event` | 1.117 / 1.157 | 1.115 / 1.099 |
| `dumps.records` | 1.027 / 1.018 | 0.978 / 0.971 |
| `loads.records` | 1.008 / 1.005 | 0.982 / 1.035 |
| `dumps.ascii_text` | 1.116 / 1.109 | 0.982 / 1.009 |
| `loads.ascii_text` | 1.094 / 1.091 | 1.011 / 1.018 |
| `dumps.unicode_text` | 1.132 / 1.118 | 1.023 / 1.041 |
| `loads.unicode_text` | 0.951 / 0.948 | 0.990 / 0.998 |
| `dumps.escaped_text` | 1.834 / 1.855 | 1.014 / 1.013 |
| `loads.escaped_text` | 1.065 / 1.072 | 0.956 / 0.962 |
| `dumps.dense_escapes` | 9.143 / 8.544 | 1.016 / 1.016 |
| `loads.dense_escapes` | 1.038 / 1.038 | 0.888 / 0.877 |
| `dumps.numbers` | 0.596 / 1.010 | 1.058 / 1.052 |
| `loads.numbers` | 1.026 / 1.027 | 0.976 / 0.972 |
| `dumps.floats` | 1.065 / 0.838 | 0.973 / 0.983 |
| `loads.floats` | 1.463 / 1.029 | 0.932 / 0.917 |
| `dumps.datetimes` | 1.009 / 1.005 | 1.063 / 1.031 |
| `loads.datetimes` | 1.037 / 1.036 | 1.072 / 1.042 |
| `dumps.records_fastapi` | 1.099 / 1.096 | 1.112 / 1.021 |
| `dumps.records_sorted` | 0.999 / 0.997 | 0.972 / 1.006 |
| `dumps.records_pretty` | 1.006 / 1.014 | 0.958 / 0.962 |
| `loads.bytes_64` | 1.365 / 1.426 | 1.264 / 1.287 |
| `loads.bytes_256` | 1.306 / 1.361 | 1.182 / 1.190 |
| `loads.bytes_321` | 1.276 / 1.274 | 1.108 / 1.135 |
| `loads.bytes_322` | 1.065 / 1.070 | 0.996 / 0.999 |
| `loads.bytes_512` | 1.068 / 1.091 | 1.033 / 1.020 |

### Matched stable source build

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `dumps.event` | 1.011 / 1.029 | 1.006 / 1.035 |
| `loads.event` | 1.188 / 1.161 | 1.250 / 1.160 |
| `dumps.records` | 0.988 / 0.979 | 0.984 / 0.980 |
| `loads.records` | 1.023 / 1.013 | 0.950 / 0.993 |
| `dumps.ascii_text` | 5.975 / 5.729 | 1.023 / 1.029 |
| `loads.ascii_text` | 1.004 / 1.003 | 1.002 / 1.005 |
| `dumps.unicode_text` | 6.330 / 6.233 | 1.018 / 1.026 |
| `loads.unicode_text` | 0.998 / 1.000 | 1.013 / 1.007 |
| `dumps.escaped_text` | 3.603 / 3.591 | 1.003 / 1.001 |
| `loads.escaped_text` | 1.002 / 0.997 | 1.007 / 1.003 |
| `dumps.dense_escapes` | 0.983 / 1.007 | 0.990 / 0.989 |
| `loads.dense_escapes` | 0.996 / 0.992 | 1.023 / 1.030 |
| `dumps.numbers` | 1.013 / 0.127 | 0.992 / 1.002 |
| `loads.numbers` | 0.998 / 1.002 | 0.984 / 0.979 |
| `dumps.floats` | 0.955 / 0.993 | 0.998 / 0.997 |
| `loads.floats` | 0.726 / 0.515 | 0.980 / 1.000 |
| `dumps.datetimes` | 0.992 / 0.987 | 1.034 / 1.029 |
| `loads.datetimes` | 1.000 / 0.994 | 0.994 / 0.975 |
| `dumps.records_fastapi` | 1.091 / 1.088 | 1.067 / 1.082 |
| `dumps.records_sorted` | 0.998 / 0.996 | 0.957 / 0.945 |
| `dumps.records_pretty` | 0.985 / 0.985 | 0.999 / 0.985 |
| `loads.bytes_64` | 1.365 / 1.387 | 1.406 / 1.418 |
| `loads.bytes_256` | 1.285 / 1.260 | 1.273 / 1.269 |
| `loads.bytes_321` | 1.183 / 1.219 | 1.241 / 1.255 |
| `loads.bytes_322` | 1.013 / 1.028 | 1.046 / 1.047 |
| `loads.bytes_512` | 0.998 / 0.998 | 1.031 / 1.026 |

### Typed controls in source comparisons

These use the same Pydantic engine on both sides; differences do not establish
a new typed-core optimization.

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `typed.adapter.dumps_small` | 1.000 / 0.987 | 1.004 / 0.999 |
| `typed.adapter.loads_small` | 1.011 / 1.004 | 0.995 / 1.001 |
| `typed.codec.dumps_small` | 1.004 / 1.009 | 1.009 / 0.999 |
| `typed.codec.loads_small` | 1.008 / 0.999 | 1.006 / 0.998 |
| `typed.codec.dumps_quiet_small` | 0.997 / 1.005 | 1.002 / 0.996 |
| `typed.adapter.dumps_quiet_small` | 1.005 / 1.001 | 1.001 / 0.998 |
| `typed.adapter.dumps_batch` | 1.001 / 0.997 | 0.979 / 1.009 |
| `typed.adapter.loads_batch` | 1.006 / 1.001 | 1.007 / 1.018 |
| `typed.codec.dumps_batch` | 0.985 / 0.994 | 1.000 / 1.002 |
| `typed.codec.loads_batch` | 0.998 / 0.999 | 1.005 / 1.005 |
| `typed.codec.dumps_quiet_batch` | 0.997 / 1.012 | 0.982 / 0.988 |
| `typed.adapter.dumps_quiet_batch` | 0.999 / 1.027 | 0.996 / 1.009 |

## Retained evidence

| Pair | Forward comparison | Reverse comparison | Warning counts: baseline / candidate / candidate-reverse / baseline-reverse |
| --- | --- | --- | --- |
| [arm64-published](arm64-published/) | [comparison](arm64-published/comparison.txt) | [reverse](arm64-published/comparison-reverse.txt) | 19 / 12 / 12 / 16 |
| [arm64-source](arm64-source/) | [comparison](arm64-source/comparison.txt) | [reverse](arm64-source/comparison-reverse.txt) | 23 / 24 / 22 / 23 |
| [x86_64-published](x86_64-published/) | [comparison](x86_64-published/comparison.txt) | [reverse](x86_64-published/comparison-reverse.txt) | 19 / 23 / 21 / 15 |
| [x86_64-source](x86_64-source/) | [comparison](x86_64-source/comparison.txt) | [reverse](x86_64-source/comparison-reverse.txt) | 29 / 26 / 26 / 25 |

Each directory retains four complete pyperf reports (`*.json.gz`), measurement
logs (`*.log.gz`), original comparison text, build/environment records and
differential results. All timing values, warmups and calibration are unchanged.
Only `hostname` and `python_executable` were removed from pyperf metadata;
public CI configuration paths remain. Gzip uses a fixed timestamp.
[manifest.json](manifest.json) records original artifact/file names and hashes,
sanitized JSON hashes and retained-file hashes.

To inspect from the repository root using the current UV environment:

```sh
gzip -dc benchmarks/results/v3/arm64-published/baseline.json.gz > /tmp/orjson-v3-baseline.json
gzip -dc benchmarks/results/v3/arm64-published/candidate.json.gz > /tmp/orjson-v3-candidate.json
uv run --no-sync python benchmarks/compare_pyperf.py /tmp/orjson-v3-baseline.json /tmp/orjson-v3-candidate.json --native-only
```

The original comparison text includes pyperf's geometric-mean row. This report
does not promote it as an overall speed claim. The separate
[3.14t local diagnostic](../threaded-314t.json) measures a different no-GIL
artifact and hardware; its interpretation is in [benchmark guidance](../../README.md#free-threaded-performance-qualification).
