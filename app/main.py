import hmac
import os

from fastapi import FastAPI, HTTPException, Request
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
    submit_telegram_invite_claim,
    lookup_telegram_authorization,
    clear_conversation_memory,
)
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

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
    if not TELEGRAM_WEBHOOK_SECRET:
        logger.error("Telegram webhook rejected because TELEGRAM_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured")
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(supplied_secret.encode("utf-8"), TELEGRAM_WEBHOOK_SECRET.encode("utf-8")):
        logger.warning("Rejected Telegram webhook with invalid secret header")
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook credential")
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

        # Telegram command parsing remains at the webhook boundary. Activation
        # never enters the agent, MCP, or business API pipeline.
        command = user_message.strip().split(maxsplit=1)
        command_name = command[0].split("@", 1)[0].lower() if command else ""
        if command_name == "/start":
            invite_token = command[1].strip() if len(command) > 1 else ""
            if not invite_token:
                response = "You are not authorized to use this bot. Please contact the administrator."
            else:
                try:
                    claim = submit_telegram_invite_claim(
                        parsed.telegram_user_id, invite_token, parsed.telegram_username,
                        parsed.first_name, parsed.last_name,
                    )
                    if claim.get("status") == "PENDING_APPROVAL":
                        response = "Your request was submitted. An administrator must approve your Telegram account before you can use SpendWise."
                    elif claim.get("success"):
                        response = "Your account has been activated. You can now use SpendWise."
                    elif claim.get("status") == "ACCOUNT_BLOCKED":
                        response = "Your SpendWise account is blocked. Please contact the administrator."
                    else:
                        response = "This invitation is invalid or has expired. Please contact the administrator."
                except Exception:
                    logger.exception("Telegram activation service unavailable")
                    response = "I couldn't verify this invitation right now. Please try again shortly."
            send_message(chat_id, response)
            return {"status": "ok"}

        try:
            authorization = lookup_telegram_authorization(parsed.telegram_user_id)
        except Exception:
            logger.exception("Telegram authorization lookup failed")
            send_message(chat_id, "I couldn't verify your authorization right now. Please try again shortly.")
            return {"status": "error"}
        account_status = str(authorization.get("status", "NOT_FOUND")).upper()
        if account_status == "BLOCKED":
            response = "Your SpendWise account is blocked. Please contact the administrator."
        elif account_status == "PENDING_APPROVAL":
            response = "Your request is awaiting administrator approval. Please try again after it has been approved."
        elif account_status != "ACTIVE":
            response = "You are not authorized to use this bot. Please contact the administrator."
        elif user_message.strip().lower() in {"/reset", "/clear"}:
            logger.info("Clearing memory for authorized telegram_user_id=%s", parsed.telegram_user_id)
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
