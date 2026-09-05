"""
Qualification Route for Kepler Tech Conversational AI.
Wraps the existing NextQuestionEngine and RequirementUpdater to ask
exactly one question at a time, never repeat already-answered fields,
and support corrections mid-qualification.
"""

import logging
import re
from domain.conversation_types import Intent, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from state.next_question_engine import NextQuestionEngine
from state.requirement_updater import RequirementUpdater

logger = logging.getLogger("route:qualification")

# Module-level engines (reuse existing implementations)
_next_q = NextQuestionEngine()
_req_updater = RequirementUpdater()


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    """
    Handle qualification flow:
    1. Apply any requirement updates from the understanding and raw_message
    2. Apply any corrections
    3. Set category if detected
    4. Ask the next unanswered question, or signal ready for search
    """
    entities = understanding.entities
    intent = understanding.intent
    msg_lower = (raw_message or "").strip().lower()

    # ── Category Detection: Text keywords + Entity fallback ──────────────
    detected_cat = None
    if any(k in msg_lower for k in ["cad", "plotter", "blueprint", "architect", "engineering", "technical drawing"]):
        detected_cat = "technical_cad"
    elif any(k in msg_lower for k in ["photo booth", "dye-sub", "citizen cx", "citizen cy"]):
        detected_cat = "photo_booth"
    elif any(k in msg_lower for k in ["photo fine art", "fine art", "gallery", "exhibition", "p900", "p700"]):
        detected_cat = "photo_fine_art"
    elif any(k in msg_lower for k in ["office printer", "workforce", "copier", "am-c4000"]):
        detected_cat = "office_enterprise"
    elif not any(neg in msg_lower for neg in ["no scanner", "without scanner", "not scanner", "don't need scanner", "dont need scanner"]) and any(k in msg_lower for k in ["scanner", "document scan", "scanning"]):
        detected_cat = "scanner"

    entity_cat = entities.get("product_category")
    if not detected_cat and entity_cat and entity_cat not in ("consumable", ""):
        detected_cat = entity_cat

    if detected_cat:
        # Only switch category if not set or if customer explicitly switches category
        if not state.category or ("actually" in msg_lower and any(kw in msg_lower for kw in ["need", "want", "switch", "printer", "looking for"])):
            state.reset_category(detected_cat)
            logger.info(f"Category set to: {detected_cat}")

    # ── Direct Text Extraction for Pending / Awaiting Fields ─────────────
    # Print size: A0, A1, A2, A3, 24", 36", 4x6
    if "a0" in msg_lower or "36-inch" in msg_lower or "36\"" in msg_lower:
        state.requirements["print_size"] = "A0"
        state.awaiting_field = None
    elif "a1" in msg_lower or "24-inch" in msg_lower or "24\"" in msg_lower:
        state.requirements["print_size"] = "A1"
        state.awaiting_field = None
    elif "4x6" in msg_lower or "6x8" in msg_lower:
        state.requirements["print_size"] = "4x6"
        state.awaiting_field = None

    # Scanner requirement: yes / no
    if "no scanner" in msg_lower or "without scanner" in msg_lower or "print only" in msg_lower or "no need" in msg_lower:
        state.requirements["scan_required"] = False
        state.awaiting_field = None
    elif "yes" in msg_lower or "need scanner" in msg_lower or "with scanner" in msg_lower:
        state.requirements["scan_required"] = True
        state.awaiting_field = None

    # Volume: numbers
    vol_match = re.search(r"\b(\d+)\b", msg_lower)
    if vol_match and (state.awaiting_field == "daily_volume" or "volume" in msg_lower or "day" in msg_lower or state.requirements.get("scan_required") is not None):
        try:
            vol_val = int(vol_match.group(1))
            if vol_val > 0:
                state.requirements["daily_volume"] = vol_val
                if state.awaiting_field == "daily_volume":
                    state.awaiting_field = None
        except ValueError:
            pass

    # ── Apply corrections from understanding ─────────────────────────────
    if intent == Intent.CORRECTION:
        field = entities.get("correction_field")
        value = entities.get("correction_value")
        if field and value is not None:
            if field == "scan_required":
                value = False if str(value).lower() in ("false", "no", "0", "none", "without") else True
            elif field == "daily_volume":
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass
            state.requirements[field] = value
            state.active_product = None
            state.candidate_products = []
            logger.info(f"Correction applied: {field} = {value}")

    # ── Apply requirement updates from understanding ─────────────────────
    req_updates = understanding.requirement_updates
    if req_updates:
        for field, value in req_updates.items():
            if field == "scan_required":
                value = False if str(value).lower() in ("false", "no", "0", "none", "without") else True
            state.requirements[field] = value
            if field == state.awaiting_field:
                state.awaiting_field = None
            logger.info(f"Requirement updated: {field} = {value}")

    # Ensure direct negative scanner check takes precedence
    if "no scanner" in msg_lower or "without scanner" in msg_lower or "print only" in msg_lower:
        state.requirements["scan_required"] = False
        state.awaiting_field = None

    # ── Apply entity-level field updates ─────────────────────────────────
    if entities.get("print_size") and not state.requirements.get("print_size"):
        state.requirements["print_size"] = entities["print_size"]
        if state.awaiting_field == "print_size":
            state.awaiting_field = None

    if entities.get("scan_required") is not None:
        val = entities["scan_required"]
        state.requirements["scan_required"] = False if str(val).lower() in ("false", "no", "0", "none") else bool(val)
        if state.awaiting_field == "scan_required":
            state.awaiting_field = None

    if entities.get("daily_volume") is not None:
        try:
            vol_val = int(entities["daily_volume"])
            if vol_val > 0:
                state.requirements["daily_volume"] = vol_val
                if state.awaiting_field == "daily_volume":
                    state.awaiting_field = None
        except (ValueError, TypeError):
            pass

    if entities.get("scanner_type") and (state.category == "scanner" or state.category is None) and any(kw in msg_lower for kw in ["scanner", "scan", "document", "flatbed", "sheetfed"]):
        if not any(neg in msg_lower for neg in ["no scanner", "without scanner"]):
            state.requirements["scanner_type"] = entities["scanner_type"]
            state.category = "scanner"
            if state.awaiting_field == "scanner_type":
                state.awaiting_field = None

    if entities.get("model_code"):
        state.requirements["printer_model"] = entities["model_code"]
        if state.awaiting_field == "printer_model":
            state.awaiting_field = None

    # ── If customer wants recommendations now or asks to skip remaining questions ──
    from agent.decision_engine import qualification_complete
    rec_keywords = ["recommend now", "recommend", "show options", "show recommendations",
                    "what do you recommend", "suggest options", "show me options",
                    "give me options", "skip", "just show"]
    if any(k in msg_lower for k in rec_keywords) and qualification_complete(state):
        state.stage = "recommending"
        state.awaiting_field = None
        return RouteResult(
            reply="__READY_FOR_SEARCH__",
            source="route:qualification",
        )

    # ── Ask next question or signal ready ────────────────────────────────
    state.stage = "qualifying"
    next_step = _next_q.evaluate_next_step(state)

    if next_step:
        question = next_step["question"]
        pills = next_step.get("pills", [])
        field = next_step.get("field", "")

        # Save as pending question (in case user interrupts socially)
        state.save_pending_question(question, field)

        return RouteResult(
            reply=question,
            suggested_chips=pills,
            source="route:qualification",
        )

    # All required fields are collected — signal ready for product search
    state.stage = "recommending"
    return RouteResult(
        reply="__READY_FOR_SEARCH__",  # Sentinel for orchestrator to trigger product route
        source="route:qualification",
    )
