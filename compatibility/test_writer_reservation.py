# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Run allocation-boundary regressions in isolated, sanitizer-friendly processes."""

import subprocess
import sys
import textwrap

import pytest

REGRESSION = textwrap.dedent(
    r"""
    import gc
    import json
    import sys

    import orjson

    options = (0, orjson.OPT_APPEND_NEWLINE, orjson.OPT_INDENT_2,
               orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE)

    def check(payload, expected_value, default=None):
        for option in options:
            pretty = bool(option & orjson.OPT_INDENT_2)
            expected = json.dumps(
                expected_value,
                indent=2 if pretty else None,
                separators=(',', ': ') if pretty else (',', ':'),
            ).encode()
            if option & orjson.OPT_APPEND_NEWLINE:
                expected += b'\n'
            assert orjson.dumps(payload, default=default, option=option) == expected

    case = sys.argv[1]
    if case in ('fragment_suffix', 'fragment_default', 'fragment_enum'):
        # The compact 17-item container's initial reservation does not grow the
        # roughly 4 KiB writer. This fragment consumes nearly all of it before
        # sixteen 20-digit integers need another 336 bytes with separators.
        fragment = orjson.Fragment(b'"' + b'x' * 3988 + b'"')
        first = fragment
        default = None
        if case == 'fragment_default':
            first = object()
            def default(value):
                assert value is first
                return fragment
        elif case == 'fragment_enum':
            from enum import Enum
            class Value(Enum):
                FIRST = fragment
            first = Value.FIRST
        suffix = [2**64 - 1] * 16
        check([first] + suffix, ['x' * 3988] + suffix, default)
    elif case == 'fragment_unwind':
        # The deepest fragment leaves a fixed tail while each compact ancestor
        # still needs a closing bracket. Bounds must survive every unwind.
        for depth in (160, 250):
            content = 'x' * (3988 - depth)
            payload = orjson.Fragment(b'"' + content.encode() + b'"')
            expected = content
            for _ in range(depth):
                payload = [payload]
                expected = [expected]
            check(payload, expected)
    elif case == 'primitive_siblings':
        from datetime import datetime, timedelta, timezone
        from uuid import UUID
        fragment = orjson.Fragment(b'"' + b'x' * 3988 + b'"')
        for value, expected in (
            (datetime(2001, 2, 3, 4, 5, 6, 7,
                      tzinfo=timezone(timedelta(hours=5, minutes=1))),
             '2001-02-03T04:05:06.000007+05:01'),
            (UUID('12345678-1234-5678-1234-567812345678'),
             '12345678-1234-5678-1234-567812345678'),
            (-1.7976931348623157e308, -1.7976931348623157e308),
        ):
            check([fragment] + [value] * 16, ['x' * 3988] + [expected] * 16)
    elif case == 'numpy_f64':
        import numpy as np
        # 166 negative maximum finite doubles emit 4151 bytes. The former
        # sizeof(f64)+16 reservation requested only 4048 bytes.
        options = tuple(option | orjson.OPT_SERIALIZE_NUMPY for option in options)
        for length in (166, 150, 165, 167, 180):
            values = np.full(length, -np.finfo(np.float64).max, dtype=np.float64)
            check(values, [-1.7976931348623157e308] * length)
    else:
        raise AssertionError(case)
    # Corruption in the original reproducers sometimes surfaced at collection
    # or finalization after dumps had already returned plausible-looking bytes.
    gc.collect()
    """
)


@pytest.mark.parametrize(
    "case",
    [
        "fragment_suffix",
        "fragment_default",
        "fragment_enum",
        "fragment_unwind",
        "primitive_siblings",
        "numpy_f64",
    ],
)
def test_writer_reservation_boundaries_in_subprocess(case):
    if case == "numpy_f64":
        pytest.importorskip("numpy")
    result = subprocess.run(
        [sys.executable, "-I", "-X", "dev", "-c", REGRESSION, case],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, (case, result.stdout, result.stderr)
