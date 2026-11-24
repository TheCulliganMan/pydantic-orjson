# Large JSON: Pydantic ORJSON / ORJSON / json

Source: `5d095448697f3f8fe91e05131a823a8befb9ec0f`. Complete 1/10/100 MiB family matrix.

Actual MiB uses the measured fixture byte count (1 MiB = 1,048,576 bytes). Throughput divides those same bytes by median latency, so extra output bytes do not inflate an engine's rate. Encoding produces UTF-8 bytes, including json's UTF-8 conversion; all decoders consume identical fixture bytes.

2 balanced rounds. Ratios are baseline / Pydantic ORJSON latency; >1 favors Pydantic ORJSON. >10% worker/sample spread or round drift is marked unstable. Fewer than four processes or four values per process is insufficient sampling. One loop per value is legitimate for a large document. Tags describe observed ranges, not statistical confidence or universal speed.

| Case | Actual MiB | Pydantic ORJSON ms / MiB/s | ORJSON ms / MiB/s | json ms / MiB/s | vs ORJSON (rounds) | vs json (rounds) |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Encode records-1mib | 1.000043 | 0.800 / 1250.58 | 0.848 / 1179.00 | 5.251 / 190.44 | unstable: 0.984x / 1.075x | unstable: 6.636x / 6.509x |
| Decode records-1mib | 1.000043 | 2.790 / 358.39 | 2.843 / 351.82 | 5.131 / 194.91 | unstable: 1.020x / 1.017x | unstable: 1.590x / 1.922x |
| Encode records-10mib | 10.000031 | 8.143 / 1228.02 | 8.715 / 1147.48 | 53.121 / 188.25 | unstable: 1.052x / 1.071x | unstable: 6.539x / 6.367x |
| Decode records-10mib | 10.000031 | 29.845 / 335.07 | 27.526 / 363.30 | 54.419 / 183.76 | unstable: 0.822x / 1.041x | unstable: 1.609x / 2.111x |
| Encode records-100mib | 100.000031 | 68.247 / 1465.26 | 74.970 / 1333.86 | 522.662 / 191.33 | unstable: 1.181x / 1.109x | unstable: 7.431x / 7.774x |
| Decode records-100mib | 100.000031 | 353.629 / 282.78 | 303.333 / 329.67 | 635.808 / 157.28 | unstable: 0.848x / 0.887x | unstable: 1.692x / 1.950x |
| Encode numeric-1mib | 1.000002 | 1.122 / 891.45 | 1.579 / 633.44 | 12.169 / 82.18 | unstable: 1.515x / 1.196x | unstable: 10.799x / 9.584x |
| Decode numeric-1mib | 1.000002 | 1.678 / 595.86 | 1.659 / 602.73 | 6.875 / 145.46 | unstable: 1.057x / 0.958x | unstable: 4.168x / 4.099x |
| Encode numeric-10mib | 10.000005 | 11.174 / 894.94 | 17.503 / 571.34 | 125.512 / 79.67 | unstable: 1.479x / 1.603x | unstable: 11.033x / 11.474x |
| Decode numeric-10mib | 10.000005 | 20.210 / 494.80 | 19.999 / 500.03 | 71.956 / 138.97 | unstable: 0.799x / 1.009x | unstable: 3.274x / 3.617x |
| Encode numeric-100mib | 100.000001 | 74.313 / 1345.67 | 176.644 / 566.11 | 1100.467 / 90.87 | unstable: 2.262x / 2.506x | unstable: 11.506x / 16.801x |
| Decode numeric-100mib | 100.000001 | 210.608 / 474.81 | 203.784 / 490.72 | 738.487 / 135.41 | unstable: 0.987x / 0.939x | unstable: 3.580x / 3.400x |
| Encode nested_unicode-1mib | 1.001508 | 0.586 / 1709.06 | 0.586 / 1708.06 | 6.083 / 164.64 | unstable: 0.997x / 0.967x | unstable: 9.283x / 11.807x |
| Decode nested_unicode-1mib | 1.001508 | 2.856 / 350.69 | 2.691 / 372.22 | 6.175 / 162.19 | unstable: 0.812x / 1.019x | unstable: 2.184x / 2.147x |
| Encode nested_unicode-10mib | 10.000833 | 6.880 / 1453.58 | 8.674 / 1152.96 | 57.052 / 175.29 | unstable: 1.478x / 0.992x | unstable: 9.560x / 7.142x |
| Decode nested_unicode-10mib | 10.000833 | 38.133 / 262.26 | 33.572 / 297.89 | 73.068 / 136.87 | unstable: 0.757x / 1.000x | unstable: 1.961x / 1.832x |
| Encode nested_unicode-100mib | 100.001489 | 59.338 / 1685.28 | 72.865 / 1372.43 | 393.124 / 254.38 | unstable: 1.472x / 1.085x | win: 6.813x / 6.550x |
| Decode nested_unicode-100mib | 100.001489 | 337.429 / 296.36 | 321.608 / 310.94 | 659.153 / 151.71 | unstable: 0.931x / 0.991x | unstable: 2.283x / 1.642x |

