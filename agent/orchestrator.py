"""
Single Conversational Orchestrator for Kepler Tech SalesAI.
Implements the required unified conversational pipeline:
Customer message
→ Detect category
→ Extract requirements
→ Update conversation state
→ Check mandatory requirements
→ Ask one missing question at a time
→ Determine final subcategory
→ Fetch every eligible catalogue product
→ Rank matching products
→ Return all matching products as cards
→ Allow comparison, selection or requirement refinement

Deterministic Python code strictly controls qualification, catalogue filtering,
validation, and product-card selection.
The local LLM is used strictly for natural-language understanding and response composition.
"""

import re
import logging
import time
from typing import Dict, Any, List, Optional

from nlp.normalizer import normalize_text
from nlp.deterministic_interceptor import intercept
from agent.response_composer import ResponseComposer
from nlp.llm_understanding import LLMUnderstandingEngine
from domain.conversation_types import Intent, LLMUnderstanding, RouteResult, RouteName
from domain.conversation_state import ConversationState
from guardrails import validate_and_sanitize_response, PRICE_REFUSAL, STATIC_SAFE_REFUSAL
from ollama_client import OllamaClient

from catalog.catalogue_loader import catalogue_loader
from catalog.subcategory_resolver import resolve_subcategory
from catalog.catalogue_filter import catalogue_filter
from catalog.catalogue_resolver import (
    find_mentioned_catalogue_products,
    build_model_detail_response,
    build_approved_comparison_response,
)
from conversation.qualification_schema import (
    get_mandatory_fields,
    get_missing_mandatory_fields,
    get_next_question,
)
from conversation.normalizer import (
    normalize_category,
    extract_deterministic_requirements,
)
from validation.catalogue_validator import (
    validate_product_cards,
    validate_and_sanitize_catalogue_text,
)
from rag.consumables_engine import consumables_engine

logger = logging.getLogger("orchestrator")


