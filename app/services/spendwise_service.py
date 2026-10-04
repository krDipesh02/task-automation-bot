import os
from typing import Any, List

import requests

from app.core.models import ConversationTurn, TelegramRequestContext
from app.utils.logger import get_logger

SPENDWISE_BASE_URL = os.getenv("SPENDWISE_BASE_URL", "").rstrip("/")
SPENDWISE_TELEGRAM_SERVICE_TOKEN = os.getenv("SPENDWISE_TELEGRAM_SERVICE_TOKEN", "").strip()
logger = get_logger(__name__)

def _backend_headers() -> dict[str, str]:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_TELEGRAM_SERVICE_TOKEN:
        raise RuntimeError("SPENDWISE_TELEGRAM_SERVICE_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {SPENDWISE_TELEGRAM_SERVICE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def lookup_telegram_authorization(telegram_user_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{SPENDWISE_BASE_URL}/internal/telegram/users/{telegram_user_id}",
        headers=_backend_headers(), timeout=15,
    )
    if response.status_code == 404:
        return {"status": "NOT_FOUND"}
    response.raise_for_status()
    return response.json()


def submit_telegram_invite_claim(telegram_user_id: str, invite_token: str,
                                username: str | None = None, first_name: str | None = None,
                                last_name: str | None = None) -> dict[str, Any]:
    response = requests.post(
        f"{SPENDWISE_BASE_URL}/internal/telegram/claim",
        json={"telegramUserId": telegram_user_id, "inviteToken": invite_token,
              "username": username, "firstName": first_name, "lastName": last_name},
        headers=_backend_headers(), timeout=15,
    )
    if response.status_code == 403:
        return {"success": False, "status": "ACCOUNT_BLOCKED"}
    if response.status_code in {400, 404, 409, 410}:
        try:
            return {"success": False, "status": response.json().get("code", "INVALID_INVITE")}
        except (ValueError, requests.exceptions.JSONDecodeError):
            return {"success": False, "status": "INVALID_INVITE"}
    response.raise_for_status()
    payload = response.json()
    payload["success"] = payload.get("status") in {"PENDING_APPROVAL", "ALREADY_ACTIVE"}
    return payload


def create_telegram_credential_setup_link(telegram_user_id: str) -> str:
    response = requests.post(
        f"{SPENDWISE_BASE_URL}/internal/telegram/users/{telegram_user_id}/credential-setup",
        headers=_backend_headers(), timeout=15,
    )
    response.raise_for_status()
    return response.json()["setupUrl"]


def fetch_conversation_memory(context: TelegramRequestContext) -> List[ConversationTurn]:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_TELEGRAM_SERVICE_TOKEN:
        raise RuntimeError("SPENDWISE_TELEGRAM_SERVICE_TOKEN is not configured")

    response = requests.get(
        f"{SPENDWISE_BASE_URL}/internal/telegram/users/{context.telegram_user_id}/memory",
        headers={
            "Authorization": f"Bearer {SPENDWISE_TELEGRAM_SERVICE_TOKEN}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError:
        payload = {}
    return [
        ConversationTurn(role=item["role"], content=item["content"])
        for item in payload.get("messages", [])
        if item.get("role") and item.get("content")
    ]


def store_conversation_memory(context: TelegramRequestContext, messages: List[ConversationTurn]) -> List[ConversationTurn]:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_TELEGRAM_SERVICE_TOKEN:
        raise RuntimeError("SPENDWISE_TELEGRAM_SERVICE_TOKEN is not configured")

    response = requests.put(
        f"{SPENDWISE_BASE_URL}/internal/telegram/users/{context.telegram_user_id}/memory",
        json={
            "telegramUserId": context.telegram_user_id,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
        },
        headers={
            "Authorization": f"Bearer {SPENDWISE_TELEGRAM_SERVICE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=15,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError:
        payload = {}
    logger.info("Stored conversation memory for telegram_user_id=%s", context.telegram_user_id)
    return [
        ConversationTurn(role=item["role"], content=item["content"])
        for item in payload.get("messages", [])
        if item.get("role") and item.get("content")
    ]


def clear_conversation_memory(context: TelegramRequestContext) -> None:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_TELEGRAM_SERVICE_TOKEN:
        raise RuntimeError("SPENDWISE_TELEGRAM_SERVICE_TOKEN is not configured")

    response = requests.delete(
        f"{SPENDWISE_BASE_URL}/internal/telegram/users/{context.telegram_user_id}/memory",
        headers={
            "Authorization": f"Bearer {SPENDWISE_TELEGRAM_SERVICE_TOKEN}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Cleared conversation memory for telegram_user_id=%s", context.telegram_user_id)
