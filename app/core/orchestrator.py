from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any
import json

from app.services.llm_service import generate_response

# ---- AGENTS ----
from app.agents.n8n_agent import handle_n8n_task
from app.agents.default_agent import handle_default_task


# ---- STATE ----
class AgentState(TypedDict):
    user_input: str
    response: str


# ---- AGENT REGISTRY ----
AGENTS = {
    "n8n_agent": handle_n8n_task,
    "default_agent": handle_default_task
}

# ---- HELPERS ----
def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    return text


def safe_parse_json(raw_response: str) -> Optional[Dict[str, Any]]:
    try:
        cleaned = clean_json_response(raw_response)
        return json.loads(cleaned)
    except Exception:
        try:
            start = raw_response.find("{")
            end = raw_response.rfind("}") + 1
            return json.loads(raw_response[start:end])
        except Exception as e:
            print("JSON parsing failed:", e)
            print("Raw response:", raw_response)
            return None


# ---- NODE ----
def orchestrator_node(state: AgentState):
    user_input = state["user_input"]

    system_prompt = f"""
You are an AI orchestrator. You have to decide which agent should handle the user's request based on the input.

Available agents:
1. n8n_agent → performs actions, workflows
2. default_agent → handles conversation

Rules:
- If user wants to perform an action → n8n_agent
- Otherwise → default_agent

Return response in JSON format.

Example JSON:
{{
  "agent": "selected_agent_name",
}}
"""

    raw_response = generate_response(system_prompt, user_prompt=user_input)

    parsed = safe_parse_json(raw_response)

    if not parsed:
        return {"response": raw_response}

    agent_name = parsed.get("agent", "default_agent")

    agent_fn = AGENTS.get(agent_name, AGENTS["default_agent"])

    # ---- ROUTE TO AGENT ----
    agent_response = agent_fn(user_input)

    return {"response": agent_response}


# ---- GRAPH ----
builder = StateGraph(AgentState)

builder.add_node("orchestrator", orchestrator_node)

builder.set_entry_point("orchestrator")
builder.add_edge("orchestrator", END)

graph = builder.compile()


# ---- ENTRY ----
def run_orchestrator(user_input: str) -> str:
    result = graph.invoke({"user_input": user_input})
    return result["response"]