class Orchestrator:
    def __init__(self, ollama_client: OllamaClient = None):
        self.ollama_client = ollama_client
        self.llm_engine = LLMUnderstandingEngine(ollama_client)
        self.response_composer = ResponseComposer(ollama_client)

    def process_turn(
        self,
        raw_message: str,
        session_id: str = "default-session",
        history: Optional[List[Dict[str, str]]] = None,
        state: Optional[ConversationState] = None,
        model_name: str = None,
    ) -> Dict[str, Any]:
        """
        Processes a conversational turn through the single orchestrator pipeline.
        """
        if state is None:
            state = ConversationState(session_id=session_id)
        if history is None:
            history = state.history_turns if hasattr(state, "history_turns") else []
        start_time = time.time()

        # ── 1. Normalize Text ─────────────────────────────────────────────
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

        # ── 2. Deterministic Intercept (Commercial Guardrails & Greetings) ─
        intercept_result = intercept(normalized_msg, raw_message)

        if intercept_result.matched and not intercept_result.should_continue:
            nlp_result["intent"] = intercept_result.intent or ""
            source = "guardrail:price_refusal" if intercept_result.intent in ("price_inquiry", "discount_inquiry", "quote", "commercial") else f"interceptor:{intercept_result.intent}"

            if intercept_result.intent in ("price_inquiry", "discount_inquiry", "quote", "commercial"):
                reply_text = PRICE_REFUSAL
                chips_to_return = []
            else:
                reply_text = intercept_result.response
                chips_to_return = intercept_result.suggested_chips or []
                if intercept_result.intent in ("greeting", "reset"):
                    state.reset_category(None)
                    state.requirements = {}
                    state.stage = "open"
                    chips_to_return = [
                        "Technical CAD Plotters",
                        "Office Enterprise Documents",
                        "Professional Photographs",
                        "Event Photos (Photo Booth)",
                    ]

            state.last_assistant_response = reply_text
            state.increment_turn()

            return self._build_response(
                reply=reply_text,
                source=source,
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # ── 3. LLM Understanding (Intent & Semantic Entities) ─────────────
        state_summary = state.to_dict()
        recent_turns = state.history_turns[-6:] if state.history_turns else []

        understanding = self.llm_engine.understand(
            customer_message=normalized_msg,
            recent_turns=recent_turns,
            state_summary=state_summary,
            model=model_name,
        )

        nlp_result["intent"] = understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent)
        logger.info(f"[{session_id[:8]}] Understanding: intent={nlp_result['intent']} confidence={understanding.confidence:.2f}")

        # Update customer name if provided
        ents = understanding.entities or {}
        if ents.get("customer_name") and not state.customer_name:
            state.customer_name = ents["customer_name"]

        # ── 4. Deterministic Category Detection & State Update ────────────
        detected_category = normalize_category(normalized_msg, state.category)
        if detected_category and state.category != detected_category:
            logger.info(f"[{session_id[:8]}] Category updated to: {detected_category}")
            state.reset_category(detected_category)

        # ── 5. Deterministic Requirement Extraction & Normalization ───────
        det_reqs, det_corrections = extract_deterministic_requirements(normalized_msg, state.category)

        # If user was specifically answering awaiting_field == "daily_volume", ensure number is captured
        if state.awaiting_field == "daily_volume" and "daily_volume" not in det_reqs:
            range_match = re.search(r"(\d+)\s*(?:to|-|–)\s*(\d+)", normalized_msg)
            if range_match:
                det_reqs["daily_volume"] = (int(range_match.group(1)) + int(range_match.group(2))) // 2
            else:
                num_match = re.search(r"\b(\d+)\b", normalized_msg)
                if num_match:
                    det_reqs["daily_volume"] = int(num_match.group(1))
        
        # Merge LLM requirement updates if present and not overridden by deterministic rules
        if understanding.requirement_updates:
            for k, v in understanding.requirement_updates.items():
                if k not in det_reqs and v is not None and v != "":
                    det_reqs[k] = v

        state.update_requirements(det_reqs, det_corrections)
        logger.info(f"[{session_id[:8]}] Current requirements: {state.requirements}")

        # Clear awaiting field if answered
        if state.awaiting_field and state.awaiting_field in state.requirements:
            state.awaiting_field = None

        # ── 6. Preserve Existing System Behavior (Non-Qualification Routes) ─

        # Check for direct mentioned approved catalogue products
        mentioned_products = find_mentioned_catalogue_products(normalized_msg)

        # Fail-closed refusal for unapproved models (e.g. SC-F100, SC-F500, competitor brands)
        from validation.catalogue_validator import UNAPPROVED_MODELS
        unapproved_detected = [m for m in UNAPPROVED_MODELS if re.search(rf"\b{re.escape(m)}\b", normalized_msg.lower())]
        if unapproved_detected and not mentioned_products:
            unapproved_names = ", ".join([m.upper() for m in unapproved_detected[:2]])
            reply_text = (
                f"The requested model ({unapproved_names}) is not part of Kepler Tech's approved catalogue. "
                "We specialize in official Epson SureColor Technical (T-Series), Photo & Fine Art (P-Series), "
                "WorkForce Enterprise Office printers, and Citizen Photo printers. "
                "What type of printing application are you looking to support?"
            )
            chips_to_return = [
                "Technical CAD Plotters",
                "Office Enterprise Documents",
                "Professional Photographs",
                "Event Photos (Photo Booth)",
            ]
            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="guardrail:unapproved_model_refusal",
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 6a. Comparison Query (Between 2+ Approved Catalogue Products)
        is_comparison_query = (
            understanding.intent == Intent.PRODUCT_COMPARISON
            or any(w in normalized_msg.lower() for w in ["compare", " vs ", " versus ", "difference between"])
        )
        if is_comparison_query and len(mentioned_products) >= 2:
            reply_text, cards = build_approved_comparison_response(mentioned_products)
            state.stage = "comparing"
            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="route:comparison",
                product_cards=cards,
                consumable_cards=[],
                suggested_chips=["View Technical Specifications", "Compatible Consumables"],
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 6b. Exact Model Detail Inquiry (For one of the 41 approved products)
        is_detail_query = any(w in normalized_msg.lower() for w in ["tell me about", "specs of", "specifications", "details of", "information on", "about the"])
        if mentioned_products and (is_detail_query or len(normalized_msg.split()) <= 4):
            # Answer directly without forcing a new qualification flow
            target_prod = mentioned_products[0]
            reply_text, cards = build_model_detail_response(target_prod)
            state.active_product = target_prod
            state.active_product_id = target_prod["id"]
            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="route:model_detail",
                product_cards=cards,
                consumable_cards=[],
                suggested_chips=["View Compatible Consumables", "Compare with Alternative"],
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 6c. Consumables Inquiry
        is_printer_search = any(k in normalized_msg.lower() for k in [
            "need a printer", "looking for a printer", "photo printer", "which printer",
            "show all matching models", "show matching", "show every matching", "show me all",
            "show all", "list every", "which model", "matching catalogue", "suitable printer"
        ])
        is_consumables_query = (
            not is_printer_search
            and (
                understanding.intent == Intent.CONSUMABLES_QUERY
                or any(w in normalized_msg.lower() for w in ["ink", "inks", "cartridge", "cartridges", "toner", "ribbon", "maintenance box", "maintenance tank"])
            )
        )
        if is_consumables_query:
            p_name = mentioned_products[0]["display_name"] if mentioned_products else (state.active_product.get("name") if state.active_product else "")
            c_cards = []
            if p_name:
                c_cards = consumables_engine.get_printer_consumables(p_name, limit=6)
            reply_text = f"Here are the verified inks and media compatible with {p_name or 'your requested printer'}:" if c_cards else "Which printer model do you need compatible inks, ribbons, or maintenance tanks for?"
            chips_to_return = ["Epson SC-T3100 Inks", "Citizen CX-02 Media", "Epson SC-P900 Inks"] if not c_cards else []
            return self._build_response(
                reply=reply_text,
                source="route:consumables",
                product_cards=[],
                consumable_cards=c_cards,
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 6d. Company Information / Business Hours / Location
        is_product_query = any(k in normalized_msg.lower() for k in [
            "printer", "printers", "plotter", "plotters", "mfp", "copier", "copiers",
            "print", "scanner", "scan", "cartridge", "toner", "ink", "a4", "a3", "cad",
            "photo", "catalogue", "catalog", "model", "models", "show me", "need a", "looking for", "pages"
        ])
        is_business_info = (
            not is_product_query
            and (
                understanding.intent == Intent.BUSINESS_INFORMATION
                or any(w in normalized_msg.lower() for w in [
                    "location", "address", "opening hours", "business hours", "working hours",
                    "contact number", "phone number", "email address", "where are you",
                    "office location", "office address", "your office"
                ])
            )
        )
        if is_business_info:
            reply_text = (
                "**Kepler Tech LLC — Dubai Headquarters**\n\n"
                "📍 **Address:** D79, Khalid Bin Waleed Road, Office No. 1, Abdulla Al Awar Building, Dubai, UAE.\n"
                "🕒 **Working Hours:** Monday – Friday: 8:30 AM to 5:30 PM | Saturday: 8:30 AM to 1:00 PM | Sunday: Closed\n"
                "📞 **Phone:** +971 4 323 1008 | +971 55 835 8586\n"
                "✉️ **Email:** sales@keplertech.ae | info@keplertech.ae\n\n"
                "We provide delivery and authorized technical support across the UAE and Middle East."
            )
            chips_to_return = ["Technical CAD Plotters", "Photo & Fine Art Printers", "Office Enterprise MFPs"]
            return self._build_response(
                reply=reply_text,
                source="route:business_info",
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # ── 7. Mandatory Qualification & Product Recommendation Flow ─────

        # 7a. If category is still unknown, prompt for category
        if not state.category:
            reply_text = "What will you primarily print—technical CAD drawings, office enterprise documents, professional photographs, or event photos?"
            chips_to_return = [
                "Technical CAD Plotters",
                "Office Enterprise Documents",
                "Professional Photographs",
                "Event Photos (Photo Booth)",
            ]
            state.awaiting_field = "category"
            state.stage = "qualifying"
            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="qualification:category_prompt",
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 7b. Check mandatory requirements against schema
        missing_mandatory = get_missing_mandatory_fields(state.category, state.requirements)
        state.missing_fields = missing_mandatory

        # If mandatory requirements are missing, ask strictly ONE question at a time
        if missing_mandatory:
            next_q = get_next_question(state.category, missing_mandatory)
            state.awaiting_field = next_q["field"]
            state.stage = "qualifying"
            state.qualification_complete = False
            reply_text = next_q["question"]
            chips_to_return = next_q["pills"]

            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="qualification:next_question",
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 7c. All mandatory requirements satisfied -> Determine leaf subcategory & return all matching cards
        state.qualification_complete = True
        state.stage = "recommending"
        state.awaiting_field = None

        subcategory = resolve_subcategory(state.category, state.requirements)
        state.subcategory = subcategory

        # Hard catalogue filtering and soft ranking
        cards, no_match = catalogue_filter.filter_and_rank(state.category, subcategory, state.requirements)

        if no_match:
            reply_text = f"{no_match['message']} {no_match['relaxation_question']}"
            product_cards = []
            chips_to_return = []
            source = "recommendation:no_match"
        else:
            # Validate cards fail-closed (all IDs must belong to 41 approved catalogue entries)
            valid_cards = validate_product_cards(cards)
            state.displayed_product_ids = [c["id"] for c in valid_cards]
            state.results_loaded = True
            product_cards = valid_cards
            if subcategory == "a3_workforce_pro_multifunction":
                reply_text = f"I found {len(valid_cards)} A3 WorkForce Pro multifunction printer{'s' if len(valid_cards) != 1 else ''} matching your requirements."
            elif subcategory == "a3_enterprise_multifunction":
                reply_text = f"I found {len(valid_cards)} A3 WorkForce Enterprise multifunction printer{'s' if len(valid_cards) != 1 else ''} matching your requirements."
            elif subcategory == "a4_colour_multifunction":
                reply_text = f"I found {len(valid_cards)} A4 colour multifunction printer{'s' if len(valid_cards) != 1 else ''} matching your requirements."
            elif state.requirements.get("paper_size") == "a3":
                reply_text = f"I found {len(valid_cards)} A3 multifunction printer{'s' if len(valid_cards) != 1 else ''} matching your requirements:"
            else:
                reply_text = f"I found {len(valid_cards)} catalogue printer{'s' if len(valid_cards) != 1 else ''} matching your requirements:"
            # Natural language fail-closed validation
            sanitized_reply, _ = validate_and_sanitize_catalogue_text(reply_text, valid_cards)
            reply_text = sanitized_reply
            chips_to_return = ["Compare Matching Models", "View Detailed Specifications", "Filter by Requirements"]
            source = "recommendation:catalogue_list"

        state.last_assistant_response = reply_text
        state.increment_turn()

        return self._build_response(
            reply=reply_text,
            source=source,
            product_cards=product_cards,
            consumable_cards=[],
            suggested_chips=chips_to_return,
            nlp_result=nlp_result,
            state=state,
            latency_ms=int((time.time() - start_time) * 1000),
            subcategory=subcategory,
        )

    def _build_response(
        self,
        reply: str,
        source: str,
        product_cards: List[Dict[str, Any]],
        consumable_cards: List[Dict[str, Any]],
        suggested_chips: List[str],
        nlp_result: Dict[str, Any],
        state: ConversationState,
        latency_ms: int,
        subcategory: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Formats the standardized JSON response."""
        res_type = "product_list" if product_cards else ("no_exact_match" if "no_match" in source else "message")
        return {
            "type": res_type,
            "reply": reply,
            "message": reply,
            "result_count": len(product_cards),
            "subcategory": subcategory or state.subcategory,
            "cards": product_cards,
            "product_cards": product_cards,
            "consumable_cards": consumable_cards,
            "suggested_chips": suggested_chips,
            "source": source,
            "nlp": nlp_result,
            "grounding": {"status": "verified_catalogue_source"},
            "state": state,
            "latency_ms": latency_ms,
        }


orchestrator = Orchestrator()
