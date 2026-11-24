# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Semantic boundaries that a direct-core default path must retain."""

import importlib.util
import warnings
from dataclasses import dataclass
from datetime import date
from functools import wraps
from typing import Annotated

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PydanticUserError,
    SerializeAsAny,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_serializer,
    field_validator,
)
from pydantic.plugin import _loader
from pydantic_core import (
    PydanticSerializationError,
    SchemaSerializer,
    SchemaValidator,
    core_schema,
)

import orjson.pydantic as integration
from orjson.pydantic import Codec


def test_default_schema_aliases_and_strict_json_mode():
    class Event(BaseModel):
        model_config = ConfigDict(strict=True, serialize_by_alias=True)
        when: date = Field(alias="eventDate")
        position: tuple[int, int]

    adapter = TypeAdapter(Event)
    codec = Codec(adapter)
    raw = b'{"eventDate":"2026-11-24","position":[1,2]}'
    result = codec.loads(raw)
    assert result == adapter.validate_json(raw)
    assert codec.dumps(result) == adapter.dump_json(result) == raw


def test_subclass_fields_do_not_escape_declared_schema():
    class Public(BaseModel):
        name: str

    class Private(Public):
        password: str

    value = Private(name="Ada", password="private")
    assert Codec(Public).dumps(value) == b'{"name":"Ada"}'
    assert Codec(SerializeAsAny[Public]).dumps(value) == (
        b'{"name":"Ada","password":"private"}'
    )
    assert Codec(Public).dumps(value, serialize_as_any=True) == (
        b'{"name":"Ada","password":"private"}'
    )


def test_computed_fields_and_custom_serializers_remain_active():
    class Amount(BaseModel):
        amount: int

        @field_validator("amount")
        @classmethod
        def increment(cls, value):
            return value + 1

        @field_serializer("amount")
        def label(self, value):
            return f"USD {value}"

        @computed_field
        @property
        def doubled(self) -> int:
            return self.amount * 2

    codec = Codec(Amount)
    value = codec.loads(b'{"amount":4}')
    assert codec.dumps(value) == b'{"amount":"USD 5","doubled":10}'
    assert codec.dumps(value, exclude_computed_fields=True) == b'{"amount":"USD 5"}'


def test_recursive_model_and_nested_exclusions():
    class Node(BaseModel):
        name: str
        children: list["Node"] = Field(default_factory=list)

    codec = Codec(Node)
    raw = b'{"name":"root","children":[{"name":"leaf","children":[]}]}'
    value = codec.loads(raw)
    assert codec.dumps(value) == raw
    assert codec.dumps(value, exclude={"children": {0: {"children"}}}) == (
        b'{"name":"root","children":[{"name":"leaf"}]}'
    )


def test_dataclass_and_annotated_constraints():
    @dataclass
    class Positive:
        count: Annotated[int, Field(gt=0)]

    codec = Codec(Positive)
    assert codec.dumps(codec.loads(b'{"count":2}')) == b'{"count":2}'
    with pytest.raises(ValidationError):
        codec.loads(b'{"count":0}')


def test_default_warning_and_error_behavior_match_adapter():
    adapter = TypeAdapter(int)
    with pytest.warns(UserWarning) as expected:
        adapter.dump_json("not-an-integer")
    with pytest.warns(UserWarning) as actual:
        Codec(adapter).dumps("not-an-integer")
    assert [str(w.message) for w in actual] == [str(w.message) for w in expected]
    assert [w.filename for w in actual] == [w.filename for w in expected]
    with pytest.raises(PydanticSerializationError):
        Codec(adapter).dumps("not-an-integer", warnings="error")
    with pytest.raises(PydanticSerializationError):
        Codec(object).dumps(object())


def test_pydantic_warning_module_filter_keeps_default_error_behavior():
    with warnings.catch_warnings():
        warnings.filterwarnings("error", module=r"pydantic\.type_adapter")
        with pytest.raises(UserWarning):
            Codec(int).dumps("not-an-integer")


def test_explicit_disabled_warning_serialization_matches_public_adapter():
    adapter = TypeAdapter(int)
    codec = Codec(adapter)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error")
        assert codec.dumps("text", warnings=False) == adapter.dump_json(
            "text", warnings=False
        )
    assert not caught
    assert codec.dumps(2, warnings=False) == b"2"


