# Pydantic ORJSON / ORJSON / json

All durations are microseconds per operation; lower is better. Every encoder returns UTF-8 bytes. The json column includes UTF-8 encoding. Decode uses the same canonical bytes. Typed rows include model conversion/validation and are separate from native JSON performance.

Profile: **standard**; 89 cases; 2 balanced rounds. Complete declared profile.

A win requires every observed worker median to beat the baseline by >1.0%, with worker/sample spread and round drift ≤10.0%. Tolerance is 2.0%; within tolerance is not a win. These are conservative observed bounds, not confidence intervals or a guarantee on unmeasured workloads.

| Case | Pydantic ORJSON µs | ORJSON µs | json µs | Pydantic / ORJSON result | Pydantic / json result |
| --- | ---: | ---: | ---: | --- | --- |
| dumps.scalar.null | 0.039 | 0.078 | 1.431 | win (1.989x/1.988x) | win (36.511x/36.448x) |
| loads.scalar.null | 0.029 | 0.097 | 1.085 | win (3.308x/3.317x) | win (37.145x/37.209x) |
| dumps.scalar.bool | 0.040 | 0.078 | 1.426 | unstable (1.935x/1.962x) | win (35.226x/35.953x) |
| loads.scalar.bool | 0.029 | 0.097 | 1.083 | win (3.295x/3.348x) | win (36.913x/37.201x) |
| dumps.scalar.int | 0.045 | 0.082 | 1.475 | win (1.791x/1.800x) | win (32.315x/32.310x) |
| loads.scalar.int | 0.070 | 0.113 | 1.153 | win (1.622x/1.618x) | win (16.466x/16.512x) |
| dumps.scalar.float | 0.062 | 0.101 | 1.760 | unstable (1.661x/1.637x) | win (28.526x/28.461x) |
| loads.scalar.float | 0.070 | 0.114 | 1.313 | win (1.631x/1.632x) | win (18.779x/18.883x) |
| dumps.scalar.string | 0.096 | 0.083 | 0.761 | unstable (0.914x/0.859x) | win (7.885x/7.999x) |
| loads.scalar.string | 0.061 | 0.120 | 1.120 | win (1.975x/1.965x) | win (18.335x/18.338x) |
| dumps.records.1 | 0.173 | 0.165 | 2.196 | regression (0.953x/0.956x) | win (12.771x/12.644x) |
| loads.records.1 | 0.317 | 0.370 | 1.650 | win (1.162x/1.180x) | win (5.199x/5.217x) |
| dumps.records.1.sorted | 0.228 | 0.220 | 2.424 | inconclusive (0.967x/0.959x) | win (10.600x/10.590x) |
| dumps.records.1.pretty | 0.213 | 0.203 | 2.469 | regression (0.957x/0.953x) | win (11.604x/11.565x) |
| dumps.records.1.fastapi_flags | 0.261 | 0.265 | 2.197 | inconclusive (1.013x/1.017x) | win (8.422x/8.392x) |
| dumps.records.16 | 1.281 | 1.298 | 10.897 | inconclusive (1.012x/1.018x) | win (8.509x/8.533x) |
| loads.records.16 | 3.940 | 3.983 | 9.515 | inconclusive (1.007x/1.009x) | win (2.391x/2.428x) |
| dumps.records.16.sorted | 1.782 | 1.824 | 14.459 | win (1.024x/1.023x) | win (8.157x/8.082x) |
| dumps.records.16.pretty | 1.610 | 1.607 | 12.979 | inconclusive (0.998x/0.997x) | win (8.038x/8.059x) |
| dumps.records.16.fastapi_flags | 2.343 | 2.593 | 10.899 | win (1.107x/1.105x) | win (4.652x/4.651x) |
| dumps.records.128 | 9.596 | 9.689 | 70.460 | within tolerance (1.010x/1.009x) | win (7.341x/7.384x) |
| loads.records.128 | 32.477 | 32.755 | 69.808 | inconclusive (1.007x/1.006x) | win (2.143x/2.148x) |
| dumps.records.128.sorted | 13.341 | 13.671 | 98.005 | win (1.024x/1.025x) | win (7.330x/7.467x) |
| dumps.records.128.pretty | 12.057 | 11.969 | 84.781 | within tolerance (0.992x/0.993x) | win (7.032x/7.032x) |
| dumps.records.128.fastapi_flags | 18.050 | 19.938 | 70.638 | win (1.104x/1.105x) | win (3.898x/3.930x) |
| dumps.records.1024 | 74.541 | 75.218 | 547.774 | within tolerance (1.011x/1.008x) | win (7.365x/7.343x) |
| loads.records.1024 | 290.567 | 293.795 | 571.896 | inconclusive (1.004x/1.015x) | win (1.986x/1.960x) |
| dumps.records.1024.sorted | 105.211 | 107.600 | 770.458 | win (1.023x/1.022x) | win (7.323x/7.328x) |
| dumps.records.1024.pretty | 94.694 | 94.075 | 659.811 | within tolerance (0.994x/0.993x) | win (6.961x/6.989x) |
| dumps.records.1024.fastapi_flags | 143.061 | 157.051 | 549.104 | win (1.096x/1.101x) | win (3.832x/3.864x) |
| dumps.text.ascii.32_chars | 0.116 | 0.103 | 1.744 | regression (0.887x/0.889x) | win (15.038x/14.962x) |
| loads.text.ascii.32_chars | 0.129 | 0.176 | 1.250 | win (1.358x/1.368x) | win (9.627x/9.717x) |
| dumps.text.ascii.256_chars | 0.126 | 0.118 | 2.272 | regression (0.938x/0.940x) | win (18.003x/18.182x) |
| loads.text.ascii.256_chars | 0.199 | 0.255 | 1.489 | win (1.277x/1.286x) | win (7.482x/7.470x) |
| dumps.text.ascii.4096_chars | 0.462 | 0.523 | 11.244 | win (1.133x/1.131x) | win (24.362x/24.298x) |
| loads.text.ascii.4096_chars | 1.487 | 1.640 | 4.774 | win (1.108x/1.101x) | win (3.206x/3.229x) |
| dumps.text.ascii.65536_chars | 4.357 | 5.111 | 152.215 | win (1.173x/1.172x) | win (34.945x/34.938x) |
| loads.text.ascii.65536_chars | 20.280 | 22.902 | 55.668 | win (1.129x/1.129x) | win (2.746x/2.744x) |
| dumps.text.unicode.32_chars | 0.123 | 0.106 | 1.833 | unstable (0.868x/0.864x) | win (14.995x/14.873x) |
| loads.text.unicode.32_chars | 0.208 | 0.244 | 1.537 | win (1.174x/1.168x) | win (7.382x/7.390x) |
| dumps.text.unicode.256_chars | 0.136 | 0.149 | 2.896 | win (1.103x/1.060x) | win (21.409x/21.265x) |
| loads.text.unicode.256_chars | 0.760 | 0.724 | 2.296 | regression (0.954x/0.952x) | win (3.013x/3.025x) |
| dumps.text.unicode.4096_chars | 0.702 | 0.793 | 17.014 | win (1.130x/1.183x) | win (24.251x/25.443x) |
| loads.text.unicode.4096_chars | 9.753 | 8.041 | 11.595 | regression (0.821x/0.831x) | win (1.185x/1.198x) |
| dumps.text.unicode.65536_chars | 8.128 | 9.561 | 246.624 | win (1.176x/1.177x) | win (30.338x/30.437x) |
| loads.text.unicode.65536_chars | 150.354 | 125.933 | 161.345 | regression (0.834x/0.839x) | win (1.069x/1.076x) |
| dumps.text.escaped.32_chars | 0.131 | 0.133 | 1.742 | win (1.019x/1.028x) | win (13.363x/13.304x) |
| loads.text.escaped.32_chars | 0.140 | 0.187 | 1.375 | win (1.339x/1.344x) | win (9.854x/9.849x) |
| dumps.text.escaped.256_chars | 0.241 | 0.397 | 2.258 | win (1.647x/1.657x) | win (9.401x/9.372x) |
| loads.text.escaped.256_chars | 0.251 | 0.301 | 2.008 | win (1.200x/1.199x) | win (8.018x/7.994x) |
| dumps.text.escaped.4096_chars | 2.133 | 4.979 | 10.997 | win (2.334x/2.335x) | win (5.154x/5.162x) |
| loads.text.escaped.4096_chars | 2.136 | 2.197 | 9.751 | win (1.030x/1.029x) | win (4.522x/4.567x) |
| dumps.text.escaped.65536_chars | 30.935 | 76.795 | 148.525 | win (2.482x/2.482x) | win (4.810x/4.796x) |
| loads.text.escaped.65536_chars | 31.205 | 31.917 | 121.029 | win (1.024x/1.023x) | win (3.875x/3.889x) |
| dumps.text.dense_escapes.32_chars | 0.139 | 0.265 | 1.741 | win (1.905x/1.908x) | win (12.498x/12.555x) |
| loads.text.dense_escapes.32_chars | 0.185 | 0.231 | 1.507 | win (1.249x/1.247x) | win (8.150x/8.111x) |
| dumps.text.dense_escapes.256_chars | 0.313 | 2.010 | 2.329 | win (6.436x/6.542x) | win (7.464x/7.587x) |
| loads.text.dense_escapes.256_chars | 0.570 | 0.615 | 2.583 | win (1.080x/1.096x) | win (4.537x/4.530x) |
| dumps.text.dense_escapes.4096_chars | 3.354 | 32.196 | 10.615 | win (9.602x/9.597x) | win (3.169x/3.164x) |
| loads.text.dense_escapes.4096_chars | 7.259 | 7.254 | 15.936 | within tolerance (0.999x/1.001x) | win (2.197x/2.194x) |
| dumps.text.dense_escapes.65536_chars | 51.237 | 517.723 | 142.728 | win (10.106x/10.100x) | win (2.785x/2.786x) |
| loads.text.dense_escapes.65536_chars | 113.242 | 113.336 | 217.689 | inconclusive (1.001x/1.000x) | win (1.913x/1.928x) |
| dumps.integers.8 | 0.122 | 0.112 | 1.998 | inconclusive (0.917x/0.918x) | win (16.383x/16.451x) |
| loads.integers.8 | 0.126 | 0.173 | 1.555 | unstable (1.376x/1.382x) | unstable (12.385x/12.424x) |
| dumps.floats.8 | 0.248 | 0.272 | 3.964 | win (1.098x/1.100x) | win (15.938x/15.972x) |
| loads.floats.8 | 0.225 | 0.281 | 2.559 | win (1.252x/1.246x) | win (11.633x/11.325x) |
| dumps.integers.128 | 0.515 | 0.608 | 7.807 | unstable (1.180x/1.181x) | win (15.087x/15.365x) |
| loads.integers.128 | 0.897 | 1.008 | 8.303 | win (1.125x/1.124x) | win (9.255x/9.248x) |
| dumps.floats.128 | 2.346 | 3.128 | 41.081 | win (1.336x/1.323x) | win (17.502x/17.513x) |
| loads.floats.128 | 2.833 | 2.988 | 27.516 | win (1.056x/1.055x) | win (9.713x/9.719x) |
| dumps.integers.2048 | 7.565 | 7.863 | 96.108 | unstable (1.040x/1.039x) | unstable (12.765x/12.593x) |
| loads.integers.2048 | 33.988 | 34.999 | 124.066 | inconclusive (1.025x/1.036x) | win (3.629x/3.673x) |
| dumps.floats.2048 | 35.818 | 52.272 | 627.500 | win (1.458x/1.458x) | win (17.524x/17.694x) |
| loads.floats.2048 | 54.070 | 55.776 | 434.201 | win (1.030x/1.031x) | win (7.989x/8.196x) |
| loads.bytes.64 | 0.130 | 0.178 | 1.272 | win (1.370x/1.371x) | win (9.825x/9.778x) |
| loads.bytes.256 | 0.191 | 0.246 | 1.438 | win (1.293x/1.288x) | win (7.548x/7.532x) |
| loads.bytes.321 | 0.215 | 0.273 | 1.539 | win (1.269x/1.288x) | win (7.149x/7.256x) |
| loads.bytes.322 | 0.215 | 0.273 | 1.535 | win (1.267x/1.270x) | win (7.119x/7.125x) |
| loads.bytes.512 | 0.279 | 0.345 | 1.692 | win (1.234x/1.257x) | win (6.080x/6.160x) |
| loads.bytes.610 | 0.316 | 0.384 | 1.777 | win (1.215x/1.216x) | win (5.623x/5.639x) |
| loads.bytes.611 | 0.363 | 0.384 | 1.777 | win (1.058x/1.058x) | win (4.893x/4.892x) |
| loads.bytes.4096 | 1.467 | 1.637 | 4.764 | win (1.115x/1.118x) | win (3.248x/3.246x) |
| loads.bytes.65536 | 20.182 | 22.858 | 55.698 | win (1.133x/1.130x) | win (2.760x/2.754x) |
| dumps.typed.records.1 | 0.895 | 0.909 | 2.864 | inconclusive (1.011x/1.032x) | win (3.196x/3.215x) |
| loads.typed.records.1 | 1.015 | 1.058 | 2.363 | win (1.037x/1.057x) | win (2.328x/2.334x) |
| dumps.typed.records.128 | 33.579 | 40.002 | 80.046 | win (1.188x/1.195x) | win (2.383x/2.384x) |
| loads.typed.records.128 | 69.001 | 73.065 | 101.370 | inconclusive (1.066x/1.051x) | win (1.490x/1.452x) |
| dumps.typed.records.1024 | 266.449 | 336.123 | 635.298 | win (1.266x/1.259x) | win (2.388x/2.382x) |
| loads.typed.records.1024 | 759.935 | 772.115 | 978.659 | inconclusive (1.013x/1.020x) | win (1.289x/1.287x) |

