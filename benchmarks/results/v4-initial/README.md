# Initial .4 three-engine measurements

These are **historical intermediate builds**, not measurements of the latest
implementation or a final release. All four jobs completed compatibility checks
and all 89 benchmark cases. **All four failed the all-cases-win performance gate.**
Every comparison explicitly labels **Pydantic ORJSON**, published **ORJSON**, and
Python standard-library **json**; regressions and unstable results remain visible.

| Build profile | Exact source | GitHub run | Architectures |
| --- | --- | --- | --- |
| Portable | `c3346c8775a1b9c5f439be47f4fc0f989118de45` | [45451602951](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45451602951) | ARM64, x86-64 |
| Clang + cross-language LTO experiment | `546eb5678662deb0544198c2101adb283fcf7d02` | [45452996618](https://github.com/TheCulliganMan/pydantic-orjson/actions/runs/45452996618) | ARM64, x86-64 |

Between those commits only the build script/workflow changed; native algorithms
were identical. Both profiles built actual manylinux 2.17 wheels with UV 0.13.9,
Rust 1.99.0 and regular-GIL CPython 3.13.18. The experimental profile used Clang/LLD
23.1.5, C `-O2 -fstrict-aliasing -flto=full` and Rust linker-plugin/fat LTO;
exact compiler settings and toolchain digests are retained in its build receipt.
The baseline is the official binary-only PyPI `orjson==3.13.0` wheel.

Both ARM runners report **Neoverse-N2**. The x86 portable job used **AMD EPYC
7763**, while the x86 LTO job used **Intel Xeon 6975P-C**. Consequently, x86
cross-run absolute-time differences cannot be attributed to LTO. Compare each
candidate against its own same-run ORJSON/json controls. No no-GIL or other
Python-version performance claims follow from these runs.

## All 89 cases

Each linked report includes every case, all three latency columns and both order
ratios. There are 83 native JSON cases and six explicitly labeled typed-pipeline
cases. Typed comparisons include model conversion/validation and do not claim a
faster Pydantic core; the direct TypeAdapter API is available to all users.

| Report | Wins vs ORJSON | Regressions | Unstable | Inconclusive | Within 2% tolerance | Wins vs json | Unstable vs json |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Portable ARM64](portable/arm64/comparison.md) | 57 | 7 | 7 | 13 | 5 | 87 | 2 |
| [Portable x86-64](portable/x86_64/comparison.md) | 31 | 20 | 23 | 14 | 1 | 67 | 22 |
| [LTO ARM64](clang-lto/arm64/comparison.md) | 53 | 5 | 9 | 14 | 8 | 86 | 3 |
| [LTO x86-64](clang-lto/x86_64/comparison.md) | 33 | 18 | 14 | 18 | 6 | 77 | 12 |

For the 83 **native-only** cases, wins/regressions/unstable/inconclusive/tolerance
counts are respectively **54/7/7/10/5** (portable ARM), **28/20/21/13/1** (portable
x86), **49/5/9/12/8** (LTO ARM), and **31/18/14/14/6** (LTO x86). No aggregate
average substitutes for the case-level acceptance gate.

The gate requires >1% separation between the slowest candidate worker median
and fastest baseline worker median, with at most 10% worker/sample spread and
round drift. Within tolerance is not a win. These are conservative observed
bounds, not statistical confidence intervals. All 89 rows compare UTF-8 bytes;
json encoding includes `str.encode('utf-8')`. No unsupported capability receives
a fabricated timing.

## Material findings from these exact builds

- **Portable ARM Unicode decoding regressed:** 4,096 characters took 9.75 µs
  versus ORJSON's 8.04; 65,536 characters took 150.35 versus 125.93. Both orders
  and low-spread workers agreed. LTO reduced these to 8.82 and 138.79 µs, still
  behind its same-run baseline at 8.04 and 125.94.
- **Portable x86 float decoding regressed:** 128 values took 3.74 versus 3.14 µs;
  2,048 took 71.51 versus 60.31. ASCII/byte decoding at 4 KiB and 64 KiB also
  regressed by about 16–18%. The LTO job tied its own baseline on those cases,
  but different x86 hardware prevents a causal compiler-only conclusion.
- **Record encoding still needed work:** portable x86 compact records were
  about 6–7% slower; pretty 128/1,024-record encoding was about 14% slower.
  Compact/sorted records remained slower in the separate LTO x86 comparison.
- **LTO was a tradeoff on ARM:** 65,536-character ASCII decoding went from a
  portable 20.28 µs to 22.87 µs, approximately matching the 22.90-µs official
  baseline. Thus Unicode improvement did not justify a blanket LTO claim.
- **Stable improvements were real but workload-specific:** dense-escape
  encoding at 65,536 characters was about 10.10× faster on portable ARM and
  4.68× on portable x86, with low process spread. ARM 2,048-float encoding
  improved about 1.46×. These do not establish universal speed.

Short integer-array encoding, short ARM ASCII encoding and Unicode construction
remained concrete optimization priorities. Historical severe 10× numeric worker
bimodality was absent in these particular integer medians, but that does not
prove the cause of earlier instability or justify discarding remaining warnings.

## Compatibility and measurement provenance

Each job passed **2,430 tests, with 45 skips and no failures/errors**, and the
differential comparison matched **2,425 inputs plus seven API contracts**.
Full JUnit records, dependency lists, binary/wheel digests, build output, CPU
details and upstream installation logs are retained under each `provenance/`.
These attest only to the named historical wheel and source.

Each case used two balanced engine-order rounds, four worker processes per round,
four timed values per worker, two warmups and a 0.07-second minimum. All workers
were pinned to logical CPU 3. The actual worker metadata records
`python_hash_seed=random`; the parent's requested seed was not inherited by
pyperf workers in these historical runs. CPU affinity does not establish a
dedicated physical core, fixed frequency or absence of hypervisor contention.

Four `measurements.tar.gz` bundles retain **2,136 raw reports and 2,136 complete
logs**, including **34,176 timed values**, calibration/warmups and all warnings.
They also contain comparison JSON/Markdown, the original sanitized manifest and
an updated manifest whose report/log hashes match the retained files. Extracting
one bundle restores ordinary `report_matrix.py` inputs:

```sh
mkdir -p .artifacts/retained-review
tar -xzf benchmarks/results/v4-initial/portable/arm64/measurements.tar.gz -C .artifacts/retained-review
uv run --no-sync python benchmarks/report_matrix.py .artifacts/retained-review/matrix --gate all-wins
```

The command is expected to return a failing gate. Extraction/comparison changes
only the scratch directory. `retain.py` records the archive preparation recipe;
run it through UV against downloaded GitHub artifacts to reproduce the bundles.

Each `retention.json.gz` records original artifact-file hashes, sanitized-content
hashes, retained member/file hashes and the archive hash. Only runner hostname,
absolute interpreter identity and runner home/checkout paths were removed; XML
hostnames were removed and path placeholders escaped. Numeric timing data,
warmups, options, fixture hashes, native hashes and warnings were preserved.
Original wheel archives remain in the linked CI artifacts rather than being
duplicated in Git; their complete digests are retained here. All retained digests,
privacy removals, four extracted 89-case manifests and JUnit XML were verified.
