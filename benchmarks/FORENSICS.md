# Historical timing audit

This audit reads the immutable raw reports in `results/v3-uv/`, measured at
`5db2adfe38696aeb658e3f68900227fa80b3948e`, GitHub run `45426539830`.
It does not reinterpret that source as the current candidate or the final
portable release wheels. All timings below are microseconds per operation.

The apparent ARM integer-encoding gain of **10.044×**, followed by a reverse-order
ratio of **0.534×**, is not credible evidence of either an algorithmic win or
regression. Individual fresh workers using the *same candidate binary* occupy
different timing modes:

| ARM published comparison | Worker 1 median | Worker 2 | Worker 3 | Worker 4 | Fixed loops per timed value |
| --- | ---: | ---: | ---: | ---: | ---: |
| Candidate, forward, `dumps.numbers` | 61.375 | 6.376 | 6.361 | 6.352 | 16,384 |
| Candidate, reverse, `dumps.numbers` | 6.347 | 63.970 | 58.862 | 61.987 | 16,384 |
| Official ORJSON, forward, `dumps.numbers` | 56.063 | 64.392 | 67.807 | 60.617 | 2,048 |
| Official ORJSON, reverse, `dumps.numbers` | 7.883 | 7.868 | 65.677 | 58.960 | 16,384 |

Candidate worker duration also changes consistently with these samples: about
0.635 seconds in the fast mode versus about 6.1 seconds in the slow mode. Thus
the artifact does not support a simple wrong-loop-count or unit-normalization
explanation. Each worker uses fresh fixtures; timing calls do not mutate lists,
and exact output assertions surround the measurements. Fixture hashes match.
The harness passes real 2,048-item numeric lists, not a changing generator.

Float operations also split into worker modes. ARM published forward baseline
`loads.floats` worker medians are **116.056 / 55.337 / 55.921 / 115.457**;
the candidate has **116.922 / 53.628 / 53.821 / 117.057**. Pooling just 16 timing
samples can move the median into either mode depending on which four processes
were sampled. Reversing whole-suite order does not correct that problem.

The former encoder reserves about **295 KiB** for a 2,048-element list, despite
the integer JSON output being only **9,131 bytes**, then shrinks the allocation.
Both baseline and candidate used that over-allocation policy. Crossing allocator
mapping thresholds, ASLR-dependent layout or allocator state is a concrete
explanation to investigate, but the old artifacts do **not** prove it. A causal
experiment must vary allocation policy or allocator thresholds while preserving
the workload, and inspect fresh-worker distributions, rather than changing the
fixture until a fast timing appears. Never publish only the fast mode.

CPU affinity alone did not qualify the old runs. All ARM workers were pinned to
logical CPU 3, but reports record no ARM CPU model/frequency or frequency governor.
ASLR remained enabled. `cpu_config=idle:none` does not establish an isolated core,
fixed frequency, zero hypervisor steal time or absence of competing SMT work.
Those reports cannot attribute the cause uniquely. The new matrix records the
available policy, SMT and pressure data and rejects large process/sample spread.

Some regressions have much stronger support. In the x86 published comparison,
`loads.floats` baseline worker medians are approximately **59.9–60.1 µs**, versus
candidate **64.9–65.9 µs** in the forward run. Reverse-order workers remain
approximately **60.3–61.2 µs** versus **65.4–66.5 µs**. Recorded frequencies remain
near **3,244 MHz**, and both orders agree. That is credible regression evidence
for those exact wheels and fixture; it must be resolved or reported, not averaged
away with a small-document parsing improvement. By contrast, x86 source Unicode
encoding also has candidate worker modes near **0.35 / 0.55 / 0.66 µs**, so a
single pooled ratio overstates the certainty of its exact regression magnitude.

The source and published controls answer different questions. The source control
and candidate used the same UV lock, Rust 1.99.0, Maturin 1.16.0 and default stable
source-build recipe. The official downloaded wheel may use different SIMD,
compiler or release flags; its full compiler provenance is not established by
installed WHEEL metadata. Its native hash and binary-only PyPI install receipt
identify the binary actually measured. X86 source and published jobs also used
different CPU models (EPYC 9V74 and EPYC 7763), so absolute times must not be
compared across those jobs. Primary user comparisons must use the published
ORJSON wheel beside Pydantic ORJSON and standard-library json on the same runner;
matched-source comparisons remain an additional engineering control.

The new acceptance report keeps every row, order, worker median and raw sample.
It distinguishes a stable observed win, a regression, within-tolerance timings,
insufficient sampling, and inconclusive/unstable results. A complete profile on
one architecture/Python build never proves universal speed on every input or
on the other regular/free-threaded builds.
