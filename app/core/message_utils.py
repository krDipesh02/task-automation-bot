import json
from typing import Any, Iterable, Optional


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]).strip())
                elif item.get("content"):
                    parts.append(str(item["content"]).strip())
            elif item:
                parts.append(str(item).strip())
        return "\n".join(part for part in parts if part).strip()

    if content is None:
        return ""

    return str(content).strip()


def _looks_like_tool_narration(text: str) -> bool:
    lowered = text.lower()
    return (
        lowered.startswith("calling:")
        or "calling:" in lowered
        or "i'll search for" in lowered
        or "let me search for" in lowered
    )


def _iter_messages(result: dict) -> Iterable[Any]:
    return result.get("messages", []) or []


def extract_agent_response(result: dict) -> str:
    messages = list(_iter_messages(result))

    # Prefer the latest assistant message that contains actual user-facing text.
    for message in reversed(messages):
        message_type = getattr(message, "type", "")
        if message_type != "ai":
            continue

        content = _normalize_content(getattr(message, "content", ""))
        tool_calls = getattr(message, "tool_calls", None) or []

        if content and not tool_calls and not _looks_like_tool_narration(content):
            return content

    # Fall back to the latest tool result if the model never produced a final answer.
    for message in reversed(messages):
        if getattr(message, "type", "") != "tool":
            continue

        content = _normalize_content(getattr(message, "content", ""))
        if not content:
            continue

        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2)
        except Exception:
            return content

    # Last resort: return the newest non-empty content we have.
    for message in reversed(messages):
        content = _normalize_content(getattr(message, "content", ""))
        if content:
            return content

    return ""
