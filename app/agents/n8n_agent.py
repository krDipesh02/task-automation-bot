import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from app.utils.logger import get_logger
from app.prompts.agent_prompts import N8N_AGENT_PROMPT
from app.services.llm_service import llm
logger = get_logger(__name__)

async def get_n8n_agent():
    """
    """

    logger.info("Initializing N8n Agent")

    client = MultiServerMCPClient(
        {
            "n8n": {
                "transport": "streamable_http",
                "url": os.getenv("N8N_MCP_URL"),
                "headers": {
                    "Authorization": f"Bearer {os.getenv("N8N_AUTH_TOKEN")}",
                },
            }
        }
    )

    tools = await client.get_tools()

    agent = create_react_agent(
        name = "n8n_agent",
        model = llm, 
        tools = tools,
        prompt = N8N_AGENT_PROMPT
    )

    logger.info("N8N agent initialized with tools: %s", [tool.name for tool in tools])

    return agent

