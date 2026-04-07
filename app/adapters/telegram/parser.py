import html
import re

from app.core.models import TelegramRequestContext


def parse_telegram_input_data(data):
    message = data.get("message", {})
    user = message.get("from", {})
    return TelegramRequestContext(
        chat_id=message.get("chat", {}).get("id"),
        telegram_user_id=str(user.get("id") or ""),
        telegram_username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        user_message=message.get("text") or "",
    )


def format_telegram_output(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    formatted_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line or line == "---":
            formatted_lines.append("")
            continue

        escaped = html.escape(line)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

        if escaped.startswith("- "):
            escaped = "• " + escaped[2:]

        if re.match(r"^\d+\.\s", escaped):
            formatted_lines.append(escaped)
        else:
            formatted_lines.append(escaped)

    formatted = "\n".join(formatted_lines).strip()
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    return formatted
