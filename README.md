# Kepler Tech — SalesAI Conversational Assistant

> **AI-Powered Sales & CRM Bot for Kepler Tech LLC** — Dubai's #1 Printer, Inkjet Media & Consumables Supplier.

---

## Changelog

### v3.0 — 09 Sep 2026 *(Current)*

**Conversation Architecture**
- Rebuilt the chatbot flow using a structured **9-step conversational state system** with full session persistence and optimistic concurrency control.
- Implemented a **single canonical orchestrator pipeline** (`agent/orchestrator.py`) replacing all legacy duplicated logic.
- Separated concerns into dedicated route handlers: Product Discovery, Consumables, Qualification, Comparison, Guardrail, and Help.

**AI Memory & Multi-Turn State**
- Added persistent **conversation state** via `domain/state_store.py` — thread-safe in-memory store with 2-hour TTL, LRU eviction, and pluggable **Redis backend**.
- State tracks: intent, sales stage, active product, selected requirements, history turns, and clarification queue — survives topic switches and mid-conversation corrections.
- Added **HMAC-signed session tokens** for tamper-proof session identity.

**Qualification Flow**
- Enforced **one-question-at-a-time** discipline with priority-ranked requirement collection (`conversation/next_question_engine.py`).
- Fixed multi-turn loops caused by un-cleared `awaiting_field` — system now correctly advances after each extracted requirement.
- Added yes/no resolution to satisfy pending clarification fields without re-asking the same question.
- Handles topic switching mid-qualification without losing prior context.

**Zero-Hallucination Routing & Claim Validation**
- Upgraded `validation/claim_validator.py` with **8 verification layers**:
  - Print speed ↔ paper size pairing (speed-to-size rules per model)
  - Product weight vs. package weight disambiguation
  - URL slug verification (no invented product links)
  - DPI resolution cross-check against verified specs
  - Print speed validation against catalog evidence
  - Max-width inch validation against catalog evidence
  - Scanner capability — rejects scanner claims on print-only hardware
  - `sanitize()` method for safe inline claim reversion
- `validate_all()` now returns a structured `(is_valid, reason, violations[])` 3-tuple.

**Product Recommendation & Eligibility**
- Implemented strict eligibility gating (`recommendation/eligibility.py`): conflicting requirements (e.g., A0 size + integrated scanner) surface a grounded clarification instead of returning wrong cards.
- Boosted product keyword matching in `rag/retriever.py` with explicit confidence thresholds (exact ≥ 0.95 / product ≥ 0.35 / unknown < 0.20).
- Prevented paper media and software items from appearing in hardware product cards.

**Security & Production Hardening**
- **SSRF protection**: client-supplied `ollama_base_url` is silently ignored; Ollama URL is bound exclusively to `OLLAMA_BASE_URL` env var.
- **Model allowlist**: unknown model names rejected with HTTP 400.
- **CORS**: restricted to configured origins (`CORS_ORIGINS` env var).
- **Payload limit**: configurable `MAX_REQUEST_BYTES` (default 64 KB) enforced at Flask level.
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy` on all responses.
- **Health probes**: `/health/live` (liveness) and `/health/ready` (readiness — verifies catalog + Ollama).
- **ProxyFix** middleware for Cloudflare Tunnel / reverse-proxy deployments.
- `.env.example` template with all configurable variables documented.

**Chatbot Widget & Landing Page**
- Built a responsive **floating chatbot widget** with modal-based full-screen mode.
- Kepler-branded demo landing page (`/`) with product category quick pills.
- `/chat` and `/chat-full` routes for embedded and standalone widget modes.

**Catalog Verification**
- Audited and verified **833 catalog items** with live product links, SKU badges, and authentic product images.
- Verified price data (`data/verified_prices.json`), product descriptions (`data/verified_descriptions.json`), and brochure links (`data/verified_brochures.json`).
- `catalog/product_spec_engine.py` for deterministic attribute-specific answers (speed, width, ink, scanner, full specs).

**Testing — 100% Pass Rate**
- **45 regression & orchestration tests** passing across 6 test suites:
  - `test_app.py` — API endpoint and guardrail tests
  - `test_consumables.py` — consumable matching and card output
  - `test_nlp.py` — NLP normalization and intent extraction
  - `test_rag.py` — RAG retrieval and confidence gating
  - `tests/test_claim_validator.py` — 7 zero-hallucination claim tests
  - `tests/test_architecture_single_orchestrator.py` — canonical orchestrator and state manager integrity
  - `tests/test_security_hardening.py` — SSRF, allowlist, headers, health endpoints
  - `tests/test_retrieval_and_eligibility.py` — RAG corpus join and strict eligibility
  - `.github/workflows/ci.yml` — GitHub Actions CI on Python 3.11 & 3.12

---

## Quick Start

### 1. Configure environment
```bash
cp .env.example .env
# Edit .env — set SECRET_KEY and confirm OLLAMA_BASE_URL
```

### 2. Run the server
```bash
python run.py
```
Server starts at **http://localhost:5055**

### 3. Open the chat widget
Visit `http://localhost:5055` — click the floating chat button or go to `/chat` for the full-screen interface.

### 4. API — Chat endpoint
```bash
curl -X POST http://localhost:5055/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a CAD plotter for A1 drawings.", "session_id": "demo-001"}'
```

### 5. Health check
```bash
curl http://localhost:5055/health/live   # {"status": "alive"}
curl http://localhost:5055/health/ready  # {"status": "ready", "catalog_count": 833, "ollama_ok": true}
```

---

## Architecture

```
app.py  ──▶  agent/orchestrator.py  ──▶  agent/decision_engine.py
                     │                          │
             routes/product_route.py     rag/retriever.py
             routes/qualification_route.py    ↕
             routes/consumables_route.py  catalog/repository.py
             routes/comparison_route.py
             routes/help_and_guardrail_route.py
                     │
             validation/claim_validator.py  (zero-hallucination)
             domain/state_store.py          (HMAC session state)
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5055` | Flask server port |
| `SECRET_KEY` | *(must set)* | HMAC session signing key |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:32b` | Default LLM model |
| `ALLOWED_MODELS` | *(see .env.example)* | Comma-separated model allowlist |
| `CORS_ORIGINS` | `localhost:5055` | Comma-separated allowed origins |
| `MAX_REQUEST_BYTES` | `65536` | Max POST body size (bytes) |
| `REDIS_URL` | *(optional)* | Redis URL for persistent state |

See [`.env.example`](.env.example) for full reference.

---

## Running Tests

```bash
# Unit tests
python -m unittest discover -s tests -p "test_*.py"

# Integration tests (requires running server + Ollama)
python test_app.py
python test_consumables.py
python test_nlp.py
python test_rag.py
```

---

## Contact

**Kepler Tech LLC** — Dubai, UAE
- 📧 sales@keplertech.ae
- 📞 +971 4 323 1008 | +971 55 835 8586
- 🌐 [www.keplertechllc.com](https://www.keplertechllc.com)
