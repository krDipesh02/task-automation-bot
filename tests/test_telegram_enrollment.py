import json
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from app import main


def request_for(text, telegram_id="12345"):
    body = {"message": {"text": text, "chat": {"id": 99}, "from": {"id": int(telegram_id)}}}
    sent = False
    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
    scope = {"type": "http", "method": "POST", "path": "/webhook/telegram", "headers": [(b"x-telegram-bot-api-secret-token", b"hook-secret")], "query_string": b""}
    return Request(scope, receive)


@pytest.mark.asyncio
async def test_unknown_telegram_user_is_stopped_before_orchestrator(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "lookup_telegram_authorization", return_value={"status": "NOT_FOUND"}), \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock) as orchestrator, \
         patch.object(main, "send_message") as send:
        result = await main.telegram_webhook(request_for("hello"))
    assert result == {"status": "ok"}
    orchestrator.assert_not_awaited()
    assert "not authorized" in send.call_args.args[1].lower()


@pytest.mark.asyncio
async def test_active_telegram_user_reaches_orchestrator(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "lookup_telegram_authorization", return_value={"status": "ACTIVE"}), \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock, return_value="Done") as orchestrator, \
         patch.object(main, "send_message"):
        await main.telegram_webhook(request_for("show my expenses"))
    orchestrator.assert_awaited_once()
    assert orchestrator.await_args.args[0].telegram_user_id == "12345"


@pytest.mark.asyncio
async def test_blocked_user_is_stopped_before_orchestrator(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "lookup_telegram_authorization", return_value={"status": "BLOCKED"}), \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock) as orchestrator, \
         patch.object(main, "send_message") as send:
        await main.telegram_webhook(request_for("hello"))
    orchestrator.assert_not_awaited()
    assert "blocked" in send.call_args.args[1].lower()


@pytest.mark.asyncio
async def test_start_invite_is_handled_without_orchestrator(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "submit_telegram_invite_claim", return_value={"success": True, "status": "ALREADY_ACTIVE"}) as claim, \
         patch.object(main, "lookup_telegram_authorization") as lookup, \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock) as orchestrator, \
         patch.object(main, "send_message") as send:
        await main.telegram_webhook(request_for("/start secret-token"))
    claim.assert_called_once_with("12345", "secret-token", None, None, None)
    lookup.assert_not_called()
    orchestrator.assert_not_awaited()
    assert "activated" in send.call_args.args[1].lower()


@pytest.mark.asyncio
async def test_start_claim_waits_for_admin_approval(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "submit_telegram_invite_claim", return_value={"success": True, "status": "PENDING_APPROVAL"}) as claim, \
         patch.object(main, "lookup_telegram_authorization") as lookup, \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock) as orchestrator, \
         patch.object(main, "send_message") as send:
        await main.telegram_webhook(request_for("/start secret-token"))
    claim.assert_called_once()
    lookup.assert_not_called()
    orchestrator.assert_not_awaited()
    assert "administrator" in send.call_args.args[1].lower()


@pytest.mark.asyncio
async def test_setup_command_sends_one_time_link_without_agent(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "create_telegram_credential_setup_link", return_value="https://spendwise.test/setup-password?token=one-time") as setup, \
         patch.object(main, "lookup_telegram_authorization") as lookup, \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock) as orchestrator, \
         patch.object(main, "send_message") as send:
        await main.telegram_webhook(request_for("/setup"))
    setup.assert_called_once_with("12345")
    lookup.assert_not_called()
    orchestrator.assert_not_awaited()
    assert "one-time" in send.call_args.args[1]


@pytest.mark.asyncio
async def test_invalid_invite_returns_safe_message_without_orchestrator(monkeypatch):
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch.object(main, "submit_telegram_invite_claim", return_value={"success": False}), \
         patch.object(main, "run_orchestrator", new_callable=AsyncMock) as orchestrator, \
         patch.object(main, "send_message") as send:
        await main.telegram_webhook(request_for("/start bad-token"))
    orchestrator.assert_not_awaited()
    assert "invalid or has expired" in send.call_args.args[1].lower()

@pytest.mark.asyncio
async def test_mcp_interceptor_replaces_model_supplied_identity():
    from langchain_mcp_adapters.interceptors import MCPToolCallRequest
    from app.agents.spendwise_agent import _inject_trusted_telegram_identity
    from app.core.models import TelegramRequestContext, reset_current_request_context, set_current_request_context

    context = main.parse_telegram_input_data({"message": {"from": {"id": 12345}, "chat": {"id": 99}, "text": "hello"}})
    token = set_current_request_context(context)
    request = MCPToolCallRequest(name="expense_create", args={"telegram_user_id": "99999", "amount": 1}, server_name="spendwise")
    seen = {}
    async def handler(overridden):
        seen.update(overridden.args)
        return "ok"
    try:
        await _inject_trusted_telegram_identity(request, handler)
    finally:
        reset_current_request_context(token)
    assert seen["telegram_user_id"] == "12345"
    assert seen["amount"] == 1


def test_activation_helper_calls_authenticated_backend(monkeypatch):
    from app.services import spendwise_service
    from unittest.mock import Mock

    response = Mock(status_code=200)
    response.json.return_value = {"status": "PENDING_APPROVAL", "userId": None}
    post = Mock(return_value=response)
    monkeypatch.setattr(spendwise_service, "SPENDWISE_BASE_URL", "http://backend/api/v1")
    monkeypatch.setattr(spendwise_service, "SPENDWISE_TELEGRAM_SERVICE_TOKEN", "service-secret")
    monkeypatch.setattr(spendwise_service.requests, "post", post)

    result = spendwise_service.submit_telegram_invite_claim("12345", "raw-invite", "dipesh", "Dipesh", "K")

    assert result["success"] is True
    post.assert_called_once()
    args, kwargs = post.call_args
    assert args[0] == "http://backend/api/v1/internal/telegram/claim"
    assert kwargs["headers"]["Authorization"] == "Bearer service-secret"
    assert kwargs["json"] == {"telegramUserId": "12345", "inviteToken": "raw-invite", "username": "dipesh", "firstName": "Dipesh", "lastName": "K"}


def test_invalid_invite_response_does_not_expose_backend_error(monkeypatch):
    from app.services import spendwise_service
    from unittest.mock import Mock

    response = Mock(status_code=409)
    response.json.return_value = {"detail": "INVITE_ALREADY_USED"}
    monkeypatch.setattr(spendwise_service, "SPENDWISE_BASE_URL", "http://backend/api/v1")
    monkeypatch.setattr(spendwise_service, "SPENDWISE_TELEGRAM_SERVICE_TOKEN", "service-secret")
    monkeypatch.setattr(spendwise_service.requests, "post", Mock(return_value=response))

    result = spendwise_service.submit_telegram_invite_claim("12345", "raw-invite")

    assert result["success"] is False
    assert "INVITE_ALREADY_USED" not in result["status"]


@pytest.mark.asyncio
async def test_webhook_rejects_forged_update_before_backend_lookup(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(main, "TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    with patch.object(main, "lookup_telegram_authorization") as lookup:
        with pytest.raises(HTTPException) as exc:
            await main.telegram_webhook(request_for("hello"))
    assert exc.value.status_code == 403
    lookup.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_requires_secret_configuration():
    from fastapi import HTTPException
    with patch.object(main, "TELEGRAM_WEBHOOK_SECRET", ""):
        with pytest.raises(HTTPException) as exc:
            await main.telegram_webhook(request_for("hello"))
    assert exc.value.status_code == 503
