from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TelegramRequestContext:
    chat_id: Optional[int]
    telegram_user_id: str
    telegram_username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    user_message: str


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str


_current_request_context: ContextVar[TelegramRequestContext | None] = ContextVar(
    "current_request_context",
    default=None,
)
_current_conversation_history: ContextVar[list[ConversationTurn]] = ContextVar(
    "current_conversation_history",
    default=[],
)


def set_current_request_context(context: TelegramRequestContext) -> Token:
    return _current_request_context.set(context)


def reset_current_request_context(token: Token) -> None:
    _current_request_context.reset(token)


def get_current_request_context() -> TelegramRequestContext | None:
    return _current_request_context.get()


def set_current_conversation_history(history: list[ConversationTurn]) -> Token:
    return _current_conversation_history.set(history)


def reset_current_conversation_history(token: Token) -> None:
    _current_conversation_history.reset(token)


def get_current_conversation_history() -> list[ConversationTurn]:
    return _current_conversation_history.get()
