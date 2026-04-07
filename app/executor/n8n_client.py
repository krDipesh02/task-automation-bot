import json
import os
from typing import Optional

import requests
from sseclient import SSEClient
from app.core.models import TelegramRequestContext, get_current_conversation_history
from app.services.spendwise_service import get_automation_access_token
from app.utils.logger import get_logger

N8N_MCP_URL = os.getenv("N8N_MCP_URL")
N8N_AUTH_TOKEN = os.getenv("N8N_AUTH_TOKEN")
logger = get_logger(__name__)


def _build_headers() -> dict:
    return {
        "Authorization": f"Bearer {N8N_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _merge_request_context(params: Optional[dict], context: Optional[TelegramRequestContext]) -> dict:
    payload = dict(params or {})
    if context is None:
        return payload

    telegram_user_id = context.telegram_user_id
    provided = payload.get("telegram_user_id")
    if provided is not None and str(provided) != telegram_user_id:
        raise ValueError("telegram_user_id mismatch with trusted Telegram request context")
    payload["telegram_user_id"] = telegram_user_id
    provided_access_token = payload.get("access_token")
    trusted_access_token = get_automation_access_token(context)
    if provided_access_token is not None and str(provided_access_token) != trusted_access_token:
        raise ValueError("access_token mismatch with trusted Telegram request context")
    payload["access_token"] = trusted_access_token
    _inject_default_workflow_inputs(payload, context)
    return payload


def _inject_default_workflow_inputs(payload: dict, context: TelegramRequestContext) -> None:
    inputs = payload.get("inputs")
    if inputs is None:
        inputs = {}
        payload["inputs"] = inputs
    elif not isinstance(inputs, dict):
        raise ValueError("inputs must be an object when request context is injected")

    provided = inputs.get("telegram_user_id")
    if provided is not None and str(provided) != context.telegram_user_id:
        raise ValueError("inputs.telegram_user_id mismatch with trusted Telegram request context")

    trusted_access_token = get_automation_access_token(context)
    provided_access_token = inputs.get("access_token")
    if provided_access_token is not None and str(provided_access_token) != trusted_access_token:
        raise ValueError("inputs.access_token mismatch with trusted Telegram request context")

    inputs["telegram_user_id"] = context.telegram_user_id
    inputs["access_token"] = trusted_access_token
    inputs.setdefault("type", "chat")

    if not inputs.get("chatInput"):
        inputs["chatInput"] = _build_chat_input(context)


def _build_chat_input(context: TelegramRequestContext) -> str:
    prior_user_messages = [
        turn.content.strip()
        for turn in get_current_conversation_history()
        if turn.role == "user" and turn.content.strip()
    ]
    prior_user_messages.append(context.user_message.strip())
    unique_messages = []
    for message in prior_user_messages:
        if message and (not unique_messages or unique_messages[-1] != message):
            unique_messages.append(message)
    return "\n".join(unique_messages[-4:]).strip()


def _send_mcp_request(method: str, params: Optional[dict] = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }

    try:
        logger.info("Sending MCP request: %s", method)
        response = requests.post(
            N8N_MCP_URL,
            data=json.dumps(payload),
            headers=_build_headers(),
            stream=True,
        )
        response.raise_for_status()

        client = SSEClient(response)

        for event in client.events():
            if not event.data:
                continue

            parsed = json.loads(event.data)

            if "error" in parsed:
                logger.error("MCP error for %s: %s", method, parsed["error"])
                return {"error": parsed["error"]}

            if "result" in parsed:
                logger.info("Received MCP result for %s", method)
                return parsed["result"]

            logger.info("Received raw MCP payload for %s", method)
            return parsed

        logger.warning("No response from MCP for %s", method)
        return {"error": "No response from MCP"}

    except Exception as e:
        logger.exception("MCP request failed for %s: %s", method, e)
        return {"error": str(e)}
