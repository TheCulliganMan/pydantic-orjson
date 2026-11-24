# Optional Pydantic integration

The fork keeps `import orjson`, `orjson.dumps`, and `orjson.loads` unchanged.
The following APIs are additive and use Pydantic's JSON semantics. They do not
claim to accelerate Pydantic's own native JSON engine.

```python
from datetime import date
from pydantic import BaseModel, ConfigDict
from orjson.pydantic import Codec


class Event(BaseModel):
    model_config = ConfigDict(strict=True)
    when: date
    coordinates: tuple[int, int]


codec = Codec(Event)  # Construct once, then reuse.
event = codec.loads(b'{"when":"2026-11-24","coordinates":[1,2]}')
assert codec.dumps(event) == b'{"when":"2026-11-24","coordinates":[1,2]}'
```

`Codec` also accepts an existing `pydantic.TypeAdapter`, which is retained by
identity and exposed through the read-only `.adapter` property. Supply an
existing adapter for explicit configuration or locally scoped forward references.
`dumps` delegates to `TypeAdapter.dump_json` and returns bytes; `loads` delegates
to `TypeAdapter.validate_json` and returns the schema's type. Keyword arguments,
validation/serialization context, and exceptions pass through unchanged.
Options are those of the installed Pydantic version; native orjson option bits
are not accepted by these typed APIs.

JSON validation is intentionally direct. Parsing first with `orjson.loads` and
then calling `validate_python` would change strict-mode behavior for dates,
tuples, and other types. Custom validators and serializers, aliases, exclusions,
and schema-directed subclass filtering remain Pydantic's responsibility.

For message history with the optional Pydantic AI dependency:

```python
from orjson.pydantic_ai import dump_messages, load_messages

stored = dump_messages(result.all_messages())
history = load_messages(stored)
```

These helpers reuse Pydantic AI's `ModelMessagesTypeAdapter`. They do not patch
agent internals or provider clients. Message history is not all resumable agent
state, and values typed `Any` can be normalized by a JSON round trip. Follow the
installed Pydantic AI version's persistence contract. Pydantic AI is imported
lazily on the first history-helper call.

Partial validation is available only when explicitly requested through the
Pydantic `experimental_allow_partial` keyword. It is experimental and may omit
an invalid final item; always validate the complete final input again with
partial mode disabled before accepting it as complete.

Tests are synthetic and make no network or model calls:

```sh
python -m pytest integration_pydantic
```

References:

- [Pydantic TypeAdapter](https://docs.pydantic.dev/latest/api/type_adapter/)
- [Pydantic JSON semantics](https://docs.pydantic.dev/latest/concepts/json/)
- [Partial validation](https://docs.pydantic.dev/latest/concepts/experimental/)
- [Pydantic AI message history](https://ai.pydantic.dev/message-history/)
