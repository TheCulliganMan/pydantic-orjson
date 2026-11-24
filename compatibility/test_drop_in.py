# SPDX-License-Identifier: MIT
"""Installed-wheel contracts used by existing orjson consumers."""

import importlib
import importlib.metadata
import inspect
import json
import subprocess
import sys

import fastapi.responses
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, field_serializer
from starlette.responses import JSONResponse

import orjson


def test_original_functions_are_native_and_not_wrapped():
    native = importlib.import_module("orjson.orjson")
    for name in ("dumps", "loads", "Fragment", "JSONEncodeError", "JSONDecodeError"):
        assert getattr(orjson, name) is getattr(native, name)
    assert inspect.isbuiltin(orjson.dumps)
    assert inspect.isbuiltin(orjson.loads)
    assert str(inspect.signature(orjson.dumps)) == "(obj, /, default=None, option=None)"
    assert str(inspect.signature(orjson.loads)) == "(obj, /)"


def test_dependency_distribution_identity():
    # A differently named distribution with the same import cannot satisfy
    # transitive Requires-Dist: orjson constraints and is not a full drop-in.
    distribution = importlib.metadata.distribution("orjson")
    assert distribution.metadata["Name"] == "orjson"
    assert distribution.version.split("+")[0] == orjson.__version__
    assert distribution.locate_file("orjson/__init__.py").is_file()


def test_core_does_not_import_optional_integrations():
    source = """
import importlib.abc
import sys
class RejectOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pydantic', 'pydantic_core', 'pydantic_ai', 'fastapi'}:
            raise AssertionError('core imported optional integration: ' + fullname)
sys.meta_path.insert(0, RejectOptional())
import orjson
assert orjson.loads(orjson.dumps({'ready': True})) == {'ready': True}
"""
    subprocess.run(
        [sys.executable, "-I", "-c", source], check=True, capture_output=True
    )


def test_default_callback_and_byte_result():
    class Custom:
        pass

    value = Custom()
    called = []

    def default(obj):
        called.append(obj)
        return {"custom": True}

    assert orjson.dumps(value, default) == b'{"custom":true}'
    assert called == [value]
    assert type(orjson.dumps({})) is bytes


def test_error_types_and_decode_locations():
    assert orjson.JSONEncodeError is TypeError
    assert issubclass(orjson.JSONDecodeError, json.JSONDecodeError)
    with pytest.raises(orjson.JSONDecodeError) as caught:
        orjson.loads('{\n"a": ]}')
    error = caught.value
    assert (error.pos, error.lineno, error.colno) == (7, 2, 6)
    assert error.doc == '{\n"a": ]}'


def test_models_still_require_explicit_integration():

    class Value(BaseModel):
        value: int

    with pytest.raises(orjson.JSONEncodeError):
        orjson.dumps(Value(value=1))


@pytest.mark.parametrize(
    "factory",
    [
        str,
        lambda s: s.encode(),
        lambda s: bytearray(s.encode()),
        lambda s: memoryview(s.encode()),
    ],
    ids=["str", "bytes", "bytearray", "memoryview"],
)
def test_supported_decode_inputs(factory):
    assert orjson.loads(factory('{"value": "雪"}')) == {"value": "雪"}


def test_fragment_and_combined_flags():
    assert (
        orjson.dumps(
            {"z": orjson.Fragment(b"[1,2]"), "a": True},
            option=orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE,
        )
        == b'{"a":true,"z":[1,2]}\n'
    )


def test_fastapi_orjson_response_uses_candidate(monkeypatch):

    assert fastapi.responses.orjson is orjson
    original = orjson.dumps
    calls = []

    def recording_dumps(obj, /, default=None, option=None):
        calls.append(option)
        return original(obj, default=default, option=option)

    monkeypatch.setattr(orjson, "dumps", recording_dumps)
    app = FastAPI()

    @app.get("/array")
    def array():
        return ORJSONResponse({1: np.array([2, 3], dtype=np.int64)})

    with TestClient(app) as client:
        response = client.get("/array")
    assert response.status_code == 200
    assert response.content == b'{"1":[2,3]}'
    assert response.headers["content-type"] == "application/json"
    assert int(response.headers["content-length"]) == len(response.content)
    assert calls == [orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY]


@pytest.mark.parametrize("custom_response", [False, True])
def test_fastapi_response_model_filtering_and_aliases(custom_response):

    class PublicUser(BaseModel):
        user_id: int = Field(alias="id")
        name: str
        note: str | None = None

        @field_serializer("name")
        def serialize_name(self, value):
            return value.upper()

    app = FastAPI()
    route_options = {"response_class": ORJSONResponse} if custom_response else {}

    @app.get(
        "/user",
        response_model=PublicUser,
        response_model_by_alias=True,
        response_model_exclude_none=True,
        **route_options,
    )
    def user():
        return {"id": 7, "name": "Ada", "note": None, "password": "must-not-leak"}

    with TestClient(app) as client:
        response = client.get("/user")
    assert response.status_code == 200
    assert response.json() == {"id": 7, "name": "ADA"}
    assert b"password" not in response.content


def test_fastapi_request_validation_and_errors():

    class Input(BaseModel):
        count: int = Field(gt=0)

    app = FastAPI(default_response_class=ORJSONResponse)

    @app.post("/input")
    def accept(item: Input):
        return {"count": item.count}

    with TestClient(app) as client:
        assert client.post("/input", json={"count": 3}).content == b'{"count":3}'
        invalid = client.post("/input", json={"count": 0})
        malformed = client.post(
            "/input", content=b'{"count":', headers={"content-type": "application/json"}
        )
    assert invalid.status_code == malformed.status_code == 422
    assert invalid.json()["detail"][0]["loc"] == ["body", "count"]


def test_starlette_custom_response():

    class OrjsonResponse(JSONResponse):
        def render(self, content):
            return orjson.dumps(content)

    response = OrjsonResponse({"unicode": "雪"})
    assert response.body == '{"unicode":"雪"}'.encode()