## Separate memory probes

Each cell is **observed operation-window process RSS peak / incremental observed peak**, in MiB. Incremental peak is observed peak minus the prepared-input baseline. One fresh process per case/engine is sampled externally from READY/GO until DONE, with the result held until ACK; correctness validation occurs after sampling. These are separate memory probes, not latency-worker measurements. Input/prepared-value residency and interpreter imports contribute to the baseline. Sampling can miss transient peaks: these are observed RSS values, not exact maxima or allocated-byte counts. Latency timing includes output release on each iteration.

| Case | Pydantic ORJSON observed peak / +MiB | ORJSON observed peak / +MiB | json observed peak / +MiB |
| --- | ---: | ---: | ---: |
| Encode records-1mib | 38.06 / +1.14 | 36.94 / +0.03 | 35.38 / +0.00 |
| Decode records-1mib | 40.19 / +8.45 | 39.83 / +8.45 | 35.34 / +5.80 |
| Encode records-10mib | 98.50 / +0.09 | 98.11 / +0.05 | 108.02 / +11.48 |
| Decode records-10mib | 124.61 / +83.97 | 124.27 / +83.95 | 96.00 / +57.47 |
| Encode records-100mib | 706.39 / +0.09 | 706.52 / +0.03 | 805.03 / +100.06 |
| Decode records-100mib | 968.06 / +837.45 | 967.88 / +837.42 | 704.53 / +575.94 |
| Encode numeric-1mib | 36.38 / +1.12 | 36.33 / +1.05 | 33.98 / +0.48 |
| Decode numeric-1mib | 36.36 / +4.62 | 36.69 / +5.14 | 33.47 / +3.75 |
| Encode numeric-10mib | 92.38 / +10.05 | 92.20 / +9.97 | 92.20 / +11.56 |
| Decode numeric-10mib | 92.81 / +52.17 | 92.77 / +52.17 | 80.88 / +42.14 |
| Encode numeric-100mib | 630.03 / +99.30 | 629.66 / +99.23 | 629.17 / +100.03 |
| Decode numeric-100mib | 648.20 / +517.56 | 648.06 / +517.56 | 529.08 / +400.27 |
| Encode nested_unicode-1mib | 41.09 / +0.70 | 40.75 / +0.64 | 41.62 / +2.88 |
| Decode nested_unicode-1mib | 38.45 / +6.92 | 38.20 / +6.89 | 38.73 / +9.03 |
| Encode nested_unicode-10mib | 148.02 / +18.30 | 147.88 / +18.36 | 166.14 / +38.22 |
| Decode nested_unicode-10mib | 109.52 / +68.69 | 109.05 / +68.66 | 127.91 / +89.02 |
| Encode nested_unicode-100mib | 1201.97 / +166.78 | 1201.81 / +166.72 | 1400.11 / +366.66 |
| Decode nested_unicode-100mib | 815.70 / +685.27 | 815.59 / +685.31 | 1033.19 / +904.58 |

Memory method: external psutil RSS samples from GO through retained result; validation excluded; observed peak, not exact allocation peak.

Each raw probe also retains prepared-input baseline RSS, retained-result RSS, sample count, requested interval and largest observed sample gap.

## Memory sampling resolution

Each cell shows sample count / largest sample gap in milliseconds; requested intervals are retained in comparison.json.

| Case | Pydantic ORJSON | ORJSON | json |
| --- | ---: | ---: | ---: |
| Encode records-1mib | 4 / 1.043 ms | 4 / 0.778 ms | 7 / 1.521 ms |
| Decode records-1mib | 5 / 2.497 ms | 5 / 1.526 ms | 7 / 1.569 ms |
| Encode records-10mib | 9 / 1.617 ms | 10 / 1.542 ms | 37 / 3.650 ms |
| Decode records-10mib | 19 / 1.529 ms | 19 / 1.526 ms | 35 / 3.098 ms |
| Encode records-100mib | 49 / 3.434 ms | 55 / 3.442 ms | 291 / 1.579 ms |
| Decode records-100mib | 215 / 2.666 ms | 214 / 2.438 ms | 441 / 3.207 ms |
| Encode numeric-1mib | 4 / 1.230 ms | 5 / 1.534 ms | 12 / 1.717 ms |
| Decode numeric-1mib | 5 / 1.531 ms | 5 / 1.531 ms | 8 / 1.705 ms |
| Encode numeric-10mib | 12 / 1.916 ms | 16 / 1.644 ms | 77 / 3.365 ms |
| Decode numeric-10mib | 15 / 1.994 ms | 14 / 1.949 ms | 46 / 3.325 ms |
| Encode numeric-100mib | 75 / 2.887 ms | 109 / 2.584 ms | 870 / 10.100 ms |
| Decode numeric-100mib | 110 / 2.683 ms | 115 / 2.342 ms | 458 / 2.496 ms |
| Encode nested_unicode-1mib | 4 / 1.281 ms | 4 / 1.289 ms | 7 / 1.535 ms |
| Decode nested_unicode-1mib | 5 / 1.540 ms | 5 / 1.752 ms | 7 / 1.549 ms |
| Encode nested_unicode-10mib | 12 / 1.576 ms | 12 / 2.385 ms | 42 / 2.221 ms |
| Decode nested_unicode-10mib | 23 / 2.852 ms | 25 / 1.568 ms | 47 / 3.520 ms |
| Encode nested_unicode-100mib | 69 / 1.601 ms | 80 / 2.233 ms | 332 / 2.661 ms |
| Decode nested_unicode-100mib | 153 / 1.523 ms | 156 / 1.533 ms | 326 / 1.531 ms |

