import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from app.services.llm_service import llm
from app.utils.logger import get_logger
from langgraph.prebuilt import create_react_agent
from app.prompts.agent_prompts import SPENDWISE_AGENT_PROMPT

load_dotenv()
logger = get_logger(__name__)

async def get_spendwise_agent():
    logger.info("Initializing spendwise agent")

    client = MultiServerMCPClient(
        {
            "spendwise": {
                "url": os.getenv("SPENDWISE_MCP_URL"),
                "headers": {
                    "Authorization": f"Bearer {os.getenv('SPENDWISE_MCP_AUTH_TOKEN')}",
                },
                "transport": "streamable_http",
            }
        }
    )

    tools = await client.get_tools()

    agent = create_react_agent(
        name = "spendwise_agent",
        model = llm,
        tools = tools,
        prompt = SPENDWISE_AGENT_PROMPT,
    )

    logger.info("Spendwise agent created with tools: %s", [tool.name for tool in tools])
    return agent