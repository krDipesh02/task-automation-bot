import requests
import os
from app.adapters.telegram.parser import format_telegram_output
from app.utils.logger import get_logger

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger = get_logger(__name__)

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    formatted_text = format_telegram_output(text)
    payload = {
        "chat_id": chat_id,
        "text": formatted_text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=payload)
    if not response.ok:
        logger.error("Telegram send failed: %s", response.text)
