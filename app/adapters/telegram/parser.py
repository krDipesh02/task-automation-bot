def parse_telegram_input_data(data):
    message = data.get("message", {})
    return {
        "chat_id": message.get("chat", {}).get("id"),
        "user_message": message.get("text")
    }