from venv import logger

from langgraph.prebuilt import create_react_agent
from app.prompts.agent_prompts import DEFAULT_AGENT_PROMPT
from app.services.llm_service import llm

async def get_default_agent():
    """
    """

    agent = create_react_agent(
        name="default_agent",
        model = llm,
        tools = [],
        prompt = DEFAULT_AGENT_PROMPT
    )

    logger.info("Default agent initialized")
    return agent

