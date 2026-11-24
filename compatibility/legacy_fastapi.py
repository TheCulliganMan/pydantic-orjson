# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Emit comparable HTTP/native observations from a Pydantic 1 environment.

Run separately against installed upstream and replacement wheels using:
uv run --no-project --python /path/to/venv/bin/python python -I \
    compatibility/legacy_fastapi.py

This standalone probe is intentionally outside pytest collection: the regular
development environment qualifies current FastAPI and Pydantic 2 separately.
"""

import importlib
import importlib.metadata
import inspect
import json
import platform
import sys

import orjson

# Check fresh core import before loading framework dependencies below.
assert not {"fastapi", "pydantic", "pydantic_core", "pydantic_ai"}.intersection(
    sys.modules
)

import fastapi.responses
import numpy as np
import pydantic
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field


def check_native_identity():
    native = importlib.import_module("orjson.orjson")
    identities = {
        name: getattr(orjson, name) is getattr(native, name)
        for name in ("dumps", "loads", "Fragment", "JSONEncodeError", "JSONDecodeError")
    }
    assert all(identities.values())
    assert inspect.isbuiltin(orjson.dumps) and inspect.isbuiltin(orjson.loads)
    assert orjson.JSONEncodeError is TypeError
    assert issubclass(orjson.JSONDecodeError, json.JSONDecodeError)
    return identities


def error_record(call):
    try:
        call()
    except (orjson.JSONEncodeError, orjson.JSONDecodeError) as error:
        result = {
            "module": type(error).__module__,
            "name": type(error).__qualname__,
            "message": str(error),
        }
        if isinstance(error, orjson.JSONDecodeError):
            result.update(
                doc=error.doc, pos=error.pos, lineno=error.lineno, colno=error.colno
            )
        return result
    raise AssertionError("Expected native JSON error")


def main():
    identities = check_native_identity()
    assert pydantic.VERSION.startswith("1.10."), pydantic.VERSION
    assert not hasattr(pydantic, "TypeAdapter")
    assert fastapi.responses.orjson is orjson

    class PublicUser(BaseModel):
        user_id: int = Field(alias="id")
        name: str
        note: str | None = None

    class Input(BaseModel):
        count: int = Field(gt=0)

    app = FastAPI(default_response_class=ORJSONResponse)

    @app.get("/array")
    def array():
        return ORJSONResponse({1: np.array([2, 3], dtype=np.int64)})

    @app.get(
        "/user",
        response_model=PublicUser,
        response_model_by_alias=True,
        response_model_exclude_none=True,
    )
    def user():
        return {"id": 7, "name": "Ada", "note": None, "password": "must-not-leak"}

    @app.post("/input")
    def accept(item: Input):
        return {"count": item.count}

    observations = {}

    def record(name, response):
        observations[name] = {
            "status": response.status_code,
            "body_hex": response.content.hex(),
            "content_type": response.headers["content-type"],
            "content_length": int(response.headers["content-length"]),
        }
        assert response.status_code == (422 if name.endswith("_422") else 200)
        assert observations[name]["content_length"] == len(response.content)

    original_dumps = orjson.dumps
    options = []

    def recording_dumps(obj, /, default=None, option=None):
        options.append(option)
        return original_dumps(obj, default=default, option=option)

    # Observe the actual FastAPI call, then immediately restore native identity.
    orjson.dumps = recording_dumps
    try:
        with TestClient(app) as client:
            response = client.get("/array")
            assert response.content == b'{"1":[2,3]}'
            record("numpy_non_string_key_response", response)
    finally:
        orjson.dumps = original_dumps
    assert options == [orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY]

    with TestClient(app) as client:
        response = client.get("/user")
        assert response.content == b'{"id":7,"name":"Ada"}'
        record("response_model_alias_filter_exclude_none", response)
        response = client.post("/input", json={"count": 3})
        assert response.content == b'{"count":3}'
        record("valid_request", response)
        response = client.post("/input", json={"count": 0})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "count"]
        record("invalid_request_422", response)
        response = client.post(
            "/input", content=b'{"count":', headers={"content-type": "application/json"}
        )
        assert response.status_code == 422
        record("malformed_request_422", response)

    observations.update(
        native_identity=identities,
        native_signatures={
            "dumps": str(inspect.signature(orjson.dumps)),
            "loads": str(inspect.signature(orjson.loads)),
        },
        orjson_response_options=options,
        model_still_requires_explicit_serialization=error_record(
            lambda: orjson.dumps(PublicUser(id=7, name="Ada"))
        ),
        native_encode_error=error_record(lambda: orjson.dumps(object())),
        native_decode_error=error_record(lambda: orjson.loads('{\n"a": ]}')),
        optional_helpers_imported=any(
            module in sys.modules
            for module in ("orjson.pydantic", "orjson.pydantic_ai", "pydantic_core")
        ),
    )
    assert observations["optional_helpers_imported"] is False
    assert check_native_identity() == identities
    dependencies = {
        distribution.metadata["Name"].lower(): distribution.version
        for distribution in importlib.metadata.distributions()
    }
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "python_compiler": platform.python_compiler(),
                "platform": sys.platform,
                "architecture": platform.machine(),
                "dependencies": dict(sorted(dependencies.items())),
                "observations": observations,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
