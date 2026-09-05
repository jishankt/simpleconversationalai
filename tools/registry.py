"""
Tool Registry and Dispatcher for Kepler Tech Conversational AI.
Exposes JSON schemas for LLM function calling and dispatches validated tool calls.
"""

from typing import Dict, Any, List, Optional
from agent.tool_registry import CATALOG_TOOLS
from tools.executor import validated_tool_executor, ToolResult


class ToolRegistry:
    def __init__(self):
        self.tools = {t["function"]["name"]: t for t in CATALOG_TOOLS}
        self.executor = validated_tool_executor

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return CATALOG_TOOLS

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Dispatches validated tool execution."""
        if tool_name == "search_catalog":
            return self.executor.search_catalog(**arguments)
        elif tool_name == "get_product_specs":
            return self.executor.get_product_specs(**arguments)
        elif tool_name == "get_compatible_consumables":
            return self.executor.get_compatible_consumables(**arguments)
        elif tool_name == "compare_products":
            return self.executor.compare_products(**arguments)
        else:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Unknown tool: {tool_name}",
                evidence=f"The tool '{tool_name}' is not recognized.",
            )


tool_registry = ToolRegistry()
