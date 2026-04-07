from fastapi import FastAPI, Request
from dotenv import load_dotenv
from fastapi.concurrency import asynccontextmanager

# Load env variables
load_dotenv()

# Import adapter + core
from app.adapters.telegram.parser import parse_telegram_input_data
from app.adapters.telegram.sender import send_message
from app.core.orchestrator import run_orchestrator
from app.agents.agent_registry import init_agents
from app.tools.mcp_tools import close_n8n_tools
from app.services.spendwise_service import (
    bootstrap_telegram_user,
    build_bootstrap_response,
    clear_conversation_memory
)
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = FastAPI()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application lifespan start")

    await init_agents()

    yield

    await close_n8n_tools()
    logger.info("Application lifespan end")

app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "running"}

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        logger.info("Telegram webhook received")

        # Parse Telegram payload
        parsed = parse_telegram_input_data(data)

        chat_id = parsed.chat_id
        user_message = parsed.user_message
        logger.info(
            "Parsed Telegram message chat_id=%s telegram_user_id=%s",
            chat_id,
            parsed.telegram_user_id,
        )

        # Ignore empty messages
        if not user_message:
            logger.info("Ignoring empty Telegram message", extra={"chat_id": chat_id})
            return {"status": "ignored"}

        if user_message.strip().lower() == "/hi":
            logger.info("Bootstrapping Telegram user chat_id=%s", chat_id)
            bootstrap_payload = bootstrap_telegram_user(parsed)
            response = build_bootstrap_response(bootstrap_payload)
        elif user_message.strip().lower() in {"/reset", "/clear"}:
            logger.info("Clearing memory for chat_id=%s telegram_user_id=%s", chat_id, parsed.telegram_user_id)
            clear_conversation_memory(parsed)
            response = "Conversation memory cleared. You can start a fresh request now."
        else:
            response = await run_orchestrator(parsed)
        logger.info("Generated orchestrator response", extra={"chat_id": chat_id})

        # Send response back to Telegram
        send_message(chat_id, response)
        logger.info("Sent Telegram response", extra={"chat_id": chat_id})

        return {"status": "ok"}

    except Exception as e:
        logger.exception("Telegram webhook failed: %s", e)
        return {"status": "error"}
