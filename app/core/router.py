import json
from typing import Iterable, Optional

from app.core.models import ConversationTurn
from app.services.llm_service import llm
from app.prompts.agent_prompts import ROUTER_SYSTEM_PROMPT, build_router_user_prompt
from app.utils.logger import get_logger

logger = get_logger(__name__)

def _format_history(history: Optional[Iterable[ConversationTurn]]) -> str:
    if not history:
        return ""

    turns = list(history)[-6:]
    return "\n".join(f"{turn.role}: {turn.content}" for turn in turns if turn.content)


def route_to_agent(user_input: str, history: Optional[Iterable[ConversationTurn]] = None) -> str:
    """Decide which agent should handle the request."""

    try:
        logger.info("Routing user input")
        response = llm.invoke([
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": build_router_user_prompt(user_input, _format_history(history))},
        ])

        content = response.content.strip()

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(content)
        agent_name = parsed.get("agent", "default_agent")
        logger.info("Routing completed: %s", agent_name)
        return agent_name

    except Exception as e:
        logger.exception("Routing error: %s", e)
        return "default_agent"
