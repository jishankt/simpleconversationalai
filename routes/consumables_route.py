"""
Consumables Route for Kepler Tech Conversational AI.
Handles consumable/ink queries using the existing tool_executor.
"""

import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:consumables")


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    """Handle consumable queries — find inks/cartridges for a given printer."""
    entities = understanding.entities
    model_code = entities.get("model_code")

    # Determine target printer
    target = model_code
    if not target and raw_message:
        import re
        m = re.search(r"\b(?:sc-?)?(?:[tpf]\d{3,4}[a-z]?|ds-?\d{3}[a-z]?|cx-?\d{2}|cy-?\d{2}|cz-?\d{2}|am-?c\d{3,4}|wf-?c\d{3,4}[a-z]?)\b", raw_message.lower())
        if m:
            target = m.group(0).upper()
        else:
            from rag.consumables_engine import consumables_engine
            target = consumables_engine.identify_printer_key(raw_message)

    if not target and state.active_product:
        target = state.active_product.get("name") or state.active_product.get("sku")
    if not target and state.active_printer_for_consumables:
        target = state.active_printer_for_consumables

    if not target:
        # Need to know which printer
        state.category = "consumable"
        state.awaiting_field = "printer_model"
        return RouteResult(
            reply="Which printer or scanner model do you need consumables for?",
            suggested_chips=["SC-P900", "SC-T3100", "SC-F100", "SC-P700", "WF-C20600"],
            source="route:consumables",
        )

    # Execute tool
    res = catalog_tool_executor.execute_tool(
        "get_compatible_consumables",
        {"printer_identifier": target, "limit": 6}
    )
    consumable_cards = res.get("consumable_cards", [])
    product_cards = res.get("product_cards", [])
    printer_name = res.get("printer_name") or target

    if consumable_cards:
        items = ", ".join([c["name"] for c in consumable_cards[:3]])
        reply = f"Here are the genuine compatible consumables for {printer_name} (including {items}):"
    else:
        reply = f"I could not locate verified consumables for '{target}' in our catalog. Please contact sales@keplertech.ae for specialty sourcing."

    return RouteResult(
        reply=reply,
        product_cards=product_cards,
        consumable_cards=consumable_cards,
        source="tool:get_compatible_consumables",
    )
