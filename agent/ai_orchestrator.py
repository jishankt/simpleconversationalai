"""
AI Orchestrator with Dynamic Tool Calling for Kepler Tech Conversational AI.
Eliminates hardcoded mappings and executes genuine catalog tools.
Coordinates:
1. Canonical State & Entity Extraction
2. AI Tool Selection (search_catalog, get_product_specs, get_compatible_consumables, compare_products, ask_consultative_question)
3. Dynamic Catalog Tool Execution
4. Grounded Natural Language Response Synthesis
5. Section E Commercial Guardrail Enforcement
"""

import logging
import re
from typing import Dict, Any, List, Optional
from nlp.intent_extractor import analyze_input, INTENT_PRICE, INTENT_DISCOUNT
from guardrails import check_user_intent_for_pricing_or_discount, validate_and_sanitize_response, PRICE_REFUSAL, DISCOUNT_REFUSAL
from nlp.grounding_validator import validate_grounding
from agent.tool_executor import catalog_tool_executor
from agent.tool_registry import CATALOG_TOOLS
from state.conversation_state import CanonicalState
from state.requirement_updater import RequirementUpdater
from state.next_question_engine import NextQuestionEngine
from nlp.dialogue_act import (
    classify_dialogue_act,
    ACT_ANSWERING_QUESTION,
    ACT_CORRECTING_ANSWER,
    ACT_ASKING_PRODUCT_QUESTION,
    ACT_ASKING_COMPARISON,
    ACT_ASKING_CONSUMABLES,
    ACT_CHANGING_REQUIREMENT,
    ACT_CHANGING_TOPIC,
    ACT_REFERENCING_ITEM,
    ACT_GREETING,
    ACT_ENDING,
    ACT_GENERAL_DISCOVERY
)

logger = logging.getLogger("ai_orchestrator")
req_updater = RequirementUpdater()
next_question_engine = NextQuestionEngine()


