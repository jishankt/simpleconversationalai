"""
Flask Application for Conversational AI Customer Relations Assistant.
Connects with Ollama (gpt-oss:20b), runs NLP normalization, intent extraction,
enforces strict commercial guardrails, and guarantees zero-hallucination grounding.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import uuid
import logging
from config import PORT, DEBUG, DEFAULT_COMPANY_CONTEXT, DEFAULT_MODEL, OLLAMA_BASE_URL
from prompts import build_system_prompt, format_generate_prompt, format_evidence_grounded_prompt
from guardrails import check_user_intent_for_pricing_or_discount, validate_and_sanitize_response, PRICE_REFUSAL, DISCOUNT_REFUSAL
from ollama_client import OllamaClient
from nlp.intent_extractor import analyze_input, INTENT_PRICE, INTENT_DISCOUNT
from nlp.grounding_validator import validate_grounding
from nlp.discovery_engine import is_broad_query, get_discovery_question
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
    ACT_CONFIRMING,
    ACT_REJECTING,
    ACT_GENERAL_DISCOVERY
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("conversational_ai")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Session store: session_id -> list of {"role": "user"|"assistant", "content": str}
SESSIONS = {}
# Canonical State store: session_id -> CanonicalState
STATE_STORE = {}

ollama_client = OllamaClient(base_url=OLLAMA_BASE_URL, default_model=DEFAULT_MODEL)


@app.route("/")
def index():
    """Serves the static store landing page with floating chatbot widget icon."""
    return render_template("landing.html")


@app.route("/chat-widget")
def chat_widget():
    """Serves the embedded chat widget interface for the modal."""
    return render_template("index.html")


@app.route("/chat-full")
def chat_full():
    """Serves the standalone full-screen chat interface."""
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    """Returns current default company context and model configuration."""
    return jsonify({
        "company_context": DEFAULT_COMPANY_CONTEXT,
        "default_model": DEFAULT_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL
    })


@app.route("/api/health", methods=["GET"])
def health_check():
    """Returns status of Ollama connection and installed models."""
    health_data = ollama_client.check_health()
    return jsonify(health_data)


@app.route("/api/reset", methods=["POST"])
def reset_session():
    """Resets conversation history and canonical state for a given session."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if session_id:
        if session_id in SESSIONS:
            del SESSIONS[session_id]
        if session_id in STATE_STORE:
            del STATE_STORE[session_id]
        logger.info(f"Session {session_id} reset successfully.")
    return jsonify({"success": True, "message": "Session reset."})


from rag.retriever import rag_retriever
from rag.comparison_engine import detect_comparison_request, generate_comparison_response
from rag.consumables_engine import consumables_engine

req_updater = RequirementUpdater(consumables_engine=consumables_engine)
next_question_engine = NextQuestionEngine()


