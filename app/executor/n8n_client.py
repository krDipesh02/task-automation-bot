import json
import os
from typing import Optional

import requests
from sseclient import SSEClient

N8N_MCP_URL = os.getenv("N8N_MCP_URL")
N8N_AUTH_TOKEN = os.getenv("N8N_AUTH_TOKEN")


def _build_headers() -> dict:
    return {
        "Authorization": f"Bearer {N8N_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _send_mcp_request(method: str, params: Optional[dict] = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }

    try:
        response = requests.post(
            N8N_MCP_URL,
            data=json.dumps(payload),
            headers=_build_headers(),
            stream=True,
        )
        response.raise_for_status()

        client = SSEClient(response)

        for event in client.events():
            if not event.data:
                continue

            parsed = json.loads(event.data)

            if "error" in parsed:
                print("❌ MCP ERROR:", parsed["error"])
                return {"error": parsed["error"]}

            if "result" in parsed:
                return parsed["result"]

            return parsed

        return {"error": "No response from MCP"}

    except Exception as e:
        return {"error": str(e)}


def list_n8n_tools() -> dict:
    """
    Fetch the available MCP tools from n8n.
    """

    return _send_mcp_request("tools/list")


def call_n8n_workflow(tool_name: str, params: Optional[dict] = None) -> dict:
    """
    Call an n8n MCP tool using JSON-RPC.
    """

    return _send_mcp_request(
        "tools/call",
        {
            "name": tool_name,
            "arguments": params or {},
        },
    )
