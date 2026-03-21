import json
import os
from typing import Optional

import requests
from sseclient import SSEClient
from app.utils.logger import get_logger

N8N_MCP_URL = os.getenv("N8N_MCP_URL")
N8N_AUTH_TOKEN = os.getenv("N8N_AUTH_TOKEN")
logger = get_logger(__name__)


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
        logger.info("Sending MCP request: %s", method)
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
                logger.error("MCP error for %s: %s", method, parsed["error"])
                return {"error": parsed["error"]}

            if "result" in parsed:
                logger.info("Received MCP result for %s", method)
                return parsed["result"]

            logger.info("Received raw MCP payload for %s", method)
            return parsed

        logger.warning("No response from MCP for %s", method)
        return {"error": "No response from MCP"}

    except Exception as e:
        logger.exception("MCP request failed for %s: %s", method, e)
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

    logger.info("Calling n8n workflow tool: %s", tool_name)
    return _send_mcp_request(
        "tools/call",
        {
            "name": tool_name,
            "arguments": params or {},
        },
    )