Ratios are baseline / Pydantic ORJSON for each round; >1 favors Pydantic ORJSON. Unstable ratios remain visible but are inconclusive evidence.

All tested cases beat both baselines: **NOT PROVEN**. No observed regressions within tolerance: **NOT PROVEN**.

## Installed engine identities

- **Pydantic ORJSON** 3.13.0+pydantic.4; native SHA-256 `cdc06d673b6dafdda090cc3c40699c82650e7887452488308813edeb1d2b6c1e`.
- **ORJSON** 3.13.0; native SHA-256 `517e7d2707defdb785b6fdd213d0ea18f6ff0057878c214756f057a46b3cc838`.
- **json** 3.13.18; native SHA-256 `85717866e5c4ca64f6f7756e073199c0fb55f215f0dd7c4a6c0154eb64497bb9`.

## Unsupported native capabilities

These capabilities are not assigned fake timings or zeroes. They are outside the common-data matrix.

- `native_datetime` — **json: unsupported.** Requires a user default callback; json has no native datetime encoder.
- `native_numpy` — **json: unsupported.** Requires a user default callback; json has no OPT_SERIALIZE_NUMPY.
- `native_fragment` — **json: unsupported.** No equivalent to orjson.Fragment.
- `pydantic_ai_message_json` — **ORJSON: unsupported.** No built-in Pydantic AI persistence helper; compose the official adapter separately.
- `pydantic_ai_message_json` — **json: unsupported.** No built-in Pydantic AI persistence helper; compose the official adapter separately.

FastAPI-flags rows measure serialization of ordinary record data with ORJSONResponse's flags. json produces equivalent JSON for those fixtures; it has no equivalent NumPy/non-string-key extension flags. These rows do not measure HTTP throughput.

Typed rows compare Codec's direct TypeAdapter JSON calls with explicit dump_python + encoder / parser + validate_python pipelines. Every user can call that same direct TypeAdapter API without this package; these rows do not claim a faster Pydantic core or the best possible upstream typed workflow. See the separate source/adapter engineering controls.
