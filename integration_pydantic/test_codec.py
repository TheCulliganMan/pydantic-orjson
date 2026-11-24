# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from datetime import date
from typing import Annotated, Literal

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_serializer,
    field_validator,
)

import orjson
from orjson.pydantic import Codec


class Event(BaseModel):
    model_config = ConfigDict(strict=True)
    when: date
    coordinates: tuple[int, int]


class Account(BaseModel):
    name: str = Field(alias="displayName")
    secret: str = Field(exclude=True)

    @field_validator("name")
    @classmethod
    def add_prefix(cls, value: str, info: ValidationInfo) -> str:
        return (info.context or {}).get("prefix", "") + value

    @field_serializer("name")
    def format_name(self, value: str, info: SerializationInfo) -> str:
        return value.upper() if (info.context or {}).get("uppercase") else value


class Cat(BaseModel):
    kind: Literal["cat"]
    lives: int


class Dog(BaseModel):
    kind: Literal["dog"]
    bark: bool


Pet = Annotated[Cat | Dog, Field(discriminator="kind")]


def test_strict_json_semantics_are_not_python_validation():
    codec = Codec(Event)
    raw = b'{"when":"2026-11-24","coordinates":[1,2]}'
    event = codec.loads(raw, strict=True)
    assert event.when == date(2026, 11, 24)
    assert event.coordinates == (1, 2)
    assert codec.dumps(event) == raw
    with pytest.raises(ValidationError):
        codec.adapter.validate_python(orjson.loads(raw), strict=True)


def test_existing_adapter_is_preserved_and_property_is_readonly():
    adapter = TypeAdapter(list[int], config=ConfigDict(strict=True))
    codec = Codec(adapter)
    assert codec.adapter is adapter
    assert codec.loads("[1,2]") == [1, 2]
    with pytest.raises(ValidationError):
        codec.loads('["1"]')
    with pytest.raises(AttributeError):
        codec.adapter = TypeAdapter(str)


def test_aliases_exclusion_serializers_and_context():
    codec = Codec(Account)
    account = codec.loads(
        '{"displayName":"Ada","secret":"private"}', context={"prefix": "Dr "}
    )
    assert account.name == "Dr Ada"
    assert codec.dumps(account, by_alias=True, context={"uppercase": True}) == (
        b'{"displayName":"DR ADA"}'
    )
    assert codec.dumps(account, exclude={"name"}) == b"{}"


def test_root_model_and_discriminated_union():
    codec = Codec(RootModel[list[Pet]])
    raw = b'[{"kind":"cat","lives":9},{"kind":"dog","bark":true}]'
    result = codec.loads(raw)
    assert isinstance(result.root[0], Cat)
    assert isinstance(result.root[1], Dog)
    assert codec.dumps(result) == raw


@pytest.mark.parametrize("data", ['[{"kind":"cat","lives":"bad"}]', "[{"])
def test_validation_errors_match_adapter(data):
    adapter = TypeAdapter(list[Pet])
    with pytest.raises(ValidationError) as expected:
        adapter.validate_json(data)
    with pytest.raises(ValidationError) as actual:
        Codec(adapter).loads(data)
    assert actual.value.errors() == expected.value.errors()


@pytest.mark.parametrize(
    "make_input",
    [str, lambda value: value.encode(), lambda value: bytearray(value.encode())],
    ids=["str", "bytes", "bytearray"],
)
def test_supported_input_types(make_input):
    assert Codec(list[int]).loads(make_input("[1,2]")) == [1, 2]


def test_native_api_remains_opt_in():
    event = Event(when=date(2026, 11, 24), coordinates=(1, 2))
    with pytest.raises(orjson.JSONEncodeError):
        orjson.dumps(event)
    with pytest.raises(orjson.JSONDecodeError):
        orjson.loads("{")
    with pytest.raises(TypeError):
        Codec(Event).dumps(event, option=orjson.OPT_SORT_KEYS)


def test_partial_validation_is_explicit_and_final_input_still_required():
    codec = Codec(list[int])
    raw = b"[1,2,"
    assert codec.loads(raw, experimental_allow_partial=True) == [1, 2]
    with pytest.raises(ValidationError):
        codec.loads(raw)
