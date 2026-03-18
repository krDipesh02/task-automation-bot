from app.agents.agent_registry import invoke_agent

def handle_default_task(user_input: str) -> str:
    return invoke_agent("default_agent", user_input)
