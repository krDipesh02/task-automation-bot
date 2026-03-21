from app.agents.agent_registry import invoke_agent
from app.core.router import route_to_agent
from app.utils.logger import get_logger

logger = get_logger(__name__)

def run_orchestrator(user_input: str) -> str:
    try:
        logger.info("Running orchestrator")
        agent_name = route_to_agent(user_input)
        logger.info("Selected agent: %s", agent_name)
        return invoke_agent(agent_name, user_input)
    except Exception as e:
        logger.exception("Orchestrator error: %s", e)
        return f"Error: {str(e)}"
