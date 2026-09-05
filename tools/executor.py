"""
Validated Tool Executor for Kepler Tech Conversational AI.
Enforces Pydantic argument and return validation around dynamic catalog operations.
"""

import logging
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from agent.tool_executor import CatalogToolExecutor, tool_executor
from tools.schemas import (
    SearchCatalogArgs,
    GetProductSpecsArgs,
    GetCompatibleConsumablesArgs,
    CompareProductsArgs,
    ToolResult,
)

logger = logging.getLogger("tools.executor")


class ValidatedToolExecutor:
    def __init__(self, backend_executor: Optional[CatalogToolExecutor] = None):
        self.backend = backend_executor or tool_executor

    def search_catalog(self, **kwargs) -> ToolResult:
        try:
            args = SearchCatalogArgs(**kwargs)
        except ValidationError as e:
            logger.warning(f"search_catalog validation error: {e}")
            return ToolResult(
                success=False,
                tool_name="search_catalog",
                error=str(e),
                evidence="Invalid search arguments provided.",
            )

        res = self.backend.execute_tool(
            "search_catalog",
            {"query": args.query, "category": args.category, "limit": args.max_results}
        )
        return ToolResult(
            success=res.get("success", True),
            tool_name="search_catalog",
            evidence=res.get("context_text", ""),
            product_cards=res.get("product_cards", []),
            consumable_cards=res.get("consumable_cards", []),
            suggested_chips=res.get("suggested_chips", []),
        )

    def get_product_specs(self, **kwargs) -> ToolResult:
        try:
            args = GetProductSpecsArgs(**kwargs)
        except ValidationError as e:
            logger.warning(f"get_product_specs validation error: {e}")
            return ToolResult(
                success=False,
                tool_name="get_product_specs",
                error=str(e),
                evidence="Invalid product spec arguments provided.",
            )

        res = self.backend.execute_tool(
            "get_product_specs",
            {"product_identifier": args.product_identifier}
        )
        return ToolResult(
            success=res.get("success", False),
            tool_name="get_product_specs",
            evidence=res.get("specs_text") or res.get("context_text", ""),
            product_cards=res.get("product_cards", []),
            suggested_chips=res.get("suggested_chips", []),
        )

    def get_compatible_consumables(self, **kwargs) -> ToolResult:
        try:
            args = GetCompatibleConsumablesArgs(**kwargs)
        except ValidationError as e:
            logger.warning(f"get_compatible_consumables validation error: {e}")
            return ToolResult(
                success=False,
                tool_name="get_compatible_consumables",
                error=str(e),
                evidence="Invalid consumables arguments provided.",
            )

        res = self.backend.execute_tool(
            "get_compatible_consumables",
            {"printer_identifier": args.printer_name, "limit": args.limit}
        )
        return ToolResult(
            success=res.get("success", False),
            tool_name="get_compatible_consumables",
            evidence=res.get("consumables_text") or res.get("context_text", ""),
            consumable_cards=res.get("consumable_cards", []),
            suggested_chips=res.get("suggested_chips", []),
        )

    def compare_products(self, **kwargs) -> ToolResult:
        try:
            args = CompareProductsArgs(**kwargs)
        except ValidationError as e:
            logger.warning(f"compare_products validation error: {e}")
            return ToolResult(
                success=False,
                tool_name="compare_products",
                error=str(e),
                evidence="Invalid comparison arguments provided.",
            )

        names = args.product_names
        model_a = names[0] if len(names) > 0 else ""
        model_b = names[1] if len(names) > 1 else ""
        res = self.backend.execute_tool(
            "compare_products",
            {"model_a": model_a, "model_b": model_b}
        )
        return ToolResult(
            success=res.get("success", False),
            tool_name="compare_products",
            evidence=res.get("comparison_text", ""),
            product_cards=res.get("product_cards", []),
            suggested_chips=res.get("suggested_chips", []),
        )


validated_tool_executor = ValidatedToolExecutor()
