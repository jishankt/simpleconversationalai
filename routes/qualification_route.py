"""Conservative consultative qualification route.

Only requirements explicitly supported by the customer's current message are
committed to state.  LLM extraction is treated as a proposal, not as truth.
The route asks exactly one missing question at a time.
"""

import logging
import re
from typing import Any, Dict
from domain.conversation_types import Intent, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from state.next_question_engine import NextQuestionEngine

logger = logging.getLogger("route:qualification")
_next_q = NextQuestionEngine()


def _detect_category(text: str, entities: Dict[str, Any]) -> str | None:
    if any(k in text for k in ["cad", "plotter", "blueprint", "architect", "engineering", "technical drawing"]):
        return "technical_cad"
    if any(k in text for k in ["photo booth", "dye-sub", "dye sub", "citizen cx", "citizen cy"]):
        return "photo_booth"
    if any(k in text for k in ["photo fine art", "fine art", "gallery", "exhibition", "p900", "p700"]):
        return "photo_fine_art"
    if any(k in text for k in ["office printer", "workforce", "copier", "enterprise printer", "am-c4000"]):
        return "office_enterprise"
    scanner_negative = any(k in text for k in ["no scanner", "without scanner", "don't need scanner", "dont need scanner", "print only"])
    if not scanner_negative and any(k in text for k in ["scanner", "document scan", "scanning", "flatbed", "sheetfed"]):
        return "scanner"
    entity_cat = entities.get("product_category")
    if entity_cat and entity_cat not in ("", "consumable"):
        return str(entity_cat)
    return None


def _explicit_print_size(text: str) -> str | None:
    if re.search(r"\ba0\b", text) or "36-inch" in text or '36"' in text or "36 inch" in text:
        return "A0"
    if re.search(r"\ba1\b", text) or "24-inch" in text or '24"' in text or "24 inch" in text:
        return "A1"
    if "6x8" in text:
        return "6x8"
    if "4x6" in text:
        return "4x6"
    return None


def _explicit_scan_requirement(text: str, awaiting_field: str | None) -> bool | None:
    negatives = ["no scanner", "without scanner", "print only", "don't need scanner", "dont need scanner", "scanner not required"]
    positives = ["need scanner", "with scanner", "scanner required", "built in scanner", "built-in scanner", "need scanning"]
    if any(k in text for k in negatives):
        return False
    if any(k in text for k in positives):
        return True
    # A bare yes/no is meaningful ONLY as an answer to the scanner question.
    if awaiting_field == "scan_required":
        if text.strip() in {"yes", "yeah", "yep", "yes please"}:
            return True
        if text.strip() in {"no", "nope", "no thanks"}:
            return False
    return None


def _explicit_daily_volume(text: str, awaiting_field: str | None) -> int | None:
    # Never turn an arbitrary product/model/size number into daily volume.
    explicit = re.search(r"\b(\d+)\s*(?:prints?|pages?|drawings?|sheets?)?\s*(?:per\s+day|a\s+day|daily)\b", text)
    if explicit:
        value = int(explicit.group(1))
        return value if value > 0 else None
    if awaiting_field == "daily_volume":
        bare = re.fullmatch(r"\s*(\d+)\s*", text)
        if bare:
            value = int(bare.group(1))
            return value if value > 0 else None
    return None


def _supported_llm_update(field: str, value: Any, text: str, awaiting_field: str | None) -> bool:
    """Accept an LLM proposal only when current customer text supports it."""
    if value in (None, "", [], {}):
        return False
    if field == "print_size":
        explicit = _explicit_print_size(text)
        return explicit is not None and str(value).lower().replace(" ", "") in explicit.lower().replace(" ", "")
    if field == "scan_required":
        explicit = _explicit_scan_requirement(text, awaiting_field)
        return explicit is not None and bool(value) is explicit
    if field == "daily_volume":
        explicit = _explicit_daily_volume(text, awaiting_field)
        try:
            return explicit is not None and int(value) == explicit
        except (TypeError, ValueError):
            return False
    # For other fields require the proposed value itself to be present in text.
    value_text = str(value).strip().lower()
    return len(value_text) >= 2 and value_text in text


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    entities = understanding.entities
    msg = (raw_message or "").strip().lower()

    detected_cat = _detect_category(msg, entities)
    if detected_cat and (
        not state.category
        or ("actually" in msg and any(k in msg for k in ["need", "want", "switch", "looking for"]))
    ):
        state.reset_category(detected_cat)
        logger.info("Category set to %s", detected_cat)

    # Capture the question context before any extraction clears awaiting_field.
    awaiting = state.awaiting_field

    size = _explicit_print_size(msg)
    if size is not None:
        state.requirements["print_size"] = size
        if awaiting == "print_size":
            state.awaiting_field = None

    scan = _explicit_scan_requirement(msg, awaiting)
    if scan is not None:
        state.requirements["scan_required"] = scan
        if awaiting == "scan_required":
            state.awaiting_field = None

    volume = _explicit_daily_volume(msg, awaiting)
    if volume is not None:
        state.requirements["daily_volume"] = volume
        if awaiting == "daily_volume":
            state.awaiting_field = None

    # Corrections are also evidence-bound.  A correction entity cannot silently
    # introduce a value that the customer did not express in this turn.
    if understanding.intent == Intent.CORRECTION:
        field = entities.get("correction_field")
        value = entities.get("correction_value")
        if field and _supported_llm_update(field, value, msg, awaiting):
            state.requirements[field] = value
            state.active_product = None
            state.active_product_id = None
            state.candidate_products = []

    # LLM requirement_updates are proposals only.
    for field, value in (understanding.requirement_updates or {}).items():
        if _supported_llm_update(field, value, msg, awaiting):
            state.requirements[field] = value
            if field == state.awaiting_field:
                state.awaiting_field = None
        else:
            logger.info("Ignored unsupported LLM requirement proposal: %s=%r", field, value)

    # Safe entity-level fields.
    model_code = entities.get("model_code")
    if model_code and str(model_code).lower() in msg:
        state.requirements["printer_model"] = model_code
        if state.awaiting_field == "printer_model":
            state.awaiting_field = None

    scanner_type = entities.get("scanner_type")
    if scanner_type and (state.category == "scanner" or state.category is None):
        scanner_words = ["scanner", "scan", "document", "flatbed", "sheetfed"]
        if any(k in msg for k in scanner_words) and not any(k in msg for k in ["no scanner", "without scanner"]):
            # Entity is useful for normalization, but only in an explicitly scanner-related turn.
            state.requirements["scanner_type"] = scanner_type
            state.category = "scanner"
            if state.awaiting_field == "scanner_type":
                state.awaiting_field = None

    from agent.decision_engine import qualification_complete
    rec_keywords = [
        "recommend now", "recommend", "show options", "show recommendations",
        "what do you recommend", "suggest options", "show me options",
        "give me options", "skip", "just show",
    ]
    if any(k in msg for k in rec_keywords) and qualification_complete(state):
        state.stage = "recommending"
        state.awaiting_field = None
        return RouteResult(reply="__READY_FOR_SEARCH__", source="route:qualification")

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
            needs_composition=False,
        )

    state.stage = "recommending"
    return RouteResult(reply="__READY_FOR_SEARCH__", source="route:qualification")
