import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from app.core.models import get_current_request_context
from dotenv import load_dotenv
from app.services.llm_service import llm
from app.utils.logger import get_logger
from langgraph.prebuilt import create_react_agent
from app.prompts.agent_prompts import SPENDWISE_AGENT_PROMPT

load_dotenv()
logger = get_logger(__name__)

async def _inject_trusted_telegram_identity(request: MCPToolCallRequest, handler):
    context = get_current_request_context()
    if context is None or not context.telegram_user_id:
        raise RuntimeError("SpendWise MCP calls require an authenticated Telegram request context")
    args = {**request.args, "telegram_user_id": context.telegram_user_id}
    return await handler(request.override(args=args))


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
        },
        tool_interceptors=[_inject_trusted_telegram_identity],
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