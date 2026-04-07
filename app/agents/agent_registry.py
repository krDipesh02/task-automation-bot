from typing import List, Optional, Tuple

from langgraph.prebuilt import create_react_agent
from app.agents.default_agent import get_default_agent
from app.agents.n8n_agent import get_n8n_agent
from app.agents.spendwise_agent import get_spendwise_agent
from app.services.llm_service import llm
from app.core.models import (
    ConversationTurn,
    TelegramRequestContext,
    reset_current_conversation_history,
    reset_current_request_context,
    set_current_conversation_history,
    set_current_request_context,
)
from app.services.spendwise_service import get_automation_access_token
from app.core.message_utils import extract_agent_response
from app.prompts.agent_prompts import DEFAULT_AGENT_PROMPT, N8N_AGENT_PROMPT, SPENDWISE_AGENT_PROMPT
from app.utils.logger import get_logger

_agents = {}
logger = get_logger(__name__)


async def init_agents():
    logger.info("Initializing agents")

    _agents["n8n_agent"] = await get_n8n_agent()

    _agents["default_agent"] = await get_default_agent()
    
    _agents["spendwise_agent"] = await get_spendwise_agent()

    logger.info("Agents initialized: %s", list(_agents.keys()))


def get_agents():
    if not _agents:
        raise RuntimeError("Agents are not initialized. Application startup did not complete.")
    return _agents


def _build_n8n_execution_context(context: TelegramRequestContext) -> str:
    # access_token = get_automation_access_token(context)
    return f"""
Trusted execution context for this Telegram request:
- telegram_user_id: {context.telegram_user_id}

Use these exact trusted values when a native n8n MCP tool requires them.
Never ask the user for either value.
Never expose the access_token in user-facing output.
""".strip()


async def invoke_agent(agent_name: str,
                       user_input: str,
                       context: Optional[TelegramRequestContext] = None,
                       history: Optional[List[ConversationTurn]] = None) -> str:
    agent = get_agents().get(agent_name)

    if agent is None:
        logger.error("Agent not initialized: %s", agent_name)
        return f"❌ Agent '{agent_name}' not initialized"

    logger.info("Invoking agent: %s", agent_name)
    token = set_current_request_context(context) if context is not None else None
    history_token = set_current_conversation_history(history or [])
    try:
        messages: List[Tuple[str, str]] = [(item.role, item.content) for item in (history or []) if item.content]
        if agent_name == "n8n_agent" and context is not None:
            messages.insert(0, ("system", _build_n8n_execution_context(context)))
        messages.append(("user", user_input))
        result = await agent.ainvoke({
            "messages": messages
        }, config={"recursion_limit": 25})
        logger.info("Agent invocation completed: %s", agent_name)
        return extract_agent_response(result)
    finally:
        reset_current_conversation_history(history_token)
        if token is not None:
            reset_current_request_context(token)