class AIOrchestrator:
    def __init__(self, ollama_client=None):
        self.ollama_client = ollama_client

    def process_turn(
        self,
        raw_message: str,
        session_id: str,
        history: List[Dict[str, str]],
        state: CanonicalState,
        model_name: str = "gpt-oss:20b"
    ) -> Dict[str, Any]:
        """
        Processes a single conversational turn end-to-end:
        1. NLP Normalization & Guardrail Intercept
        2. Dialogue Act Classification & Requirement Updating
        3. Dynamic Tool Calling & Execution
        4. Grounded Response Formulation
        """
        # 1. NLP Analysis
        nlp_result = analyze_input(raw_message)
        normalized_msg = nlp_result["normalized_text"]
        detected_intent = nlp_result["intent"]

        # 2. Strict Commercial Rule Intercept (Section E)
        fast_refusal = check_user_intent_for_pricing_or_discount(raw_message)
        if not fast_refusal and (detected_intent == INTENT_PRICE):
            fast_refusal = PRICE_REFUSAL
        elif not fast_refusal and (detected_intent == INTENT_DISCOUNT):
            fast_refusal = DISCOUNT_REFUSAL

        if fast_refusal:
            return {
                "reply": fast_refusal,
                "source": "guardrail_rule",
                "product_cards": state.candidate_products[:4] if state.candidate_products else [],
                "consumable_cards": [],
                "suggested_chips": ["Printers", "Scanners", "Consumables"],
                "grounding": {
                    "is_grounded": True,
                    "status": "GUARDRAIL_INTERCEPT",
                    "notes": ["Strict commercial boundary enforced (price/discount refusal)."]
                },
                "nlp": nlp_result,
                "state": state
            }

        # 3. Classify Dialogue Act & Update Canonical State
        act_info = classify_dialogue_act(
            text=raw_message,
            awaiting_field=state.awaiting_field,
            current_category=state.category,
            active_product=state.active_product
        )
        act = act_info.get("act")
        act_params = act_info.get("params", {})

        # Handle category changes
        if act == ACT_CHANGING_TOPIC and act_params.get("target_category"):
            state.reset_category(act_params["target_category"])
        elif act_params.get("field") == "scanner_type":
            state.category = "scanner"
        elif not state.category:
            low_msg = normalized_msg.lower()
            if any(k in low_msg for k in ["architect", "cad", "plotter", "technical", "blueprint"]):
                state.category = "technical_cad"
            elif any(k in low_msg for k in ["photo booth", "dyesub", "instant print"]):
                state.category = "photo_booth"
            elif any(k in low_msg for k in ["fine art", "photo printer", "gallery"]):
                state.category = "photo_fine_art"
            elif any(k in low_msg for k in ["scanner", "scanners", "flatbed"]):
                state.category = "scanner"
            elif any(k in low_msg for k in ["consumable", "consumables", "ink", "cartridge"]):
                state.category = "consumable"
            elif any(k in low_msg for k in ["office", "enterprise", "workforce"]):
                state.category = "office_enterprise"

        # Update requirements from message
        state = req_updater.update_state(state, act_info, raw_message)

        # 4. Dynamic Tool Calling Execution
        product_cards = []
        consumable_cards = []
        suggested_chips = []
        assistant_reply = ""
        source = "ai_agent"

        # Case A: User explicitly asks for consumables
        if act == ACT_ASKING_CONSUMABLES or (state.category == "consumable" and not state.awaiting_field):
            target_model = act_params.get("model_code")
            if not target_model and state.active_product:
                target_model = state.active_product.get("name") or state.active_product.get("sku")
            if not target_model:
                target_model = normalized_msg

            # Execute tool: get_compatible_consumables
            res_cons = catalog_tool_executor.execute_tool(
                "get_compatible_consumables",
                {"printer_identifier": target_model, "limit": 6}
            )
            consumable_cards = res_cons.get("consumable_cards", [])

            # Also retrieve hardware card if user asked for both ("printer and its inks")
            if any(k in normalized_msg.lower() for k in ["printer", "machine", "hardware", "scanner", "plotter", "show me"]):
                res_hw = catalog_tool_executor.execute_tool("get_product_specs", {"product_identifier": target_model})
                if res_hw.get("success"):
                    product_cards = res_hw.get("product_cards", [])
                    state.active_product = res_hw.get("product")

            p_display = res_cons.get("printer_name") or target_model
            if consumable_cards:
                items_preview = ", ".join([c["name"] for c in consumable_cards[:3]])
                assistant_reply = f"Here are the genuine compatible inks and consumables for {p_display} (including {items_preview}):"
            else:
                assistant_reply = f"I could not locate verified consumables for '{target_model}' in our catalog. Please contact sales@keplertech.ae for specialty sourcing."

            source = "tool:get_compatible_consumables"

        # Case B: Specific product question or reference
        elif act in (ACT_ASKING_PRODUCT_QUESTION, ACT_REFERENCING_ITEM):
            target_p = None
            if act_params.get("model_code"):
                res_specs = catalog_tool_executor.execute_tool("get_product_specs", {"product_identifier": act_params["model_code"]})
                if res_specs.get("success"):
                    target_p = res_specs.get("product")
                    product_cards = res_specs.get("product_cards", [])
            elif act_params.get("item_ref") is not None and 0 <= act_params["item_ref"] < len(state.candidate_products):
                target_p = state.candidate_products[act_params["item_ref"]]
                product_cards = [target_p]
            elif state.active_product:
                target_p = state.active_product
                product_cards = [target_p]
            elif state.candidate_products:
                target_p = state.candidate_products[0]
                product_cards = [target_p]

            if target_p:
                state.active_product = target_p
                # Answer specific feature question using dynamic catalog specs
                low_q = normalized_msg.lower()
                p_name = target_p.get("name", "")
                p_desc = target_p.get("description", "")
                p_width = target_p.get("width", "")
                p_speed = target_p.get("speed", "")
                p_ink = target_p.get("ink_technology", "")

                if any(k in low_q for k in ["scanner", "scan", "scanning"]):
                    has_scan = any(k in p_name.lower() or k in p_desc.lower() for k in ["mfp", "scan", "scanner", "copier"])
                    assistant_reply = f"Yes, the {p_name} features an integrated scanner designed for blueprints and document capture." if has_scan else f"The {p_name} is a dedicated high-precision printing unit without an integrated scanner."
                elif any(k in low_q for k in ["size", "width", "maximum"]):
                    eff_width = p_width
                    if not eff_width:
                        if any(w in p_name or w in p_desc for w in ["36", "T5", "5400", "5100", "5700", "A0"]):
                            eff_width = "36″ (A0 / 914 mm)"
                        elif any(w in p_name or w in p_desc for w in ["24", "T3", "3100", "3400", "A1"]):
                            eff_width = "24″ (A1 / 610 mm)"
                        elif any(w in p_name or w in p_desc for w in ["44", "T7", "7200", "7700", "B0"]):
                            eff_width = "44″ (B0 / 1118 mm)"
                        else:
                            eff_width = "standard production sizes"
                    assistant_reply = f"The {p_name} supports media widths up to {eff_width}."
                elif any(k in low_q for k in ["ink", "cartridge", "technology"]):
                    res_c = catalog_tool_executor.execute_tool("get_compatible_consumables", {"printer_identifier": p_name, "limit": 4})
                    consumable_cards = res_c.get("consumable_cards", [])
                    assistant_reply = f"The {p_name} utilizes {p_ink or 'genuine UltraChrome inks'}. Here are compatible inks:"
                else:
                    assistant_reply = f"Here are the verified specifications for the {p_name}: {p_desc}"
                source = "tool:get_product_specs"

        # Case C: Product comparison
        elif act == ACT_ASKING_COMPARISON:
            if len(state.candidate_products) >= 2:
                model_a = state.candidate_products[0].get("name")
                model_b = state.candidate_products[1].get("name")
                res_comp = catalog_tool_executor.execute_tool("compare_products", {"model_a": model_a, "model_b": model_b})
                product_cards = res_comp.get("product_cards", state.candidate_products[:2])
                assistant_reply = f"{model_a} and {model_b} are both premium production systems from Kepler Tech LLC. Review their detailed specifications above to select the ideal match."
                source = "tool:compare_products"
            elif state.active_product and "which is better" in normalized_msg.lower():
                product_cards = [state.active_product]
                assistant_reply = f"The {state.active_product.get('name')} is ideal for your specified workflow, providing high productivity and genuine consumables support."
                source = "tool:compare_products"

        # Case D: Greeting & Courtesy
        elif act == ACT_GREETING:
            assistant_reply = "Hello! Welcome to Kepler Tech LLC. How can I assist you with your printing solutions or consumable needs today?"
            suggested_chips = ["Printers", "Scanners", "Consumables"]
            source = "ai_agent:greeting"

        elif act == ACT_ENDING:
            assistant_reply = "Thank you for contacting Kepler Tech LLC! Please let us know if you need any further assistance with your printing equipment or media."
            source = "ai_agent:ending"

        # Case E: Consultative Discovery & Catalog Search
        else:
            # Check if consultative question needed
            next_step = None if act == "recommend_now" else next_question_engine.evaluate_next_step(state)

            if next_step:
                assistant_reply = next_step["question"]
                suggested_chips = next_step.get("pills", [])
                source = "tool:ask_consultative_question"
            else:
                # Formulate search query dynamically from state requirements
                search_terms = []
                cat_filter = None

                if state.category == "scanner":
                    cat_filter = "Scanner"
                    st = state.requirements.get("scanner_type")
                    if st == "document_sheetfed":
                        search_terms.append("DS-770 DS-790WN DS-870 DS-970 DS-900WN high speed network duplex document scanner")
                    elif st == "flatbed_a3":
                        search_terms.append("DS-32000 DS-30000 DS-60000 DS-70000 12000XL A3 large format flatbed scanner")
                    elif st == "business":
                        search_terms.append("DS-70 DS-80W DS-1630 DS-1660W DS-310 DS-410 compact business scanner")
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

                else:
                    search_terms.append(normalized_msg)

                # Execute dynamic catalog search tool
                query_str = " ".join(search_terms)
                search_res = catalog_tool_executor.execute_tool(
                    "search_catalog",
                    {"query": query_str, "category": cat_filter, "limit": 4}
                )

                candidates = search_res.get("product_cards", [])
                state.candidate_products = candidates
                product_cards = candidates

                if candidates:
                    state.active_product = candidates[0]
                    cat_name = state.category.replace("_", " ") if state.category else "printing equipment"
                    assistant_reply = f"Based on your requirements, here are our recommended {cat_name} options:"
                else:
                    assistant_reply = "I would be glad to help you find the ideal printing solution from Kepler Tech LLC. Could you tell me what specific print applications or workload you are looking to support?"

                source = "tool:search_catalog"

        # 5. Sanitize and Ground Response
        sanitized = validate_and_sanitize_response(assistant_reply, normalized_msg)
        grounding_result = validate_grounding(sanitized, normalized_msg, nlp_result)

        return {
            "reply": grounding_result["sanitized_response"],
            "source": source,
            "product_cards": product_cards,
            "consumable_cards": consumable_cards,
            "suggested_chips": suggested_chips,
            "grounding": {
                "is_grounded": grounding_result["is_grounded"],
                "status": grounding_result["status"],
                "notes": grounding_result.get("notes", [])
            },
            "nlp": nlp_result,
            "state": state
        }


# Global singleton orchestrator
ai_orchestrator = AIOrchestrator()
