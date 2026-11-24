# SPDX-License-Identifier: MIT
"""Compare installed upstream/candidate wheels in isolated Python processes.

Run with --baseline PYTHON --candidate PYTHON. No candidate module is imported
by the controller; each interpreter imports its own installed orjson wheel.
"""

import argparse
import dataclasses
import datetime
import enum
import importlib.metadata
import inspect
import json
import math
import pathlib
import random
import subprocess
import sys
import uuid


def normalize(value):
    """Preserve type, dict order, byte contents, and the sign of floating zero."""
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, dict):
        return ["dict", [[normalize(k), normalize(v)] for k, v in value.items()]]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [normalize(item) for item in value]]
    if isinstance(value, float):
        return ["float", repr(value)]
    return [type(value).__name__, value]


def outcome(call):
    try:
        return {"result": normalize(call())}
    except Exception as error:
        result = {"error": type(error).__name__, "message": str(error)}
        for key in ("msg", "pos", "lineno", "colno", "doc"):
            if hasattr(error, key):
                result[key] = getattr(error, key)
        if error.__cause__ is not None:
            result["cause"] = [type(error.__cause__).__name__, str(error.__cause__)]
        return result


def edge_cases(encode, decode):
    # Exercise vector lanes/tails and the small-parser arena boundary against
    # the installed reference, including exact error positions and UTF-8 sizes.
    for length in (0, 1, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128):
        for special in [*(chr(i) for i in range(32)), '"', "\\", "雪", "🌊"]:
            for position in sorted({0, length // 2, length}):
                value = "x" * position + special + "x" * (length - position)
                encode(f"vector/{length}/{ord(special)}/{position}", value)
    for length in range(310, 335):
        valid = b'{"message":"' + b"x" * (length - 14) + b'"}'
        invalid = b'{"items":' + b" " * (length - 11) + b"]}"
        for kind, factory in (
            ("bytes", bytes),
            ("bytearray", bytearray),
            ("memoryview", memoryview),
        ):
            decode(f"arena/{length}/{kind}", factory(valid))
            decode(f"arena-invalid/{length}/{kind}", factory(invalid))


def snapshot():
    import orjson  # noqa: PLC0415 -- only child interpreters import the wheel

    results = {}

    def encode(name, value, **kwargs):
        results["encode/" + name] = outcome(lambda: orjson.dumps(value, **kwargs))

    def decode(name, value):
        results["decode/" + name] = outcome(lambda: orjson.loads(value))

    # Metadata is reported for reproducibility, but versions may intentionally
    # carry a fork suffix. API and option values must still compare exactly.
    api = {
        "dumps_signature": str(inspect.signature(orjson.dumps)),
        "loads_signature": str(inspect.signature(orjson.loads)),
        "dumps_builtin": inspect.isbuiltin(orjson.dumps),
        "loads_builtin": inspect.isbuiltin(orjson.loads),
        "encode_error_is_type_error": orjson.JSONEncodeError is TypeError,
        "decode_error_is_json_subclass": issubclass(
            orjson.JSONDecodeError, json.JSONDecodeError
        ),
        "options": {
            name: getattr(orjson, name)
            for name in dir(orjson)
            if name.startswith("OPT_")
        },
    }

    @dataclasses.dataclass
    class Record:
        name: str
        count: int

    class Choice(enum.Enum):
        FIRST = "first"

    class Custom:
        pass

    values = {
        "null": None,
        "booleans": [True, False],
        "unicode": {"雪": "emoji 🎉 and null \0 and newline\n"},
        "empty": [{}, [], ""],
        "int_limits": [-(2**63), 2**63 - 1, 2**64 - 1],
        "int_underflow": -(2**63) - 1,
        "int_overflow": 2**64,
        "float_limits": [0.0, -0.0, 1.2e30, 5e-324, 1.7976931348623157e308],
        "nonfinite": [math.nan, math.inf, -math.inf],
        "dataclass": Record("item", 2),
        "date": datetime.date(2024, 2, 29),
        "datetime_naive": datetime.datetime(2024, 2, 29, 1, 2, 3, 4000),
        "datetime_aware": datetime.datetime(
            2024, 2, 29, 1, 2, tzinfo=datetime.timezone.utc
        ),
        "uuid": uuid.UUID(int=1),
        "enum": Choice.FIRST,
        "unsupported_bytes": b"abc",
        "unsupported_set": {1, 2},
        "unsupported_object": Custom(),
        "surrogate": "\ud800",
        "tuple": (1, "two"),
        "fragment": {"raw": orjson.Fragment(b"[1, 2]")},
    }
    for name, value in values.items():
        encode(name, value)
    circular = []
    circular.append(circular)
    encode("circular", circular)
    encode("strict_integer", 2**53, option=orjson.OPT_STRICT_INTEGER)
    encode(
        "non_str_keys",
        {1: "integer", None: "null", Choice.FIRST: "enum"},
        option=orjson.OPT_NON_STR_KEYS,
    )
    encode("non_str_keys_default", {1: "integer"})
    encode(
        "sort_indent_newline",
        {"z": [1, 2], "a": "雪"},
        option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
    )
    encode(
        "datetime_flags",
        values["datetime_naive"],
        option=orjson.OPT_NAIVE_UTC | orjson.OPT_UTC_Z | orjson.OPT_OMIT_MICROSECONDS,
    )
    encode("default_callback", Custom(), default=lambda obj: {"custom": True})
    encode(
        "dataclass_passthrough",
        values["dataclass"],
        option=orjson.OPT_PASSTHROUGH_DATACLASS,
        default=lambda obj: "custom-record",
    )
    encode(
        "datetime_passthrough",
        values["datetime_aware"],
        option=orjson.OPT_PASSTHROUGH_DATETIME,
        default=lambda obj: "custom-time",
    )

    def rejected_default(obj):
        raise ValueError("intentional callback failure")

    encode("default_failure", Custom(), default=rejected_default)
    for option in (-1, 2**30, "not-an-option", True, 1.5):
        encode("invalid_option_" + repr(option), {}, option=option)
    results["call/dumps_keyword_obj"] = outcome(lambda: orjson.dumps(obj={}))
    results["call/loads_keyword_obj"] = outcome(lambda: orjson.loads(obj="{}"))

    documents = [
        "null",
        "true",
        "{}",
        "[]",
        '["雪", "🎉"]',
        '{"a":1,"a":2}',
        "-0.0",
        "1e999",
        "NaN",
        "Infinity",
        "",
        " ",
        "{",
        "[1,]",
        '{"a":}',
        '{\n"a": ]}',
        "{} trailing",
        '"\\ud800"',
        '"\\ud83c\\udf89"',
        "01",
        "+1",
        "18446744073709551616",
        "-9223372036854775809",
        "[" * 1025 + "]" * 1025,
    ]
    for index, document in enumerate(documents):
        for kind, value in (
            ("str", document),
            ("bytes", document.encode()),
            ("bytearray", bytearray(document.encode())),
            ("memoryview", memoryview(document.encode())),
        ):
            decode(f"document_{index}/{kind}", value)
    for index, invalid in enumerate(
        (b"\xff", b"\xef\xbb\xbf{}", '"\ud800"', None, 1, {}, memoryview(b"{ } ")[::2])
    ):
        decode(f"invalid_{index}", invalid)

    edge_cases(encode, decode)

    rng = random.Random(20261124)

    def random_value(depth=0):
        primitives = [
            None,
            True,
            False,
            rng.randrange(-(2**53), 2**53),
            rng.uniform(-1e20, 1e20),
            "雪🎉\n" * rng.randrange(5),
        ]
        if depth == 3:
            return rng.choice(primitives)
        choice = rng.randrange(3)
        if choice == 0:
            return [random_value(depth + 1) for _ in range(rng.randrange(5))]
        if choice == 1:
            return {str(i): random_value(depth + 1) for i in range(rng.randrange(5))}
        return rng.choice(primitives)

    for index in range(100):
        value = random_value()
        encode(f"generated_{index}", value)
        encode(f"generated_sorted_{index}", value, option=orjson.OPT_SORT_KEYS)
        decode(f"generated_{index}", json.dumps(value, ensure_ascii=False))

    fixtures = pathlib.Path(__file__).resolve().parent.parent / "data" / "parsing"
    for path in sorted(fixtures.glob("*.json")):
        decode("fixture/" + path.name, path.read_bytes())

    return {
        "metadata": {
            "python": sys.version.split()[0],
            "orjson": orjson.__version__,
            "distribution": importlib.metadata.version("orjson"),
        },
        "api": api,
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", help="Python executable containing upstream wheel"
    )
    parser.add_argument(
        "--candidate", help="Python executable containing candidate wheel"
    )
    parser.add_argument("--snapshot", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--output", type=pathlib.Path, help="Write a concise machine-readable report"
    )
    args = parser.parse_args()
    if args.snapshot:
        print(json.dumps(snapshot(), ensure_ascii=True, sort_keys=True))
        return
    if not args.baseline or not args.candidate:
        parser.error("both --baseline and --candidate are required")

    def capture(python):
        completed = subprocess.run(
            [python, "-I", str(pathlib.Path(__file__).resolve()), "--snapshot"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return json.loads(completed.stdout)

    baseline = capture(args.baseline)
    candidate = capture(args.candidate)
    mismatches = []
    # Existing option constants must agree; future opt-in extensions may add
    # constants without changing the old API contract.
    for key, expected in baseline["api"].items():
        actual = candidate["api"].get(key)
        if key == "options":
            actual = {name: actual.get(name) for name in expected}
        if expected != actual:
            mismatches.append(
                {"case": "api/" + key, "baseline": expected, "candidate": actual}
            )
    for name in sorted(baseline["cases"].keys() | candidate["cases"].keys()):
        expected = baseline["cases"].get(name)
        actual = candidate["cases"].get(name)
        if expected != actual:
            mismatches.append({"case": name, "baseline": expected, "candidate": actual})
    report = {
        "baseline": baseline["metadata"],
        "candidate": candidate["metadata"],
        "cases": len(baseline["cases"]),
        "api_contracts": len(baseline["api"]),
        "mismatches": mismatches,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