## Stability details

Each cell shows worker-median spread / largest within-worker sample spread / round-median drift.

| Case | Pydantic ORJSON | ORJSON | json |
| --- | ---: | ---: | ---: |
| dumps.records-1mib | 15.1% / 24.2% / 0.0% | 24.4% / 19.6% / 9.3% | 7.8% / 10.6% / 1.9% |
| loads.records-1mib | 19.5% / 9.0% / 0.5% | 15.3% / 14.2% / 0.2% | 31.2% / 45.1% / 21.4% |
| dumps.records-10mib | 14.4% / 27.0% / 4.1% | 10.8% / 31.8% / 6.0% | 14.1% / 17.8% / 1.4% |
| loads.records-10mib | 38.5% / 10.7% / 32.6% | 30.6% / 74.1% / 4.8% | 10.2% / 14.6% / 1.1% |
| dumps.records-100mib | 32.0% / 13.1% / 0.9% | 28.6% / 11.7% / 7.5% | 19.1% / 19.4% / 3.7% |
| loads.records-100mib | 11.2% / 28.7% / 0.5% | 28.8% / 21.6% / 5.3% | 29.7% / 27.4% / 15.8% |
| dumps.numeric-1mib | 18.3% / 16.5% / 2.9% | 36.9% / 9.4% / 30.2% | 40.2% / 20.5% / 15.9% |
| loads.numeric-1mib | 26.9% / 21.6% / 5.6% | 20.7% / 14.8% / 4.4% | 8.2% / 14.7% / 3.9% |
| dumps.numeric-10mib | 49.2% / 30.8% / 1.4% | 13.1% / 24.2% / 6.8% | 14.3% / 22.7% / 2.6% |
| loads.numeric-10mib | 17.8% / 21.4% / 0.0% | 38.9% / 20.1% / 26.2% | 47.6% / 27.1% / 10.5% |
| dumps.numeric-100mib | 2.3% / 2.6% / 0.1% | 27.7% / 74.6% / 10.9% | 56.6% / 12.5% / 46.1% |
| loads.numeric-100mib | 8.4% / 9.2% / 5.2% | 22.4% / 28.0% / 0.0% | 33.1% / 32.3% / 0.1% |
| dumps.nested_unicode-1mib | 30.3% / 15.2% / 27.0% | 38.3% / 25.2% / 31.0% | 33.1% / 13.6% / 0.1% |
| loads.nested_unicode-1mib | 25.2% / 27.3% / 0.6% | 45.3% / 15.1% / 24.7% | 8.1% / 7.8% / 2.4% |
| dumps.nested_unicode-10mib | 50.8% / 27.2% / 36.2% | 26.6% / 46.0% / 9.4% | 41.2% / 10.2% / 1.7% |
| loads.nested_unicode-10mib | 6.0% / 13.9% / 2.9% | 45.1% / 22.2% / 36.0% | 45.7% / 22.1% / 4.0% |
| dumps.nested_unicode-100mib | 3.6% / 6.0% / 1.3% | 49.8% / 20.2% / 33.9% | 6.5% / 7.1% / 2.7% |
| loads.nested_unicode-100mib | 31.6% / 38.7% / 3.0% | 14.7% / 19.4% / 9.7% | 41.7% / 17.3% / 34.9% |

## Artifact identities

- **Pydantic ORJSON** 3.13.0+pydantic.4; native SHA-256 `e068294d53c85c457cdda458e03c617e5d7b354d935de35c307cb7217cf1efe2`.
- **ORJSON** 3.13.0; native SHA-256 `28493f56a8efab6ab67f596eb0dbd82da3a2510bb5a23b160a5bacd873226722`.
- **json** 3.13.12; native SHA-256 `195bf4d1a94d361083124ab3cce00c2315c4d6af26583815fd1082b088a7cc4d`.

Every fixture file's actual length and SHA-256 were verified on disk.

All report, log and memory-probe hashes and the complete declared case/round set were verified. Every regression and unstable case remains visible; no aggregate statistic certifies this library as universally faster.
