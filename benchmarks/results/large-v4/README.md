# Large JSON: 1, 10 and 100 MiB

**[Full three-way report: latency, MiB/s, memory and stability](apple-m5/comparison.md)**

Completed on November 24, 2026 using **Apple M5 ARM64, 24 GiB RAM, CPython 3.13.12**. The candidate is Pydantic ORJSON `3.13.0+pydantic.4`, native source `5d095448697f3f8fe91e05131a823a8befb9ec0f`; the baseline is the published ORJSON `3.13.0` wheel. Python stdlib json is the third engine. This measures native dumps/loads; optional Pydantic validation is outside this suite.

**Timing variation prevents speed qualification:** all 18 comparisons with upstream ORJSON are marked unstable under the declared 10% spread/drift threshold. The medians below describe these measurements. Every raw value and regression remains available; this run does not establish an all-workloads speed win.

## Documents tested

| Family | Target sizes | Items at 100 MiB | Actual bytes at 100 MiB |
| --- | --- | ---: | ---: |
| records | 1 / 10 / 100 MiB | 379,427 | 104,857,633 |
| numeric | 1 / 10 / 100 MiB | 7,800,669 | 104,857,601 |
| nested_unicode | 1 / 10 / 100 MiB | 62,928 | 104,859,161 |

The nine files contain varied record arrays, mixed finite numeric arrays, and nested multilingual documents with escaped prose. Sizes use actual UTF-8 bytes and complete-item boundaries. They are not a single padded string. Exact shapes, counts and hashes are retained in [fixture receipts](apple-m5/fixtures/).

[Environment and installed-library receipts](apple-m5/environment.json) record
the Python/compiler details, native hashes, wheel metadata and matching dependency
versions. The measured worker sources match benchmark commit `c7d85ff`; the
[native build receipt](../../../compatibility/results/local-v4.json) identifies
the candidate artifact.

## 100 MiB medians

Milliseconds per operation; lower is better. See the full report for all 1/10/100 MiB rows, throughput, order-specific ratios and instability details.

| Family / operation | Pydantic ORJSON ms | ORJSON ms | json ms |
| --- | ---: | ---: | ---: |
| records / encode | 68.25 | 74.97 | 522.66 |
| records / decode | 353.63 | 303.33 | 635.81 |
| numeric / encode | 74.31 | 176.64 | 1100.47 |
| numeric / decode | 210.61 | 203.78 | 738.49 |
| nested_unicode / encode | 59.34 | 72.86 | 393.12 |
| nested_unicode / decode | 337.43 | 321.61 | 659.15 |

The medians show faster candidate encoding on these 100 MiB fixtures and slower candidate decoding than upstream. Large decoding remains an optimization target. json has different memory tradeoffs; all three memory columns are included in the detailed report.

## Method and evidence

- Eighteen cases: nine fixtures, each encoded and decoded. Two balanced engine-order rounds, four fresh worker processes per round, four timed values per worker: **108 timing reports and 1,728 timed values**, plus warmups.
- Latency measures warmed calls on preloaded input, including returned-output release. File IO, object construction and independent correctness checks are excluded. json includes UTF-8 encoding inside timing.
- **54 separate memory probes**, one fresh process per case/engine. External RSS sampling is separate from latency; baseline input, retained output, observed peaks, resident growth and actual sample gaps are reported. These are sampled observations, not exact allocation maxima.
- macOS user-initiated QoS was requested; CPU affinity was unavailable. The machine was not an isolated fixed-frequency benchmark host. These measurements do not qualify other architectures, Python versions or no-GIL throughput.

Raw measurements, logs, memory probes, exact harness sources and receipts are preserved in [raw-evidence.tar.gz](apple-m5/raw-evidence.tar.gz). [retention.json](apple-m5/retention.json) records original, sanitized and stored hashes. Only hostname/interpreter-path metadata and user home prefixes were removed; timed values and warnings were preserved.

The 333 MiB payload corpus is reproducible using the archived generator and pinned Python. Payloads are omitted from Git; their hashes and actual lengths were verified before retention. A replay without regenerated payloads explicitly reports their absence.

```sh
mkdir -p .artifacts/large-review
tar -xzf benchmarks/results/large-v4/apple-m5/raw-evidence.tar.gz -C .artifacts/large-review
uv run --no-sync python .artifacts/large-review/source/report_large.py .artifacts/large-review/matrix
```

See [large-benchmark instructions](../../LARGE_JSON.md) to regenerate and rerun all sizes. The [Linux x86-64/ARM64 run](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45467361621) is separate; its pending results are not included in this local report.
