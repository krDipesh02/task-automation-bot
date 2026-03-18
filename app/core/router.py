import json
from app.services.llm_service import llm
from app.prompts.agent_prompts import ROUTER_SYSTEM_PROMPT, build_router_user_prompt


def route_to_agent(user_input: str) -> str:
    """Decide which agent should handle the request."""

    try:
        response = llm.invoke([
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": build_router_user_prompt(user_input)},
        ])

        content = response.content.strip()

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(content)

        return parsed.get("agent", "default_agent")

    except Exception as e:
        print("Routing error:", e)
        return "default_agent"
