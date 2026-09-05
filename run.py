"""
Launch script for Customer Relations Conversational AI.
"""

import sys
from app import app
from config import PORT

if __name__ == "__main__":
    print("=" * 65)
    print("  Customer Relations Assistant — Conversational AI")
    print(f"  Running locally at: http://localhost:{PORT}")
    print("  Connected to Ollama: http://127.0.0.1:11434 (model: gpt-oss:20b)")
    print("=" * 65)
    app.run(host="0.0.0.0", port=PORT, debug=False)
