# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Optional message-history helpers using Pydantic AI's official adapter.

This module does not replace an agent's internal serialization or validation.
Pydantic AI is imported on the first call, and the library's own message schema
is reused rather than duplicated here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from .pydantic import Codec

if TYPE_CHECKING:
    from pydantic_ai import Conversation
    from pydantic_ai.messages import ModelMessage

__all__ = (
    "dump_conversation",
    "dump_messages",
    "load_conversation",
    "load_messages",
)


@lru_cache(maxsize=1)
def _messages_codec() -> Codec[list[ModelMessage]]:
    from pydantic_ai.messages import ModelMessagesTypeAdapter  # noqa: PLC0415

    return Codec(ModelMessagesTypeAdapter)


def dump_messages(messages: list[ModelMessage], **kwargs: Any) -> bytes:
    """Encode message history with the official adapter and Pydantic dump options."""
    return _messages_codec().dumps(messages, **kwargs)


def load_messages(data: str | bytes | bytearray, **kwargs: Any) -> list[ModelMessage]:
    """Decode history with the official adapter and Pydantic validation options."""
    return _messages_codec().loads(data, **kwargs)


@lru_cache(maxsize=1)
def _conversation_codec() -> Codec[Conversation]:
    from pydantic_ai import ConversationTypeAdapter  # noqa: PLC0415

    return Codec(ConversationTypeAdapter)


def dump_conversation(conversation: Conversation, **kwargs: Any) -> bytes:
    """Encode resumable messages, usage, IDs and deferred tools with the AI schema."""
    return _conversation_codec().dumps(conversation, **kwargs)


def load_conversation(data: str | bytes | bytearray, **kwargs: Any) -> Conversation:
    """Decode resumable agent state with the official conversation adapter."""
    return _conversation_codec().loads(data, **kwargs)
