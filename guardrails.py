"""
Commercial rules guardrail and response validator.
Ensures zero price leaks, zero budget queries, zero discount promises,
and strictly enforces standard refusal phrases.
"""

import re

# Exact refusal templates defined in the system prompt
PRICE_REFUSAL = "I can help you find the right option based on your requirements, but pricing isn’t available through this chat."
DISCOUNT_REFUSAL = "Discount information isn’t available through this chat, but I can help you choose the most suitable option."

# Intent detection regex patterns on user messages
PRICE_USER_PATTERNS = [
    r"\b(?:how much|price|pricing|cost|costs|rate|quotation|quote|charge|charges|fee|fees|expensive|cheap|affordable)\b",
    r"[$₹€£]\s*\d+",
    r"\b\d+\s*(?:dollars|bucks|rupees|inr|usd|eur|cents)\b",
    r"\bwhat is the price\b",
    r"\bwhat does it cost\b",
]

DISCOUNT_USER_PATTERNS = [
    r"\b(?:discount|discounts|offer|offers|bargain|deal|deals|coupon|promo|rebate|concession|cheaper rate)\b",
    r"\b(?:can you give me a discount|any discount|best price|special deal)\b",
]

# Patterns for model output violations that must be stripped or rewritten
PROHIBITED_OUTPUT_PATTERNS = [
    r"\b(?:hand you over|transfer you to a human|talk to a human|contact our sales rep|human agent|live agent|escalate)\b",
    r"\b(?:what is your budget|what's your budget|whats your budget|how much are you looking to spend)\b",
    r"\b(?:it costs|the price is|priced at|starting at)\s*[$₹€£]?\s*\d+",
]


def check_user_intent_for_pricing_or_discount(user_message: str):
    """
    Checks if the user message specifically asks for pricing or discounts.
    Returns standard refusal response if detected, or None.
    """
    clean_msg = user_message.lower().strip()

    for pattern in DISCOUNT_USER_PATTERNS:
        if re.search(pattern, clean_msg):
            return DISCOUNT_REFUSAL

    for pattern in PRICE_USER_PATTERNS:
        if re.search(pattern, clean_msg):
            return PRICE_REFUSAL

    return None


def validate_and_sanitize_response(response_text: str, user_message: str) -> str:
    """
    Validates model output against the strict commercial rules and output guidelines.
    If the response violates price, budget, or handover rules, it corrects it.
    """
    if not response_text:
        return "I am here to help. Could you tell me what type of product or service you're looking for?"

    text = response_text.strip()

    # Remove unwanted internal reasoning blocks or markdown artifacts if model emits them
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```[a-zA-Z]*\n?.*?\n?```", "", text, flags=re.DOTALL)

    # Check if user asked for discount
    if any(re.search(p, user_message.lower()) for p in DISCOUNT_USER_PATTERNS):
        return DISCOUNT_REFUSAL

    # Check if user asked for price
    if any(re.search(p, user_message.lower()) for p in PRICE_USER_PATTERNS):
        return PRICE_REFUSAL

    # Check if the model inadvertently asked about budget
    if re.search(r"\b(?:budget|how much are you willing to spend)\b", text, re.IGNORECASE):
        # Replace budget inquiry with technical requirement query
        text = re.sub(
            r"(?i)[^.!?]*\bbudget\b[^.!?]*[.!?]?",
            "What specific features or volume requirements do you have?",
            text
        )

    # Check if model inadvertently offered handover
    if re.search(r"\b(?:human|agent|representative|transfer|escalate)\b", text, re.IGNORECASE):
        text = re.sub(
            r"(?i)[^.!?]*\b(?:transfer|human|escalat|representative)\b[^.!?]*[.!?]?",
            "",
            text
        )

    # Clean up excess whitespace or empty results
    text = " ".join(text.split())
    if not text:
        return "Could you tell me a little more about the specific requirements you have in mind?"

    return text
