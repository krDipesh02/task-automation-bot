from fastapi import FastAPI, Request
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Import adapter + core
from app.adapters.telegram.parser import parse_telegram_input_data
from app.adapters.telegram.sender import send_message
from app.core.orchestrator import run_orchestrator

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "running"}

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()

        # Parse Telegram payload
        parsed = parse_telegram_input_data(data)

        chat_id = parsed.get("chat_id")
        user_message = parsed.get("user_message")

        # Ignore empty messages
        if not user_message:
            return {"status": "ignored"}

        # Run orchestrator (your logic)
        response = run_orchestrator(user_message)

        # Send response back to Telegram
        send_message(chat_id, response)

        return {"status": "ok"}

    except Exception as e:
        print("Error:", e)
        return {"status": "error"}