"""
Qualification Route for Kepler Tech Conversational AI.
Wraps the unified NextQuestionEngine and RequirementExtractor to ask
exactly one question at a time, never repeat already-answered fields,
and support corrections and topic switches mid-qualification.
"""

import logging
import re
from domain.conversation_types import Intent, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from conversation.next_question_engine import NextQuestionEngine
from conversation.requirement_extractor import requirement_extractor
from agent.decision_engine import qualification_complete

logger = logging.getLogger("route:qualification")
_next_q = NextQuestionEngine()


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    """
    Handle qualification flow:
    1. Apply category detection & topic switching
    2. Extract and update requirements from raw message and entities
    3. Ask the next unanswered question or transition to recommendation
    """
    entities = understanding.entities
    intent = understanding.intent
    msg_lower = (raw_message or "").strip().lower()

    # ── 1. Dynamic Category Detection & Switching ────────────────────────
    is_explicit_cat_switch = any(w in msg_lower for w in ["switch", "instead", "changed my mind", "actually now i need", "now i need"])
    is_answering_category = state.awaiting_field == "category" or not state.category
    
    # Check LLM understanding first
    detected_cat = entities.get("product_category") if entities else None
    if not detected_cat and (not state.category or is_explicit_cat_switch or is_answering_category):
        if any(k in msg_lower for k in ["cad", "plotter", "blueprint", "architect", "engineering", "technical drawing", "technical & cad", "technical_cad"]):
            detected_cat = "technical_cad"
        elif any(k in msg_lower for k in ["photo booth", "dye-sub", "citizen cx", "citizen cy", "events", "photo_booth"]):
            detected_cat = "photo_booth"
        elif any(k in msg_lower for k in ["photo fine art", "photo printer", "photos", "fine art", "gallery", "exhibition", "p900", "p700", "p5300", "p7500", "p9500", "photo_fine_art"]):
            detected_cat = "photo_fine_art"
        elif any(k in msg_lower for k in ["office", "enterprise", "workforce", "copier", "am-c4000", "am-c550", "mfp", "office_enterprise", "business printer"]) or (is_answering_category and any(k in msg_lower for k in ["printer", "printers", "normal", "standard", "document", "regular", "office"])):
            detected_cat = "office_enterprise"
        elif not any(neg in msg_lower for neg in ["no scanner", "without scanner", "not scanner", "don't need scanner", "dont need scanner", "print only", "printer only"]) and any(k in msg_lower for k in ["standalone scanner", "dedicated scanner", "document scanner", "sheetfed scanner", "scanner", "scanners"]):
            detected_cat = "scanner"
        elif any(re.search(rf"\b{re.escape(k)}\b", msg_lower) for k in ["ink", "inks", "cartridge", "cartridges", "toner", "ribbon", "consumable", "maintenance box"]):
            detected_cat = "consumable"

    if detected_cat and (not state.category or is_explicit_cat_switch or is_answering_category):
        state.reset_category(detected_cat)
        state.awaiting_field = None
        logger.info(f"Category set/switched to: {detected_cat}")

    # ── 2. Extract Verified Requirements ─────────────────────────────────
    extracted = requirement_extractor.extract_and_validate(raw_message, state)
    if extracted:
        state.requirements.update(extracted)
        if state.awaiting_field and state.awaiting_field in extracted:
            state.awaiting_field = None
        state.active_product = None
        state.candidate_products = []

    # ── 2b. Apply LLM Requirement Updates & Entities ──────────────────────
    if understanding.requirement_updates:
        for rk, rv in understanding.requirement_updates.items():
            if rv is not None and rv != "":
                state.requirements[rk] = rv
                if state.awaiting_field == rk:
                    state.awaiting_field = None
                state.active_product = None
                state.candidate_products = []

    if not is_explicit_cat_switch and entities:
        for ek in ["print_size", "scan_required", "daily_volume", "speed"]:
            val = entities.get(ek)
            if val is not None and val != "":
                state.requirements[ek] = val
                if state.awaiting_field == ek:
                    state.awaiting_field = None
                state.active_product = None
                state.candidate_products = []

    # Handle volume numbers (e.g. "10000 per month", "50 per day", "20")
    is_awaiting_volume = state.awaiting_field in ("daily_volume", "print_volume", "volume")
    has_volume_keyword = any(k in msg_lower for k in ["per day", "a day", "daily", "per month", "a month", "monthly", "drawings per", "pages per", "prints per", "volume"])
    if is_awaiting_volume or has_volume_keyword:
        # Strip dimensions (e.g. "594 x 841 mm" or "24 inch") so dimensions aren't treated as volume
        msg_no_dims = re.sub(r"\b\d+\s*(?:x|\*)\s*\d+\b", "", msg_lower)
        msg_no_dims = re.sub(r"\b\d+\s*(?:mm|cm|inch|\"|gsm|dpi|ml)\b", "", msg_no_dims)
        vol_match = re.search(r"\b(\d{1,6})\b", msg_no_dims)
        if vol_match:
            try:
                val = int(vol_match.group(1))
                if "month" in msg_lower:
                    val = max(1, val // 30)  # Convert monthly to approximate daily
                state.requirements["daily_volume"] = val
                if state.awaiting_field == "daily_volume":
                    state.awaiting_field = None
            except ValueError:
                pass

    # Handle scanner-specific keywords
    if state.category == "scanner":
        if any(kw in msg_lower for kw in ["document", "invoice", "paper", "sheet", "sheetfed", "high-speed", "high speed", "duplex"]):
            state.requirements["document_type"] = "standard_documents"
            state.awaiting_field = None
        elif any(kw in msg_lower for kw in ["photo", "book", "bound", "id", "card", "passport", "flatbed"]):
            state.requirements["document_type"] = "flatbed_ids"
            state.awaiting_field = None
        elif any(kw in msg_lower for kw in ["nothing", "general", "normal", "any", "standard", "all"]):
            state.requirements["document_type"] = "standard_documents"
            state.awaiting_field = None

    # Handle "nothing", "skip", "any", "none", "don't know"
    if any(s in msg_lower for s in ["nothing", "skip", "any", "no preference", "default", "dont know", "don't know"]):
        if state.awaiting_field:
            state.requirements[state.awaiting_field] = "standard"
            state.awaiting_field = None

    # Handle corrections
    if intent == Intent.CORRECTION:
        field = entities.get("correction_field")
        value = entities.get("correction_value")
        if field and value is not None:
            state.requirements[field] = value
            state.active_product = None
            state.candidate_products = []

    # ── 3. Check for recommendation triggers or completed qualification ───
    rec_keywords = ["recommend now", "recommend", "show options", "show recommendations",
                    "what do you recommend", "suggest options", "show me options",
                    "give me options", "just show"]
    if any(k in msg_lower for k in rec_keywords) or qualification_complete(state):
        state.stage = "recommending"
        state.awaiting_field = None
        return RouteResult(
            reply="__READY_FOR_SEARCH__",
            source="route:qualification",
        )

    # ── 4. Deterministic Next Question ───────────────────────────────────
    state.stage = "qualifying"
    next_step = _next_q.evaluate_next_step(state)

    if next_step:
        question = next_step["question"]
        pills = next_step.get("pills", [])
        field = next_step.get("field", "")

        state.save_pending_question(question, field)

        return RouteResult(
            reply=question,
            suggested_chips=pills,
            source="route:qualification",
        )

    # All requirements collected -> Ready for product recommendation
    state.stage = "recommending"
    return RouteResult(
        reply="__READY_FOR_SEARCH__",
        source="route:qualification",
    )