def test_alias_keyword_error_remains_pydantic_user_error():
    with pytest.raises(PydanticUserError) as caught:
        Codec(int).loads(b"1", by_alias=False)
    assert caught.value.code == "validate-by-alias-and-name-false"


def test_custom_adapter_overrides_are_called():
    class CustomAdapter(TypeAdapter):
        def dump_json(self, value, **kwargs):
            return b'"custom"'

        def validate_json(self, data, **kwargs):
            return 42

    codec = Codec(CustomAdapter(int))
    assert codec.dumps(1) == b'"custom"'
    assert codec.loads(b"1") == 42


@pytest.mark.parametrize("patch_before_construction", [False, True])
def test_instance_method_overrides_are_observed_live(
    monkeypatch, patch_before_construction
):
    adapter = TypeAdapter(int)
    codec = None if patch_before_construction else Codec(adapter)
    calls = []

    def dump(value, **kwargs):
        calls.append(("dump", value, kwargs))
        return b'"custom-instance"'

    def load(data, **kwargs):
        calls.append(("load", data, kwargs))
        return 42

    monkeypatch.setattr(adapter, "dump_json", dump)
    monkeypatch.setattr(adapter, "validate_json", load)
    if codec is None:
        codec = Codec(adapter)
    assert codec.dumps(1) == b'"custom-instance"'
    assert codec.dumps(1, warnings=False) == b'"custom-instance"'
    assert codec.loads(b"1") == 42
    assert calls == [
        ("dump", 1, {}),
        ("dump", 1, {"warnings": False}),
        ("load", b"1", {}),
    ]


@pytest.mark.parametrize("patch_before_construction", [False, True])
def test_class_method_overrides_are_observed_live(
    monkeypatch, patch_before_construction
):
    adapter = TypeAdapter(int)
    codec = None if patch_before_construction else Codec(adapter)
    calls = []

    def dump(self, value, **kwargs):
        calls.append(("dump", self, value, kwargs))
        return b'"custom-class"'

    def load(self, data, **kwargs):
        calls.append(("load", self, data, kwargs))
        return 42

    monkeypatch.setattr(TypeAdapter, "dump_json", dump)
    monkeypatch.setattr(TypeAdapter, "validate_json", load)
    if codec is None:
        codec = Codec(adapter)
    assert codec.dumps(1) == b'"custom-class"'
    assert codec.dumps(1, warnings=False) == b'"custom-class"'
    assert codec.loads(b"1") == 42
    assert calls == [
        ("dump", adapter, 1, {}),
        ("dump", adapter, 1, {"warnings": False}),
        ("load", adapter, b"1", {}),
    ]


def test_instance_method_bound_to_other_adapter_is_not_bypassed(monkeypatch):
    adapter = TypeAdapter(int)
    codec = Codec(adapter)
    strings = TypeAdapter(str)
    monkeypatch.setattr(adapter, "dump_json", strings.dump_json)
    monkeypatch.setattr(adapter, "validate_json", strings.validate_json)
    assert codec.dumps("text") == b'"text"'
    assert codec.dumps("text", warnings=False) == b'"text"'
    assert codec.loads(b'"text"') == "text"


def test_instrumentation_installed_before_integration_import_is_preserved(monkeypatch):
    adapter = TypeAdapter(int)

    @wraps(TypeAdapter.dump_json)
    def dump(self, value, **kwargs):
        return b'"pre-import"'

    @wraps(TypeAdapter.validate_json)
    def load(self, data, **kwargs):
        return 42

    monkeypatch.setattr(TypeAdapter, "dump_json", dump)
    monkeypatch.setattr(TypeAdapter, "validate_json", load)
    spec = importlib.util.spec_from_file_location(
        "isolated_codec", integration.__file__
    )
    isolated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isolated)
    codec = isolated.Codec(adapter)
    assert codec.dumps(1, warnings=False) == b'"pre-import"'
    assert codec.loads(b"1") == 42


def test_live_validator_is_snapshotted_once(monkeypatch):
    adapter = TypeAdapter(int)
    codec = Codec(adapter)
    original = adapter.validator
    replacement = TypeAdapter(str).validator
    reads = []

    def get_validator(self):
        reads.append(self)
        return original if len(reads) == 1 else replacement

    monkeypatch.setattr(
        TypeAdapter, "validator", property(get_validator), raising=False
    )
    assert codec.loads(b"2") == 2
    assert reads == [adapter]


