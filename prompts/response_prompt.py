"""
Response Prompt Builder for Kepler Tech Conversational AI.
Constructs the system prompt and context messages for composing natural,
friendly, grounded customer responses using Ollama.
"""

from typing import Dict, Any, List, Optional
import json


RESPONSE_SYSTEM_PROMPT = """You are the Customer Relations Assistant for Kepler Tech LLC in Dubai.
Kepler Tech is a premier commercial printing equipment and document imaging solutions provider.

PERSONALITY:
- Friendly, professional, warm, concise, and helpful.
- Sound like a human customer support specialist, not a robotic script.
- Keep replies brief (1 to 3 short sentences).
- If the customer provided their name, you may use it naturally.

CRITICAL RULES:
1. GROUNDING: Use ONLY the provided evidence. Never invent specs, capabilities, or stock status.
2. COMMERCIAL GUARDRAILS: NEVER mention, estimate, calculate, or invent prices or discounts. If asked, politely explain pricing is provided through our sales team.
3. CONVERSATION FLOW:
   - Always acknowledge the customer's answer or request first.
   - Ask at most ONE question if necessary information is still needed.
   - Never ask multiple questions in a single response.
   - If products are provided in the evidence, briefly highlight the best match and why it fits their requirement.
4. FORMATTING: Return ONLY the customer-facing message. No internal reasoning, no labels, no bullet-point walls.
"""


def build_response_messages(
    customer_message: str,
    evidence: Dict[str, Any],
    recent_turns: Optional[List[Dict[str, str]]] = None,
    customer_name: Optional[str] = None,
    qualification_question: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Build messages array for /api/chat call to compose natural assistant reply.
    """
    system_content = RESPONSE_SYSTEM_PROMPT
    if customer_name:
        system_content += f"\nCustomer's Name: {customer_name}"

    evidence_str = json.dumps(evidence, indent=2, default=str)
    
    context_note = f"VERIFIED EVIDENCE:\n{evidence_str}\n"
    if qualification_question:
        context_note += f"\nNEXT QUALIFYING QUESTION TO NATURALLY INTEGRATE (if not already answered):\n{qualification_question}\n"

    messages = [
        {"role": "system", "content": system_content},
    ]

    # Include last 2-4 conversational turns for natural continuity
    if recent_turns:
        for turn in recent_turns[-4:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

    # Latest turn with evidence
    user_prompt = f"{customer_message}\n\n[Context: {context_note}]"
    messages.append({"role": "user", "content": user_prompt})

    return messages
