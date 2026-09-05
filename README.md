# Customer Relations Assistant — Conversational AI

A conversational AI assistant built for **natural customer discovery, requirement gathering, and product consultation**, strictly enforcing customer relations personality rules and commercial boundaries.

---

## Key Features

1. **Strict Commercial Rules & Guardrails**:
   - Zero price generation, estimation, or negotiation.
   - Guaranteed adherence to standard refusal:
     > *"I can help you find the right option based on your requirements, but pricing isn’t available through this chat."*
   - Zero discount promises or concessions:
     > *"Discount information isn’t available through this chat, but I can help you choose the most suitable option."*
   - Never inquires about customer budget or offers human handover.
2. **Ollama Integration**:
   - Connects to `http://localhost:11434/api/generate` with model `gpt-oss:20b` (or any custom pulled model).
   - Seamless rule-based fallback simulator if Ollama service is booting or offline.
3. **Dynamic Company Context**:
   - Easily modify Company Name, Business Type, Location, Working Hours, Products & Services, and verified specs on-the-fly directly in the UI drawer.
4. **Single-Question Conversational Flow**:
   - Follows the defined stages: First Message, Discovery, Comparison, Troubleshooting, Unavailable Info, and Ending.
   - Maximum 1 question per response.

---

## Quick Start

### 1. Run the Application
```bash
python run.py
```
The server will start at: **http://localhost:5050**

### 2. Test via Web Interface
Open `http://localhost:5050` in your web browser:
- Try the quick-test buttons to verify price and discount refusals.
- Open the **Settings** drawer to customize company info or Ollama endpoint/model.

### 3. Test via cURL / API
Send a query directly to the chat API:
```bash
curl -X POST http://localhost:5050/api/chat -H "Content-Type: application/json" -d '{
  "message": "I need a printer for CAD drawings.",
  "model": "gpt-oss:20b"
}'
```

Test the price guardrail:
```bash
curl -X POST http://localhost:5050/api/chat -H "Content-Type: application/json" -d '{
  "message": "How much does the A1 plotter cost?"
}'
```
Response:
```json
{
  "reply": "I can help you find the right option based on your requirements, but pricing isn’t available through this chat.",
  "source": "guardrail_rule",
  "success": true
}
```

---

## Ollama Direct Testing

To test Ollama directly as provided in your prompt:
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "gpt-oss:20b",
  "prompt": "Your question here",
  "stream": false
}'
```