def test_deferred_adapter_rebuild_is_observed():
    adapter = TypeAdapter("DeferredValue", config=ConfigDict(defer_build=True))
    codec = Codec(adapter)
    with pytest.raises(PydanticUserError):
        codec.loads(b"2")
    assert adapter.rebuild(_types_namespace={"DeferredValue": int})
    assert codec.loads(b"2") == 2
    assert codec.dumps(2) == b"2"


def test_completed_adapter_rebuild_replaces_live_core_objects():
    class IncreasingMinimum:
        minimum = 1

        @classmethod
        def __get_pydantic_core_schema__(cls, source, handler):
            prefix = f"{cls.minimum}:"
            return core_schema.int_schema(
                ge=cls.minimum,
                serialization=core_schema.plain_serializer_function_ser_schema(
                    lambda value: f"{prefix}{value}"
                ),
            )

    adapter = TypeAdapter(IncreasingMinimum)
    codec = Codec(adapter)
    assert codec.loads(b"1") == 1
    assert codec.dumps(1) == b'"1:1"'
    old_validator = adapter.validator
    IncreasingMinimum.minimum = 5
    adapter.rebuild(force=True)
    assert adapter.validator is not old_validator
    with pytest.raises(ValidationError):
        codec.loads(b"1")
    assert codec.loads(b"5") == 5
    assert codec.dumps(5) == b'"5:5"'


def test_validation_plugin_keeps_default_event_arguments(monkeypatch):
    entered = []
    succeeded = []

    class Handler:
        def on_enter(self, value, **kwargs):
            entered.append((value, kwargs))

        def on_success(self, result):
            succeeded.append(result)

    class Plugin:
        def new_schema_validator(self, *args):
            return None, Handler(), None

    monkeypatch.setattr(_loader, "get_plugins", lambda: [Plugin()])
    adapter = TypeAdapter(list[int])
    codec = Codec(adapter)
    assert codec.loads(b"[1]") == [1]
    codec_event = entered[-1]
    assert adapter.validate_json(b"[1]") == [1]
    assert entered[-1] == codec_event
    assert succeeded == [[1], [1]]


def test_callback_warning_origins_and_module_filters_match_adapter():
    class Warned(BaseModel):
        count: int

        @field_validator("count")
        @classmethod
        def validate_count(cls, value):
            warnings.warn("validator callback", stacklevel=2)
            return value

        @field_serializer("count")
        def serialize_count(self, value):
            warnings.warn("serializer callback", stacklevel=2)
            return value

    adapter = TypeAdapter(Warned)
    codec = Codec(adapter)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = Warned(count=2)
    for reference, actual, error_type in (
        (
            lambda: adapter.dump_json(value, warnings=False),
            lambda: codec.dumps(value, warnings=False),
            PydanticSerializationError,
        ),
        (
            lambda: adapter.validate_json(b'{"count":2}'),
            lambda: codec.loads(b'{"count":2}'),
            UserWarning,
        ),
    ):
        with pytest.warns(UserWarning) as expected:
            reference()
        with pytest.warns(UserWarning) as observed:
            actual()
        assert [(w.filename, str(w.message)) for w in observed] == [
            (w.filename, str(w.message)) for w in expected
        ]
        with warnings.catch_warnings():
            warnings.filterwarnings("error", module=r"pydantic\.type_adapter")
            with pytest.raises(error_type) as expected_error:
                reference()
            with pytest.raises(error_type) as actual_error:
                actual()
            assert str(actual_error.value) == str(expected_error.value)


def test_default_factory_and_computed_field_warning_origins_are_preserved():
    def default_count():
        warnings.warn("default factory", stacklevel=2)
        return 2

    class Computed(BaseModel):
        count: int = Field(default_factory=default_count)

        @computed_field
        @property
        def doubled(self) -> int:
            warnings.warn("computed field", stacklevel=2)
            return self.count * 2

    adapter = TypeAdapter(Computed)
    codec = Codec(adapter)
    with pytest.warns(UserWarning) as expected:
        value = adapter.validate_json(b"{}")
    with pytest.warns(UserWarning) as observed:
        assert codec.loads(b"{}") == value
    assert [w.filename for w in observed] == [w.filename for w in expected]
    with pytest.warns(UserWarning) as expected:
        encoded = adapter.dump_json(value, warnings=False)
    with pytest.warns(UserWarning) as observed:
        assert codec.dumps(value, warnings=False) == encoded
    assert [w.filename for w in observed] == [w.filename for w in expected]


