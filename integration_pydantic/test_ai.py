# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ValidationError

pytest.importorskip("pydantic_ai")

from pydantic_ai import (
    Agent,
    Conversation,
    ConversationTypeAdapter,
    DeferredToolRequests,
    models,
)
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel as OfflineModel

from orjson.pydantic import Codec
from orjson.pydantic_ai import (
    dump_conversation,
    dump_messages,
    load_conversation,
    load_messages,
)


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


def test_retry_and_binary_messages_roundtrip():
    timestamp = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    messages = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    [
                        "Inspect this",
                        BinaryContent(b"\x00\xff\x80", media_type="image/png"),
                    ],
                    timestamp=timestamp,
                ),
                RetryPromptPart(
                    "Use a positive count.",
                    tool_name="count",
                    tool_call_id="retry-1",
                    timestamp=timestamp,
                ),
            ]
        )
    ]
    encoded = dump_messages(messages)
    assert encoded == ModelMessagesTypeAdapter.dump_json(messages)
    restored = load_messages(encoded)
    assert restored == ModelMessagesTypeAdapter.validate_json(encoded)
    assert restored[0].parts[0].content[1].data == b"\x00\xff\x80"
    assert restored[0].parts[1].tool_call_id == "retry-1"


def test_actual_agent_history_persists_and_resumes(monkeypatch):
    monkeypatch.setenv("PYDANTIC_AI_NO_BANNER", "1")
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    agent = Agent(OfflineModel(custom_output_text="stored answer"))
    first = agent.run_sync("First question")
    history = load_messages(dump_messages(first.all_messages()))
    resumed = agent.run_sync("Next question", message_history=history)
    assert resumed.output == "stored answer"
    assert resumed.all_messages()[: len(history)] == history
    assert len(resumed.new_messages()) == 2


def test_conversation_retains_state_across_actual_agent_runs(monkeypatch):
    monkeypatch.setenv("PYDANTIC_AI_NO_BANNER", "1")
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    agent = Agent(OfflineModel(custom_output_text="stored answer"))
    first = agent.run_sync("First question", conversation_id="persisted-conversation")
    state = first.conversation
    raw = dump_conversation(state)
    assert raw == ConversationTypeAdapter.dump_json(state)
    restored = load_conversation(raw)
    assert restored == ConversationTypeAdapter.validate_json(raw)
    assert restored.conversation_id == "persisted-conversation"
    assert restored.usage == state.usage
    previous_requests = restored.usage.requests
    resumed = agent.run_sync("Next question", conversation=restored)
    assert resumed.conversation_id == "persisted-conversation"
    assert resumed.conversation.usage.requests == previous_requests + 1
    assert resumed.all_messages()[: len(state.messages)] == state.messages
    assert dump_conversation(state, indent=2) == ConversationTypeAdapter.dump_json(
        state, indent=2
    )


def test_invalid_conversation_uses_official_validation_error():
    raw = b'{"messages":[{"kind":"unknown"}]}'
    with pytest.raises(ValidationError) as expected:
        ConversationTypeAdapter.validate_json(raw)
    with pytest.raises(ValidationError) as actual:
        load_conversation(raw)
    assert actual.value.errors() == expected.value.errors()


def test_conversation_preserves_deferred_tool_state_and_revision():
    call = ToolCallPart("approved_tool", {"count": 2}, "deferred-1")
    state = Conversation(
        messages=[ModelResponse(parts=[call])],
        conversation_id="pending-approval",
        deferred_tool_requests=DeferredToolRequests(
            approvals=[call],
            metadata={"deferred-1": {"requestor": "test"}},
            validated_args={"deferred-1": {"count": 2}},
        ),
        revision="revision-3",
        new_message_index=0,
    )
    restored = load_conversation(dump_conversation(state))
    assert restored == ConversationTypeAdapter.validate_json(
        ConversationTypeAdapter.dump_json(state)
    )
    assert restored.deferred_tool_requests.approvals[0].tool_call_id == "deferred-1"
    assert restored.deferred_tool_requests.validated_args == {
        "deferred-1": {"count": 2}
    }
    assert restored.revision == "revision-3"
    assert restored.new_message_index == 0


def test_streamed_agent_output_requires_complete_validation(monkeypatch):
    monkeypatch.setenv("PYDANTIC_AI_NO_BANNER", "1")
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    class Answer(BaseModel):
        count: int
        labels: list[str]

    agent = Agent(
        OfflineModel(custom_output_args={"count": 2, "labels": ["one", "two"]}),
        output_type=Answer,
    )

    async def run():
        async with agent.run_stream("Return two labels") as result:
            snapshots = [item async for item in result.stream_output(debounce_by=None)]
            return snapshots, await result.get_output(), result.all_messages()

    snapshots, answer, messages = asyncio.run(run())
    assert snapshots
    codec = Codec(Answer)
    complete = codec.dumps(answer)
    assert codec.loads(complete) == Answer(count=2, labels=["one", "two"])
    with pytest.raises(ValidationError):
        codec.loads(complete[:-1])
    restored_history = load_messages(dump_messages(messages))
    assert restored_history == ModelMessagesTypeAdapter.validate_json(
        ModelMessagesTypeAdapter.dump_json(messages)
    )
