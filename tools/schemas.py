"""
Tool Argument and Result Schemas for Kepler Tech Conversational AI.
Enforces strict Pydantic validation on all tool arguments and execution results.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SearchCatalogArgs(BaseModel):
    query: str = Field(..., description="Customer search query or specifications")
    category: Optional[str] = Field(None, description="Product category filter")
    max_results: int = Field(4, ge=1, le=10, description="Max candidate products to return")


class GetProductSpecsArgs(BaseModel):
    product_identifier: str = Field(..., description="Product name, SKU, or model substring")


class GetCompatibleConsumablesArgs(BaseModel):
    printer_name: str = Field(..., description="Exact or partial name of printer")
    consumable_type: str = Field("all", description="'all', 'ink', 'tank', or 'media'")
    limit: int = Field(6, ge=1, le=20, description="Max consumables to return")


class CompareProductsArgs(BaseModel):
    product_names: List[str] = Field(..., min_length=2, max_length=4, description="List of product names to compare")


class ToolResult(BaseModel):
    success: bool = True
    tool_name: str
    evidence: str = ""
    product_cards: List[Dict[str, Any]] = Field(default_factory=list)
    consumable_cards: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_chips: List[str] = Field(default_factory=list)
    error: Optional[str] = None
