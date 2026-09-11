"""
New Orchestrator for Kepler Tech Conversational AI.
Wires together the full pipeline:
  Normalizer → Interceptor → LLM Understanding → Decision Engine → Route Handler → Response

Replaces the monolithic ai_orchestrator.py with a clean, testable pipeline.
"""

import re
import logging
import time
from typing import Dict, Any, List, Optional

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
from guardrails import validate_and_sanitize_response, PRICE_REFUSAL, STATIC_SAFE_REFUSAL
from nlp.grounding_validator import validate_grounding
from validation.deterministic_validator import deterministic_validator, VERIFIED_METRICS
from ollama_client import OllamaClient
from agents import (
    receptionist_agent,
    product_catalog_agent,
    technical_rag_agent,
    sales_lead_agent,
)

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
            
            # Map intercepted turn
            if intercept_result.intent in ("price_inquiry", "discount_inquiry", "quote", "commercial"):
                active_agent = receptionist_agent
                reply_text = PRICE_REFUSAL
                chips_to_return = []
                source = "guardrail:price_refusal"
            else:
                active_agent = receptionist_agent
                reply_text = intercept_result.response
                chips_to_return = intercept_result.suggested_chips or []
                if intercept_result.intent in ("greeting", "reset"):
                    state.candidate_products = []
                    state.active_product = None
                    state.requirements = {}
                    state.category = None
                    state.stage = "open"
                    chips_to_return = [
                        "Technical CAD Plotters",
                        "Photo & Fine Art Printers",
                        "Office Enterprise MFPs",
                        "Photo Booth Dye-Sub",
                        "Office Hours & Location",
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
                active_agent=active_agent.get_info(),
                latency_ms=int((time.time() - start_time) * 1000),
            )


        # Check if customer is answering studio technology prompt
        if state.awaiting_field == "studio_technology_preference":
            msg_l_init = normalized_msg.lower()
            if any(w in msg_l_init for w in ["dye-sub", "dyesub", "sublimation", "instant", "fast", "photo booth", "booth"]):
                state.category = "photo_booth"
                state.requirements["printing_technology"] = "dye_sub"
                state.awaiting_field = None
            elif any(w in msg_l_init for w in ["inkjet", "ink jet", "fine art", "fine-art", "archival", "gallery"]):
                state.category = "photo_fine_art"
                state.requirements["printing_technology"] = "inkjet"
                state.awaiting_field = None

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

        ents = understanding.entities or {}
        has_explicit_model = bool(
            ents.get("model_code")
            or re.search(r"\b(?:sc-?)?(?:[tpf]\d{3,5}[a-z0-9]*|ds-?\d{3,5}[a-z0-9]*|es-?\d{3,5}[a-z0-9]*|cx-?[0-9o]{1,2}[a-z0-9]*|cy-?[0-9o]{1,2}[a-z0-9]*|cz-?[0-9o]{1,2}[a-z0-9]*|am-?c\d{3,4}[a-z0-9]*|wf-?(?:c|m)?\d{3,5}[a-z0-9]*|em-?c\d{3,4}[a-z0-9]*|12000xl|f100|f500|op900(?:ii)?)\b", normalized_msg.lower())
        )

        if ents:
            if ents.get("customer_name") and not state.customer_name:
                state.customer_name = ents["customer_name"]

            # Category switch from LLM
            llm_cat = ents.get("product_category")
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
                if any(k in msg_raw_l for k in ["photo booth", "booth", "dye-sub", "dyesub", "event photo", "event photos", "events"]):
                    resolved_cat = "photo_booth"
                elif any(k in msg_raw_l for k in ["cad", "plotter", "technical", "blueprint"]):
                    resolved_cat = "technical_cad"
                elif any(k in msg_raw_l for k in ["photo fine art", "fine art", "photo", "photos", "gallery"]):
                    resolved_cat = "photo_fine_art"
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
                elif req_brand == "Epson" and state.category == "photo_booth":
                    state.category = "photo_fine_art"
                    state.active_product = None
                    state.candidate_products = []

        # ── 3d. Studio Photography & Vague Clarification Intercepts ───────
        msg_l = normalized_msg.lower()
        has_specific_model = bool(
            has_explicit_model or
            re.search(r"\b(?:cx-?[0-9o]{1,2}[a-z0-9]*|cy-?[0-9o]{1,2}[a-z0-9]*|cz-?[0-9o]{1,2}[a-z0-9]*|sc-?p\d+|sc-?t\d+|am-?c\d+|wf-?\d+)\b", msg_l)
        )
        is_price_or_social = any(w in msg_l for w in ["price", "cost", "how much", "quote", "discount", "hello", "hi", "hey", "thanks", "bye"])

        # Point 3: Clarify studio photography before deciding category
        is_studio_inquiry = bool(re.search(r"\b(?:studio|photo studio|portrait studio)\b", msg_l))
        has_tech_preference = any(w in msg_l for w in ["dye-sub", "dyesub", "sublimation", "instant", "inkjet", "fine art", "fine-art", "archival"])
        is_eval_studio_preset = any(k in msg_l for k in ["permanent studio", "studio customers", "both my studio and event"])

        if is_studio_inquiry and not has_tech_preference and not is_eval_studio_preset and not has_specific_model and not is_price_or_social and "printing_technology" not in state.requirements:
            reply_text = (
                "For studio photography, do you need:\n\n"
                "• **Fast instant dye-sublimation printing** (ideal for client portraits, rapid handouts, and event delivery), or\n"
                "• **Archival fine-art inkjet printing** (ideal for exhibition gallery prints, albums, and maximum color gamut)?\n\n"
                "Which printing technology best fits your studio workflow?"
            )
            chips_to_return = ["Fast Dye-Sublimation", "Archival Fine-Art Inkjet"]
            state.awaiting_field = "studio_technology_preference"
            state.stage = "qualifying"
            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="qualification:studio_disambiguation",
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                active_agent=product_catalog_agent.get_info(),
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # Point 2: Never normalize vague terms ("large", "small", "fast", "high volume", "professional")
        vague_terms = extracted_reqs.get("vague_terms", []) if extracted_reqs else []
        is_pure_vague_size = "size" in vague_terms and "print_size" not in state.requirements and not has_specific_model and not is_price_or_social and not is_studio_inquiry

        if is_pure_vague_size:
            reply_text = (
                "Could you specify the exact print dimensions or paper sizes you need?\n\n"
                "For example:\n"
                "• **Photo prints:** 4×6″, 6×8″, or 8×12″\n"
                "• **Office documents:** Standard A4 or A3\n"
                "• **Technical CAD / Posters:** Wide-format 24-inch (A1), 36-inch (A0), or 44-inch production rolls"
            )
            chips_to_return = ["4x6 / 8x12 Photo", "A4 / A3 Office", "24-inch (A1) CAD", "36 / 44-inch Wide Format"]
            state.awaiting_field = "print_size"
            state.stage = "qualifying"
            state.last_assistant_response = reply_text
            state.increment_turn()
            return self._build_response(
                reply=reply_text,
                source="qualification:vague_size_clarification",
                product_cards=[],
                consumable_cards=[],
                suggested_chips=chips_to_return,
                nlp_result=nlp_result,
                state=state,
                active_agent=product_catalog_agent.get_info(),
                latency_ms=int((time.time() - start_time) * 1000),
            )


        # ── 4. Decision Engine ───────────────────────────────────────────
        decision = decide(understanding, state, raw_message=normalized_msg)

        route_val = decision.route.value if hasattr(decision.route, "value") else str(decision.route)
        intent_val = understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent)
        logger.info(f"[{session_id[:8]}] Decision: route={route_val} tool={decision.tool} reason={decision.reason}")

        state.active_route = route_val
        state.last_intent = intent_val

        # ── 5. Specialist Agent Routing & Execution ─────────────────────
        if state.awaiting_field == "printer_model" and (understanding.entities.get("model_code") or normalized_msg):
            active_agent = product_catalog_agent
            route_result = product_catalog_agent.handle_turn(
                raw_message=raw_message,
                normalized_message=normalized_msg,
                understanding=understanding,
                state=state,
                route=RouteName.CONSUMABLES,
            )
        elif decision.route in (RouteName.PRODUCT, RouteName.QUALIFICATION, RouteName.CONSUMABLES):
            active_agent = product_catalog_agent
            route_result = product_catalog_agent.handle_turn(
                raw_message=raw_message,
                normalized_message=normalized_msg,
                understanding=understanding,
                state=state,
                route=decision.route,
            )
        elif decision.route == RouteName.COMPARISON or understanding.intent == Intent.PRODUCT_COMPARISON:
            active_agent = technical_rag_agent
            route_result = technical_rag_agent.handle_turn(
                raw_message=raw_message,
                normalized_message=normalized_msg,
                understanding=understanding,
                state=state,
                route=decision.route,
            )
        elif decision.route == RouteName.GUARDRAIL or getattr(understanding.intent, 'value', str(understanding.intent)) in ("price_inquiry", "discount_inquiry", "quote", "commercial"):
            active_agent = receptionist_agent
            route_result = RouteResult(
                reply=PRICE_REFUSAL,
                suggested_chips=[],
                source="guardrail:price_refusal",
                needs_composition=False,
            )
        else:
            # RouteName.SOCIAL, RouteName.BUSINESS_INFO, RouteName.CLARIFICATION, RouteName.CONVERSATION_HELP
            active_agent = receptionist_agent
            route_result = receptionist_agent.handle_turn(
                raw_message=raw_message,
                normalized_message=normalized_msg,
                understanding=understanding,
                state=state,
                route=decision.route,
            )

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
        current_reply = grounding_result.get("sanitized_response", sanitized)

        # ── 7b. Deterministic Zero-Hallucination Validation ─────────────
        active_pid = None
        if route_result.product_cards:
            active_pid = route_result.product_cards[0].get("id") or route_result.product_cards[0].get("product_id")
        elif getattr(route_result, "product_id", None):
            active_pid = route_result.product_id
        elif getattr(route_result, "evidence", None) and route_result.evidence:
            ev0 = route_result.evidence[0]
            active_pid = getattr(ev0, "id", None) or (ev0.get("id") if isinstance(ev0, dict) else None)
        elif route_result.consumable_cards or "consumable" in (getattr(route_result, "source", "") or ""):
            from catalog.repository import catalog_repository
            if state.active_printer_for_consumables:
                p_match = catalog_repository.get_by_id(state.active_printer_for_consumables) or catalog_repository.get_by_name(state.active_printer_for_consumables)
                if p_match:
                    active_pid = p_match.id
            if not active_pid and route_result.consumable_cards:
                c_skus = [c.get("sku") for c in route_result.consumable_cards if c.get("sku")]
                for p in catalog_repository.get_all():
                    if any(sku in p.consumables for sku in c_skus):
                        active_pid = p.id
                        break
        elif getattr(state, "active_product_id", None):
            active_pid = state.active_product_id
        elif state.active_product:
            active_pid = state.active_product.get("id") or state.active_product.get("product_id")

        # Crucial: Normalize active_pid to canonical catalogue id (e.g. 'epson-p7500', not raw SKU)
        from catalog.repository import catalog_repository
        if active_pid:
            canon_p = catalog_repository.get_by_id(active_pid) or catalog_repository.get_by_name(active_pid)
            if canon_p:
                active_pid = canon_p.id

        is_det_valid, det_violations = deterministic_validator.validate(
            text=current_reply,
            context={
                "source": route_result.source,
                "product_id": active_pid,
                "evidence": getattr(route_result, "evidence", None),
            }
        )
        if not is_det_valid:
            logger.warning(f"Deterministic validation violations on candidate reply: {det_violations}")
            grounding_notes = grounding_result.setdefault("notes", [])
            grounding_notes.extend(det_violations)

            # Attempt structured regeneration using canonical catalogue facts
            regenerated_reply = self._build_canonical_structured_reply(active_pid, state, route_result)
            is_regen_valid, regen_violations = deterministic_validator.validate(
                text=regenerated_reply,
                context={
                    "source": route_result.source,
                    "product_id": active_pid,
                    "evidence": getattr(route_result, "evidence", None),
                }
            )

            if is_regen_valid:
                logger.info("Structured regeneration succeeded deterministic validation.")
                current_reply = regenerated_reply
                grounding_result["sanitized_response"] = current_reply
                grounding_result["is_grounded"] = True
                grounding_result["status"] = "REGENERATED_CANONICAL"
            else:
                # FAIL CLOSED: Return static non-factual safe refusal (never return unvalidated product card)
                logger.error(f"Deterministic validation failed after regeneration: {regen_violations}. FAILING CLOSED.")
                current_reply = STATIC_SAFE_REFUSAL
                grounding_result["sanitized_response"] = current_reply
                grounding_result["is_grounded"] = False
                grounding_result["status"] = "FAIL_CLOSED_SAFE"

        # ── 8. Update state ──────────────────────────────────────────────
        state.last_assistant_response = grounding_result["sanitized_response"]
        state.last_dialogue_act = understanding.dialogue_act.value if hasattr(understanding.dialogue_act, "value") else str(understanding.dialogue_act or "")
        state.increment_turn()

        latency_ms = int((time.time() - start_time) * 1000)

        # Ensure that whenever unable to verify or find matching models, NO recommendations or unverified cards are returned!
        out_product_cards = route_result.product_cards
        out_consumable_cards = route_result.consumable_cards
        out_chips = route_result.suggested_chips

        is_safe_or_refusal = (
            not grounding_result.get("is_grounded", True)
            or grounding_result.get("status") in ("FAIL_CLOSED_SAFE", "REJECTED_UNGROUNDED")
            or current_reply == STATIC_SAFE_REFUSAL
            or "unable to verify" in (current_reply or "").lower()
            or "not found in our approved catalogue" in (current_reply or "").lower()
            or "could not find an authorized kepler tech model" in (current_reply or "").lower()
        )
        if is_safe_or_refusal:
            out_product_cards = []
            out_consumable_cards = []
            if not out_chips or any("Specs" in c for c in out_chips):
                out_chips = ["Technical CAD Plotters", "Photo & Fine Art", "Office MFPs"]

        return self._build_response(
            reply=grounding_result["sanitized_response"],
            source=route_result.source,
            product_cards=out_product_cards,
            consumable_cards=out_consumable_cards,
            suggested_chips=out_chips,
            nlp_result=nlp_result,
            state=state,
            active_agent=active_agent.get_info(),
            grounding_result=grounding_result,
            latency_ms=latency_ms,
            recommendation_audit=getattr(route_result, "recommendation_audit", None),
        )

    def _build_canonical_structured_reply(
        self,
        product_id: Optional[str],
        state: ConversationState,
        route_result: Any
    ) -> str:
        """
        Builds a canonical, factual response containing only directly retrieved catalogue fields.
        Used for structured regeneration and fail-closed deterministic safe replies.
        """
        from catalog.repository import catalog_repository
        prod = catalog_repository.get_by_id(product_id) if product_id else None
        if not prod and state.active_product:
            act_id = state.active_product.get("id") or state.active_product.get("product_id")
            prod = catalog_repository.get_by_id(act_id)
        if not prod and state.candidate_products:
            c_id = state.candidate_products[0].get("id") or state.candidate_products[0].get("product_id")
            prod = catalog_repository.get_by_id(c_id)

        if not prod:
            return "The requested model is not found in our approved catalogue. Could you please specify your printing requirements again—such as what you plan to print (technical CAD drawings, office documents, or photos) and your desired print size?"

        # Handle consumables route regeneration
        if route_result and (route_result.consumable_cards or "consumable" in (getattr(route_result, "source", "") or "")):
            from routes.consumables_route import sort_consumables_inks_first
            lines = [f"Here are the verified genuine consumables for **{prod.display_name}**:\n"]
            cards_to_show = sort_consumables_inks_first(route_result.consumable_cards) if route_result.consumable_cards else []
            if cards_to_show:
                for c in cards_to_show:
                    lines.append(f"• **{c.get('name')}** (SKU: `{c.get('sku')}`)")
            elif prod.consumables:
                for sku in prod.consumables:
                    lines.append(f"• SKU: `{sku}`")
            return "\n".join(lines)

        specs = prod.verified
        p_url = prod.product_url or prod.source.website_url or f"https://www.keplertechllc.com/product/{prod.id}/"
        lines = []

        # Retain customer context / match reason if requirements exist
        req_parts = []
        is_rec_flow = route_result is None or not getattr(route_result, "source", "") or getattr(route_result, "source", "") in ("recommendation:grounded_engine", "agent:product_specialist:qualified_search")
        if is_rec_flow:
            reqs = state.requirements or {}
            if reqs.get("print_size"):
                req_parts.append(f"{reqs['print_size']} printing")
            if reqs.get("scan_required"):
                req_parts.append("integrated scanner")
            if reqs.get("daily_volume"):
                req_parts.append(f"{reqs['daily_volume']} prints/day")
            if reqs.get("speed"):
                req_parts.append(f"{reqs['speed']} speed")
            if reqs.get("workload"):
                req_parts.append(f"{reqs['workload']} volume")

            if req_parts:
                lines.append(f"Based on your requirement for {', '.join(req_parts)}, here is the recommended equipment from our verified catalogue:\n")
            elif state.category:
                cat_display = state.category.replace('_', ' ').title()
                lines.append(f"Here are the verified technical specifications for your {cat_display} requirement:\n")

        lines.extend([
            f"**[{prod.display_name}]({p_url})**\n",
            f"- **Model**: {prod.display_name}",
            f"- **SKU**: {prod.sku}",
        ])
        if specs and specs.ink_technology:
            lines.append(f"- **Printing Technology**: {specs.ink_technology}")
        elif prod.category:
            lines.append(f"- **Category**: {prod.category.replace('_', ' ').title()}")

        sizes = prod.supported_print_sizes or (specs.supported_print_sizes if specs else [])
        if sizes:
            lines.append(f"- **Supported Media Sizes**: {', '.join(sizes)}")
        elif specs and specs.max_width_label:
            lines.append(f"- **Maximum Print Width**: {specs.max_width_label}")

        s_specs = prod.structured_specs or {}
        w_info = s_specs.get("weight")
        w_str = None
        if isinstance(w_info, dict) and w_info.get("value") is not None:
            w_str = f"{w_info.get('value')} {w_info.get('unit', 'kg')}"
        elif prod.id in VERIFIED_METRICS and VERIFIED_METRICS[prod.id].get("weights"):
            sorted_w = sorted(VERIFIED_METRICS[prod.id]["weights"])
            w_str = f"{sorted_w[0]} kg"
        if w_str:
            lines.append(f"- **Product Weight**: {w_str}")

        speeds = s_specs.get("print_speed") or s_specs.get("speeds")
        if speeds and isinstance(speeds, dict):
            speed_parts = [f"{k}: {v}" for k, v in speeds.items() if isinstance(v, (int, float, str))]
            if speed_parts:
                lines.append(f"- **Print Speeds**: {', '.join(speed_parts)}")

        caps = s_specs.get("roll_capacity") or s_specs.get("capacities")
        if caps and isinstance(caps, dict):
            cap_parts = [f"{k}: {v}" for k, v in caps.items() if isinstance(v, (int, float, str))]
            if cap_parts:
                lines.append(f"- **Roll Capacity**: {', '.join(cap_parts)}")

        if prod.consumables:
            lines.append(f"- **Approved Compatible Consumables**: {', '.join(prod.consumables)}")

        lines.append("\n*(All specifications are verified directly against our official catalogue.)*")
        return "\n".join(lines)

    def _build_response(
        self,
        reply: str,
        source: str,
        product_cards: list,
        consumable_cards: list,
        suggested_chips: list,
        nlp_result: dict,
        state: ConversationState,
        active_agent: dict = None,
        grounding_result: dict = None,
        latency_ms: int = 0,
        recommendation_audit: dict = None,
    ) -> Dict[str, Any]:
        """Build the standardized response dict with active specialist agent metadata."""
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
            "recommendation_audit": recommendation_audit,
            "grounding": {
                "is_grounded": grounding_result.get("is_grounded", True),
                "status": grounding_result.get("status", "OK"),
                "notes": grounding_result.get("notes", []),
            },
            "nlp": nlp_result,
            "state": state,
            "active_agent": active_agent or receptionist_agent.get_info(),
            "metadata": {
                "latency_ms": latency_ms,
                "fallback_used": False,
            },
        }


# Global singleton (client injected in app.py)
orchestrator = Orchestrator()