@app.route("/api/consumables", methods=["GET"])
def get_consumables():
    """Returns compatible inks, maintenance tanks, and media for a given printer."""
    printer_name = request.args.get("printer", "").strip()
    c_type = request.args.get("type", "all").strip()
    if not printer_name:
        return jsonify({"consumables": []})
    consumables = consumables_engine.get_printer_consumables(printer_name, consumable_filter=c_type, limit=6)
    return jsonify({
        "success": True,
        "printer": printer_name,
        "consumables": consumables
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Main conversational endpoint:
    - Normalizes user text and extracts NLP entities & intent
    - Fast-paths commercial rules (price/discount refusal)
    - Performs RAG retrieval over scraped product corpus
    - Handles product comparison (Section D) or deep specifications
    - Attaches rich hardware cards and compatible consumable cards from 833-item catalog
    - Calls Ollama /api/generate with RAG context
    - Validates zero-hallucinations against verified knowledge base
    - Returns sanitized reply, interactive suggestion chips, product cards, and retrieved RAG sources
    """
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' field"}), 400

    raw_message = data["message"].strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    company_context = data.get("company_context") or DEFAULT_COMPANY_CONTEXT
    model_name = data.get("model") or DEFAULT_MODEL
    ollama_url = data.get("ollama_base_url") or OLLAMA_BASE_URL

    # 1. NLP Analysis: Normalization, Intent Classification, Entity Extraction
    nlp_result = analyze_input(raw_message)
    normalized_msg = nlp_result["normalized_text"]
    detected_intent = nlp_result["intent"]

    # Update client target if client supplied custom base URL
    if ollama_url != ollama_client.base_url:
        ollama_client.base_url = ollama_url.rstrip("/")

    # Initialize session history and canonical state
    if session_id not in SESSIONS:
        SESSIONS[session_id] = []
    history = SESSIONS[session_id]

    if session_id not in STATE_STORE:
        STATE_STORE[session_id] = CanonicalState(session_id=session_id)
    state = STATE_STORE[session_id]

    logger.info(f"[{session_id[:8]}] Customer: '{raw_message}' -> Normalized: '{normalized_msg}' | Intent: {detected_intent}")

    # 2. Strict Commercial Rule Intercept
    fast_refusal = check_user_intent_for_pricing_or_discount(raw_message)
    if not fast_refusal and (detected_intent == INTENT_PRICE):
        fast_refusal = PRICE_REFUSAL
    elif not fast_refusal and (detected_intent == INTENT_DISCOUNT):
        fast_refusal = DISCOUNT_REFUSAL

    retrieved_items = []
    product_cards = []
    consumable_cards = []
    suggested_chips = nlp_result.get("suggested_chips", [])
    assistant_reply = ""
    source = ""

    if fast_refusal:
        assistant_reply = fast_refusal
        source = "guardrail_rule"
        grounding_result = {
            "is_grounded": True,
            "status": "GUARDRAIL_INTERCEPT",
            "notes": ["Strict commercial boundary enforced (price/discount refusal)."]
        }
    else:
        # 3. Dialogue Act Classification
        act_info = classify_dialogue_act(
            text=raw_message,
            awaiting_field=state.awaiting_field,
            current_category=state.category,
            active_product=state.active_product
        )
        act = act_info.get("act")
        act_params = act_info.get("params", {})
        logger.info(f"[{session_id[:8]}] Dialogue Act: {act} | Params: {act_params} | Current Awaiting: {state.awaiting_field}")

        low_msg = normalized_msg.lower()

        # Category initialization or switching
        if act == ACT_CHANGING_TOPIC and act_params.get("target_category"):
            state.reset_category(act_params["target_category"])
        elif not state.category:
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

        # 4. Requirement Updater
        state = req_updater.update_state(state, act_info, raw_message)

        # Check for model keys or history for consumables
        last_assistant_msg = ""
        for turn in reversed(history):
            if turn.get("role") == "assistant":
                last_assistant_msg = turn.get("content", "").lower()
                break
        was_asking_for_consumables = any(k in last_assistant_msg for k in ["need consumables for", "printer or scanner model", "cartridge size are you looking for", "which printer model do you have"])
        identified_key = consumables_engine.identify_printer_key(normalized_msg)

        # 5. Route by Dialogue Act
        if act == ACT_ASKING_CONSUMABLES:
            target_p = None
            model_code = act_params.get("model_code")
            if model_code:
                consumable_cards = consumables_engine.get_printer_consumables(model_code, limit=6)
                if consumable_cards:
                    assistant_reply = f"Here are the genuine compatible inks and consumables for {model_code}:"
                    source = "consumables_engine"
                    grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Verified compatible consumables."]}

            if not consumable_cards:
                if act_params.get("item_ref") is not None and 0 <= act_params["item_ref"] < len(state.candidate_products):
                    target_p = state.candidate_products[act_params["item_ref"]]
                elif state.active_product:
                    target_p = state.active_product
                elif state.candidate_products:
                    target_p = state.candidate_products[0]

                if target_p:
                    consumable_cards = consumables_engine.get_printer_consumables(target_p.get("name") or target_p.get("sku"), limit=6)
                    model_name = target_p.get("name", "this printer")
                    assistant_reply = f"Here are the genuine compatible inks and consumables for {model_name}:"
                    source = "consumables_engine"
                    grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Verified compatible consumables."]}
                else:
                    consumable_cards = consumables_engine.get_printer_consumables(normalized_msg, limit=6)
                    if consumable_cards:
                        assistant_reply = f"Here are the genuine compatible inks and consumables for {normalized_msg.upper()}:"
                        source = "consumables_engine"
                        grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Verified compatible consumables."]}

        elif act == ACT_ASKING_PRODUCT_QUESTION:
            target_p = None
            if act_params.get("item_ref") is not None and 0 <= act_params["item_ref"] < len(state.candidate_products):
                target_p = state.candidate_products[act_params["item_ref"]]
                state.active_product = target_p
            elif state.active_product:
                target_p = state.active_product
            elif state.candidate_products:
                target_p = state.candidate_products[0]
                state.active_product = target_p

            if target_p:
                ev_prompt = format_evidence_grounded_prompt(
                    selected_product=target_p,
                    customer_requirement=state.requirements,
                    user_query=raw_message,
                    dialogue_act="asking_product_question"
                )
                gen_result = ollama_client.generate(prompt=ev_prompt, model=model_name)
                raw_response = gen_result.get("response", "")
                source = gen_result.get("source", "ollama")
                sanitized = validate_and_sanitize_response(raw_response, normalized_msg)
                grounding_result = validate_grounding(sanitized, normalized_msg, nlp_result)
                assistant_reply = grounding_result["sanitized_response"]
                product_cards = state.candidate_products[:4] if state.candidate_products else [target_p]

        elif act == ACT_ASKING_COMPARISON:
            if "which is better" in raw_message.lower() and state.active_product:
                ev_prompt = format_evidence_grounded_prompt(
                    selected_product=state.active_product,
                    customer_requirement=state.requirements,
                    user_query=raw_message,
                    dialogue_act="which_is_better_for_me"
                )
                gen_result = ollama_client.generate(prompt=ev_prompt, model=model_name)
                raw_response = gen_result.get("response", "")
                source = gen_result.get("source", "ollama")
                sanitized = validate_and_sanitize_response(raw_response, normalized_msg)
                grounding_result = validate_grounding(sanitized, normalized_msg, nlp_result)
                assistant_reply = grounding_result["sanitized_response"]
                product_cards = state.candidate_products[:4]
            elif len(state.candidate_products) >= 2:
                comp_res = generate_comparison_response(state.candidate_products[0], state.candidate_products[1], raw_message)
                assistant_reply = comp_res["text"]
                source = "rag_comparison_engine"
                grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Section D comparison."]}
                product_cards = state.candidate_products[:2]

        elif act == ACT_CHANGING_REQUIREMENT:
            if state.candidate_products and len(state.candidate_products) > 1:
                if state.active_product:
                    product_cards = [state.active_product]
                    assistant_reply = f"Here is another option that matches your requirements: {state.active_product.get('name')}."
                    source = "state_candidate_rotator"
                    grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Alternative candidate."]}

        elif act == ACT_REFERENCING_ITEM:
            if state.active_product:
                product_cards = [state.active_product]
                assistant_reply = f"Here are the details for the {state.active_product.get('name')}:"
                source = "consumables_engine"
                grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Direct item reference."]}

        elif act == ACT_GREETING:
            assistant_reply = "Hello! Welcome to Kepler Tech LLC. How can I assist you with your printing solutions or consumable needs today?"
            suggested_chips = ["Printers", "Scanners", "Consumables"]
            source = "greeting_engine"
            grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Greeting response."]}

        elif act == ACT_ENDING:
            assistant_reply = "Thank you for contacting Kepler Tech LLC! Please let us know if you need any further assistance with your printing equipment or media."
            source = "ending_engine"
            grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Conversation conclusion."]}

        elif act in (ACT_ANSWERING_QUESTION, ACT_CORRECTING_ANSWER, ACT_CHANGING_TOPIC, "recommend_now") or state.category:
            if act == "recommend_now":
                next_step = None
            else:
                next_step = next_question_engine.evaluate_next_step(state)

            if next_step:
                assistant_reply = next_step["question"]
                suggested_chips = next_step.get("pills", [])
                source = "next_question_engine"
                grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Consultative qualification active."]}
                product_cards = []
                consumable_cards = []
            else:
                candidates = consumables_engine.rank_candidates_from_state(state, limit=4)
                state.candidate_products = candidates
                if candidates:
                    state.active_product = candidates[0]
                    product_cards = candidates
                    cat_label = "printers"
                    if state.category == "technical_cad":
                        cat_label = "Epson Technical & CAD plotters"
                    elif state.category == "photo_booth":
                        cat_label = "Citizen compact dye-sub photo printers"
                    elif state.category == "photo_fine_art":
                        cat_label = "Epson SureColor Fine Art & Photo printers"
                    elif state.category == "scanner":
                        st = state.requirements.get("scanner_type")
                        if st == "document_sheetfed":
                            cat_label = "Epson high-speed network & duplex document scanners"
                        elif st == "flatbed_a3":
                            cat_label = "Epson A3 large-format flatbed scanners"
                        elif st == "business":
                            cat_label = "Epson compact desktop & portable business scanners"
                        else:
                            cat_label = "Epson document and flatbed scanners"
                    elif state.category == "consumable":
                        cat_label = "genuine consumables"

                    req_summary = []
                    if "print_size" in state.requirements:
                        req_summary.append(str(state.requirements['print_size']))
                    if "scan_required" in state.requirements:
                        req_summary.append("integrated scanner" if state.requirements['scan_required'] else "print-only")
                    if "daily_volume" in state.requirements:
                        req_summary.append(f"~{state.requirements['daily_volume']} prints/day")

                    summary_str = f" ({', '.join(req_summary)})" if req_summary else ""
                    assistant_reply = f"Based on your requirements{summary_str}, here are our recommended {cat_label}:"
                    source = "state_retrieval_engine"
                    grounding_result = {"is_grounded": True, "status": "VERIFIED_GROUNDED", "notes": ["Ranked from canonical state."]}

        # Fallback RAG if no response was formulated
        if not assistant_reply:
            retrieved_items = rag_retriever.retrieve(normalized_msg, nlp_context=nlp_result, top_k=3)
            rag_context_str = rag_retriever.format_prompt_context(retrieved_items)
            system_prompt = build_system_prompt(company_context)
            full_prompt = format_generate_prompt(system_prompt, history, normalized_msg, nlp_context=nlp_result, rag_context=rag_context_str)
            gen_result = ollama_client.generate(prompt=full_prompt, model=model_name)
            raw_response = gen_result.get("response", "")
            source = gen_result.get("source", "ollama")
            sanitized = validate_and_sanitize_response(raw_response, normalized_msg)
            grounding_result = validate_grounding(sanitized, normalized_msg, nlp_result)
            assistant_reply = grounding_result["sanitized_response"]

    # Save state and history turns
    state.history_turns.append({"role": "user", "content": normalized_msg})
    state.history_turns.append({"role": "assistant", "content": assistant_reply})
    STATE_STORE[session_id] = state

    history.append({"role": "user", "content": normalized_msg})
    history.append({"role": "assistant", "content": assistant_reply})

    logger.info(f"[{session_id[:8]}] Assistant ({source} | Grounding: {grounding_result['status']}): {assistant_reply}")

    # Format retrieved sources for frontend UI inspection
    sources_summary = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "score": r.get("similarity_score", 0),
            "width": r.get("width") or r.get("print_sizes") or r.get("speed", ""),
            "ink": r.get("ink_technology") or r.get("technology", ""),
            "url": r.get("source_url", "https://www.keplertechllc.com/")
        }
        for r in retrieved_items
    ]

    return jsonify({
        "success": True,
        "session_id": session_id,
        "reply": assistant_reply,
        "source": source,
        "suggested_chips": suggested_chips,
        "retrieved_sources": sources_summary,
        "product_cards": product_cards,
        "consumable_cards": consumable_cards,
        "canonical_state": state.to_dict(),
        "nlp": {
            "raw_input": raw_message,
            "normalized_input": normalized_msg,
            "corrections": nlp_result["corrections"],
            "intent": detected_intent,
            "brands": nlp_result["brands"],
            "categories": nlp_result["categories"],
            "models": nlp_result["models"],
            "sizes": nlp_result["sizes"]
        },
        "grounding": {
            "is_grounded": grounding_result["is_grounded"],
            "status": grounding_result["status"],
            "notes": grounding_result.get("notes", [])
        },
        "turns_count": len(history) // 2
    })


if __name__ == "__main__":
    logger.info(f"Starting Customer Relations Assistant on http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
