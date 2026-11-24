# Pydantic ORJSON / ORJSON / json

All durations are microseconds per operation; lower is better. Every encoder returns UTF-8 bytes. The json column includes UTF-8 encoding. Decode uses the same canonical bytes. Typed rows include model conversion/validation and are separate from native JSON performance.

Profile: **standard**; 89 cases; 2 balanced rounds. Complete declared profile.

A win requires every observed worker median to beat the baseline by >1.0%, with worker/sample spread and round drift ≤10.0%. Tolerance is 2.0%; within tolerance is not a win. These are conservative observed bounds, not confidence intervals or a guarantee on unmeasured workloads.

| Case | Pydantic ORJSON µs | ORJSON µs | json µs | Pydantic / ORJSON result | Pydantic / json result |
| --- | ---: | ---: | ---: | --- | --- |
| dumps.scalar.null | 0.038 | 0.070 | 1.698 | unstable (1.788x/1.832x) | unstable (43.726x/44.356x) |
| loads.scalar.null | 0.028 | 0.089 | 1.268 | unstable (3.086x/3.186x) | unstable (43.874x/45.448x) |
| dumps.scalar.bool | 0.037 | 0.070 | 1.695 | win (1.858x/1.952x) | win (45.003x/47.350x) |
| loads.scalar.bool | 0.029 | 0.089 | 1.258 | unstable (3.177x/2.916x) | unstable (45.323x/40.794x) |
| dumps.scalar.int | 0.045 | 0.072 | 1.754 | win (1.622x/1.594x) | win (39.351x/38.508x) |
| loads.scalar.int | 0.074 | 0.106 | 1.345 | unstable (1.453x/1.423x) | unstable (18.533x/18.045x) |
| dumps.scalar.float | 0.062 | 0.093 | 2.085 | win (1.486x/1.506x) | win (33.653x/33.524x) |
| loads.scalar.float | 0.075 | 0.104 | 1.579 | win (1.383x/1.391x) | win (21.143x/21.350x) |
| dumps.scalar.string | 0.074 | 0.074 | 0.882 | inconclusive (1.001x/1.001x) | win (11.818x/12.154x) |
| loads.scalar.string | 0.053 | 0.118 | 1.314 | unstable (2.210x/2.254x) | unstable (24.835x/24.592x) |
| dumps.records.1 | 0.160 | 0.161 | 2.536 | inconclusive (1.015x/0.997x) | win (15.877x/15.708x) |
| loads.records.1 | 0.359 | 0.425 | 1.950 | win (1.179x/1.184x) | win (5.393x/5.488x) |
| dumps.records.1.sorted | 0.223 | 0.207 | 2.837 | regression (0.923x/0.926x) | win (12.596x/12.776x) |
| dumps.records.1.pretty | 0.215 | 0.203 | 2.825 | unstable (0.944x/0.944x) | win (13.215x/13.065x) |
| dumps.records.1.fastapi_flags | 0.256 | 0.263 | 2.553 | unstable (1.044x/1.016x) | unstable (10.058x/9.957x) |
| dumps.records.16 | 1.492 | 1.394 | 11.579 | regression (0.937x/0.933x) | win (7.739x/7.803x) |
| loads.records.16 | 4.428 | 4.524 | 10.096 | inconclusive (1.013x/1.025x) | win (2.278x/2.280x) |
| dumps.records.16.sorted | 2.055 | 1.903 | 15.827 | unstable (0.929x/0.925x) | unstable (7.717x/7.701x) |
| dumps.records.16.pretty | 2.135 | 1.903 | 13.993 | regression (0.902x/0.888x) | win (6.601x/6.546x) |
| dumps.records.16.fastapi_flags | 2.626 | 2.706 | 11.583 | inconclusive (1.061x/1.018x) | win (4.414x/4.404x) |
| dumps.records.128 | 11.440 | 10.757 | 73.717 | regression (0.943x/0.939x) | win (6.402x/6.560x) |
| loads.records.128 | 36.146 | 37.244 | 72.264 | inconclusive (1.033x/1.008x) | win (1.993x/1.999x) |
| dumps.records.128.sorted | 15.867 | 14.988 | 105.030 | inconclusive (0.941x/0.961x) | unstable (6.597x/6.638x) |
| dumps.records.128.pretty | 16.844 | 14.700 | 89.554 | regression (0.866x/0.874x) | win (5.275x/5.339x) |
| dumps.records.128.fastapi_flags | 20.486 | 20.868 | 73.263 | unstable (1.019x/1.062x) | win (3.573x/3.608x) |
| dumps.records.1024 | 91.533 | 85.803 | 575.602 | regression (0.939x/0.936x) | win (6.294x/6.218x) |
| loads.records.1024 | 314.025 | 321.207 | 576.833 | inconclusive (1.020x/1.027x) | win (1.827x/1.852x) |
| dumps.records.1024.sorted | 126.655 | 116.536 | 813.143 | unstable (0.920x/0.923x) | unstable (6.353x/6.445x) |
| dumps.records.1024.pretty | 133.405 | 116.888 | 702.057 | regression (0.878x/0.881x) | unstable (5.327x/5.233x) |
| dumps.records.1024.fastapi_flags | 163.434 | 164.903 | 563.032 | inconclusive (1.008x/1.012x) | win (3.432x/3.452x) |
| dumps.text.ascii.32_chars | 0.093 | 0.105 | 2.029 | win (1.120x/1.117x) | win (21.722x/21.780x) |
| loads.text.ascii.32_chars | 0.139 | 0.185 | 1.508 | win (1.332x/1.328x) | win (10.763x/10.981x) |
| dumps.text.ascii.256_chars | 0.108 | 0.119 | 2.525 | win (1.099x/1.117x) | win (23.196x/23.720x) |
| loads.text.ascii.256_chars | 0.219 | 0.258 | 1.869 | win (1.169x/1.181x) | win (8.491x/8.510x) |
| dumps.text.ascii.4096_chars | 0.437 | 0.396 | 10.655 | regression (0.906x/0.908x) | win (24.425x/24.298x) |
| loads.text.ascii.4096_chars | 1.666 | 1.431 | 7.121 | regression (0.860x/0.858x) | win (4.299x/4.260x) |
| dumps.text.ascii.65536_chars | 4.220 | 4.095 | 138.697 | regression (0.972x/0.969x) | unstable (32.861x/32.873x) |
| loads.text.ascii.65536_chars | 24.711 | 21.035 | 92.170 | regression (0.851x/0.851x) | win (3.729x/3.724x) |
| dumps.text.unicode.32_chars | 0.095 | 0.107 | 2.192 | win (1.124x/1.136x) | win (23.165x/23.018x) |
| loads.text.unicode.32_chars | 0.230 | 0.278 | 1.939 | win (1.210x/1.213x) | win (8.488x/8.388x) |
| dumps.text.unicode.256_chars | 0.126 | 0.148 | 3.233 | unstable (1.167x/1.173x) | win (25.502x/25.698x) |
| loads.text.unicode.256_chars | 0.774 | 0.763 | 3.044 | inconclusive (0.990x/0.973x) | win (3.943x/3.931x) |
| dumps.text.unicode.4096_chars | 0.666 | 0.660 | 16.225 | unstable (0.986x/0.990x) | win (24.242x/24.388x) |
| loads.text.unicode.4096_chars | 9.099 | 8.200 | 18.091 | regression (0.914x/0.897x) | win (1.982x/1.992x) |
| dumps.text.unicode.65536_chars | 7.858 | 7.731 | 228.757 | inconclusive (0.989x/0.981x) | win (28.984x/29.208x) |
| loads.text.unicode.65536_chars | 143.430 | 137.630 | 263.930 | unstable (0.968x/0.938x) | win (1.841x/1.840x) |
| dumps.text.escaped.32_chars | 0.113 | 0.124 | 2.045 | win (1.096x/1.095x) | win (18.134x/17.977x) |
| loads.text.escaped.32_chars | 0.155 | 0.196 | 1.678 | unstable (1.261x/1.266x) | unstable (10.836x/10.776x) |
| dumps.text.escaped.256_chars | 0.246 | 0.315 | 2.615 | unstable (1.282x/1.271x) | unstable (10.675x/10.513x) |
| loads.text.escaped.256_chars | 0.312 | 0.353 | 2.582 | win (1.126x/1.138x) | win (8.238x/8.276x) |
| dumps.text.escaped.4096_chars | 2.663 | 3.720 | 11.726 | win (1.397x/1.398x) | win (4.390x/4.439x) |
| loads.text.escaped.4096_chars | 2.790 | 2.653 | 14.511 | unstable (0.951x/0.964x) | win (5.200x/5.195x) |
| dumps.text.escaped.65536_chars | 40.452 | 55.580 | 152.955 | win (1.379x/1.373x) | win (3.799x/3.771x) |
| loads.text.escaped.65536_chars | 44.786 | 40.974 | 196.972 | regression (0.915x/0.914x) | win (4.387x/4.421x) |
| dumps.text.dense_escapes.32_chars | 0.131 | 0.230 | 2.040 | win (1.767x/1.746x) | unstable (15.659x/15.524x) |
| loads.text.dense_escapes.32_chars | 0.223 | 0.309 | 1.839 | win (1.383x/1.419x) | win (8.228x/8.404x) |
| dumps.text.dense_escapes.256_chars | 0.424 | 1.501 | 2.711 | win (3.530x/3.546x) | win (6.399x/6.373x) |
| loads.text.dense_escapes.256_chars | 0.932 | 1.800 | 3.437 | win (1.944x/1.926x) | win (3.678x/3.705x) |
| dumps.text.dense_escapes.4096_chars | 5.163 | 23.257 | 11.062 | win (4.514x/4.507x) | win (2.146x/2.152x) |
| loads.text.dense_escapes.4096_chars | 12.657 | 27.099 | 25.902 | unstable (2.166x/2.141x) | unstable (2.070x/2.042x) |
| dumps.text.dense_escapes.65536_chars | 78.986 | 369.824 | 147.169 | win (4.676x/4.687x) | win (1.861x/1.865x) |
| loads.text.dense_escapes.65536_chars | 206.366 | 435.589 | 386.748 | win (2.112x/2.183x) | unstable (1.841x/1.975x) |
| dumps.integers.8 | 0.122 | 0.103 | 2.247 | regression (0.839x/0.853x) | win (18.476x/18.544x) |
| loads.integers.8 | 0.144 | 0.183 | 1.725 | win (1.269x/1.279x) | win (12.012x/12.006x) |
| dumps.floats.8 | 0.271 | 0.286 | 4.605 | unstable (1.057x/1.052x) | unstable (17.028x/16.943x) |
| loads.floats.8 | 0.269 | 0.284 | 2.907 | unstable (1.050x/1.063x) | unstable (10.764x/10.956x) |
| dumps.integers.128 | 0.539 | 0.592 | 8.260 | win (1.092x/1.112x) | win (15.329x/15.261x) |
| loads.integers.128 | 1.377 | 1.353 | 8.272 | unstable (0.983x/0.982x) | unstable (5.984x/5.999x) |
| dumps.floats.128 | 3.446 | 3.462 | 47.930 | inconclusive (1.005x/1.000x) | win (13.904x/13.850x) |
| loads.floats.128 | 3.744 | 3.144 | 29.773 | regression (0.828x/0.849x) | win (7.947x/7.946x) |
| dumps.integers.2048 | 7.946 | 7.975 | 102.838 | inconclusive (0.995x/1.015x) | unstable (12.831x/12.962x) |
| loads.integers.2048 | 41.600 | 38.985 | 116.611 | regression (0.937x/0.941x) | win (2.813x/2.805x) |
| dumps.floats.2048 | 53.024 | 52.794 | 739.871 | within tolerance (0.998x/0.993x) | win (14.059x/13.901x) |
| loads.floats.2048 | 71.513 | 60.311 | 460.175 | regression (0.852x/0.838x) | win (6.494x/6.396x) |
| loads.bytes.64 | 0.135 | 0.189 | 1.556 | unstable (1.388x/1.403x) | unstable (11.452x/11.564x) |
| loads.bytes.256 | 0.207 | 0.248 | 1.821 | win (1.201x/1.199x) | win (8.809x/8.810x) |
| loads.bytes.321 | 0.243 | 0.276 | 1.933 | win (1.128x/1.134x) | win (7.926x/7.929x) |
| loads.bytes.322 | 0.240 | 0.277 | 1.929 | win (1.157x/1.143x) | win (8.112x/7.946x) |
| loads.bytes.512 | 0.307 | 0.329 | 2.208 | win (1.079x/1.064x) | win (7.238x/7.131x) |
| loads.bytes.610 | 0.349 | 0.364 | 2.341 | inconclusive (1.042x/1.051x) | win (6.710x/6.756x) |
| loads.bytes.611 | 0.396 | 0.363 | 2.356 | regression (0.917x/0.926x) | win (5.970x/5.952x) |
| loads.bytes.4096 | 1.644 | 1.417 | 7.114 | regression (0.863x/0.860x) | win (4.331x/4.318x) |
| loads.bytes.65536 | 24.595 | 20.974 | 90.826 | regression (0.851x/0.855x) | win (3.685x/3.717x) |
| dumps.typed.records.1 | 1.096 | 1.099 | 3.406 | unstable (1.014x/1.002x) | win (3.116x/3.108x) |
| loads.typed.records.1 | 1.186 | 1.327 | 2.835 | win (1.110x/1.128x) | win (2.370x/2.423x) |
| dumps.typed.records.128 | 39.257 | 40.759 | 81.820 | inconclusive (1.051x/1.032x) | win (2.089x/2.073x) |
| loads.typed.records.128 | 74.475 | 78.609 | 103.837 | win (1.046x/1.063x) | win (1.396x/1.391x) |
| dumps.typed.records.1024 | 311.466 | 335.352 | 635.081 | win (1.071x/1.070x) | win (2.055x/2.009x) |
| loads.typed.records.1024 | 787.849 | 820.811 | 997.117 | unstable (1.034x/1.052x) | unstable (1.265x/1.268x) |

