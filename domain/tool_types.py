"""
Tool Types for Kepler Tech Conversational AI.
Defines formal contracts for tool requests and results.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


# ---------------------------------------------------------------------------
# Tool Request (what the decision engine asks a tool to do)
# ---------------------------------------------------------------------------
@dataclass
class ToolRequest:
    """A validated request to execute a specific tool."""
    name: str  # search_catalog | get_product_specs | get_compatible_consumables | compare_products | get_business_information
    arguments: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Basic validation: name must be in the allowed set."""
        return self.name in ALLOWED_TOOLS


# Allowed tool names
ALLOWED_TOOLS = frozenset({
    "search_catalog",
    "get_product_specs",
    "get_compatible_consumables",
    "compare_products",
    "get_business_information",
    "ask_consultative_question",
})


# ---------------------------------------------------------------------------
# Tool Result (what a tool returns)
# ---------------------------------------------------------------------------
@dataclass
class ToolResult:
    """Standardized result from any tool execution."""
    success: bool
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    product_cards: List[Dict[str, Any]] = field(default_factory=list)
    consumable_cards: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_executor_result(cls, result: Dict[str, Any]) -> "ToolResult":
        """Convert from the existing tool_executor dict format to a ToolResult."""
        return cls(
            success=result.get("success", False),
            evidence=[],
            product_cards=result.get("product_cards", []),
            consumable_cards=result.get("consumable_cards", []),
            warnings=[],
            error=result.get("error"),
            raw_data=result,
        )

    @classmethod
    def failure(cls, error: str) -> "ToolResult":
        """Create a failure result."""
        return cls(success=False, error=error)
