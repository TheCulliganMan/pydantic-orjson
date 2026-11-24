# Pydantic ORJSON / ORJSON / json

All durations are microseconds per operation; lower is better. Every encoder returns UTF-8 bytes. The json column includes UTF-8 encoding. Decode uses the same canonical bytes. Typed rows include model conversion/validation and are separate from native JSON performance.

Profile: **standard**; 89 cases; 2 balanced rounds. Complete declared profile.

A win requires every observed worker median to beat the baseline by >1.0%, with worker/sample spread and round drift ≤10.0%. Tolerance is 2.0%; within tolerance is not a win. These are conservative observed bounds, not confidence intervals or a guarantee on unmeasured workloads.

| Case | Pydantic ORJSON µs | ORJSON µs | json µs | Pydantic / ORJSON result | Pydantic / json result |
| --- | ---: | ---: | ---: | --- | --- |
| dumps.scalar.null | 0.039 | 0.078 | 1.429 | win (1.990x/1.987x) | win (36.611x/36.456x) |
| loads.scalar.null | 0.029 | 0.097 | 1.083 | win (3.306x/3.317x) | win (37.018x/37.223x) |
| dumps.scalar.bool | 0.040 | 0.078 | 1.438 | win (1.961x/1.960x) | win (36.092x/36.060x) |
| loads.scalar.bool | 0.029 | 0.097 | 1.081 | win (3.342x/3.303x) | win (37.247x/36.900x) |
| dumps.scalar.int | 0.045 | 0.082 | 1.468 | unstable (1.809x/1.811x) | win (32.483x/32.444x) |
| loads.scalar.int | 0.068 | 0.114 | 1.150 | win (1.680x/1.684x) | win (16.974x/17.016x) |
| dumps.scalar.float | 0.062 | 0.101 | 1.753 | unstable (1.730x/1.642x) | win (28.401x/28.430x) |
| loads.scalar.float | 0.067 | 0.114 | 1.312 | win (1.707x/1.698x) | win (19.700x/19.498x) |
| dumps.scalar.string | 0.096 | 0.083 | 0.761 | regression (0.858x/0.859x) | win (7.929x/7.907x) |
| loads.scalar.string | 0.060 | 0.120 | 1.113 | win (1.993x/1.994x) | win (18.458x/18.571x) |
| dumps.records.1 | 0.171 | 0.165 | 2.197 | inconclusive (0.961x/0.962x) | win (12.826x/12.825x) |
| loads.records.1 | 0.317 | 0.368 | 1.647 | win (1.153x/1.165x) | win (5.159x/5.214x) |
| dumps.records.1.sorted | 0.230 | 0.220 | 2.415 | inconclusive (0.960x/0.958x) | win (10.523x/10.523x) |
| dumps.records.1.pretty | 0.212 | 0.203 | 2.472 | regression (0.961x/0.954x) | win (11.637x/11.630x) |
| dumps.records.1.fastapi_flags | 0.260 | 0.267 | 2.193 | inconclusive (1.018x/1.039x) | win (8.445x/8.440x) |
| dumps.records.16 | 1.270 | 1.298 | 10.881 | win (1.021x/1.028x) | win (8.577x/8.568x) |
| loads.records.16 | 3.971 | 3.939 | 9.504 | inconclusive (0.991x/0.994x) | win (2.402x/2.379x) |
| dumps.records.16.sorted | 1.774 | 1.823 | 14.472 | win (1.026x/1.029x) | win (8.184x/8.136x) |
| dumps.records.16.pretty | 1.608 | 1.606 | 12.879 | within tolerance (0.998x/1.001x) | win (8.002x/8.033x) |
| dumps.records.16.fastapi_flags | 2.344 | 2.586 | 10.918 | win (1.104x/1.103x) | win (4.663x/4.644x) |
| dumps.records.128 | 9.585 | 9.693 | 70.463 | inconclusive (1.011x/1.009x) | win (7.337x/7.362x) |
| loads.records.128 | 32.653 | 32.708 | 69.800 | inconclusive (1.003x/1.001x) | win (2.140x/2.142x) |
| dumps.records.128.sorted | 13.378 | 13.675 | 98.035 | win (1.022x/1.022x) | win (7.368x/7.322x) |
| dumps.records.128.pretty | 12.094 | 11.972 | 84.546 | within tolerance (0.991x/0.989x) | win (7.003x/6.981x) |
| dumps.records.128.fastapi_flags | 18.105 | 19.932 | 70.533 | win (1.099x/1.101x) | win (3.889x/3.900x) |
| dumps.records.1024 | 74.150 | 75.252 | 547.398 | inconclusive (1.016x/1.016x) | win (7.408x/7.373x) |
| loads.records.1024 | 290.805 | 294.828 | 574.162 | inconclusive (1.014x/1.011x) | win (1.975x/1.959x) |
| dumps.records.1024.sorted | 105.232 | 107.587 | 770.894 | win (1.023x/1.022x) | win (7.424x/7.255x) |
| dumps.records.1024.pretty | 95.029 | 94.176 | 661.124 | within tolerance (0.989x/0.993x) | win (6.970x/6.941x) |
| dumps.records.1024.fastapi_flags | 143.138 | 157.952 | 548.044 | win (1.103x/1.102x) | win (3.825x/3.829x) |
| dumps.text.ascii.32_chars | 0.116 | 0.103 | 1.739 | regression (0.893x/0.895x) | win (15.043x/15.056x) |
| loads.text.ascii.32_chars | 0.133 | 0.176 | 1.249 | win (1.325x/1.324x) | win (9.439x/9.390x) |
| dumps.text.ascii.256_chars | 0.125 | 0.118 | 2.263 | unstable (0.984x/0.940x) | win (18.040x/18.080x) |
| loads.text.ascii.256_chars | 0.211 | 0.265 | 1.490 | win (1.235x/1.259x) | win (7.045x/7.074x) |
| dumps.text.ascii.4096_chars | 0.461 | 0.523 | 11.231 | win (1.135x/1.136x) | win (24.407x/24.354x) |
| loads.text.ascii.4096_chars | 1.644 | 1.639 | 4.768 | within tolerance (0.998x/0.996x) | win (2.894x/2.909x) |
| dumps.text.ascii.65536_chars | 4.356 | 5.110 | 152.347 | win (1.173x/1.173x) | win (34.969x/34.963x) |
| loads.text.ascii.65536_chars | 22.874 | 22.897 | 55.692 | within tolerance (1.001x/1.001x) | win (2.435x/2.434x) |
| dumps.text.unicode.32_chars | 0.123 | 0.108 | 1.847 | unstable (0.920x/0.867x) | win (15.088x/14.987x) |
| loads.text.unicode.32_chars | 0.202 | 0.244 | 1.539 | win (1.206x/1.237x) | win (7.615x/7.648x) |
| dumps.text.unicode.256_chars | 0.135 | 0.149 | 2.904 | win (1.104x/1.105x) | win (21.452x/21.466x) |
| loads.text.unicode.256_chars | 0.723 | 0.725 | 2.296 | inconclusive (1.001x/1.001x) | win (3.171x/3.181x) |
| dumps.text.unicode.4096_chars | 0.700 | 0.793 | 17.081 | unstable (1.131x/1.134x) | unstable (24.406x/24.395x) |
| loads.text.unicode.4096_chars | 8.821 | 8.042 | 11.597 | regression (0.911x/0.912x) | win (1.315x/1.314x) |
| dumps.text.unicode.65536_chars | 8.127 | 9.561 | 246.508 | win (1.176x/1.177x) | win (30.353x/30.340x) |
| loads.text.unicode.65536_chars | 138.790 | 125.936 | 161.731 | regression (0.908x/0.906x) | win (1.168x/1.163x) |
| dumps.text.escaped.32_chars | 0.131 | 0.133 | 1.742 | win (1.019x/1.012x) | win (13.303x/13.289x) |
| loads.text.escaped.32_chars | 0.143 | 0.188 | 1.382 | win (1.347x/1.309x) | win (9.612x/9.654x) |
| dumps.text.escaped.256_chars | 0.241 | 0.396 | 2.262 | win (1.643x/1.644x) | win (9.371x/9.396x) |
| loads.text.escaped.256_chars | 0.255 | 0.301 | 2.013 | win (1.182x/1.183x) | win (7.902x/7.903x) |
| dumps.text.escaped.4096_chars | 2.159 | 4.983 | 10.986 | win (2.307x/2.308x) | win (5.089x/5.086x) |
| loads.text.escaped.4096_chars | 2.150 | 2.195 | 9.739 | win (1.022x/1.022x) | win (4.533x/4.528x) |
| dumps.text.escaped.65536_chars | 31.228 | 76.794 | 148.378 | win (2.458x/2.461x) | win (4.748x/4.756x) |
| loads.text.escaped.65536_chars | 31.313 | 31.925 | 121.537 | win (1.022x/1.020x) | win (3.885x/3.882x) |
| dumps.text.dense_escapes.32_chars | 0.138 | 0.265 | 1.736 | win (1.902x/1.921x) | win (12.530x/12.548x) |
| loads.text.dense_escapes.32_chars | 0.183 | 0.232 | 1.502 | win (1.258x/1.265x) | win (8.161x/8.220x) |
| dumps.text.dense_escapes.256_chars | 0.313 | 2.008 | 2.337 | win (6.426x/6.413x) | win (7.460x/7.467x) |
| loads.text.dense_escapes.256_chars | 0.558 | 0.619 | 2.587 | win (1.104x/1.118x) | win (4.643x/4.627x) |
| dumps.text.dense_escapes.4096_chars | 3.360 | 32.177 | 10.622 | win (9.607x/9.555x) | win (3.165x/3.158x) |
| loads.text.dense_escapes.4096_chars | 7.160 | 7.255 | 16.036 | inconclusive (1.010x/1.013x) | win (2.248x/2.229x) |
| dumps.text.dense_escapes.65536_chars | 51.248 | 517.705 | 142.750 | win (10.095x/10.103x) | win (2.782x/2.785x) |
| loads.text.dense_escapes.65536_chars | 109.900 | 113.317 | 217.862 | inconclusive (1.025x/1.031x) | win (2.032x/1.977x) |
| dumps.integers.8 | 0.121 | 0.112 | 2.001 | inconclusive (0.922x/0.925x) | win (16.550x/16.479x) |
| loads.integers.8 | 0.128 | 0.173 | 1.561 | win (1.349x/1.348x) | win (12.167x/12.200x) |
| dumps.floats.8 | 0.248 | 0.272 | 3.981 | win (1.100x/1.104x) | win (16.120x/16.004x) |
| loads.floats.8 | 0.227 | 0.280 | 2.560 | win (1.230x/1.230x) | win (11.268x/11.234x) |
| dumps.integers.128 | 0.507 | 0.608 | 7.821 | unstable (1.197x/1.199x) | win (15.409x/15.421x) |
| loads.integers.128 | 0.954 | 1.011 | 8.357 | unstable (1.059x/1.061x) | win (8.761x/8.769x) |
| dumps.floats.128 | 2.345 | 3.129 | 41.175 | win (1.335x/1.335x) | win (17.581x/17.507x) |
| loads.floats.128 | 2.870 | 2.994 | 28.231 | win (1.043x/1.044x) | win (10.069x/9.604x) |
| dumps.integers.2048 | 6.543 | 7.848 | 95.780 | unstable (1.159x/1.244x) | unstable (14.251x/14.983x) |
| loads.integers.2048 | 34.761 | 35.068 | 123.306 | unstable (1.010x/1.007x) | unstable (3.548x/3.547x) |
| dumps.floats.2048 | 35.750 | 52.267 | 628.221 | win (1.459x/1.466x) | win (17.754x/17.569x) |
| loads.floats.2048 | 53.903 | 55.636 | 435.120 | win (1.032x/1.030x) | win (8.059x/8.057x) |
| loads.bytes.64 | 0.135 | 0.178 | 1.274 | win (1.297x/1.320x) | win (9.257x/9.451x) |
| loads.bytes.256 | 0.203 | 0.246 | 1.434 | win (1.213x/1.217x) | win (7.078x/7.094x) |
| loads.bytes.321 | 0.228 | 0.272 | 1.529 | win (1.192x/1.200x) | win (6.737x/6.699x) |
| loads.bytes.322 | 0.228 | 0.273 | 1.533 | win (1.200x/1.199x) | win (6.739x/6.722x) |
| loads.bytes.512 | 0.302 | 0.345 | 1.696 | win (1.143x/1.142x) | win (5.625x/5.621x) |
| loads.bytes.610 | 0.341 | 0.384 | 1.776 | win (1.123x/1.127x) | win (5.196x/5.217x) |
| loads.bytes.611 | 0.388 | 0.384 | 1.783 | within tolerance (0.990x/0.991x) | win (4.595x/4.604x) |
| loads.bytes.4096 | 1.625 | 1.643 | 4.760 | within tolerance (1.012x/1.006x) | win (2.926x/2.931x) |
| loads.bytes.65536 | 22.774 | 22.848 | 55.708 | within tolerance (1.003x/1.003x) | win (2.444x/2.446x) |
| dumps.typed.records.1 | 0.896 | 0.912 | 2.860 | inconclusive (1.018x/1.017x) | win (3.186x/3.186x) |
| loads.typed.records.1 | 1.007 | 1.068 | 2.356 | win (1.062x/1.060x) | win (2.334x/2.347x) |
| dumps.typed.records.128 | 33.753 | 39.850 | 79.942 | win (1.172x/1.184x) | win (2.362x/2.378x) |
| loads.typed.records.128 | 68.752 | 73.492 | 101.152 | win (1.065x/1.073x) | win (1.465x/1.479x) |
| dumps.typed.records.1024 | 268.093 | 336.580 | 634.779 | win (1.255x/1.260x) | win (2.371x/2.370x) |
| loads.typed.records.1024 | 769.424 | 773.324 | 993.440 | inconclusive (1.009x/1.003x) | win (1.298x/1.289x) |

Ratios are baseline / Pydantic ORJSON for each round; >1 favors Pydantic ORJSON. Unstable ratios remain visible but are inconclusive evidence.

All tested cases beat both baselines: **NOT PROVEN**. No observed regressions within tolerance: **NOT PROVEN**.

## Installed engine identities

- **Pydantic ORJSON** 3.13.0+pydantic.4; native SHA-256 `65c3df3f2eb8f944002e6ee1a781721a443ec9833ca758d5930b740c8ff81757`.
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
