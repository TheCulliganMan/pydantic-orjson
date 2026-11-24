# Pydantic ORJSON / ORJSON / json

All durations are microseconds per operation; lower is better. Every encoder returns UTF-8 bytes. The json column includes UTF-8 encoding. Decode uses the same canonical bytes. Typed rows include model conversion/validation and are separate from native JSON performance.

Profile: **standard**; 89 cases; 2 balanced rounds. Complete declared profile.

A win requires every observed worker median to beat the baseline by >1.0%, with worker/sample spread and round drift ≤10.0%. Tolerance is 2.0%; within tolerance is not a win. These are conservative observed bounds, not confidence intervals or a guarantee on unmeasured workloads.

| Case | Pydantic ORJSON µs | ORJSON µs | json µs | Pydantic / ORJSON result | Pydantic / json result |
| --- | ---: | ---: | ---: | --- | --- |
| dumps.scalar.null | 0.023 | 0.043 | 1.074 | win (1.906x/1.902x) | win (47.412x/47.274x) |
| loads.scalar.null | 0.019 | 0.057 | 0.755 | win (3.072x/3.061x) | win (40.754x/40.629x) |
| dumps.scalar.bool | 0.023 | 0.043 | 1.060 | win (1.910x/1.916x) | win (46.685x/48.011x) |
| loads.scalar.bool | 0.019 | 0.057 | 0.755 | win (2.968x/2.982x) | win (39.526x/39.412x) |
| dumps.scalar.int | 0.026 | 0.044 | 1.112 | win (1.733x/1.690x) | win (43.305x/42.012x) |
| loads.scalar.int | 0.049 | 0.069 | 0.817 | win (1.393x/1.395x) | win (16.627x/16.582x) |
| dumps.scalar.float | 0.036 | 0.051 | 1.351 | unstable (1.422x/1.444x) | unstable (37.960x/37.888x) |
| loads.scalar.float | 0.058 | 0.074 | 0.943 | win (1.277x/1.282x) | win (16.401x/16.340x) |
| dumps.scalar.string | 0.046 | 0.044 | 0.526 | unstable (0.969x/0.973x) | win (11.545x/11.535x) |
| loads.scalar.string | 0.034 | 0.072 | 0.787 | win (2.119x/2.107x) | win (22.933x/23.026x) |
| dumps.records.1 | 0.090 | 0.089 | 1.711 | inconclusive (0.981x/0.984x) | win (18.844x/19.043x) |
| loads.records.1 | 0.212 | 0.249 | 1.226 | win (1.180x/1.180x) | unstable (5.741x/5.808x) |
| dumps.records.1.sorted | 0.123 | 0.120 | 1.924 | inconclusive (0.979x/0.979x) | win (15.652x/15.763x) |
| dumps.records.1.pretty | 0.119 | 0.115 | 1.935 | inconclusive (0.973x/0.970x) | win (16.371x/16.155x) |
| dumps.records.1.fastapi_flags | 0.148 | 0.151 | 1.714 | inconclusive (1.019x/1.020x) | win (11.497x/11.652x) |
| dumps.records.16 | 0.859 | 0.852 | 8.146 | unstable (1.000x/0.982x) | unstable (9.539x/9.458x) |
| loads.records.16 | 2.676 | 2.792 | 6.757 | unstable (1.030x/1.055x) | unstable (2.494x/2.567x) |
| dumps.records.16.sorted | 1.119 | 1.073 | 11.089 | regression (0.959x/0.960x) | win (9.898x/9.953x) |
| dumps.records.16.pretty | 1.067 | 1.025 | 9.757 | unstable (0.950x/0.981x) | unstable (9.196x/9.098x) |
| dumps.records.16.fastapi_flags | 1.457 | 1.515 | 8.165 | inconclusive (1.041x/1.038x) | win (5.616x/5.596x) |
| dumps.records.128 | 6.441 | 5.947 | 50.646 | regression (0.918x/0.937x) | win (7.881x/7.865x) |
| loads.records.128 | 21.924 | 22.366 | 45.729 | inconclusive (1.015x/1.022x) | win (2.082x/2.082x) |
| dumps.records.128.sorted | 8.387 | 7.831 | 73.189 | regression (0.932x/0.938x) | win (8.695x/8.772x) |
| dumps.records.128.pretty | 8.438 | 7.655 | 62.689 | unstable (0.915x/0.911x) | win (7.520x/7.370x) |
| dumps.records.128.fastapi_flags | 11.077 | 11.311 | 50.591 | inconclusive (1.013x/1.027x) | win (4.534x/4.578x) |
| dumps.records.1024 | 50.517 | 46.216 | 383.171 | regression (0.914x/0.918x) | win (7.577x/7.599x) |
| loads.records.1024 | 186.220 | 188.482 | 362.975 | inconclusive (1.014x/1.011x) | win (1.959x/1.948x) |
| dumps.records.1024.sorted | 65.717 | 61.315 | 566.599 | regression (0.936x/0.931x) | win (8.638x/8.604x) |
| dumps.records.1024.pretty | 63.875 | 59.937 | 478.535 | regression (0.934x/0.938x) | win (7.497x/7.476x) |
| dumps.records.1024.fastapi_flags | 86.885 | 88.303 | 382.585 | unstable (1.018x/1.016x) | unstable (4.391x/4.411x) |
| dumps.text.ascii.32_chars | 0.055 | 0.053 | 1.308 | regression (0.961x/0.962x) | win (23.796x/23.563x) |
| loads.text.ascii.32_chars | 0.089 | 0.108 | 0.914 | unstable (1.212x/1.209x) | unstable (10.334x/10.222x) |
| dumps.text.ascii.256_chars | 0.059 | 0.056 | 1.652 | regression (0.959x/0.962x) | win (28.156x/28.181x) |
| loads.text.ascii.256_chars | 0.151 | 0.170 | 1.133 | win (1.130x/1.120x) | win (7.484x/7.489x) |
| dumps.text.ascii.4096_chars | 0.211 | 0.213 | 7.085 | within tolerance (1.006x/1.007x) | win (33.494x/33.488x) |
| loads.text.ascii.4096_chars | 1.297 | 1.298 | 3.951 | within tolerance (1.000x/1.002x) | win (3.049x/3.048x) |
| dumps.text.ascii.65536_chars | 1.909 | 1.764 | 92.314 | regression (0.923x/0.925x) | win (48.401x/48.322x) |
| loads.text.ascii.65536_chars | 20.707 | 20.560 | 48.546 | within tolerance (0.993x/0.993x) | win (2.344x/2.345x) |
| dumps.text.unicode.32_chars | 0.056 | 0.054 | 1.427 | regression (0.963x/0.971x) | win (25.560x/25.777x) |
| loads.text.unicode.32_chars | 0.128 | 0.148 | 1.132 | win (1.159x/1.158x) | win (8.867x/8.811x) |
| dumps.text.unicode.256_chars | 0.063 | 0.062 | 2.303 | inconclusive (0.972x/0.976x) | win (36.312x/36.468x) |
| loads.text.unicode.256_chars | 0.620 | 0.531 | 1.802 | regression (0.858x/0.857x) | win (2.901x/2.908x) |
| dumps.text.unicode.4096_chars | 0.276 | 0.306 | 13.441 | win (1.111x/1.108x) | win (48.672x/48.842x) |
| loads.text.unicode.4096_chars | 8.100 | 6.204 | 10.665 | regression (0.765x/0.768x) | win (1.320x/1.315x) |
| dumps.text.unicode.65536_chars | 3.266 | 3.264 | 189.665 | unstable (1.000x/0.988x) | win (58.073x/57.485x) |
| loads.text.unicode.65536_chars | 128.472 | 100.839 | 150.171 | regression (0.785x/0.784x) | win (1.167x/1.169x) |
| dumps.text.escaped.32_chars | 0.071 | 0.070 | 1.308 | inconclusive (0.998x/0.982x) | win (18.481x/18.558x) |
| loads.text.escaped.32_chars | 0.094 | 0.113 | 1.026 | unstable (1.204x/1.202x) | unstable (10.915x/10.864x) |
| dumps.text.escaped.256_chars | 0.154 | 0.279 | 1.695 | win (1.813x/1.806x) | win (10.896x/11.140x) |
| loads.text.escaped.256_chars | 0.195 | 0.207 | 1.690 | inconclusive (1.059x/1.061x) | win (8.669x/8.670x) |
| dumps.text.escaped.4096_chars | 1.753 | 3.835 | 7.178 | win (2.172x/2.205x) | win (4.079x/4.104x) |
| loads.text.escaped.4096_chars | 2.090 | 1.874 | 10.919 | regression (0.897x/0.895x) | win (5.238x/5.219x) |
| dumps.text.escaped.65536_chars | 26.219 | 61.364 | 93.779 | win (2.338x/2.352x) | win (3.569x/3.595x) |
| loads.text.escaped.65536_chars | 33.637 | 31.951 | 148.347 | regression (0.949x/0.952x) | win (4.411x/4.428x) |
| dumps.text.dense_escapes.32_chars | 0.081 | 0.260 | 1.331 | unstable (3.401x/3.055x) | unstable (17.355x/15.650x) |
| loads.text.dense_escapes.32_chars | 0.137 | 0.158 | 1.139 | win (1.157x/1.157x) | win (8.355x/8.353x) |
| dumps.text.dense_escapes.256_chars | 0.263 | 1.689 | 1.765 | win (6.467x/6.416x) | win (6.761x/6.693x) |
| loads.text.dense_escapes.256_chars | 0.584 | 0.596 | 2.293 | inconclusive (1.018x/1.011x) | win (3.926x/3.886x) |
| dumps.text.dense_escapes.4096_chars | 3.319 | 25.718 | 5.896 | win (7.471x/7.837x) | win (1.714x/1.796x) |
| loads.text.dense_escapes.4096_chars | 9.193 | 8.114 | 17.170 | unstable (0.894x/0.882x) | unstable (1.879x/1.868x) |
| dumps.text.dense_escapes.65536_chars | 51.055 | 410.833 | 74.618 | win (8.007x/8.080x) | win (1.457x/1.466x) |
| loads.text.dense_escapes.65536_chars | 147.031 | 132.580 | 250.348 | regression (0.910x/0.883x) | win (1.716x/1.669x) |
| dumps.integers.8 | 0.068 | 0.062 | 1.488 | regression (0.918x/0.920x) | win (21.811x/21.981x) |
| loads.integers.8 | 0.090 | 0.115 | 1.094 | win (1.273x/1.270x) | win (12.171x/12.161x) |
| dumps.floats.8 | 0.164 | 0.168 | 3.104 | win (1.024x/1.032x) | win (18.885x/18.919x) |
| loads.floats.8 | 0.167 | 0.181 | 1.917 | win (1.105x/1.072x) | win (11.591x/11.388x) |
| dumps.integers.128 | 0.392 | 0.414 | 5.297 | win (1.056x/1.055x) | win (13.538x/13.490x) |
| loads.integers.128 | 0.907 | 0.955 | 5.491 | win (1.053x/1.056x) | win (6.048x/6.066x) |
| dumps.floats.128 | 2.091 | 2.135 | 31.833 | unstable (1.023x/0.967x) | unstable (15.200x/14.354x) |
| loads.floats.128 | 2.198 | 2.195 | 19.799 | within tolerance (1.006x/0.994x) | win (9.012x/8.974x) |
| dumps.integers.2048 | 4.447 | 4.969 | 58.891 | win (1.119x/1.119x) | win (13.117x/13.282x) |
| loads.integers.2048 | 22.298 | 21.894 | 74.061 | inconclusive (0.982x/0.982x) | unstable (3.324x/3.352x) |
| dumps.floats.2048 | 32.968 | 33.180 | 491.692 | unstable (1.012x/0.999x) | win (15.002x/14.692x) |
| loads.floats.2048 | 38.967 | 38.620 | 301.886 | inconclusive (0.990x/0.992x) | win (7.737x/7.754x) |
| loads.bytes.64 | 0.089 | 0.109 | 0.931 | win (1.221x/1.252x) | win (10.468x/10.605x) |
| loads.bytes.256 | 0.140 | 0.162 | 1.076 | win (1.151x/1.146x) | win (7.653x/7.626x) |
| loads.bytes.321 | 0.167 | 0.185 | 1.181 | win (1.097x/1.114x) | win (7.014x/7.149x) |
| loads.bytes.322 | 0.167 | 0.187 | 1.178 | win (1.111x/1.115x) | win (7.048x/7.000x) |
| loads.bytes.512 | 0.233 | 0.249 | 1.316 | win (1.043x/1.101x) | win (5.506x/5.829x) |
| loads.bytes.610 | 0.266 | 0.274 | 1.391 | win (1.032x/1.031x) | win (5.254x/5.259x) |
| loads.bytes.611 | 0.289 | 0.272 | 1.393 | regression (0.943x/0.943x) | win (4.816x/4.849x) |
| loads.bytes.4096 | 1.287 | 1.290 | 3.946 | within tolerance (1.001x/1.003x) | win (3.064x/3.069x) |
| loads.bytes.65536 | 20.648 | 20.664 | 48.548 | within tolerance (1.000x/1.001x) | win (2.353x/2.352x) |
| dumps.typed.records.1 | 0.653 | 0.648 | 2.388 | inconclusive (0.987x/0.990x) | win (3.614x/3.668x) |
| loads.typed.records.1 | 0.728 | 0.765 | 1.863 | inconclusive (1.047x/1.055x) | win (2.567x/2.556x) |
| dumps.typed.records.128 | 22.661 | 24.573 | 54.511 | win (1.094x/1.075x) | win (2.448x/2.377x) |
| loads.typed.records.128 | 48.668 | 47.056 | 65.859 | inconclusive (0.970x/0.960x) | win (1.361x/1.331x) |
| dumps.typed.records.1024 | 179.868 | 195.124 | 406.487 | win (1.067x/1.111x) | win (2.219x/2.304x) |
| loads.typed.records.1024 | 525.230 | 514.620 | 655.465 | inconclusive (0.983x/0.975x) | win (1.257x/1.233x) |

Ratios are baseline / Pydantic ORJSON for each round; >1 favors Pydantic ORJSON. Unstable ratios remain visible but are inconclusive evidence.

All tested cases beat both baselines: **NOT PROVEN**. No observed regressions within tolerance: **NOT PROVEN**.

## Installed engine identities

- **Pydantic ORJSON** 3.13.0+pydantic.4; native SHA-256 `1bf72ca91319b9dc6b1c04828eba0d94fa0849d727940ea1983095529d2988f3`.
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
