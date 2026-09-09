# Changelog — SalesAI (Kepler Tech AI Sales & CRM Bot)

---

## [09-09-2026] — Routing, Multi-Turn State & Security Hardening

### Routing & Decision Engine
- **10-Tier Priority System** — Refactored `agent/decision_engine.py` with strict routing order:
  Price intercept → Social → Business Info → Process/Help → Product → Comparison → Consumable → Discovery → Qualification → Clarification
- **Price & Discount Intercept** — Price queries are now caught at Tier 1, before any product logic, eliminating incorrect product card returns on pricing questions
- **Added `routes/help_and_guardrail_route.py`** — Dedicated route handling greetings, farewells, company info, and commercial guardrails

### Multi-Turn Conversation State
- **Category Switch Wipes Stale State** — Switching from CAD → Photo Booth (or any category switch) now clears previous requirements and candidate products immediately, preventing cross-category contamination
- **Pronoun Binding to Active Product** — "it", "this", "that printer" in consumables and product queries now correctly resolve to `active_product` instead of hallucinated model codes
- **Correction Flow** — Mid-conversation corrections (e.g. "actually A1 not A0", "no scanner") correctly update the requirement state and re-qualify without looping

### Photo Booth Category Support
- **New category: `photo_booth`** — Added to `conversation/requirement_schema.py` with its own critical/important qualification fields
- **Question Engine** — `conversation/next_question_engine.py` updated with photo booth qualification questions (print size, portability, volume)
- **Eligibility** — `recommendation/eligibility.py` updated so Citizen CX-02 / CY-02 correctly match photo booth requirements

### Security Hardening
- **`config.py`** — Added `SECRET_KEY`, `ALLOWED_MODELS`, `CORS_ORIGINS`, `MAX_REQUEST_BYTES`
- **`app.py`** — Added SSRF protection (model allowlist blocks unknown model injection), request size guard (returns 413 on oversized body), and security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`)
- **`.env.example`** — Full environment variable template for portable deployment

### Architecture Tests
- **`test_architecture_single_orchestrator.py`** — New test file verifying:
  - Security config fields exist (`SECRET_KEY`, `ALLOWED_MODELS`, etc.)
  - Security headers on every response
  - SSRF / model-allowlist guard
  - Oversized request rejection (413)
  - `agent/orchestrator.py` is the primary routing path (not `ai_orchestrator`)

### Testing
- **All 4 Multi-Turn Suites Pass 100%**:
  - Suite 1: Full CAD qualification + consumables + comparison + price guardrail
  - Suite 2: Correction flow (A0 → A1, scanner → no scanner)
  - Suite 3: Pronoun & item referencing (it/this/that)
  - Suite 4: Clean topic switching (CAD → Photo Booth)
- **LLM Upgraded** — Default model changed from `qwen2.5:0.5b` → `qwen2.5:32b` for significantly improved NLP quality

### Documentation
- **`README.md`** — Full 7-step setup guide for new machines, environment variable reference, model comparison table, API endpoint reference
- **`.env.example`** — All 16 configurable environment variables with defaults

---

## [03-09-2026] — Initial SalesAI Architecture

### Conversation Architecture
- Rebuilt the chatbot flow using a structured 9-step conversational state system

### AI Memory
- Added persistent conversation state to track intent, sales stage, selected products, and buying requirements

### Qualification Flow
- Improved discovery to ask strictly one relevant question at a time

### Specialized Nodes
- Separated product search, consumables, pricing, checkout, qualification, and support into dedicated flows

### Frustration Handling
- Added automatic detection and de-escalation with human manager handover options

### Chatbot Widget
- Built a responsive floating chatbot widget and Kepler-branded demo landing page

### Catalog Verification
- Audited and verified 833 catalog items with live product links

### Testing
- Achieved 100% pass rate across all 45 regression and orchestration tests
