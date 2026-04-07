from app.agents.agent_registry import invoke_agent
from app.core.models import ConversationTurn, TelegramRequestContext
from app.core.router import route_to_agent
from app.services.spendwise_service import fetch_conversation_memory, store_conversation_memory
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def run_orchestrator(context: TelegramRequestContext) -> str:
    try:
        logger.info("Running orchestrator")
        history = fetch_conversation_memory(context)
        agent_name = route_to_agent(context.user_message, history)
        logger.info("Selected agent: %s", agent_name)
        response = await invoke_agent(agent_name, context.user_message, context, history=history)
        store_conversation_memory(
            context,
            history + [
                ConversationTurn(role="user", content=context.user_message),
                ConversationTurn(role="assistant", content=response),
            ],
        )
        return response
    except Exception as e:
        logger.exception("Orchestrator error: %s", e)
        return f"Error: {str(e)}"
