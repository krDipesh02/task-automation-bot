import html
import re


def parse_telegram_input_data(data):
    message = data.get("message", {})
    return {
        "chat_id": message.get("chat", {}).get("id"),
        "user_message": message.get("text")
    }


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
