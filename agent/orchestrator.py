"""
New Orchestrator for Kepler Tech Conversational AI.
Wires together the full pipeline:
  Normalizer → Interceptor → LLM Understanding → Decision Engine → Route Handler → Response

Replaces the monolithic ai_orchestrator.py with a clean, testable pipeline.
"""

import logging
import time
from typing import Dict, Any, List

from nlp.normalizer import normalize_text
from nlp.deterministic_interceptor import intercept
from agent.response_composer import ResponseComposer
from nlp.response_validator import validate_response
from nlp.llm_understanding import LLMUnderstandingEngine
from agent.decision_engine import decide
from agent.route_registry import get_handler
from domain.conversation_types import (
    Intent, LLMUnderstanding, RouteName, RouteResult,
)
from domain.conversation_state import ConversationState
from guardrails import validate_and_sanitize_response
from nlp.grounding_validator import validate_grounding
from ollama_client import OllamaClient

logger = logging.getLogger("orchestrator")


class Orchestrator:
    def __init__(self, ollama_client: OllamaClient = None):
        self.ollama_client = ollama_client
        self.llm_engine = LLMUnderstandingEngine(ollama_client)
        self.response_composer = ResponseComposer(ollama_client)

    def process_turn(
        self,
        raw_message: str,
        session_id: str,
        history: List[Dict[str, str]],
        state: ConversationState,
        model_name: str = None,
    ) -> Dict[str, Any]:
        """
        Process a single conversational turn through the full pipeline.
        Returns the same response format as the old ai_orchestrator for compatibility.
        """
        start_time = time.time()

        # ── 1. Normalize ─────────────────────────────────────────────────
        norm_result = normalize_text(raw_message)
        normalized_msg = norm_result["normalized_text"]

        nlp_result = {
            "raw_text": norm_result["raw_text"],
            "clean_text": norm_result["clean_text"],
            "normalized_text": normalized_msg,
            "corrections": norm_result["corrections_applied"],
            "intent": "",
            "brands": [],
            "categories": [],
            "models": [],
            "sizes": norm_result["canonical_sizes"],
        }

        # ── 2. Deterministic Intercept ───────────────────────────────────
        intercept_result = intercept(normalized_msg, raw_message)

        if intercept_result.matched and not intercept_result.should_continue:
            nlp_result["intent"] = intercept_result.intent or ""
            source = "guardrail_rule" if intercept_result.intent in ("price_inquiry", "discount_inquiry") else f"interceptor:{intercept_result.intent}"
            
            # Never spam product recommendation cards during price/discount inquiries or general FAQs
            cards_to_return = []
            if intercept_result.intent in ("greeting", "reset"):
                state.candidate_products = []
                state.active_product = None
                state.requirements = {}
                state.category = None
                state.stage = "open"

            state.last_assistant_response = intercept_result.response
            state.increment_turn()

            return self._build_response(
                reply=intercept_result.response,
                source=source,
                product_cards=cards_to_return,
                consumable_cards=[],
                suggested_chips=[],
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )


        # ── 3. LLM Understanding ────────────────────────────────────────
        state_summary = state.to_dict()
        recent_turns = state.history_turns[-6:] if state.history_turns else []

        understanding = self.llm_engine.understand(
            customer_message=normalized_msg,
            recent_turns=recent_turns,
            state_summary=state_summary,
            model=model_name,
        )

        nlp_result["intent"] = understanding.intent.value
        logger.info(f"[{session_id[:8]}] Understanding: intent={understanding.intent.value} "
                     f"confidence={understanding.confidence:.2f} action={understanding.requested_action}")

        # ── 3b. Apply entities & requirement updates from LLM ─────────────
        # Ingest requirement_updates extracted directly by the LLM
        if understanding.requirement_updates:
            for k, v in understanding.requirement_updates.items():
                if v is not None and v != "":
                    state.requirements[k] = v
                    if state.awaiting_field == k:
                        state.awaiting_field = None
                    logger.info(f"[{session_id[:8]}] Applied requirement_update from LLM: {k}={v}")

        if understanding.entities:
            ents = understanding.entities
            if ents.get("customer_name") and not state.customer_name:
                state.customer_name = ents["customer_name"]

            # Category switch from LLM
            import re
            llm_cat = ents.get("product_category")
            has_explicit_model = bool(ents.get("model_code") or re.search(r"\b(?:p\d{3,4}|t\d{3,4}|am-?c\d{3,4}|ds-?\d{3,4}|f100|cx-?\d{2}|cy-?\d{2})\b", normalized_msg.lower()))
            is_general_printer_inquiry = (
                not has_explicit_model
                and state.awaiting_field != "category"
                and bool(re.search(r"\b(?:want|buy|need|looking for|get|require)\b.*?\b(?:a\s*printer|aprinter|printers?|plotters?)\b", normalized_msg.lower()))
                and not any(k in normalized_msg.lower() for k in ["cad", "photo", "blueprint", "office", "booth", "scanner", "dyesub"])
            )

            if is_general_printer_inquiry:
                state.reset_category(None)
                state.awaiting_field = "category"
                logger.info("General printer inquiry detected — category reset to None to prompt customer.")
            elif state.awaiting_field == "category":
                # Customer is responding to the category prompt
                msg_raw_l = normalized_msg.lower().strip()
                resolved_cat = None
                if any(k in msg_raw_l for k in ["cad", "plotter", "technical", "blueprint"]):
                    resolved_cat = "technical_cad"
                elif any(k in msg_raw_l for k in ["photo fine art", "fine art", "photo", "gallery"]):
                    resolved_cat = "photo_fine_art"
                elif any(k in msg_raw_l for k in ["photo booth", "booth", "dye-sub", "dyesub"]):
                    resolved_cat = "photo_booth"
                elif any(k in msg_raw_l for k in ["scanner", "scanning"]):
                    resolved_cat = "scanner"
                elif any(k in msg_raw_l for k in ["printer", "printers", "office", "enterprise", "document", "normal", "standard", "regular", "business"]):
                    resolved_cat = "office_enterprise"
                
                if resolved_cat:
                    state.reset_category(resolved_cat)
                    state.awaiting_field = None
                    logger.info(f"Category resolved from awaiting_field response to: {resolved_cat}")
            elif llm_cat in ("technical_cad", "photo_fine_art", "photo_booth", "office_enterprise", "scanner", "consumable"):
                if llm_cat == "scanner" and (
                    state.awaiting_field == "scan_required"
                    or (state.category in ("technical_cad", "office_enterprise") and any(sw in normalized_msg.lower() for sw in ["need scanner", "with scanner", "has scanner", "scanner too", "yes scanner"]))
                ):
                    pass
                else:
                    if not state.category or (state.category != llm_cat and any(w in normalized_msg.lower() for w in ["want", "need", "switch", "instead", "printer", "photo", "cad", "scanner", "office", "booth"])):
                        state.reset_category(llm_cat)
                        logger.info(f"Category set/switched via LLM understanding to: {llm_cat}")

            # Print size from LLM
            if ents.get("print_size") and ents["print_size"].strip():
                state.requirements["print_size"] = ents["print_size"].strip()
                if state.awaiting_field == "print_size":
                    state.awaiting_field = None

            # Scanner requirement from LLM
            if ents.get("scan_required") is not None and ents.get("scan_required") != "":
                state.requirements["scan_required"] = bool(ents["scan_required"])
                if state.awaiting_field == "scan_required":
                    state.awaiting_field = None
            elif ents.get("scanner_type") in ("no", "none", "false", "without"):
                state.requirements["scan_required"] = False
                if state.awaiting_field == "scan_required":
                    state.awaiting_field = None

            # Daily volume from LLM
            if ents.get("daily_volume") is not None and ents.get("daily_volume") != "":
                v = ents["daily_volume"]
                if isinstance(v, (int, float)) and v > 0:
                    state.requirements["daily_volume"] = int(v)
                elif isinstance(v, str) and v.lower() in ("low", "medium", "high"):
                    state.requirements["daily_volume"] = v.lower()
                if state.awaiting_field in ("daily_volume", "speed", "volume"):
                    state.awaiting_field = None

        # ── 3c. Extract deterministic requirements (Brand, Sizes, Scan, Volume) ──
        from conversation.requirement_extractor import requirement_extractor
        extracted_reqs = requirement_extractor.extract_and_validate(normalized_msg, state)
        if extracted_reqs:
            for rk, rv in extracted_reqs.items():
                if rv is not None and rv != "":
                    state.requirements[rk] = rv
                    if state.awaiting_field == rk:
                        state.awaiting_field = None
                    logger.info(f"[{session_id[:8]}] Applied requirement from extractor: {rk}={rv}")

            if "brand" in extracted_reqs:
                req_brand = extracted_reqs["brand"]
                state.requirements["brand"] = req_brand
                if req_brand == "Citizen" and state.category in ("photo_fine_art", "technical_cad", "office_enterprise", None):
                    state.category = "photo_booth"
                    state.active_product = None
                    state.candidate_products = []
                    req_sz = str(state.requirements.get("print_size", "")).lower()
                    if any(w in req_sz for w in ["large", "wide", "24-inch", "44-inch", "a0", "a1", "8x12", "8x10"]):
                        state.requirements["print_size"] = "8x12 inches"
                    else:
                        state.requirements["print_size"] = "4x6 inches"
                elif req_brand == "Epson" and state.category == "photo_booth":
                    state.category = "photo_fine_art"
                    state.active_product = None
                    state.candidate_products = []
                    if state.requirements.get("print_size") in ("4x6", "4x6 inches", "5x7", "6x8"):
                        state.requirements["print_size"] = "A3+"


        # ── 4. Decision Engine ───────────────────────────────────────────
        decision = decide(understanding, state, raw_message=normalized_msg)

        route_val = decision.route.value if hasattr(decision.route, "value") else str(decision.route)
        intent_val = understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent)
        logger.info(f"[{session_id[:8]}] Decision: route={route_val} tool={decision.tool} reason={decision.reason}")

        state.active_route = route_val
        state.last_intent = intent_val

        # ── 5. Route Handler ─────────────────────────────────────────────
        handler = get_handler(decision.route)
        route_result = RouteResult()

        if handler:
            # Pass normalized_msg for routes that need it
            try:
                if decision.route in (RouteName.PRODUCT, RouteName.BUSINESS_INFO, RouteName.QUALIFICATION, RouteName.CONSUMABLES, RouteName.COMPARISON):
                    route_result = handler.handle(understanding, state, raw_message=normalized_msg)
                else:
                    route_result = handler.handle(understanding, state)
            except Exception as e:
                logger.error(f"Route handler error: {e}", exc_info=True)
                route_result = RouteResult(
                    reply="I apologize for the issue. Could you please rephrase your question?",
                    source="route:error",
                )

        # ── 5b. Handle qualification-ready sentinel ──────────────────────
        if route_result.reply == "__READY_FOR_SEARCH__":
            # Qualification is complete — trigger product search
            from routes import product_route
            route_result = product_route.handle(understanding, state, raw_message=raw_message)

        # ── 6. Clarification fallback ────────────────────────────────────
        if decision.route == RouteName.CLARIFICATION or not route_result.reply:
            route_result = RouteResult(
                reply="I'd like to help — could you tell me a bit more about what you're looking for?",
                suggested_chips=[],
                source="route:clarification",
            )

        # ── 6b. Natural Response Composition ─────────────────────────────
        if not route_result.needs_composition:
            composed_reply = route_result.reply
        else:
            composed_reply = self.response_composer.compose_response(
                customer_message=raw_message,
                route_result=route_result,
                state=state,
                active_route=decision.route,
                model_name=model_name,
            )

        # ── 7. Validate, Sanitize & Ground ──────────────────────────────
        val_result = validate_response(
            response=composed_reply,
            previous_response=state.last_assistant_response,
            context_intent=understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent),
        )
        candidate_text = val_result.sanitized_response or composed_reply

        sanitized = validate_and_sanitize_response(candidate_text, normalized_msg)
        grounding_result = validate_grounding(sanitized, normalized_msg, nlp_result)

        # ── 8. Update state ──────────────────────────────────────────────
        state.last_assistant_response = grounding_result["sanitized_response"]
        state.last_dialogue_act = understanding.dialogue_act.value if hasattr(understanding.dialogue_act, "value") else str(understanding.dialogue_act or "")
        state.increment_turn()

        latency_ms = int((time.time() - start_time) * 1000)

        return self._build_response(
            reply=grounding_result["sanitized_response"],
            source=route_result.source,
            product_cards=route_result.product_cards,
            consumable_cards=route_result.consumable_cards,
            suggested_chips=route_result.suggested_chips,
            nlp_result=nlp_result,
            state=state,
            grounding_result=grounding_result,
            latency_ms=latency_ms,
        )

    def _build_response(
        self,
        reply: str,
        source: str,
        product_cards: list,
        consumable_cards: list,
        suggested_chips: list,
        nlp_result: dict,
        state: ConversationState,
        grounding_result: dict = None,
        latency_ms: int = 0,
    ) -> Dict[str, Any]:
        """Build the standardized response dict (compatible with old orchestrator)."""
        if grounding_result is None:
            grounding_result = {
                "sanitized_response": reply,
                "is_grounded": True,
                "status": "INTERCEPTED",
                "notes": [],
            }

        return {
            "reply": grounding_result.get("sanitized_response", reply),
            "source": source,
            "product_cards": product_cards,
            "consumable_cards": consumable_cards,
            "suggested_chips": suggested_chips,
            "retrieved_items": (product_cards or []) + (consumable_cards or []),
            "grounding": {
                "is_grounded": grounding_result.get("is_grounded", True),
                "status": grounding_result.get("status", "OK"),
                "notes": grounding_result.get("notes", []),
            },
            "nlp": nlp_result,
            "state": state,
            "metadata": {
                "latency_ms": latency_ms,
                "fallback_used": False,
            },
        }


# Global singleton (client injected in app.py)
orchestrator = Orchestrator()
