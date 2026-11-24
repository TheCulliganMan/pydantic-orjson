"""Error messages retain upstream's extension-type names and callback causes."""

import collections
import datetime
import decimal
import sys

import pytest

import orjson

# CPython 3.15 changed Decimal to a heap type with a different tp_name.
DECIMAL_NAME = "Decimal" if sys.version_info >= (3, 15) else "decimal.Decimal"


@pytest.mark.parametrize(
    ("value", "name"),
    [
        (datetime.timedelta(days=1), "datetime.timedelta"),
        (decimal.Decimal("1.25"), DECIMAL_NAME),
        (collections.deque([1, 2]), "collections.deque"),
    ],
)
@pytest.mark.parametrize("nested", [False, True])
def test_unsupported_extension_type_name(
    value: object, name: str, nested: bool
) -> None:
    payload = {"value": [value]} if nested else value
    with pytest.raises(orjson.JSONEncodeError) as caught:
        orjson.dumps(payload)
    assert str(caught.value) == f"Type is not JSON serializable: {name}"


def test_numpy_complex_extension_type_name() -> None:
    numpy = pytest.importorskip("numpy")
    with pytest.raises(orjson.JSONEncodeError) as caught:
        orjson.dumps(numpy.complex128(1 + 2j))
    assert str(caught.value) == "Type is not JSON serializable: numpy.complex128"


def test_callback_failure_retains_extension_type_name_and_cause() -> None:
    def reject(value: object) -> object:
        raise ValueError("intentional callback failure")

    with pytest.raises(orjson.JSONEncodeError) as caught:
        orjson.dumps(decimal.Decimal("1.25"), default=reject)
    assert str(caught.value) == f"Type is not JSON serializable: {DECIMAL_NAME}"
    assert type(caught.value.__cause__) is ValueError
    assert str(caught.value.__cause__) == "intentional callback failure"


def test_renamed_python_type_uses_current_name() -> None:
    class Original:
        pass

    value = Original()
    Original.__name__ = "Renamed"
    with pytest.raises(orjson.JSONEncodeError) as caught:
        orjson.dumps(value)
    assert str(caught.value) == "Type is not JSON serializable: Renamed"