Ratios are baseline / Pydantic ORJSON for each round; >1 favors Pydantic ORJSON. Unstable ratios remain visible but are inconclusive evidence.

All tested cases beat both baselines: **NOT PROVEN**. No observed regressions within tolerance: **NOT PROVEN**.

## Installed engine identities

- **Pydantic ORJSON** 3.13.0+pydantic.4; native SHA-256 `c7cd51b8c3677fbe1888f2f7901075fc31d09df86b5909e39d0cdf2a7c33a1d0`.
- **ORJSON** 3.13.0; native SHA-256 `6e99b08269e8b155d8131f0ec290db8f5d491638e8fc05f08cc138aaa6a8baa4`.
- **json** 3.13.18; native SHA-256 `920a02c4e61bec1cbb191868488f4a3d92ef1f6cbae5b867c1aeffe0bc7761af`.

## Unsupported native capabilities

These capabilities are not assigned fake timings or zeroes. They are outside the common-data matrix.

- `native_datetime` — **json: unsupported.** Requires a user default callback; json has no native datetime encoder.
- `native_numpy` — **json: unsupported.** Requires a user default callback; json has no OPT_SERIALIZE_NUMPY.
- `native_fragment` — **json: unsupported.** No equivalent to orjson.Fragment.
- `pydantic_ai_message_json` — **ORJSON: unsupported.** No built-in Pydantic AI persistence helper; compose the official adapter separately.
- `pydantic_ai_message_json` — **json: unsupported.** No built-in Pydantic AI persistence helper; compose the official adapter separately.

FastAPI-flags rows measure serialization of ordinary record data with ORJSONResponse's flags. json produces equivalent JSON for those fixtures; it has no equivalent NumPy/non-string-key extension flags. These rows do not measure HTTP throughput.

Typed rows compare Codec's direct TypeAdapter JSON calls with explicit dump_python + encoder / parser + validate_python pipelines. Every user can call that same direct TypeAdapter API without this package; these rows do not claim a faster Pydantic core or the best possible upstream typed workflow. See the separate source/adapter engineering controls.
