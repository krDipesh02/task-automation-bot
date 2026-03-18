from app.agents.agent_registry import invoke_agent

def handle_n8n_task(user_input: str) -> str:
    return invoke_agent("n8n_agent", user_input)
