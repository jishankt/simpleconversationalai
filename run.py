"""
Launch script for Customer Relations Conversational AI.
"""

import sys
from app import app
from config import PORT, OLLAMA_BASE_URL, DEFAULT_MODEL

if __name__ == "__main__":
    print("=" * 65)
    print("  Customer Relations Assistant — Conversational AI")
    print(f"  Running locally at: http://localhost:{PORT}")
    print(f"  Connected to Ollama: {OLLAMA_BASE_URL} (model: {DEFAULT_MODEL})")
    print("=" * 65)
    app.run(host="0.0.0.0", port=PORT, debug=False)
