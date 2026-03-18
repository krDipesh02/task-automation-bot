from langgraph.prebuilt import create_react_agent
from app.services.llm_service import llm
from app.tools.mcp_tools import get_n8n_tools
from app.core.message_utils import extract_agent_response
from app.prompts.agent_prompts import DEFAULT_AGENT_PROMPT, N8N_AGENT_PROMPT

_agents = {}


def init_agents():
    print("🚀 Initializing agents...")

    _agents["n8n_agent"] = create_react_agent(
        llm,
        get_n8n_tools(),
        state_modifier=N8N_AGENT_PROMPT,
    )

    _agents["default_agent"] = create_react_agent(
        llm,
        [],
        state_modifier=DEFAULT_AGENT_PROMPT,
    )

    print("✅ Agents initialized")


def get_agents():
    if not _agents:
        init_agents()
    return _agents


def invoke_agent(agent_name: str, user_input: str) -> str:
    agent = get_agents().get(agent_name)

    if agent is None:
        return f"❌ Agent '{agent_name}' not initialized"

    result = agent.invoke({
        "messages": [("user", user_input)]
    })
    return extract_agent_response(result)
