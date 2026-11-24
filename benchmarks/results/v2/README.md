# Version .2 performance evidence

These measurements belong to `orjson 3.13.0+pydantic.2`, commit
[`66c0d0357f7e39d3a656660060a09bc02cc28c8b`](https://github.com/TheCulliganMan/pydantic-orjson/commit/66c0d0357f7e39d3a656660060a09bc02cc28c8b),
from [successful workflow run 45417954459](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45417954459)
on November 24, 2026. All four comparison jobs completed. They demonstrate
specific repeatable improvements alongside regressions and unstable cases;
they do **not** pass a broad performance acceptance gate.

**They do not measure version `.3` or free-threaded Python.** The subsequent
free-threaded port changes ownership, copying and allocation paths and requires
its own regular/free-threaded performance qualification.

## Baselines and method

- **Published:** the actual binary-only PyPI `orjson==3.13.0` wheel, downloaded
  from the official index. Its install receipt retains the wheel URL and digest.
- **Source:** commit `e56965ebcfdc1905318da14d37b8b07990130109`, distribution
  `3.13.0+pydantic.1`, whose native engine matches the recorded upstream base.
  Baseline and candidate were built with the same stable release toolchain and
  flags. This comparison isolates the source patch more closely; it does not
  reproduce the compiler/SIMD settings of the published wheel.
- Each job measured baseline → candidate → candidate → baseline, with four
  worker processes, four values per worker, two warmups, a 70 ms minimum-time
  target and CPU affinity. There are 16 timed values per case per report plus
  calibration/warmup records. Workers run serially on one selected CPU.
- Published comparisons contain all 26 native cases. Source comparisons also
  contain 12 typed cases, for 38 total. Public TypeAdapter forwarding is
  unchanged, so typed cases are controls and wrapper-overhead measurements.
- Every comparison passed metadata/fixture checks and a differential check of
  2,418 cases plus seven API contracts with zero mismatches. This is correctness
  evidence for the corpus, not a timing acceptance test.

All jobs used regular CPython 3.13.18, Pydantic 2.14.4, pydantic-core 2.50.5,
pyperf 2.11.0, maturin 1.16.0 and rustc 1.99.0 (LLVM 23.1.1). Source builds used
`maturin build --release --strip --locked`. Python was compiled with GCC 15.2.0.
Both runners reported Linux 7.0.0-1020-azure / glibc 2.43 on Ubuntu 26.04.
The x86-64 runner reported an AMD EPYC 7763, four allowed logical CPUs and two
physical-core representatives; measurements selected logical CPU 2. ARM64
reported four logical CPUs/four representatives and selected CPU 3; its CPU
model was not captured. CPU selection, build logs, dependency locks, native
binary hashes and fixture hashes are retained with each pair.

## Results that require attention

Published-wheel comparisons show consistent gains in both orders for the
64-byte decode fixture: **1.371–1.374x on ARM64** and **1.370–1.399x on x86-64**.
ARM64 escaped-text encoding measured **1.794–1.811x**, and its dense-escape
fixture measured **8.565–8.670x**. These are individual string distributions,
not general serialization gains. The FastAPI-option records fixture measured
**1.112–1.113x on ARM64** and **1.095–1.149x on x86-64**; this times `dumps` with
FastAPI's option flags, not HTTP throughput or end-to-end request latency.

The published ARM64 Unicode decode fixture regressed in both orders, with a
ratio near **0.950x** (about 5.3% higher latency). Published x86-64 regressions
include escaped-text decoding (**0.965–0.967x**), dense-escape decoding
(**0.955x**), float decoding (**0.948–0.954x**) and integer-array encoding
(**0.960–0.962x**). Against matched source, x86-64 integer-array encoding
(**0.957–0.964x**) and pretty-record encoding (**0.963x**) also regressed.
Other smaller differences remain visible in the complete tables below.

Several ARM64 numeric results vary too much by run order to interpret as an
improvement: published integer encoding moves from **4.645x to 1.205x**, and
published float encoding moves from **2.043x to 0.828x**. Matched-source float
encoding moves **1.397x → 0.680x**, while float decoding moves
**1.912x → 0.526x**. Retaining the reverse order exposes this instability.
Do not promote the favorable numeric run or average these cases into a claim.

Every job produced pyperf stability warnings, including insufficient samples
for its 1% variation criterion. The retained logs contain the full warnings,
and the comparison files include pyperf's separate significance analysis.
Metadata matching and a green workflow do not establish timing stability.
Broader workload coverage and dedicated-runner repetitions are still needed.

## Complete native median ratios

Ratios are **baseline median / candidate median**: above 1 favors the candidate;
below 1 means the candidate took longer. `Forward / reverse` corresponds to
baseline → candidate and candidate → baseline. These descriptive median ratios
are not pyperf's mean-based significance result. No native case is omitted.

### Published upstream wheel

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `dumps.event` | 0.983 / 0.995 | 1.041 / 1.045 |
| `loads.event` | 1.142 / 1.132 | 1.186 / 1.211 |
| `dumps.records` | 1.029 / 1.033 | 1.029 / 1.020 |
| `loads.records` | 0.998 / 1.013 | 0.991 / 1.016 |
| `dumps.ascii_text` | 1.092 / 1.110 | 1.017 / 1.018 |
| `loads.ascii_text` | 1.098 / 1.099 | 0.988 / 0.992 |
| `dumps.unicode_text` | 1.107 / 1.095 | 1.000 / 1.007 |
| `loads.unicode_text` | 0.950 / 0.950 | 0.992 / 0.992 |
| `dumps.escaped_text` | 1.811 / 1.794 | 0.983 / 0.982 |
| `loads.escaped_text` | 1.070 / 1.077 | 0.967 / 0.965 |
| `dumps.dense_escapes` | 8.565 / 8.670 | 1.023 / 1.023 |
| `loads.dense_escapes` | 1.038 / 1.037 | 0.955 / 0.955 |
| `dumps.numbers` | 4.645 / 1.205 | 0.962 / 0.960 |
| `loads.numbers` | 1.031 / 1.018 | 1.033 / 1.001 |
| `dumps.floats` | 2.043 / 0.828 | 0.998 / 0.993 |
| `loads.floats` | 1.016 / 1.039 | 0.954 / 0.948 |
| `dumps.datetimes` | 1.008 / 1.010 | 1.033 / 1.008 |
| `loads.datetimes` | 1.030 / 1.026 | 1.127 / 1.145 |
| `dumps.records_fastapi` | 1.112 / 1.113 | 1.149 / 1.095 |
| `dumps.records_sorted` | 0.998 / 0.997 | 1.003 / 0.998 |
| `dumps.records_pretty` | 1.014 / 1.015 | 0.980 / 1.001 |
| `loads.bytes_64` | 1.374 / 1.371 | 1.370 / 1.399 |
| `loads.bytes_256` | 1.293 / 1.292 | 1.253 / 1.272 |
| `loads.bytes_321` | 1.265 / 1.301 | 1.197 / 1.212 |
| `loads.bytes_322` | 1.066 / 1.047 | 0.986 / 0.977 |
| `loads.bytes_512` | 1.065 / 1.066 | 1.004 / 1.005 |

### Matched stable source build

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `dumps.event` | 0.977 / 0.973 | 1.028 / 1.015 |
| `loads.event` | 1.165 / 1.156 | 1.288 / 1.236 |
| `dumps.records` | 0.987 / 0.981 | 1.000 / 0.998 |
| `loads.records` | 1.008 / 1.008 | 0.982 / 1.005 |
| `dumps.ascii_text` | 5.741 / 5.723 | 1.004 / 1.004 |
| `loads.ascii_text` | 0.992 / 1.008 | 1.004 / 1.001 |
| `dumps.unicode_text` | 6.218 / 6.236 | 1.002 / 1.006 |
| `loads.unicode_text` | 0.996 / 1.000 | 1.032 / 0.990 |
| `dumps.escaped_text` | 3.530 / 3.512 | 1.018 / 1.002 |
| `loads.escaped_text` | 0.999 / 0.989 | 1.005 / 1.002 |
| `dumps.dense_escapes` | 0.987 / 0.989 | 1.005 / 1.006 |
| `loads.dense_escapes` | 1.000 / 1.000 | 0.998 / 0.998 |
| `dumps.numbers` | 1.055 / 0.985 | 0.964 / 0.957 |
| `loads.numbers` | 0.990 / 1.002 | 0.967 / 0.993 |
| `dumps.floats` | 1.397 / 0.680 | 0.996 / 0.987 |
| `loads.floats` | 1.912 / 0.526 | 1.004 / 1.018 |
| `dumps.datetimes` | 0.993 / 0.999 | 1.042 / 1.012 |
| `loads.datetimes` | 1.007 / 1.001 | 1.044 / 1.035 |
| `dumps.records_fastapi` | 1.105 / 1.107 | 1.117 / 1.119 |
| `dumps.records_sorted` | 0.998 / 0.997 | 1.031 / 0.999 |
| `dumps.records_pretty` | 0.991 / 0.990 | 0.963 / 0.963 |
| `loads.bytes_64` | 1.379 / 1.372 | 1.442 / 1.441 |
| `loads.bytes_256` | 1.240 / 1.265 | 1.323 / 1.327 |
| `loads.bytes_321` | 1.229 / 1.233 | 1.255 / 1.290 |
| `loads.bytes_322` | 1.025 / 1.006 | 1.032 / 1.035 |
| `loads.bytes_512` | 1.010 / 0.997 | 1.055 / 1.032 |

### Typed controls in source comparisons

These use the same Pydantic engine on both sides; differences are measurement
variation and wrapper effects, not a new typed-core optimization.

| Case | ARM64 forward / reverse | x86-64 forward / reverse |
| --- | ---: | ---: |
| `typed.adapter.dumps_small` | 1.016 / 0.994 | 1.002 / 1.022 |
| `typed.adapter.loads_small` | 1.002 / 0.992 | 0.995 / 1.009 |
| `typed.codec.dumps_small` | 1.004 / 1.010 | 1.007 / 0.994 |
| `typed.codec.loads_small` | 1.002 / 1.002 | 1.007 / 1.007 |
| `typed.codec.dumps_quiet_small` | 0.985 / 1.005 | 0.997 / 1.029 |
| `typed.adapter.dumps_quiet_small` | 1.000 / 1.016 | 1.001 / 1.011 |
| `typed.adapter.dumps_batch` | 0.980 / 0.987 | 1.001 / 1.002 |
| `typed.adapter.loads_batch` | 0.991 / 1.006 | 0.996 / 1.018 |
| `typed.codec.dumps_batch` | 1.009 / 1.007 | 1.007 / 1.000 |
| `typed.codec.loads_batch` | 0.991 / 1.004 | 0.997 / 0.989 |
| `typed.codec.dumps_quiet_batch` | 0.983 / 1.010 | 0.996 / 1.001 |
| `typed.adapter.dumps_quiet_batch` | 1.002 / 1.030 | 1.008 / 1.004 |

## Retained evidence

| Pair | Forward comparison | Reverse comparison | Warning counts: baseline / candidate / candidate-reverse / baseline-reverse |
| --- | --- | --- | --- |
| [arm64-published](arm64-published/) | [comparison](arm64-published/comparison.txt) | [reverse](arm64-published/comparison-reverse.txt) | 15 / 16 / 13 / 14 |
| [arm64-source](arm64-source/) | [comparison](arm64-source/comparison.txt) | [reverse](arm64-source/comparison-reverse.txt) | 24 / 23 / 25 / 25 |
| [x86_64-published](x86_64-published/) | [comparison](x86_64-published/comparison.txt) | [reverse](x86_64-published/comparison-reverse.txt) | 14 / 19 / 13 / 13 |
| [x86_64-source](x86_64-source/) | [comparison](x86_64-source/comparison.txt) | [reverse](x86_64-source/comparison-reverse.txt) | 30 / 26 / 25 / 28 |

Each pair directory contains four complete pyperf reports (`*.json.gz`),
measurement logs (`*.log.gz`), the original comparison texts, build/environment
records and differential results. All timing values, warmups and calibration
runs are retained. Only `hostname` and `python_executable` fields were removed
from pyperf metadata; public CI compiler/configuration paths remain. Gzip uses
a fixed timestamp. [manifest.json](manifest.json) records original artifact
names and SHA-256 digests, sanitized JSON digests and retained-file digests.

To inspect a report, decompress to a temporary path, then use pyperf:

```sh
gzip -dc arm64-published/baseline.json.gz > /tmp/orjson-baseline.json
gzip -dc arm64-published/candidate.json.gz > /tmp/orjson-candidate.json
python -m pyperf stats /tmp/orjson-baseline.json
python ../../compare_pyperf.py /tmp/orjson-baseline.json /tmp/orjson-candidate.json --native-only
```

Run that example from this directory with the pinned benchmark environment.
The preserved comparison text may contain a geometric-mean row produced by
pyperf; this report intentionally does not use that row as a performance claim.
