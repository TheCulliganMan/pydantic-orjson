# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

pytest.importorskip("pydantic_ai")

from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from orjson.pydantic_ai import dump_messages, load_messages


def test_message_history_roundtrip_uses_official_schema_without_network():
    timestamp = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    messages = [
        ModelRequest(
            parts=[
                SystemPromptPart("Return the temperature.", timestamp=timestamp),
                UserPromptPart("What is the temperature?", timestamp=timestamp),
            ],
            run_id="run-test",
        ),
        ModelResponse(
            parts=[ToolCallPart("temperature", {"city": "Duluth"}, "call-1")],
            timestamp=timestamp,
            model_name="offline-test",
            run_id="run-test",
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    "temperature", {"celsius": -3}, "call-1", timestamp=timestamp
                )
            ],
            run_id="run-test",
        ),
        ModelResponse(
            parts=[TextPart("It is -3 C.")],
            timestamp=timestamp,
            model_name="offline-test",
            metadata={"source": "synthetic-test"},
            run_id="run-test",
        ),
    ]
    encoded = dump_messages(messages)
    assert encoded == ModelMessagesTypeAdapter.dump_json(messages)
    restored = load_messages(encoded)
    assert restored == ModelMessagesTypeAdapter.validate_json(encoded)
    assert dump_messages(restored) == encoded
    assert restored[1].parts[0].tool_call_id == "call-1"
    assert restored[2].parts[0].content == {"celsius": -3}
    assert restored[3].timestamp == timestamp
    assert restored[3].metadata == {"source": "synthetic-test"}
    assert dump_messages(messages, indent=2) == ModelMessagesTypeAdapter.dump_json(
        messages, indent=2
    )


def test_invalid_history_preserves_validation_error():
    raw = b'[{"kind":"unknown","parts":[]}]'
    with pytest.raises(ValidationError) as expected:
        ModelMessagesTypeAdapter.validate_json(raw)
    with pytest.raises(ValidationError) as actual:
        load_messages(raw)
    assert actual.value.errors() == expected.value.errors()
