# Kepler Tech – Conversational AI Sales Assistant

A Flask-based conversational AI assistant for Kepler Tech LLC, powered by a local Ollama LLM.
It handles product discovery, qualification, grounded recommendations, consumable lookup, and commercial guardrails — all without hallucination.

---

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| Ollama | Latest (https://ollama.com) |
| LLM model | `qwen2.5:32b` (recommended) |

---

## Setup on a New Computer

### Step 1 — Install Ollama

Download and install Ollama for your OS from https://ollama.com/download

Then pull the required model:

```bash
ollama pull qwen2.5:32b
```

> **Lighter alternatives** (if 32B is too large for your machine):
> ```bash
> ollama pull qwen2.5:14b    # ~9 GB RAM
> ollama pull qwen2.5:0.5b   # ~0.5 GB RAM (fast but less accurate)
> ```

---

### Step 2 — Clone the Repository

```bash
git clone https://github.com/jishankt/simpleconversationalai.git
cd simpleconversationalai
```

---

### Step 3 — Create a Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 4 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 5 — Configure Environment Variables

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` and set at minimum:

```env
OLLAMA_MODEL=qwen2.5:32b        # or whichever model you pulled
SECRET_KEY=<your-random-string>  # generate with: python -c "import secrets; print(secrets.token_hex(32))"
```

---

### Step 6 — Start Ollama

Make sure Ollama is running before starting the app:

```bash
ollama serve
```

> On Windows, Ollama usually starts automatically after installation.  
> You can verify it's running by visiting: http://127.0.0.1:11434

---

### Step 7 — Run the Application

```bash
python run.py
```

The app will be available at: **http://localhost:5055**

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5055` | Flask server port |
| `DEBUG` | `False` | Enable Flask debug mode |
| `SECRET_KEY` | *(weak default)* | Flask session secret — **change in production** |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:32b` | Default LLM model |
| `ALLOWED_MODELS` | *(see .env.example)* | Allowlist of safe model names |
| `CORS_ORIGINS` | `http://localhost:5055` | Allowed CORS origins |
| `MAX_REQUEST_BYTES` | `65536` | Max POST body size (bytes) |
| `OLLAMA_TIMEOUT` | `60` | Request timeout in seconds |
| `OLLAMA_TEMPERATURE` | `0.0` | LLM temperature (0 = deterministic) |
| `OLLAMA_NUM_CTX` | `4096` | Context window size (tokens) |

---

## Available LLM Models (Pre-tested)

| Model | Size | Speed | Quality |
|---|---|---|---|
| `qwen2.5:32b` | ~20 GB | Slow | ⭐⭐⭐⭐⭐ Best |
| `qwen2.5:14b` | ~9 GB | Medium | ⭐⭐⭐⭐ |
| `qwen3:8b` | ~5 GB | Fast | ⭐⭐⭐ |
| `qwen2.5:0.5b` | ~0.5 GB | Very Fast | ⭐⭐ Minimal |

---

## Running Tests

```bash
# Core unit tests
python -m pytest test_app.py -v

# Multi-turn conversation suites
python test_multiturn_conversations.py

# Architecture & security tests
python -m pytest test_architecture_single_orchestrator.py -v

# All tests
python -m pytest test_app.py test_architecture_single_orchestrator.py test_nlp.py test_rag.py -v
```

---

## Project Structure

```
simpleconversationalai/
├── app.py                   # Flask application & API endpoints
├── run.py                   # Launch script
├── config.py                # All configuration & env vars
├── agent/
│   ├── orchestrator.py      # Primary routing orchestrator
│   ├── decision_engine.py   # 10-tier routing priority engine
│   └── ...
├── routes/
│   ├── qualification_route.py
│   ├── product_route.py
│   ├── consumables_route.py
│   └── help_and_guardrail_route.py
├── catalog/                 # Product catalog & spec engine
├── conversation/            # Requirement schema & question engine
├── rag/                     # Retrieval-augmented generation
├── templates/               # HTML UI templates
├── static/                  # CSS, JS, assets
├── .env.example             # Environment variable template
└── requirements.txt         # Python dependencies
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Landing page |
| `/chat` | GET | Chat widget UI |
| `/api/chat` | POST | Main conversation endpoint |
| `/api/health` | GET | Ollama connectivity check |
| `/api/config` | GET | Current model & company config |
| `/api/reset` | POST | Reset a session |
| `/api/consumables` | GET | Compatible consumables for a printer |
