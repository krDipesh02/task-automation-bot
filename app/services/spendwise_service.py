import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from app.core.models import ConversationTurn, TelegramRequestContext
from app.utils.logger import get_logger


SPENDWISE_BASE_URL = os.getenv("SPENDWISE_BASE_URL", "").rstrip("/")
SPENDWISE_BACKEND_AUTH_TOKEN = os.getenv("SPENWISE_BACKEND_AUTH_TOKEN", "")

logger = get_logger(__name__)
_TOKEN_REFRESH_SKEW = timedelta(seconds=30)
_automation_token_cache: dict[str, tuple[str, datetime | None]] = {}

def bootstrap_telegram_user(context: TelegramRequestContext) -> Dict[str, Any]:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_BACKEND_AUTH_TOKEN:
        raise RuntimeError("SPENDWISE_BACKEND_AUTH_TOKEN is not configured")

    response = requests.post(
        f"{SPENDWISE_BASE_URL}/auth/telegram/bootstrap",
        json={
            "telegramUserId": context.telegram_user_id,
            "telegramUsername": context.telegram_username,
            "firstName": context.first_name,
            "lastName": context.last_name,
        },
        headers={
            "Authorization": f"Bearer {SPENDWISE_BACKEND_AUTH_TOKEN}",
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
    logger.info("Spendwise bootstrap completed for telegram_user_id=%s", context.telegram_user_id)
    return payload


def issue_automation_access_token(context: TelegramRequestContext) -> Dict[str, Any]:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_BACKEND_AUTH_TOKEN:
        raise RuntimeError("SPENWISE_BACKEND_AUTH_TOKEN is not configured")

    response = requests.post(
        f"{SPENDWISE_BASE_URL}/auth/automation/exchange",
        json={
            "telegramUserId": context.telegram_user_id,
        },
        headers={
            "Authorization": f"Bearer {SPENDWISE_BACKEND_AUTH_TOKEN}",
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
    _cache_automation_access_token(context.telegram_user_id, payload)
    logger.info(
        "Spendwise automation JWT issued for telegram_user_id=%s expires_at=%s",
        context.telegram_user_id,
        payload.get("expiresAt"),
    )
    return payload


def get_automation_access_token(context: TelegramRequestContext, *, force_refresh: bool = False) -> str:
    cached_token = None if force_refresh else _get_cached_automation_access_token(context.telegram_user_id)
    if cached_token:
        return cached_token

    payload = issue_automation_access_token(context)
    token = payload.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("Spendwise automation exchange did not return an access token")
    return token.strip()


def _get_cached_automation_access_token(telegram_user_id: str) -> str | None:
    cached = _automation_token_cache.get(telegram_user_id)
    if cached is None:
        return None

    token, expires_at = cached
    now = datetime.now(timezone.utc)
    if expires_at is not None and expires_at <= now + _TOKEN_REFRESH_SKEW:
        _automation_token_cache.pop(telegram_user_id, None)
        return None
    return token


def _cache_automation_access_token(telegram_user_id: str, payload: Dict[str, Any]) -> None:
    token = payload.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        return
    expires_at = _parse_expires_at(payload.get("expiresAt"))
    _automation_token_cache[telegram_user_id] = (token.strip(), expires_at)


def _parse_expires_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        logger.warning("Unable to parse Spendwise token expiry: %s", raw)
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_bootstrap_response(payload: Dict[str, Any]) -> str:
    display_name = payload.get("displayName") or "there"
    if payload.get("created"):
        return (
            f"Hi {display_name}, Please tell me what you want to do today. "
        )
    return (
        f"Hi {display_name}, Please tell me what you want to do today. "
    )


def fetch_conversation_memory(context: TelegramRequestContext) -> List[ConversationTurn]:
    if not SPENDWISE_BASE_URL:
        raise RuntimeError("SPENDWISE_BASE_URL is not configured")
    if not SPENDWISE_BACKEND_AUTH_TOKEN:
        raise RuntimeError("SPENWISE_BACKEND_AUTH_TOKEN is not configured")

    response = requests.get(
        f"{SPENDWISE_BASE_URL}/auth/telegram/memory/{context.telegram_user_id}",
        headers={
            "Authorization": f"Bearer {SPENDWISE_BACKEND_AUTH_TOKEN}",
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
    if not SPENDWISE_BACKEND_AUTH_TOKEN:
        raise RuntimeError("SPENWISE_BACKEND_AUTH_TOKEN is not configured")

    response = requests.put(
        f"{SPENDWISE_BASE_URL}/auth/telegram/memory/{context.telegram_user_id}",
        json={
            "telegramUserId": context.telegram_user_id,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
        },
        headers={
            "Authorization": f"Bearer {SPENDWISE_BACKEND_AUTH_TOKEN}",
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
    if not SPENDWISE_BACKEND_AUTH_TOKEN:
        raise RuntimeError("SPENWISE_BACKEND_AUTH_TOKEN is not configured")

    response = requests.delete(
        f"{SPENDWISE_BASE_URL}/auth/telegram/memory/{context.telegram_user_id}",
        headers={
            "Authorization": f"Bearer {SPENDWISE_BACKEND_AUTH_TOKEN}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Cleared conversation memory for telegram_user_id=%s", context.telegram_user_id)
