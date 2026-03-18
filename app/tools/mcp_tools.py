from langchain.tools import Tool
from app.executor.n8n_client import call_n8n_workflow, list_n8n_tools


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

        # 🔥 Step 2: Wrap MCP tool into Python function
        def make_tool_fn(tool_name):
            def tool_fn(input_data):
                return call_n8n_workflow(tool_name, input_data)
            return tool_fn

        tools.append(
            Tool(
                name=name,
                func=make_tool_fn(name),
                description=description
            )
        )

    if "error" in response:
        print("❌ Failed to fetch MCP tools:", response["error"])
    else:
        print("Fetched and wrapped MCP tools:", [t.name for t in tools])

    return tools
