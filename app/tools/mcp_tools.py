from __future__ import annotations

import os
from typing import Sequence

from dotenv import load_dotenv
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest, MCPToolCallResult

from app.core.models import get_current_conversation_history, get_current_request_context
from app.services.spendwise_service import get_automation_access_token

from app.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

_n8n_client: MultiServerMCPClient | None = None
_n8n_tools: list[BaseTool] = []


def _require_n8n_config() -> tuple[str, str]:
    n8n_mcp_url = os.getenv("N8N_MCP_URL")
    n8n_auth_token = os.getenv("N8N_AUTH_TOKEN")
    if not n8n_mcp_url:
        raise RuntimeError("N8N_MCP_URL is not configured")
    if not n8n_auth_token:
        raise RuntimeError("N8N_AUTH_TOKEN is not configured")
    return n8n_mcp_url, n8n_auth_token


def _build_chat_input() -> str:
    context = get_current_request_context()
    if context is None:
        return ""

    prior_user_messages = [
        turn.content.strip()
        for turn in get_current_conversation_history()
        if turn.role == "user" and turn.content.strip()
    ]
    prior_user_messages.append(context.user_message.strip())
    unique_messages: list[str] = []
    for message in prior_user_messages:
        if message and (not unique_messages or unique_messages[-1] != message):
            unique_messages.append(message)
    return "\n".join(unique_messages[-4:]).strip()


async def _inject_trusted_context(
    request: MCPToolCallRequest,
    handler,
) -> MCPToolCallResult:
    context = get_current_request_context()
    if context is None or request.name != "execute_workflow":
        return await handler(request)

    # Safely extract inputs
    args = dict(request.args or {})
    inputs = args.get("inputs") or {}

    if not isinstance(inputs, dict):
        raise ValueError("execute_workflow inputs must be an object")

    # Prevent spoofing of telegram_user_id
    provided_user_id = inputs.get("telegram_user_id")
    if provided_user_id is not None and str(provided_user_id) != context.telegram_user_id:
        raise ValueError("inputs.telegram_user_id mismatch with trusted context")

    # Inject trusted value
    inputs["telegram_user_id"] = context.telegram_user_id
    args["inputs"] = inputs

    return await handler(request.override(args=args))

async def close_n8n_tools() -> None:
    global _n8n_client, _n8n_tools
    _n8n_client = None
    _n8n_tools = []
