from typing import Any, Dict, Tuple, Type

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.executor.n8n_client import call_n8n_workflow, list_n8n_tools
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _map_json_schema_type(schema: Dict[str, Any]) -> type:
    schema_type = schema.get("type")

    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list
    if schema_type == "object":
        return dict

    return Any


def _build_args_schema(tool_name: str, input_schema: Dict[str, Any]) -> Type[BaseModel]:
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    fields: Dict[str, Tuple[type, Any]] = {}

    for field_name, field_schema in properties.items():
        field_type = _map_json_schema_type(field_schema)
        description = field_schema.get("description", "")

        if field_name in required:
            fields[field_name] = (field_type, Field(..., description=description))
        else:
            fields[field_name] = (field_type, Field(default=None, description=description))

    model_name = "".join(part.capitalize() for part in tool_name.split("_")) + "Args"
    return create_model(model_name, **fields)


def get_n8n_tools():
    """
    Dynamically fetch tools from MCP and convert to LangChain tools
    """

    # 🔥 Step 1: Fetch tools from MCP
    response = list_n8n_tools()
    tools_data = response.get("tools", [])

    if not tools_data and response.get("result", {}).get("tools"):
        tools_data = response["result"]["tools"]

    tools = []

    for tool in tools_data:
        name = tool["name"]
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})
        args_schema = _build_args_schema(name, input_schema)

        def make_tool_fn(tool_name):
            def tool_fn(**kwargs):
                payload = {key: value for key, value in kwargs.items() if value is not None}
                logger.info("Executing MCP tool wrapper: %s", tool_name)
                return call_n8n_workflow(tool_name, payload)
            return tool_fn

        tools.append(
            StructuredTool.from_function(
                name=name,
                func=make_tool_fn(name),
                description=description,
                args_schema=args_schema,
                infer_schema=False,
            )
        )

    if "error" in response:
        logger.error("Failed to fetch MCP tools: %s", response["error"])
    else:
        logger.info("Fetched and wrapped MCP tools: %s", [t.name for t in tools])

    return tools
