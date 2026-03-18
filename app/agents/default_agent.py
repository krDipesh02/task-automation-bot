from app.services.llm_service import generate_response

def handle_default_task(user_input: str) -> str:
    prompt = f"""
You are a helpful conversational assistant.

You handle:
- greetings
- general questions
- explanations

Respond in a clean, human-readable format.
Do NOT return JSON.
Use paragraphs and bullet points if needed.
"""

    return generate_response(prompt, user_prompt=user_input)