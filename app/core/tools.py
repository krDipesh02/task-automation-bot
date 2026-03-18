from app.executor.n8n_client import call_n8n_workflow

def n8n_agent_tool(user_input: str):
    payload = {
        "text": user_input
    }

    result = call_n8n_workflow(payload)

    return str(result)