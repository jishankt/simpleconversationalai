"""
Product Route for Kepler Tech Conversational AI.
Handles product search and product specification queries
using the existing tool_executor infrastructure.
"""

import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:product")


def handle(understanding: LLMUnderstanding, state: ConversationState,
           raw_message: str = "") -> RouteResult:
    """Handle product search and product spec queries."""
    entities = understanding.entities
    model_code = entities.get("model_code")

    # ── Specific product spec query ──────────────────────────────────────
    if model_code:
        res = catalog_tool_executor.execute_tool(
            "get_product_specs", {"product_identifier": model_code}
        )
        if res.get("success"):
            product = res.get("product", {})
            cards = res.get("product_cards", [])
            state.active_product = product
            state.candidate_products = cards
            if not state.category:
                p_name_l = product.get("name", "").lower()
                if any(x in p_name_l for x in ["sc-t", "surecolor t", "cad", "plotter"]):
                    state.category = "technical_cad"
                elif any(x in p_name_l for x in ["sc-p", "surecolor p", "photo"]):
                    state.category = "photo_fine_art"
                elif any(x in p_name_l for x in ["workforce", "am-c", "copier"]):
                    state.category = "office_enterprise"
                elif any(x in p_name_l for x in ["ds-", "workforce ds", "scanner"]):
                    state.category = "scanner"
                elif any(x in p_name_l for x in ["cx-", "cy-"]):
                    state.category = "photo_booth"

            p_name = product.get("name", model_code)
            return RouteResult(
                reply=f"Here are the verified specifications for the {p_name}:",
                product_cards=cards,
                source="tool:get_product_specs",
                needs_composition=True,
                evidence=[product],
                instruction=f"Describe the key specifications of {p_name} based on the evidence.",
            )

    # ── Product question on active product ───────────────────────────────
    if state.active_product and not model_code:
        product = state.active_product
        p_name = product.get("name", "")
        width = product.get("width", "")
        speed = product.get("speed", "")
        ink = product.get("ink_technology", "")
        
        reply_parts = [f"The {p_name} is an authorized system from Kepler Tech LLC."]
        if width:
            reply_parts.append(f"It supports print sizes up to {width}.")
        if speed:
            reply_parts.append(f"Print speed: {speed}.")
        if ink:
            reply_parts.append(f"Ink system: {ink}.")
        reply = " ".join(reply_parts)

        return RouteResult(
            reply=reply,
            product_cards=[product],
            source="tool:get_product_specs",
            needs_composition=True,
            evidence=[product],
            instruction=f"Answer the customer's question about {p_name} using the verified specifications: width={width}, speed={speed}, ink={ink}.",
        )

    # ── Catalog search based on state requirements ───────────────────────
    search_terms = []
    cat_filter = None

    if state.category == "scanner":
        cat_filter = "Scanner"
        st = state.requirements.get("scanner_type")
        if st == "document_sheetfed":
            search_terms.append("high speed network duplex document scanner")
        elif st == "flatbed_a3":
            search_terms.append("A3 large format flatbed scanner")
        elif st == "business":
            search_terms.append("compact business scanner")
        else:
            search_terms.append("document scanner")

    elif state.category == "photo_booth":
        cat_filter = "Printer"
        search_terms.append("Citizen photo printer CX CY")

    elif state.category == "photo_fine_art":
        cat_filter = "Printer"
        search_terms.append("Epson SureColor P photo fine art printer")

    elif state.category == "technical_cad":
        cat_filter = "Printer"
        size = state.requirements.get("print_size", "")
        scan = "MFP scanner" if state.requirements.get("scan_required") else "plotter"
        search_terms.append(f"Epson SureColor T CAD {size} {scan}")

    elif state.category == "office_enterprise":
        cat_filter = "Printer"
        search_terms.append("Epson WorkForce Enterprise office MFP")

    else:
        search_terms.append(raw_message or "printer")

    query_str = " ".join(search_terms)
    search_res = catalog_tool_executor.execute_tool(
        "search_catalog",
        {"query": query_str, "category": cat_filter, "limit": 4}
    )

    candidates = search_res.get("product_cards", [])
    if candidates and state.requirements:
        from rag.reranker import requirement_reranker
        candidates = requirement_reranker.rerank(candidates, state.requirements, limit=4)

    state.candidate_products = candidates
    if candidates:
        state.active_product = candidates[0]

    cat_name = state.category.replace("_", " ") if state.category else "printing equipment"

    if candidates:
        reply = f"Based on your requirements, here are our recommended {cat_name} options:"
    else:
        reply = "I would be glad to help you find the ideal solution. Could you tell me more about your specific requirements?"

    return RouteResult(
        reply=reply,
        product_cards=candidates,
        source="tool:search_catalog",
    )
