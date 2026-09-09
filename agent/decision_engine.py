"""
Decision Engine for Kepler Tech Conversational AI.
The LLM proposes an intent and action, but Python makes the final routing decision.
This ensures social messages never trigger product search, and invalid tool
requests are rejected before execution.
"""

import logging
from typing import Optional
from domain.conversation_types import (
    Intent, LLMUnderstanding, RouteDecision, RouteName,
    SOCIAL_INTENTS, PRODUCT_INTENTS,
)
from domain.conversation_state import ConversationState

logger = logging.getLogger("decision_engine")


def min_qualification_satisfied(state: ConversationState) -> bool:
    """Check if minimum requirements are met when customer explicitly asks to recommend now."""
    cat = state.category
    reqs = state.requirements
    if not cat:
        return False
    if cat in ("technical_cad", "photo_booth", "photo_fine_art"):
        return "print_size" in reqs
    if cat == "office_enterprise":
        return "speed" in reqs or "daily_volume" in reqs or "workload" in reqs
    if cat == "scanner":
        return "scanner_type" in reqs
    if cat == "consumable":
        return "printer_model" in reqs or state.active_printer_for_consumables is not None
    return True


def qualification_complete(state: ConversationState) -> bool:
    """Check if all consultative requirements are collected to automatically search for products."""
    cat = state.category
    reqs = state.requirements

    if not cat:
        return False

    if cat == "technical_cad":
        if reqs.get("scan_required") is True:
            return "print_size" in reqs and "daily_volume" in reqs
        return "print_size" in reqs and ("scan_required" in reqs or "daily_volume" in reqs)

    if cat == "photo_booth":
        return "print_size" in reqs

    if cat == "photo_fine_art":
        return "print_size" in reqs

    if cat == "office_enterprise":
        return "speed" in reqs or "daily_volume" in reqs or "workload" in reqs

    if cat == "scanner":
        return "scanner_type" in reqs

    if cat == "consumable":
        return "printer_model" in reqs or state.active_printer_for_consumables is not None

    return False


