# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Optional, schema-aware JSON APIs using Pydantic's public TypeAdapter.

These APIs follow Pydantic semantics. The native :mod:`orjson` API is unchanged.
Construct a codec once and reuse it, or supply an existing TypeAdapter when its
configuration or forward-reference namespace has already been resolved.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import TypeAdapter
from typing_extensions import TypeForm

__all__ = ("Codec",)

T = TypeVar("T")


class Codec(Generic[T]):
    """Reuse a Pydantic type adapter for JSON encoding and typed decoding.

    ``schema`` may be any Pydantic-supported type or an existing TypeAdapter.
    Keyword arguments to :meth:`dumps` and :meth:`loads` are passed unchanged to
    ``TypeAdapter.dump_json`` and ``TypeAdapter.validate_json`` respectively.
    In particular, they are Pydantic keyword arguments, not orjson option flags.

    Encoding returns bytes. Decoding preserves Pydantic's JSON validation mode
    and raises its ValidationError on invalid input. This initial implementation
    uses Pydantic's native engine directly and makes no performance claim over
    calling that engine yourself.
    """

    __slots__ = ("_adapter",)

    def __init__(self, schema: TypeForm[T] | TypeAdapter[T]) -> None:
        self._adapter: TypeAdapter[T] = (
            schema if isinstance(schema, TypeAdapter) else TypeAdapter(schema)
        )

    @property
    def adapter(self) -> TypeAdapter[T]:
        """The retained adapter; this property cannot be reassigned."""
        return self._adapter

    def dumps(self, value: T, **kwargs: Any) -> bytes:
        """Serialize through ``TypeAdapter.dump_json`` without an intermediate dict."""
        return self._adapter.dump_json(value, **kwargs)

    def loads(self, data: str | bytes | bytearray, **kwargs: Any) -> T:
        """Validate JSON directly, preserving JSON-specific strict-mode semantics."""
        return self._adapter.validate_json(data, **kwargs)
