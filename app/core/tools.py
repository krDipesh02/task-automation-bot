from app.executor.n8n_client import call_n8n_workflow

def n8n_agent_tool(user_input: str):
    result = call_n8n_workflow("search_workflows", {"query": user_input})

    return str(result)
