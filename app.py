"""
Flask Application for Conversational AI Customer Relations Assistant.
Connects with Ollama (gpt-oss:20b), runs NLP normalization, intent extraction,
enforces strict commercial guardrails, and guarantees zero-hallucination grounding.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import uuid
import logging
from config import PORT, DEBUG, DEFAULT_COMPANY_CONTEXT, DEFAULT_MODEL, OLLAMA_BASE_URL, ALLOWED_MODELS, CORS_ORIGINS, MAX_REQUEST_BYTES
from prompts import build_system_prompt, format_generate_prompt, format_evidence_grounded_prompt
from guardrails import check_user_intent_for_pricing_or_discount, validate_and_sanitize_response, PRICE_REFUSAL, DISCOUNT_REFUSAL
from ollama_client import OllamaClient
from nlp.intent_extractor import analyze_input, INTENT_PRICE, INTENT_DISCOUNT
from nlp.grounding_validator import validate_grounding
from nlp.discovery_engine import is_broad_query, get_discovery_question
from state.conversation_state import CanonicalState
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
from agent.orchestrator import orchestrator as new_orchestrator
from rag.consumables_engine import consumables_engine
from agents import list_agent_metadata
from persistence import lead_repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("conversational_ai")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})

# Security: enforce maximum request payload size (1 MB)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

# Session store: session_id -> list of {"role": "user"|"assistant", "content": str}
SESSIONS = {}
# Canonical State store: session_id -> CanonicalState
STATE_STORE = {}

ollama_client = OllamaClient(base_url=OLLAMA_BASE_URL, default_model=DEFAULT_MODEL)

# Inject Ollama client into new orchestrator
new_orchestrator.ollama_client = ollama_client
new_orchestrator.llm_engine.client = ollama_client
new_orchestrator.response_composer.ollama_client = ollama_client


@app.after_request
def add_security_headers(response):
    """Attach standard security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.errorhandler(413)
def payload_too_large(e):
    return jsonify({"error": "Request payload too large (max 1 MB)"}), 413


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e)}), 400


@app.route("/")
def index():
    """Serves the static store landing page with floating chatbot widget icon."""
    return render_template("landing.html")


@app.route("/chat")
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


@app.route("/health/live", methods=["GET"])
def liveness():
    """Liveness probe — confirms the server process is alive."""
    return jsonify({"status": "alive", "service": "kepler-salesai"}), 200


@app.route("/health/ready", methods=["GET"])
def readiness():
    """Readiness probe — confirms catalog loaded and Ollama is reachable."""
    from catalog.repository import catalog_repository
    catalog_ok = len(catalog_repository.get_all()) > 0
    health_info = ollama_client.check_health()
    ollama_ok = bool(health_info.get("online") or health_info.get("model_available"))
    status = "ready" if (catalog_ok and ollama_ok) else "not_ready"
    return jsonify({
        "status": status,
        "catalog_count": len(catalog_repository.get_all()),
        "ollama_ok": ollama_ok
    }), 200


