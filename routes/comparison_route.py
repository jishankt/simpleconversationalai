"""
Comparison Route for Kepler Tech Conversational AI.
Handles product comparison requests using the existing tool_executor.
"""

import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:comparison")


def handle(understanding: LLMUnderstanding, state: ConversationState) -> RouteResult:
    """Handle product comparison requests."""

    if len(state.candidate_products) >= 2:
        model_a = state.candidate_products[0].get("name", "")
        model_b = state.candidate_products[1].get("name", "")

        res = catalog_tool_executor.execute_tool(
            "compare_products",
            {"model_a": model_a, "model_b": model_b}
        )
        cards = res.get("product_cards", state.candidate_products[:2])

        return RouteResult(
            reply=f"Here is a comparison between {model_a} and {model_b}:",
            product_cards=[],
            source="tool:compare_products",
            needs_composition=True,
            evidence=cards,
            instruction=f"Compare {model_a} and {model_b} based on the evidence. Highlight key differences without recommending or attaching hardware cards.",
        )

    if state.active_product:
        return RouteResult(
            reply=f"The {state.active_product.get('name', '')} is an authorized system from Kepler Tech LLC. Would you like a direct spec comparison with another model?",
            product_cards=[],
            source="tool:compare_products",
        )

    return RouteResult(
        reply="Epson and Citizen serve distinct professional printing needs: Epson specializes in Large Format CAD plotters, Fine Art printers, and Enterprise WorkForce MFPs, whereas Citizen specializes in high-speed dye-sublimation photo printers for events and photo booths. Which solution would you like to explore?",
        suggested_chips=["CAD Plotters", "Photo Booth Printers", "Document Scanners"],
        product_cards=[],
        source="route:comparison",
    )

