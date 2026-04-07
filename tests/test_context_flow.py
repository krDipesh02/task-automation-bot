from unittest.mock import patch

from app.adapters.telegram.parser import parse_telegram_input_data
from app.agents.agent_registry import _build_n8n_execution_context
from app.core.models import (
    ConversationTurn,
    TelegramRequestContext,
    reset_current_conversation_history,
    set_current_conversation_history,
)
from app.executor.n8n_client import _build_chat_input, _merge_request_context
from app.prompts.agent_prompts import build_router_user_prompt
from app.services.spendwise_service import build_bootstrap_response


def test_parse_telegram_input_data_extracts_user_context():
    parsed = parse_telegram_input_data(
        {
            "message": {
                "text": "spent 500 on food",
                "chat": {"id": 99},
                "from": {
                    "id": 12345,
                    "username": "alice",
                    "first_name": "Alice",
                    "last_name": "Doe",
                },
            }
        }
    )

    assert parsed == TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="spent 500 on food",
    )


def test_merge_request_context_injects_telegram_user_id():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="spent 500 on food",
    )

    with patch("app.executor.n8n_client.get_automation_access_token", return_value="jwt-123"):
        merged = _merge_request_context({"amount": 500}, context)
    assert merged["telegram_user_id"] == "12345"
    assert merged["access_token"] == "jwt-123"
    assert merged["amount"] == 500
    assert merged["inputs"]["telegram_user_id"] == "12345"
    assert merged["inputs"]["access_token"] == "jwt-123"
    assert merged["inputs"]["type"] == "chat"


def test_merge_request_context_rejects_mismatch():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="spent 500 on food",
    )

    try:
        with patch("app.executor.n8n_client.get_automation_access_token", return_value="jwt-123"):
            _merge_request_context({"telegram_user_id": "54321"}, context)
    except ValueError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("expected mismatch validation error")


def test_build_bootstrap_response_for_created_user():
    message = build_bootstrap_response({"created": True, "displayName": "Alice"})
    assert "Alice" in message
    assert "account is ready" in message


def test_router_prompt_includes_recent_automation_context():
    prompt = build_router_user_prompt(
        "not needed",
        "\n".join([
            f"{ConversationTurn(role='user', content='expense 500 on food').role}: expense 500 on food",
            f"{ConversationTurn(role='assistant', content='Please provide merchant and description.').role}: Please provide merchant and description.",
        ]),
    )

    assert "Recent conversation:" in prompt
    assert "expense 500 on food" in prompt
    assert "Please provide merchant and description." in prompt
    assert "short follow-up" in prompt


def test_merge_request_context_injects_nested_workflow_inputs():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="merchant is swiggy",
    )
    history = [ConversationTurn(role="user", content="spent 500 INR on food today")]
    token = set_current_conversation_history(history)
    try:
        with patch("app.executor.n8n_client.get_automation_access_token", return_value="jwt-123"):
            merged = _merge_request_context({"inputs": {}}, context)
    finally:
        reset_current_conversation_history(token)

    assert merged["telegram_user_id"] == "12345"
    assert merged["access_token"] == "jwt-123"
    assert merged["inputs"]["telegram_user_id"] == "12345"
    assert merged["inputs"]["access_token"] == "jwt-123"
    assert merged["inputs"]["type"] == "chat"
    assert "spent 500 INR on food today" in merged["inputs"]["chatInput"]
    assert "merchant is swiggy" in merged["inputs"]["chatInput"]


def test_merge_request_context_rejects_non_object_inputs():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="spent 500 on food",
    )

    try:
        with patch("app.executor.n8n_client.get_automation_access_token", return_value="jwt-123"):
            _merge_request_context({"inputs": "invalid"}, context)
    except ValueError as exc:
        assert "inputs must be an object" in str(exc)
    else:
        raise AssertionError("expected invalid inputs validation error")


def test_merge_request_context_rejects_access_token_mismatch():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="spent 500 on food",
    )

    try:
        with patch("app.executor.n8n_client.get_automation_access_token", return_value="jwt-123"):
            _merge_request_context({"access_token": "jwt-other"}, context)
    except ValueError as exc:
        assert "access_token mismatch" in str(exc)
    else:
        raise AssertionError("expected access token mismatch validation error")


def test_build_chat_input_uses_recent_user_messages():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="no description",
    )
    history = [
        ConversationTurn(role="assistant", content="Need merchant."),
        ConversationTurn(role="user", content="spent 500 INR on food today"),
        ConversationTurn(role="user", content="merchant is swiggy"),
    ]
    token = set_current_conversation_history(history)
    try:
        chat_input = _build_chat_input(context)
    finally:
        reset_current_conversation_history(token)

    assert "spent 500 INR on food today" in chat_input
    assert "merchant is swiggy" in chat_input
    assert "no description" in chat_input
    assert "Need merchant." not in chat_input


def test_build_n8n_execution_context_uses_trusted_token():
    context = TelegramRequestContext(
        chat_id=99,
        telegram_user_id="12345",
        telegram_username="alice",
        first_name="Alice",
        last_name="Doe",
        user_message="spent 500 on food",
    )

    with patch("app.agents.agent_registry.get_automation_access_token", return_value="jwt-123"):
        execution_context = _build_n8n_execution_context(context)

    assert "telegram_user_id: 12345" in execution_context
    assert "access_token: jwt-123" in execution_context
    assert "Never expose the access_token" in execution_context
