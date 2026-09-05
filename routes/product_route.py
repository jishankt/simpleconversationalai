"""Evidence-first Product Route for Kepler Tech Conversational AI.

The route deliberately separates retrieval from recommendation.  Search returns
candidates; the recommendation engine decides how strongly those candidates are
supported by verified catalog fields.  Missing data is never guessed.
"""

import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor
from agent.evidence_guard import answer_product_question
from agent.recommendation_engine import rank_products, recommendation_intro

logger = logging.getLogger("route:product")


def _set_category_from_product(state: ConversationState, product: dict) -> None:
    """Set routing category only; this must never create product specifications."""
    if state.category:
        return
    p_name_l = product.get("name", "").lower()
    p_cat_l = product.get("category", "").lower()
    text = f"{p_name_l} {p_cat_l}"
    if any(x in text for x in ["sc-t", "surecolor t", "cad", "plotter"]):
        state.category = "technical_cad"
    elif any(x in text for x in ["sc-p", "surecolor p", "fine art", "photo"]):
        state.category = "photo_fine_art"
    elif any(x in text for x in ["workforce", "am-c", "office", "enterprise"]):
        state.category = "office_enterprise"
    elif any(x in text for x in ["ds-", "scanner"]):
        state.category = "scanner"
    elif any(x in text for x in ["cx-", "cy-", "dye sublimation"]):
        state.category = "photo_booth"


def _answer_verified_product(product: dict, raw_message: str, cards: list) -> RouteResult:
    """Direct product Q&A bypasses free-form factual generation."""
    reply = answer_product_question(product, raw_message)
    return RouteResult(
        reply=reply,
        product_cards=cards,
        source="tool:get_product_specs:evidence_only",
        needs_composition=False,
        evidence=[product],
    )


def handle(understanding: LLMUnderstanding, state: ConversationState,
           raw_message: str = "") -> RouteResult:
    """Handle product search, recommendation and product-spec questions."""
    entities = understanding.entities
    model_code = entities.get("model_code")

    # ── Specific product query ───────────────────────────────────────────
    if model_code:
        res = catalog_tool_executor.execute_tool(
            "get_product_specs", {"product_identifier": model_code}
        )
        if res.get("success"):
            product = res.get("product", {})
            cards = res.get("product_cards", [])
            state.active_product = product
            state.active_product_id = str(product.get("_id") or product.get("sku") or "") or None
            state.candidate_products = cards
            _set_category_from_product(state, product)
            return _answer_verified_product(product, raw_message, cards)

        return RouteResult(
            reply=f"I couldn't verify a catalog product matching '{model_code}'. Please check the model name or code.",
            source="tool:get_product_specs:not_found",
            needs_composition=False,
        )

    # ── Follow-up question on active product ─────────────────────────────
    if state.active_product:
        product = state.active_product
        # state.active_product should be a raw catalog record. If an older session
        # contains only a display card, resolve it again before answering.
        identifier = product.get("sku") or product.get("name")
        if identifier:
            res = catalog_tool_executor.execute_tool(
                "get_product_specs", {"product_identifier": identifier}
            )
            if res.get("success"):
                product = res.get("product", product)
                state.active_product = product
                cards = res.get("product_cards", [])
                return _answer_verified_product(product, raw_message, cards)

        return _answer_verified_product(product, raw_message, [product])

    # ── Catalog discovery based on confirmed requirements ────────────────
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
        search_terms.append("Citizen photo printer")

    elif state.category == "photo_fine_art":
        cat_filter = "Printer"
        search_terms.append("Epson SureColor P photo fine art printer")

    elif state.category == "technical_cad":
        cat_filter = "Printer"
        size = state.requirements.get("print_size", "")
        scan_required = state.requirements.get("scan_required")
        # Only add scanner to retrieval when customer explicitly requires it.
        scan_term = "MFP scanner" if scan_required is True else ""
        search_terms.append(f"Epson SureColor T CAD {size} {scan_term}".strip())

    elif state.category == "office_enterprise":
        cat_filter = "Printer"
        search_terms.append("Epson WorkForce Enterprise office MFP")

    else:
        search_terms.append(raw_message or "printer")

    search_res = catalog_tool_executor.execute_tool(
        "search_catalog",
        {"query": " ".join(search_terms), "category": cat_filter, "limit": 12}
    )

    # IMPORTANT: rank RAW catalog records, not display cards. Cards intentionally
    # omit many specification fields and therefore cannot prove requirements.
    raw_candidates = search_res.get("results", [])
    assessments = rank_products(
        raw_candidates,
        category=state.category,
        requirements=state.requirements,
        limit=4,
    )

    # Never show a candidate with a verified critical failure as a recommendation.
    eligible = [a for a in assessments if not a.failed]
    cards = [catalog_tool_executor.format_card(a.product) for a in eligible]

    state.candidate_products = cards
    if eligible:
        state.active_product = eligible[0].product
        state.active_product_id = str(
            eligible[0].product.get("_id") or eligible[0].product.get("sku") or ""
        ) or None
    else:
        state.active_product = None
        state.active_product_id = None

    reply = recommendation_intro(eligible, state.category)
    if eligible and eligible[0].confidence == "LOW":
        reply += " I need one more confirmed requirement before recommending a specific model."

    evidence = [
        {
            "product": a.product,
            "score": a.score,
            "matched_requirements": a.matched,
            "failed_requirements": a.failed,
            "unknown_requirements": a.unknown,
            "confidence": a.confidence,
        }
        for a in eligible
    ]

    return RouteResult(
        reply=reply,
        product_cards=cards,
        source="tool:search_catalog:verified_ranking",
        needs_composition=False,
        evidence=evidence,
    )
