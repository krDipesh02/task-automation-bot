from app.agents.agent_registry import invoke_agent
from app.core.router import route_to_agent

def run_orchestrator(user_input: str) -> str:
    try:
        agent_name = route_to_agent(user_input)
        print("Selected agent:", agent_name)
        return invoke_agent(agent_name, user_input)
    except Exception as e:
        print("ERROR:", str(e))
        return f"Error: {str(e)}"