def test_rebuild_introducing_callbacks_preserves_warning_origins():
    def warn_validate(value):
        warnings.warn("rebuilt validator", stacklevel=2)
        return value

    def warn_serialize(value):
        warnings.warn("rebuilt serializer", stacklevel=2)
        return value

    class Rebuildable:
        callbacks = False

        @classmethod
        def __get_pydantic_core_schema__(cls, source, handler):
            if not cls.callbacks:
                return core_schema.int_schema()
            return core_schema.no_info_before_validator_function(
                warn_validate,
                core_schema.int_schema(),
                serialization=core_schema.plain_serializer_function_ser_schema(
                    warn_serialize
                ),
            )

    adapter = TypeAdapter(Rebuildable)
    codec = Codec(adapter)
    assert codec.loads(b"2") == 2
    assert codec.dumps(2, warnings=False) == b"2"
    Rebuildable.callbacks = True
    assert adapter.rebuild(force=True)
    with pytest.warns(UserWarning) as expected:
        adapter.validate_json(b"2")
    with pytest.warns(UserWarning) as observed:
        codec.loads(b"2")
    assert [w.filename for w in observed] == [w.filename for w in expected]
    with pytest.warns(UserWarning) as expected:
        adapter.dump_json(2, warnings=False)
    with pytest.warns(UserWarning) as observed:
        codec.dumps(2, warnings=False)
    assert [w.filename for w in observed] == [w.filename for w in expected]


def test_core_object_replacement_preserves_public_warning_origins():
    def warn_validate(value):
        warnings.warn("replaced validator", stacklevel=2)
        return value

    def warn_serialize(value):
        warnings.warn("replaced serializer", stacklevel=2)
        return value

    adapter = TypeAdapter(int)
    codec = Codec(adapter)
    schema = adapter.core_schema
    adapter.validator = SchemaValidator(
        core_schema.no_info_before_validator_function(
            warn_validate, core_schema.int_schema()
        )
    )
    adapter.serializer = SchemaSerializer(
        core_schema.int_schema(
            serialization=core_schema.plain_serializer_function_ser_schema(
                warn_serialize
            )
        )
    )
    assert adapter.core_schema is schema
    with pytest.warns(UserWarning) as expected:
        adapter.validate_json(b"2")
    with pytest.warns(UserWarning) as observed:
        codec.loads(b"2")
    assert [w.filename for w in observed] == [w.filename for w in expected]

    with pytest.warns(UserWarning) as expected:
        adapter.dump_json(2, warnings=False)
    with pytest.warns(UserWarning) as observed:
        codec.dumps(2, warnings=False)
    assert [w.filename for w in observed] == [w.filename for w in expected]


def test_model_hook_added_after_codec_construction_preserves_warning_origin(
    monkeypatch,
):
    class Plain(BaseModel):
        count: int

    codec = Codec(Plain)

    def allocate(cls, *args, **kwargs):
        warnings.warn("late model allocation hook", stacklevel=2)
        return object.__new__(cls)

    monkeypatch.setattr(Plain, "__new__", staticmethod(allocate))
    with pytest.warns(UserWarning) as expected:
        codec.adapter.validate_json(b'{"count":2}')
    with pytest.warns(UserWarning) as observed:
        assert codec.loads(b'{"count":2}').count == 2
    assert [w.filename for w in observed] == [w.filename for w in expected]


def test_subclass_attribute_callback_keeps_public_serialization_warning_origin():
    class Plain(BaseModel):
        count: int

    class Custom(Plain):
        def __getattribute__(self, name):
            if name == "__dict__":
                warnings.warn("custom attribute hook", stacklevel=2)
            return super().__getattribute__(name)

    codec = Codec(Plain)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = Custom(count=2)
    with pytest.warns(UserWarning) as expected:
        reference = codec.adapter.dump_json(value, warnings=False)
    with pytest.warns(UserWarning) as observed:
        assert codec.dumps(value, warnings=False) == reference
    assert [w.filename for w in observed] == [w.filename for w in expected]
