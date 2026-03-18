from app.executor.n8n_client import call_n8n_workflow

def handle_n8n_task(user_input: str) -> str:
    payload = {
        "text": user_input
    }

    result = call_n8n_workflow(payload)

    return f"✅ n8n Agent executed:\n{result}"