def decide(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteDecision:
    """
    Deterministic routing decision based on LLM understanding, conversation state,
    and message context. The LLM's requested_action is a suggestion — this function validates and overrides.
    """
    intent = understanding.intent
    msg_lower = (raw_message or "").strip().lower()

    # ── Model Code & Specific Product Extraction ─────────────────────────
    import re
    model_matches = re.findall(r"\b(?:sc-?)?(?:[tpf]\d{3,4}[a-z]?|ds-?\d{3}[a-z]?|cx-?\d{2}w?|cy-?\d{2}|cz-?\d{2}|am-?c\d{3,4}|wf-?c\d{3,4}[a-z]?)\b", msg_lower)
    unique_models = []
    for m in model_matches:
        clean = re.sub(r"[\s\-_]+", "", m.upper())
        if clean not in [re.sub(r"[\s\-_]+", "", u.upper()) for u in unique_models]:
            unique_models.append(m.upper())
    extracted_model = unique_models[0] if unique_models else None

    # Validate candidate model code
    model_code = None
    if extracted_model:
        model_code = extracted_model
    elif understanding.entities.get("model_code"):
        cand = str(understanding.entities["model_code"]).strip()
        generic_terms = {"cad printer", "printer", "scanner", "plotter", "copier", "inks", "ink", "paper", "media"}
        if cand.lower() not in generic_terms:
            from rag.retriever import rag_retriever
            if rag_retriever.get_by_sku(cand) or rag_retriever.get_by_name(cand):
                model_code = cand

    # ── Explicit Hardware Switch / Ink Negation Detection ──────────────
    is_ink_requested = any(re.search(rf"\b{re.escape(ik)}\b", msg_lower) for ik in [
        "ink", "inks", "cartridge", "cartridges", "toner", "ribbon", "consumable", "consumables", "maintenance tank", "maintenance box"
    ])
    is_explicitly_negating_ink = any(k in msg_lower for k in [
        "not ink", "no ink", "dont want ink", "don't want ink", "not the ink", 
        "no cartridges", "not cartridge", "dont need ink", "don't need ink",
        "i want printer", "i want the printer", "want printer", "buy printer",
        "need printer", "looking for printer", "want a printer", "buy a printer",
        "need a printer", "looking for a printer", "printer p900", "printer t3100", "printer f100"
    ])
    
    is_negating_consumable = is_explicitly_negating_ink or (
        bool(model_code) and any(hw in msg_lower for hw in ["printer", "plotter", "hardware", "machine", "device", "unit"]) and not is_ink_requested
    )

    if is_negating_consumable and len(unique_models) <= 1:
        state.category = None
        state.awaiting_field = None
        state.active_printer_for_consumables = None
        if model_code:
            return RouteDecision(
                route=RouteName.PRODUCT,
                tool="get_product_specs",
                tool_arguments={"product_identifier": model_code},
                reason=f"Explicit product hardware requested: {model_code}",
            )

    # ── Product Feature, Attribute, or Superlative Question ─────────────
    is_fastest_query = any(w in msg_lower for w in ["fastest", "highest speed", "how fast", "print speed", "quickest", "print faster"])
    is_capacity_query = any(w in msg_lower for w in ["highest capacity", "largest roll", "most prints", "max capacity", "print capacity"])
    is_portable_query = any(w in msg_lower for w in ["most portable", "lightest", "smallest", "most compact", "how heavy", "weight of"])
    is_8x12_query = any(w in msg_lower for w in ["which citizen.*8x12", "print 8x12", "prints 8x12", "8 inch citizen", "8-inch citizen", "citizen.*8x12", "citizen.*8 inch"]) or ("8x12" in msg_lower and any(w in msg_lower for w in ["which", "can it", "support", "capable"]))
    is_ribbon_rewind_query = any(w in msg_lower for w in ["ribbon rewind", "rewind ribbon", "rewind feature", "rewind technology", "media waste"])
    is_tech_query = any(w in msg_lower for w in ["inkjet or dye sub", "dye sub or inkjet", "thermal or inkjet", "what technology"])

    is_price_query = any(w in msg_lower for w in ["what is the price", "what does it cost", "how much is it", "how much does it cost", "how much", "tell me the price", "what is price", "price", "cost", "pricing", "rate"]) and not any(d in msg_lower for d in ["discount", "bargain", "negotiat", "cheaper"])

    if is_price_query or is_fastest_query or is_capacity_query or is_portable_query or is_8x12_query or is_ribbon_rewind_query or is_tech_query or understanding.requested_action == "answer_product_attribute":
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="get_product_specs" if (state.active_product or model_code) else "answer_product_attribute",
            tool_arguments={"product_identifier": (state.active_product.get("name") if state.active_product else model_code)} if (state.active_product or model_code) else {},
            reason="Customer asked price, product attribute, or superlative question",
        )

    # ── Consumables query & Follow-up answers ────────────────────────────
    # Trust LLM intent; only fall back to keyword if LLM did not explicitly assign another primary intent
    is_consumable_query = not is_negating_consumable and (
        intent == Intent.CONSUMABLES_QUERY or
        understanding.requested_action == "show_consumables" or
        (is_ink_requested and intent not in (Intent.BUSINESS_INFORMATION, Intent.CORRECTION, Intent.PRODUCT_COMPARISON)) or
        (state.category == "consumable" and state.awaiting_field in ("printer_model", "ink_color"))
    )
    if is_consumable_query:
        args = {}
        # Only inject printer_identifier if the message contains a model code, user refers to active product (e.g. 'for this', 'for it'), or user is answering the model/color
        has_pronoun_to_active = any(p in msg_lower for p in ["for this", "for it", "for that", "this printer", "that printer"])
        is_general_ink = not has_pronoun_to_active and not model_code and any(k in msg_lower for k in ["i want", "need", "buy", "looking for", "have"]) and any(re.search(rf"\b{re.escape(k)}\b", msg_lower) for k in ["ink", "inks", "cartridge", "cartridges", "toner", "ribbon"])
        if model_code:
            args["printer_identifier"] = model_code
        elif has_pronoun_to_active and state.active_product:
            args["printer_identifier"] = state.active_product.get("name", "")
        elif has_pronoun_to_active and state.active_printer_for_consumables:
            args["printer_identifier"] = state.active_printer_for_consumables
        elif not is_general_ink and state.active_printer_for_consumables:
            args["printer_identifier"] = state.active_printer_for_consumables
        elif not is_general_ink and state.active_product:
            args["printer_identifier"] = state.active_product.get("name", "")
        return RouteDecision(
            route=RouteName.CONSUMABLES,
            tool="get_compatible_consumables" if args.get("printer_identifier") else None,
            tool_arguments=args,
            reason="Consumables query or model clarification answer",
        )

    # ── Product comparison ───────────────────────────────────────────────
    is_comparison_query = (
        intent == Intent.PRODUCT_COMPARISON
        or len(unique_models) >= 2
        or any(w in msg_lower for w in [
            "compare", " vs ", " versus ", "difference", "differences", "difference between",
            "which is better", "which one is better", "which is best", "which one should i choose",
            "how do they compare", "how does", "contrast", "better than", "is that true", "everyone says",
            "is it better", "is better", "better"
        ])
    )
    if is_comparison_query:
        return RouteDecision(
            route=RouteName.COMPARISON,
            tool="compare_products",
            reason="Product comparison request",
        )

    # ── Product Brochure / Datasheet Request ─────────────────────────────
    is_brochure_request = any(b in msg_lower for b in [
        "brochure", "brosure", "broucher", "brousher", "broshur", "brocher",
        "datasheet", "data sheet", "specsheet", "spec sheet",
        "download pdf", "pdf link", "give brochure", "send brochure",
        "give the brosure", "give the brochure", "product sheet", "technical sheet",
        "spec sheet", "data-sheet", "catalog pdf", "brochure link"
    ])
    if is_brochure_request:
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="get_brochure",
            tool_arguments={"product_identifier": model_code or ""} if model_code else {},
            reason="Customer requested product brochure / data sheet PDF",
        )

    # ── Specific model code directly requested ───────────────────────────
    if model_code and not any(w in msg_lower for w in ["fastest", "highest capacity", "most portable", "lightest", "how fast", "speed", "compare"]):
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="get_product_specs",
            tool_arguments={"product_identifier": model_code},
            reason=f"Specific product requested: {model_code}",
        )


    # ── Category Switch Detection ────────────────────────────────────────
    new_category = None
    llm_cat = understanding.entities.get("product_category")
    if llm_cat in ("technical_cad", "photo_fine_art", "photo_booth", "office_enterprise", "scanner", "consumable"):
        new_category = llm_cat

    if not new_category:
        if any(k in msg_lower for k in ["photo booth", "dye-sub", "citizen cx", "citizen cy", "citizen"]):
            new_category = "photo_booth"
        elif any(k in msg_lower for k in ["cad", "plotter", "blueprint", "architect", "engineering", "technical drawing", "gis", "aec"]):
            new_category = "technical_cad"
        elif "large format" in msg_lower and any(k in msg_lower for k in ["cad", "drawing", "blueprint", "architect", "plan", "plotter"]):
            new_category = "technical_cad"
        elif any(k in msg_lower for k in ["photo fine art", "photo printer", "photo", "photos", "photography", "fine art", "gallery", "exhibition", "p900", "p700", "p7500", "p9500"]):
            new_category = "photo_fine_art"
        elif any(k in msg_lower for k in ["office printer", "office", "workforce", "copier", "am-c4000", "am-c550", "enterprise printer"]):
            new_category = "office_enterprise"
        elif not any(neg in msg_lower for neg in ["no scanner", "without scanner", "not scanner", "don't need scanner", "dont need scanner"]) and any(k in msg_lower for k in ["document scanner", "sheetfed scanner", "flatbed scanner", "standalone scanner", "dedicated scanner"]):
            new_category = "scanner"
        elif not state.category and not any(neg in msg_lower for neg in ["no scanner", "without scanner", "not scanner", "don't need scanner", "dont need scanner"]) and any(k in msg_lower for k in ["scanner", "document scan", "scanning"]):
            new_category = "scanner"
    # ── General Printer Inquiry (Reset old state & ask what category) ──────
    is_general_printer_intent = (
        bool(re.search(r"\b(?:want|buy|need|looking for|get|require)\b.*?\b(?:a\s*printer|aprinter|printers?|plotters?)\b", msg_lower))
        or any(k in msg_lower for k in [
            "want a printer", "want aprinter", "buy a printer", "buy aprinter",
            "need a printer", "need aprinter", "looking for a printer", "want printer",
            "also want a printer", "also want aprinter", "want buy a printer", "buy printer", "need printer"
        ])
    )
    if is_general_printer_intent and not new_category:
        state.reset_category(None)
        state.awaiting_field = "category"
        return RouteDecision(
            route=RouteName.QUALIFICATION,
            reason="General printer inquiry — prompt customer to select category",
        )

    is_explicit_switch = (
        "switch" in msg_lower 
        or "instead" in msg_lower
        or ("actually" in msg_lower and any(kw in msg_lower for kw in ["need", "want", "switch", "printer", "plotter", "booth", "photo", "cad", "office", "scanner"]))
        or (new_category and state.category and new_category != state.category)
    )
    if new_category and (not state.category or is_explicit_switch):
        if new_category == "scanner" and (
            state.awaiting_field == "scan_required"
            or (state.category in ("technical_cad", "office_enterprise", "photo_fine_art") and not any(sw in msg_lower for sw in ["switch to scanner", "dedicated scanner", "document scanner", "only scanner", "scanner instead"]))
        ):
            pass
        else:
            saved_size = state.requirements.get("print_size")
            saved_brand = state.requirements.get("brand")
            state.reset_category(new_category)
            if saved_brand:
                state.requirements["brand"] = saved_brand
            if saved_size and ("photo" in new_category or "booth" in new_category):
                state.requirements["print_size"] = saved_size
            if qualification_complete(state):
                return RouteDecision(
                    route=RouteName.PRODUCT,
                    tool="search_catalog",
                    reason=f"Category set/switched to {new_category} with qualification satisfied",
                )
            return RouteDecision(
                route=RouteName.QUALIFICATION,
                reason=f"Category set/switched to {new_category}",
            )



    # ── Explicit recommendation request when minimum qualification is satisfied ──
    rec_keywords = ["recommend now", "recommend", "show options", "show recommendations",
                    "what do you recommend", "suggest options", "show me options",
                    "give me options", "show products", "show printers",
                    "show another", "show another one", "another option", "other options", "show alternative"]
    is_rec_request = any(k in msg_lower for k in rec_keywords)

    if is_rec_request and min_qualification_satisfied(state):
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="search_catalog",
            reason="Explicit recommendation requested",
        )

    if state.category and qualification_complete(state) and intent not in (
        Intent.BUSINESS_INFORMATION, Intent.TROUBLESHOOTING, Intent.LANGUAGE_CHANGE,
        Intent.PRODUCT_COMPARISON, Intent.CONSUMABLES_QUERY, Intent.GREETING, Intent.CONVERSATION_ENDING
    ):
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="search_catalog",
            reason="Qualification complete — ready to search",
        )

    # ── Social intents → social route (NEVER enters product search) ──────
    if intent in SOCIAL_INTENTS:
        return RouteDecision(
            route=RouteName.SOCIAL,
            reason=f"Social intent: {intent.value}",
        )

    # ── Direct answer to awaiting field (volume, size, etc.) ────────────
    vol_cand = re.search(r"\b\d+\b", msg_lower) or (
        state.awaiting_field in ("daily_volume", "speed", "print_volume", "volume") and
        any(k in msg_lower for k in ["low", "medium", "high", "standard", "heavy", "moderate", "few"])
    )
    is_scan_ans = state.awaiting_field == "scan_required" and any(k in msg_lower for k in [
        "yes", "no", "yep", "nope", "both", "scanning", "scannin", "scaning", "scanner", "scan", 
        "print only", "printer only", "only print", "only printer", "printing only", "just print", "just printer", "no scan"
    ])
    if state.awaiting_field and (
        vol_cand or
        is_scan_ans or
        any(s in msg_lower for s in ["a0", "a1", "a2", "a3", "a4", "4x6", "6x8", "24\"", "36\""]) or
        understanding.dialogue_act.value in ("informing", "answering_question")
    ):
        return RouteDecision(
            route=RouteName.QUALIFICATION,
            reason=f"Answering awaiting field: {state.awaiting_field}",
        )

    # ── Confirmation/Rejection or qualification in progress ─────────────
    if state.category and not qualification_complete(state):
        if intent in (Intent.CONFIRMATION, Intent.REJECTION, Intent.PRODUCT_DISCOVERY, Intent.UNCLEAR) or understanding.requested_action in ("continue_qualification", "ask_qualification_question", "provide_support", "ask_clarification"):
            return RouteDecision(
                route=RouteName.QUALIFICATION,
                reason="Active qualification in progress — collecting remaining requirements",
            )

    if intent == Intent.CONFIRMATION and state.awaiting_field:
        return RouteDecision(
            route=RouteName.QUALIFICATION,
            reason="Confirmation while awaiting field answer",
        )

    if intent == Intent.REJECTION and state.awaiting_field:
        return RouteDecision(
            route=RouteName.QUALIFICATION,
            reason="Rejection while awaiting field answer",
        )

    # ── Correction → update state and re-evaluate ────────────────────────
    if intent == Intent.CORRECTION:
        return RouteDecision(
            route=RouteName.QUALIFICATION,
            reason="Correction of previous answer",
        )

    # ── Business information ─────────────────────────────────────────────
    if intent == Intent.BUSINESS_INFORMATION or any(w in msg_lower for w in ["delivery", "deliver", "shipping", "ship", "address", "location", "dubai", "where are you", "office hours", "timings", "opening hours", "contact number", "phone number", "whatsapp", "email", "what brands", "what services", "amc", "warranty"]):
        return RouteDecision(
            route=RouteName.BUSINESS_INFO,
            reason="Business information request",
        )

    # ── Troubleshooting ──────────────────────────────────────────────────
    if intent == Intent.TROUBLESHOOTING:
        return RouteDecision(
            route=RouteName.SUPPORT,
            reason="Troubleshooting request",
        )

    # ── Pronoun reference to active product ──────────────────────────────

    has_pronoun_ref = (
        any(w in msg_lower.split() for w in ["it", "this", "its", "that"]) or
        any(k in msg_lower for k in ["does it", "can it", "what size", "how fast", "specs", "specifications"])
    )
    if state.active_product and has_pronoun_ref:
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="get_product_specs",
            tool_arguments={"product_identifier": state.active_product.get("name", "")},
            reason="Question about active product via pronoun/reference",
        )

    # ── Product question about active/referenced product ─────────────────
    if intent == Intent.PRODUCT_QUESTION:
        args = {}
        if state.active_product:
            args["product_identifier"] = state.active_product.get("name", "")
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="get_product_specs" if state.active_product else None,
            tool_arguments=args,
            reason="Product question",
        )

    # ── Product discovery ────────────────────────────────────────────────
    if intent == Intent.PRODUCT_DISCOVERY:
        # Check if we need more qualification first
        if not state.category:
            return RouteDecision(
                route=RouteName.QUALIFICATION,
                reason="No category set yet — need qualification",
            )
        if not qualification_complete(state):
            return RouteDecision(
                route=RouteName.QUALIFICATION,
                reason="Qualification incomplete",
            )
        return RouteDecision(
            route=RouteName.PRODUCT,
            tool="search_catalog",
            reason="Qualification complete — ready to search",
        )

    # ── Unclear / out of scope ───────────────────────────────────────────
    if intent in (Intent.UNCLEAR, Intent.OUT_OF_SCOPE):
        return RouteDecision(
            route=RouteName.CLARIFICATION,
            reason=f"Intent: {intent.value}",
        )

    # ── Language change ──────────────────────────────────────────────────
    if intent == Intent.LANGUAGE_CHANGE:
        return RouteDecision(
            route=RouteName.SOCIAL,
            reason="Language change request",
        )

    # ── Fallback ─────────────────────────────────────────────────────────
    logger.warning(f"Unhandled intent: {intent.value} — routing to clarification")
    return RouteDecision(
        route=RouteName.CLARIFICATION,
        reason=f"Unhandled intent: {intent.value}",
    )
