# Optional Pydantic integration

This project keeps `import orjson`, `orjson.dumps`, and `orjson.loads` unchanged.
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
`dumps` returns bytes; `loads` returns the schema's type. Keyword arguments,
validation/serialization context, and exceptions pass through unchanged.
Options are those of the installed Pydantic version; native orjson option bits
are not accepted by these typed APIs.

Both operations use public TypeAdapter methods. This preserves custom adapter
methods, instrumentation, model hooks, rebuilt schemas and warning filters,
including callbacks installed after codec construction. The codec does not
cache native serializer/validator objects or replace Pydantic's schema engine.
Reusing a codec avoids adapter construction on each operation; direct native
Pydantic calls remain the performance reference.

A direct-core shortcut was evaluated and rejected because it changes warning
origins and module-based warning filters. Even a previously plain model can
gain dynamic Python hooks without replacing its core schema. These semantics
are retained rather than trading them for forwarding-layer benchmark gains.

JSON validation is intentionally direct. Parsing first with `orjson.loads` and
then calling `validate_python` would change strict-mode behavior for dates,
tuples, and other types. Custom validators and serializers, aliases, exclusions,
and schema-directed subclass filtering remain Pydantic's responsibility.

The native library and Pydantic codec support Python 3.10+. Pydantic AI and
FastAPI integration tests require Python 3.11+; on 3.10 the `ai` extra omits
Pydantic AI and does not enable the history/conversation helpers.

For free-threaded Python, current Pydantic/AI integration targets 3.14t and
3.15t. Experimental 3.13t is native-orjson-only qualification using the separate
`native313t` test group; current Pydantic-core/AI dependencies do not provide
supported 3.13t builds. Do not interpret a passing native 3.13t wheel as
qualification of these optional codecs on that interpreter.

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

For full resumable conversation state in Pydantic AI 2.73+, use the official
conversation schema through these helpers:

```python
from orjson.pydantic_ai import dump_conversation, load_conversation

stored = dump_conversation(result.conversation)
conversation = load_conversation(stored)
resumed = agent.run_sync("Continue", conversation=conversation)
```

`ConversationTypeAdapter` preserves message history, cumulative usage,
conversation ID, deferred tool requests, revision and message-position state
according to the installed AI version. These functions forward the same
Pydantic options as the message helpers. They perform no implicit permission
grants, provider calls, storage operations or conversions outside the official
schema. Applications remain responsible for their storage access policy.

Partial validation is available only when explicitly requested through the
Pydantic `experimental_allow_partial` keyword. It is experimental and may omit
an invalid final item; always validate the complete final input again with
partial mode disabled before accepting it as complete.

Tests include offline `TestModel` agent runs, conversation/history replay,
deferred-tool state, binary/retry messages and a streamed structured output.
External model requests are disabled in those agent tests. Prepare the locked
`native` and `integration` groups with UV and install the built wheel using the
[development build](../README.md#build-and-use), then run:

```sh
uv run --no-sync pytest integration_pydantic
```

Use UV 0.13.9+ throughout. The `--no-sync` flag keeps the installed wheel under
test; dependency changes belong in `pyproject.toml` and `uv.lock`.

References:

- [Pydantic TypeAdapter](https://docs.pydantic.dev/latest/api/type_adapter/)
- [Pydantic JSON semantics](https://docs.pydantic.dev/latest/concepts/json/)
- [Partial validation](https://docs.pydantic.dev/latest/concepts/experimental/)
- [Pydantic AI message history](https://ai.pydantic.dev/message-history/)