from persistence import state_repository


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
        state_repository.delete_session(session_id)
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
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing or invalid JSON body"}), 400

    # Security: Model allowlist enforcement — checked before message validation
    if data.get("model") and data["model"] not in ALLOWED_MODELS:
        return jsonify({"error": f"Model not allowed: '{data['model']}'. Permitted models: {ALLOWED_MODELS}"}), 400

    if "message" not in data:
        return jsonify({"error": "Missing 'message' field"}), 400

    raw_message = data["message"].strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    company_context = data.get("company_context") or DEFAULT_COMPANY_CONTEXT

    # Security: SSRF protection — ignore client-supplied ollama_base_url
    # Ollama endpoint is strictly controlled via server environment variables only
    model_name = data.get("model") or DEFAULT_MODEL

    # 1. NLP Analysis: Normalization, Intent Classification, Entity Extraction
    nlp_result = analyze_input(raw_message)
    normalized_msg = nlp_result["normalized_text"]
    detected_intent = nlp_result["intent"]

    # Initialize session history and canonical state (with SQLite persistence recovery)
    if session_id not in STATE_STORE or session_id not in SESSIONS:
        persisted = state_repository.get_session(session_id)
        if persisted:
            STATE_STORE[session_id], SESSIONS[session_id] = persisted
        else:
            if session_id not in SESSIONS:
                SESSIONS[session_id] = []
            if session_id not in STATE_STORE:
                STATE_STORE[session_id] = CanonicalState(session_id=session_id)

    history = SESSIONS[session_id]
    state = STATE_STORE[session_id]

    logger.info(f"[{session_id[:8]}] Customer: '{raw_message}' -> Normalized: '{normalized_msg}' | Intent: {detected_intent}")

    # Process conversational turn through new orchestrator pipeline
    orchestrator_res = new_orchestrator.process_turn(
        raw_message=raw_message,
        session_id=session_id,
        history=history,
        state=state,
        model_name=model_name
    )

    assistant_reply = orchestrator_res["reply"]
    source = orchestrator_res["source"]
    product_cards = orchestrator_res["product_cards"]
    consumable_cards = orchestrator_res["consumable_cards"]
    suggested_chips = orchestrator_res["suggested_chips"]
    grounding_result = orchestrator_res["grounding"]
    nlp_result = orchestrator_res["nlp"]
    state = orchestrator_res["state"]
    retrieved_items = orchestrator_res.get("retrieved_items", [])

    # Save state and history turns
    state.history_turns.append({"role": "user", "content": normalized_msg})
    state.history_turns.append({"role": "assistant", "content": assistant_reply})
    STATE_STORE[session_id] = state

    history.append({"role": "user", "content": normalized_msg})
    history.append({"role": "assistant", "content": assistant_reply})

    # Persist session to SQLite
    state_repository.save_session(session_id, state, history)

    logger.info(f"[{session_id[:8]}] Assistant ({source} | Grounding: {grounding_result['status']}): {assistant_reply}")

    # Format retrieved sources for frontend UI inspection
    sources_summary = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "score": r.get("similarity_score", 0),
            "width": r.get("width") or r.get("print_sizes") or r.get("speed", ""),
            "ink": r.get("ink_technology") or r.get("technology", ""),
            "url": r.get("url") or r.get("source_url") or r.get("website_url") or "https://www.keplertechllc.com/"
        }
        for r in retrieved_items
    ]

    active_agent = orchestrator_res.get("active_agent")

    return jsonify({
        "success": True,
        "session_id": session_id,
        "reply": assistant_reply,
        "message": assistant_reply,
        "type": orchestrator_res.get("type", "message"),
        "result_count": orchestrator_res.get("result_count", len(product_cards)),
        "subcategory": orchestrator_res.get("subcategory"),
        "cards": product_cards,
        "source": source,
        "active_agent": active_agent,
        "suggested_chips": suggested_chips,
        "retrieved_sources": sources_summary,
        "product_cards": product_cards,
        "consumable_cards": consumable_cards,
        "recommendation_audit": orchestrator_res.get("recommendation_audit"),
        "canonical_state": state.to_dict(),
        "nlp": {
            "raw_input": raw_message,
            "normalized_input": normalized_msg,
            "corrections": nlp_result.get("corrections", []),
            "intent": detected_intent,
            "brands": nlp_result.get("brands", []),
            "categories": nlp_result.get("categories", []),
            "models": nlp_result.get("models", []),
            "sizes": nlp_result.get("sizes", [])
        },
        "grounding": {
            "is_grounded": grounding_result.get("is_grounded", True),
            "status": grounding_result.get("status", "verified_catalogue_source"),
            "notes": grounding_result.get("notes", [])
        },
        "turns_count": len(history) // 2
    })


@app.route("/api/agents", methods=["GET"])
def get_agents():
    """Returns visual and operational metadata for all 4 specialized sub-agents."""
    return jsonify({
        "success": True,
        "agents": list_agent_metadata()
    })


@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Admin endpoint to inspect captured commercial sales leads."""
    limit = int(request.args.get("limit", 50))
    leads = lead_repository.get_leads(limit=limit)
    return jsonify({
        "success": True,
        "count": len(leads),
        "leads": leads
    })


if __name__ == "__main__":
    logger.info(f"Starting Customer Relations Assistant on http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
