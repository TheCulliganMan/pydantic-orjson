# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""One engine of the public, semantically matched three-way benchmark matrix.

Use run_matrix.py to run all engines in balanced order. Every encoder produces
UTF-8 bytes; the stdlib's str-to-bytes conversion is inside the timed expression.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyperf

LABELS = {"candidate": "Pydantic ORJSON", "upstream": "ORJSON", "stdlib": "json"}
ENGINES = tuple(LABELS)
PROFILES = ("smoke", "standard", "full")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@dataclass
class Case:
    name: str
    value: Any
    operation: str
    style: str = "compact"
    typed: bool = False

    @property
    def fixture(self) -> bytes:
        return self.value if self.operation == "loads" else canonical(self.value)


def cases(profile: str = "standard") -> list[Case]:  # noqa: PLR0912
    if profile not in PROFILES:
        raise ValueError(profile)
    result: list[Case] = []

    def pair(name: str, value: Any, *, typed: bool = False) -> None:
        result.append(Case("dumps." + name, value, "dumps", typed=typed))
        result.append(Case("loads." + name, canonical(value), "loads", typed=typed))

    for name, value in (
        ("null", None),
        ("bool", True),
        ("int", 104729),
        ("float", 3.141592653589793),
        ("string", "hello"),
    ):
        pair("scalar." + name, value)
    counts = (1,) if profile == "smoke" else (1, 16, 128, 1024)
    if profile == "full":
        counts += (16384,)
    for count in counts:
        records = [
            {
                "id": i,
                "name": f"item {i}",
                "active": i % 2 == 0,
                "tags": ["api", "json"],
            }
            for i in range(count)
        ]
        pair(f"records.{count}", records)
        for style in ("sorted", "pretty", "fastapi_flags"):
            result.append(
                Case(f"dumps.records.{count}.{style}", records, "dumps", style)
            )
    lengths = (32,) if profile == "smoke" else (32, 256, 4096, 65536)
    if profile == "full":
        lengths += (1048576,)
    for kind, unit in (
        ("ascii", "Validated structured response. "),
        ("unicode", "Café 雪の街 — 📦 "),
        ("escaped", 'line one\nline two\t"quoted" \\ path '),
        ("dense_escapes", '\n\t"\\'),
    ):
        for length in lengths:
            value = {"content": (unit * (length // len(unit) + 1))[:length]}
            pair(f"text.{kind}.{length}_chars", value)
    numeric_counts = (8,) if profile == "smoke" else (8, 128, 2048)
    if profile == "full":
        numeric_counts += (32768,)
    for count in numeric_counts:
        pair(f"integers.{count}", list(range(count)))
        pair(f"floats.{count}", [i / 7 for i in range(count)])
    sizes = (
        (64, 321, 322, 610, 611)
        if profile == "smoke"
        else (64, 256, 321, 322, 512, 610, 611, 4096, 65536)
    )
    if profile == "full":
        sizes += (607, 608, 609, 612, 613, 614)
    for size in sizes:
        value = b'{"message":"' + b"x" * (size - 14) + b'"}'
        assert len(value) == size
        result.append(Case(f"loads.bytes.{size}", value, "loads"))
    for count in (1,) if profile == "smoke" else (1, 128, 1024):
        pair(
            f"typed.records.{count}",
            [
                {"id": i, "name": f"item {i}", "active": i % 2 == 0}
                for i in range(count)
            ],
            typed=True,
        )
    assert len({case.name for case in result}) == len(result)
    return result


def unsupported() -> dict[str, dict[str, str]]:
    # These are deliberately outside the common-data latency table. A made-up
    # zero duration or a silently preconverted input would misrepresent support.
    return {
        "native_datetime": {
            "stdlib": "Requires a user default callback; json has no native datetime encoder."
        },
        "native_numpy": {
            "stdlib": "Requires a user default callback; json has no OPT_SERIALIZE_NUMPY."
        },
        "native_fragment": {"stdlib": "No equivalent to orjson.Fragment."},
        "pydantic_ai_message_json": {
            "upstream": "No built-in Pydantic AI persistence helper; compose the official adapter separately.",
            "stdlib": "No built-in Pydantic AI persistence helper; compose the official adapter separately.",
        },
    }


def prepare(case: Case, engine: str) -> tuple[str, dict[str, Any], Any]:  # noqa: PLR0912
    """Return a timeit expression, bindings and a result validator target."""
    if engine not in ENGINES:
        raise ValueError(engine)
    value = case.value
    namespace: dict[str, Any] = {"value": value}
    expected = json.loads(case.fixture)
    if engine != "stdlib":
        import orjson  # noqa: PLC0415

        namespace["function"] = getattr(orjson, case.operation)
    else:
        namespace["function"] = getattr(json, case.operation)
    if case.typed:
        from pydantic import BaseModel, TypeAdapter  # noqa: PLC0415

        class Item(BaseModel):
            id: int
            name: str
            active: bool

        adapter = TypeAdapter(list[Item])
        namespace["adapter"] = adapter
        if case.operation == "dumps":
            namespace["value"] = adapter.validate_python(value)
        else:
            expected = adapter.validate_python(expected)
        if engine == "candidate":
            from orjson.pydantic import Codec  # noqa: PLC0415

            namespace["function"] = getattr(Codec(adapter), case.operation)
            return "function(value)", namespace, expected
        # Include conversion/validation in each timed operation. These are
        # end-to-end typed pipelines, not raw JSON parser comparisons.
        if case.operation == "loads":
            return "adapter.validate_python(function(value))", namespace, expected
        value_expression = "adapter.dump_python(value, mode='json')"
    else:
        value_expression = "value"
    if case.operation == "loads":
        return "function(value)", namespace, expected
    if engine == "stdlib":
        options = ", ensure_ascii=False, allow_nan=False"
        options += ", indent=2" if case.style == "pretty" else ", separators=(',', ':')"
        if case.style == "sorted":
            options += ", sort_keys=True"
        expression = f"function({value_expression}{options}).encode('utf-8')"
    else:
        option = {
            "compact": 0,
            "pretty": orjson.OPT_INDENT_2,
            "sorted": orjson.OPT_SORT_KEYS,
            "fastapi_flags": orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY,
        }[case.style]
        namespace["option"] = option
        expression = (
            f"function({value_expression})"
            if case.style == "compact"
            else f"function({value_expression}, option=option)"
        )
    return expression, namespace, expected


def check(case: Case, expression: str, namespace: dict[str, Any], expected: Any) -> int:
    result = eval(expression, namespace)  # generated locally, never user-provided
    if case.operation == "dumps":
        assert isinstance(result, bytes), case.name
        assert json.loads(result) == expected, case.name
        return len(result)
    assert result == expected, case.name
    return len(case.fixture)


def worker_arguments(command: list[str], args: Any) -> None:
    command.extend(("--engine", args.engine, "--matrix-profile", args.matrix_profile))
    if args.case:
        command.extend(("--case", args.case))
    if args.macos_qos:
        command.append("--macos-qos")


def main() -> None:
    runner = pyperf.Runner(add_cmdline_args=worker_arguments)
    runner.argparser.add_argument("--engine", choices=ENGINES, required=True)
    runner.argparser.add_argument(
        "--matrix-profile", choices=PROFILES, default="standard"
    )
    runner.argparser.add_argument("--case", help="Select one exact case name")
    runner.argparser.add_argument("--macos-qos", action="store_true")
    args = runner.parse_args()
    if args.macos_qos:
        import ctypes  # noqa: PLC0415

        if sys.platform != "darwin":
            raise RuntimeError("--macos-qos requires macOS")
        system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        set_qos = system.pthread_set_qos_class_self_np
        set_qos.argtypes, set_qos.restype = [ctypes.c_uint, ctypes.c_int], ctypes.c_int
        error = set_qos(0x19, 0)
        if error:
            raise OSError(error, "Unable to request benchmark thread QoS")
        runner.metadata["macos_qos_requested"] = "user-initiated"
    metadata = {
        "engine": args.engine,
        "engine_label": LABELS[args.engine],
        "profile": args.matrix_profile,
        "matrix_contract": "UTF-8 bytes, equivalent declared values, v1",
        "suite_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pydantic": importlib.metadata.version("pydantic"),
        "pydantic_core": importlib.metadata.version("pydantic-core"),
        "python_gil_disabled_build": str(
            bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
        ),
        "python_gil_enabled": str(sys._is_gil_enabled())
        if hasattr(sys, "_is_gil_enabled")
        else "True",
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "random"),
        "python_executable_sha256": hashlib.sha256(
            Path(sys.executable).read_bytes()
        ).hexdigest(),
    }
    if args.engine == "stdlib":
        import _json  # noqa: PLC0415

        metadata["engine_version"] = sys.version.split()[0]
        native_path = getattr(_json, "__file__", None)
        if native_path is None:
            library = Path(sysconfig.get_config_var("LIBDIR") or "") / (
                sysconfig.get_config_var("LDLIBRARY") or ""
            )
            native_path = str(library) if library.is_file() else sys.executable
        metadata["native_sha256"] = hashlib.sha256(
            Path(native_path or sys.executable).read_bytes()
        ).hexdigest()
        metadata["stdlib_accelerator"] = (
            "extension"
            if getattr(_json, "__file__", None)
            else "built into Python runtime"
        )
        metadata["stdlib_source_sha256"] = hashlib.sha256(
            b"".join(
                Path(module.__file__).read_bytes()
                for module in (json, json.encoder, json.decoder)
            )
        ).hexdigest()
    else:
        import orjson.orjson as extension  # noqa: PLC0415

        version = importlib.metadata.version("orjson")
        if ("+pydantic" in version) != (args.engine == "candidate"):
            raise RuntimeError(
                f"Wrong installed distribution for {LABELS[args.engine]}: {version}"
            )
        metadata["engine_version"] = version
        metadata["native_sha256"] = hashlib.sha256(
            Path(extension.__file__).read_bytes()
        ).hexdigest()
    runner.metadata.update(metadata)
    selected = [
        case
        for case in cases(args.matrix_profile)
        if args.case is None or case.name == args.case
    ]
    if not selected:
        raise ValueError(f"Unknown case {args.case!r}")
    for case in selected:
        expression, namespace, expected = prepare(case, args.engine)
        original = case.fixture
        size = check(case, expression, namespace, expected)
        runner.timeit(
            case.name,
            expression,
            globals=namespace,
            metadata={
                "fixture_sha256": hashlib.sha256(original).hexdigest(),
                "fixture_bytes": len(original),
                "output_bytes": size,
                "pipeline": "typed validation included"
                if case.typed
                else "native JSON",
            },
        )
        check(case, expression, namespace, expected)
        assert case.fixture == original, f"Fixture mutated: {case.name}"


if __name__ == "__main__":
    main()
