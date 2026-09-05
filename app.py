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
from prompts import build_system_prompt, format_generate_prompt
from guardrails import check_user_intent_for_pricing_or_discount, validate_and_sanitize_response, PRICE_REFUSAL, DISCOUNT_REFUSAL
from ollama_client import OllamaClient
from nlp.intent_extractor import analyze_input, INTENT_PRICE, INTENT_DISCOUNT
from nlp.grounding_validator import validate_grounding
from nlp.discovery_engine import is_broad_query, get_discovery_question

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("conversational_ai")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Session store: session_id -> list of {"role": "user"|"assistant", "content": str}
SESSIONS = {}

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
    """Resets conversation history for a given session."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if session_id and session_id in SESSIONS:
        del SESSIONS[session_id]
        logger.info(f"Session {session_id} reset successfully.")
    return jsonify({"success": True, "message": "Session reset."})


from rag.retriever import rag_retriever
from rag.comparison_engine import detect_comparison_request, generate_comparison_response
from rag.consumables_engine import consumables_engine


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

    # Initialize session history
    if session_id not in SESSIONS:
        SESSIONS[session_id] = []

    history = SESSIONS[session_id]

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

    if fast_refusal:
        assistant_reply = fast_refusal
        source = "guardrail_rule"
        grounding_result = {
            "is_grounded": True,
            "status": "GUARDRAIL_INTERCEPT",
            "notes": ["Strict commercial boundary enforced (price/discount refusal)."]
        }
    else:
        # Check for Consultative Broad Category Discovery (salesai flow)
        is_broad, broad_cat = is_broad_query(normalized_msg)
        if is_broad and broad_cat:
            assistant_reply = get_discovery_question(broad_cat)
            source = "consultative_discovery"
            grounding_result = {
                "is_grounded": True,
                "status": "VERIFIED_GROUNDED",
                "notes": ["Consultative category qualification active."]
            }
        else:
            # 3. RAG Retrieval over Scraped Product Corpus
            retrieved_items = rag_retriever.retrieve(normalized_msg, nlp_context=nlp_result, top_k=3)
            rag_context_str = rag_retriever.format_prompt_context(retrieved_items)

            # 4. Strict Intent-Based Card Delivery Flow (Give ONLY what was asked)
            lower_msg = normalized_msg.lower()

            # Check conversation history to see if assistant just asked for the consumables product model
            last_assistant_msg = ""
            for turn in reversed(history):
                if turn.get("role") == "assistant":
                    last_assistant_msg = turn.get("content", "").lower()
                    break

            was_asking_for_consumables = any(k in last_assistant_msg for k in ["need consumables for", "printer or scanner model", "cartridge size are you looking for", "which printer model do you have"])
            
            # Check if this query mentions a known printer model or is responding to consumables question
            identified_key = consumables_engine.identify_printer_key(normalized_msg)
            is_consumable_query = any(k in lower_msg for k in ["ink", "cartridge", "cartridges", "consumable", "consumables", "ribbon", "ribbons", "maintenance box", "waste box", "tank", "tanks"]) or (was_asking_for_consumables and identified_key is not None)
            is_scanner_query = any(k in lower_msg for k in ["scanner", "scanners", "flatbed", "document scanner"]) and not is_consumable_query
            is_media_query = any(k in lower_msg for k in ["paper", "media", "canvas", "roll", "rolls", "rag", "luster", "cotton"]) and not is_consumable_query

            assistant_reply = ""
            source = ""

            if is_consumable_query:
                # User asked explicitly for inks/consumables or answered which product model they have
                printer_key = identified_key or consumables_engine.identify_printer_key(normalized_msg)
                if printer_key:
                    consumable_cards = consumables_engine.get_printer_consumables(normalized_msg, limit=6)
                else:
                    consumable_cards = consumables_engine.get_printer_consumables(normalized_msg, limit=6)
                    if not consumable_cards:
                        consumable_cards = [c for c in consumables_engine.products if any(t in c.get('name', '').lower() for t in lower_msg.split()) and c.get('category') in ('Ink Cartridge', 'Maintenance Box')][:6]
                        consumable_cards = [consumables_engine._format_card(c, card_type="consumable") for c in consumable_cards]
                product_cards = []
                if consumable_cards:
                    model_display = (printer_key or normalized_msg).upper()
                    assistant_reply = f"Here are the genuine compatible inks and consumables for {model_display}:"
                    source = "consumables_engine"
            elif is_scanner_query:
                product_cards = consumables_engine.find_matching_scanners(normalized_msg, limit=4)
                consumable_cards = []
                if product_cards:
                    assistant_reply = "Here are our recommended Epson high-speed document and flatbed scanners:"
                    source = "consumables_engine"
            elif is_media_query:
                consumable_cards = consumables_engine.find_matching_media(normalized_msg, limit=4)
                product_cards = []
                if consumable_cards:
                    assistant_reply = "Here are our recommended genuine Innova fine art and Korejet media rolls:"
                    source = "consumables_engine"
            else:
                # Default / printer hardware request -> return strictly matching printer hardware cards
                product_cards = consumables_engine.find_matching_hardware(normalized_msg, limit=4)
                consumable_cards = []
                if product_cards and any(k in lower_msg for k in ["cad", "technical", "photo booth", "fine art", "office", "enterprise", "t3100", "t5100", "p900", "p700", "cx-02", "printer", "printers", "plotter"]):
                    cat_name = "printers"
                    if "cad" in lower_msg or "technical" in lower_msg:
                        cat_name = "Epson Technical & CAD plotters"
                    elif "fine art" in lower_msg or "photo" in lower_msg:
                        cat_name = "Epson SureColor Fine Art & Photo printers"
                    elif "office" in lower_msg or "enterprise" in lower_msg:
                        cat_name = "Epson WorkForce Enterprise office MFPs"
                    elif "photo booth" in lower_msg:
                        cat_name = "Citizen compact dye-sub photo printers"
                    assistant_reply = f"Here are our recommended {cat_name}:"
                    source = "consumables_engine"

            if not assistant_reply:
                # 5. Check for Dedicated Section D Product Comparison Request
                comparison_info = detect_comparison_request(normalized_msg, nlp_result)
                if comparison_info["is_comparison"] and len(comparison_info["models"]) >= 2:
                    comp_res = generate_comparison_response(comparison_info["models"][0], comparison_info["models"][1], normalized_msg)
                    raw_response = comp_res["text"]
                    source = "rag_comparison_engine"
                else:
                    # 6. Build system prompt with factual grounding & RAG context
                    system_prompt = build_system_prompt(company_context)
                    full_prompt = format_generate_prompt(system_prompt, history, normalized_msg, nlp_context=nlp_result, rag_context=rag_context_str)

                    # Call Ollama generate
                    gen_result = ollama_client.generate(prompt=full_prompt, model=model_name)
                    raw_response = gen_result.get("response", "")
                    source = gen_result.get("source", "ollama")

                # 7. Commercial sanitizer
                sanitized = validate_and_sanitize_response(raw_response, normalized_msg)

                # 8. Zero-Hallucination Grounding Validator
                grounding_result = validate_grounding(sanitized, normalized_msg, nlp_result)
                assistant_reply = grounding_result["sanitized_response"]
            else:
                grounding_result = {
                    "is_grounded": True,
                    "status": "VERIFIED_GROUNDED",
                    "notes": ["Verified catalog match."]
                }

    # Save turns to session history
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
        "suggested_chips": nlp_result["suggested_chips"],
        "retrieved_sources": sources_summary,
        "product_cards": product_cards,
        "consumable_cards": consumable_cards,
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
