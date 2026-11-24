# Large JSON benchmark

This suite measures actual **1, 10 and 100 MiB UTF-8 JSON documents**, not
character-count strings or small API examples. Every size is measured for both
encoding and decoding with **Pydantic ORJSON**, published **ORJSON**, and stdlib
**json**. The complete matrix has nine fixtures and eighteen operations.

| Family | Shape | Items in the 100 MiB fixture | Actual bytes |
| --- | --- | ---: | ---: |
| records | Varied event records, customer objects, identifiers, amounts and tags | 379,427 | 104,857,633 |
| numeric | Finite integers and floats with varied signs and magnitudes | 7,800,669 | 104,857,601 |
| nested_unicode | Nested objects/lists, multilingual text and escaped prose | 62,928 | 104,859,161 |

Files end at complete JSON items, so actual sizes exceed their targets by at
most the final item. Receipts record exact byte counts, SHA-256, item counts,
shape and generator version. Fixture generation streams stdlib JSON to disk;
the controller never constructs all nine documents as Python object graphs.

Prepare two UV environments with the same Python and locked dependencies. Install
the candidate wheel in one and the official `orjson==3.13.0` binary wheel in the
other. The benchmark does not replace installed libraries. Then run:

```sh
uv run --no-sync python benchmarks/run_large.py \
  --candidate-python .venv/bin/python \
  --orjson-python .artifacts/large/upstream/bin/python \
  --fixtures .artifacts/large/fixtures \
  --output .artifacts/large/results \
  --source-commit <candidate-source-sha>
uv run --no-sync python benchmarks/report_large.py .artifacts/large/results
```

Use `--affinity <permitted-cpu>` on Linux. On macOS, `--macos-qos` requests
user-initiated scheduling; it does not pin a performance core. The manual
`large-json.yml` workflow runs the same complete matrix against actual portable
wheels on Linux x86-64 and ARM64. Its artifacts include every latency report,
memory probe, exact fixture receipt, build receipt and dependency list.

Generation, file reads, input-object construction and correctness checks are
outside timing. All encoders return UTF-8 bytes; json's `.encode('utf-8')` is
inside its timed operation. Every decoder receives identical bytes. Encoders'
input objects are prepared through the same stdlib parser for all three engines.
Repeated latency measurements include the function call and release of its
returned output. GC settings and runtime/build identities are recorded by pyperf.

Each case uses two reversed/rotated engine-order rounds, four fresh workers per
round, four timed values per worker and one warmup. Fixed loop counts process at
least one document and approximately 16 MiB per value at smaller sizes. One loop
is appropriate for 100 MiB. Raw values, warmups, fixture and binary hashes remain
available; unstable results and regressions are never removed. Throughput uses
the same actual input byte count for every engine, even when equivalent float
spellings produce different output sizes.

Memory uses **separate fresh processes**, without a sampler affecting latency.
An external process samples RSS at a requested 1 ms interval after input
preparation and before validation. The child retains input and output until the
parent acknowledges completion. Reports show baseline RSS, observed operation-
window RSS peak, resident growth, retained-result RSS, sample counts and largest
sample gaps. RSS includes allocator reuse, shared mappings and interpreter
overhead; its growth is not total allocated bytes. Sampling can miss transient
peaks, so these measurements are observed peaks rather than exact maxima.
Process-lifetime high-water values include preparation/validation and are kept
separately. File fingerprints are streamed to avoid library-sized temporary
hash buffers biasing only one engine's preparation baseline.

The raw 333 MiB fixture corpus is reproducible from `large_fixtures.py`; it is
not committed to Git. Published results retain receipts and all measurement
evidence. A report can validate generated files on disk; an extracted evidence
archive without fixtures explicitly discloses that the bytes are unavailable
and requires regeneration for independent byte-level verification.
