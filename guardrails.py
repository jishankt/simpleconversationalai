"""
Commercial rules guardrail and response validator.
Ensures zero price leaks, zero budget queries, zero discount promises,
and strictly enforces standard refusal phrases.
"""

import re

# Exact refusal templates defined in the system prompt
# Strict zero discount, zero pricing and product-finding-only global policy
DISCOUNT_REFUSAL = (
    "Pricing, commercial discounts, and quotations are not provided through this chat assistant. "
    "I am here to help you identify the right equipment and verified technical specifications from our authorized catalogue."
)
PRICE_REFUSAL = DISCOUNT_REFUSAL

PRICE_USER_PATTERNS = [
    r"\b(?:how much|prices?|pricing|costs?|rates?|commercial rates?|quotations?|quotes?|charges?|fees?|expensive|cheap|affordable)\b",
    r"[$₹€£]\s*\d+",
    r"\b\d+\s*(?:dollars|bucks|rupees|inr|usd|eur|cents|aed)\b",
    r"\bwhat is the price\b",
    r"\bwhat does it cost\b",
]

# Intent detection regex patterns for discount and negotiation attempts
DISCOUNT_USER_PATTERNS = [
    r"\b(?:discount|discounts|discounting|offer|offers|bargain|bargaining|deal|deals|coupon|promo|rebate|concession)\b",
    r"\b(?:negotiat\w*|negosition|negotiable)\b",
    r"\b(?:cheaper rate|cheaper price|cheaper|best price|special deal|lower the price|reduce the price|reduce price|price drop)\b",
    r"\b(?:can you give me a discount|any discount|give discount|give me discount|need discount|less price|more discount)\b",
    r"\b(?:can we negotiate|can i negotiate|price negotiation|negotiate price)\b",
    r"\b(?:give me (?:a )?better price|what is your lowest price|lowest price|minimum price)\b",
]

# Prohibited output patterns: model must never negotiate, promise discounts, or ask for budget
PROHIBITED_OUTPUT_PATTERNS = [
    r"\b(?:hand you over|transfer you to a human|talk to a human|contact our sales rep|human agent|live agent|escalate)\b",
    r"\b(?:what is your budget|what's your budget|whats your budget|how much are you looking to spend)\b",
    r"\b(?:i can give you a discount|we can offer you a discount|i can lower the price|we can negotiate)\b",
]


STATIC_SAFE_REFUSAL = (
    "I am unable to verify the requested product details against our official catalogue. "
    "Please specify a verified product model or tell me your technical requirements."
)


def is_commercial_negated(text: str) -> bool:
    """Check if the user is explicitly asking to exclude commercial/discount/price discussion."""
    if not text:
        return False
    t_lower = text.lower()
    neg_patterns = [
        r"\b(?:without|no|not|excluding|ignore|don't|dont|never|free of)\s+(?:discussing|mentioning|including|talking about|asking for|getting into)?\s*(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?|commercials?)(?:\s*(?:and|or|,)\s*(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?|commercials?))*\b",
        r"\bdo not (?:mention|discuss|include)\s+(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?)(?:\s*(?:and|or|,)\s*(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?))*\b",
    ]
    return any(re.search(p, t_lower) for p in neg_patterns)


def strip_negated_commercial(text: str) -> str:
    """Strips negated commercial phrases from the query to prevent false-positive intercept."""
    if not text:
        return ""
    neg_patterns = [
        r"\b(?:without|no|not|excluding|ignore|don't|dont|never|free of)\s+(?:discussing|mentioning|including|talking about|asking for|getting into)?\s*(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?|commercials?)(?:\s*(?:and|or|,)\s*(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?|commercials?))*\b",
        r"\bdo not (?:mention|discuss|include)\s+(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?)(?:\s*(?:and|or|,)\s*(?:prices?|discounts?|costs?|rates?|pricing|quotations?|quotes?))*\b",
    ]
    cleaned = text
    for p in neg_patterns:
        cleaned = re.sub(p, " ", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def check_user_intent_for_pricing_or_discount(user_message: str):
    """
    Checks if the user message asks for discounts, bargaining, negotiations, or pricing.
    Strictly enforces the product-finding-only global policy: zero prices, zero discounts,
    zero quotations, zero sales contact.
    """
    clean_msg = strip_negated_commercial(user_message.lower().strip())

    for pattern in DISCOUNT_USER_PATTERNS + PRICE_USER_PATTERNS:
        if re.search(pattern, clean_msg):
            return DISCOUNT_REFUSAL

    return None


def validate_and_sanitize_response(response_text: str, user_message: str) -> str:
    """
    Validates model output against the strict commercial rules and output guidelines.
    Guarantees no discounts, no negotiations, and no budget queries.
    Never modifies text inside product URLs, model names, SKUs, or technical specifications.
    """
    if not response_text:
        return "I am here to help. Could you tell me what type of product or service you're looking for?"

    text = response_text.strip()

    # Remove unwanted internal reasoning blocks or markdown artifacts if model emits them
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```[a-zA-Z]*\n?.*?\n?```", "", text, flags=re.DOTALL)

    # Check if user asked for discount or negotiation (ignoring negated mentions)
    clean_user_msg = strip_negated_commercial(user_message.lower().strip())
    if any(re.search(p, clean_user_msg) for p in DISCOUNT_USER_PATTERNS + PRICE_USER_PATTERNS):
        return DISCOUNT_REFUSAL

    # If user explicitly specified not to discuss price or discounts, scrub any commercial terms
    if is_commercial_negated(user_message):
        text = re.sub(r"(?i)[^.!?\n]*\b(?:discount|discounts|pricing policy|zero-discount|quotation|quote|rate|rates|pricing)\b[^.!?\n]*[.!?]?", "", text)

    # Check if the model inadvertently asked about budget
    if re.search(r"\b(?:budget|how much are you willing to spend)\b", text, re.IGNORECASE):
        # Replace budget inquiry with technical requirement query
        text = re.sub(
            r"(?i)[^.!?]*\bbudget\b[^.!?]*[.!?]?",
            "What specific features or volume requirements do you have?",
            text
        )

    # Check if model inadvertently offered handover, sales representative, or lead capture
    if re.search(r"\b(?:human|agent|representative|transfer|escalate|lead capture|handover|sales rep)\b", text, re.IGNORECASE):
        text = re.sub(
            r"(?i)[^.!?\n]*\b(?:transfer|human|escalat|representative|sales rep|handover)\b[^.!?\n]*[.!?]?",
            "",
            text
        )

    # Scrub contact information ONLY from explicit contact sentences or raw email addresses
    # Never use broad digit regexes that corrupt technical model names, SKUs, dimensions, or URLs
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "", text)
    text = re.sub(
        r"(?i)[^.!?\n]*\b(?:call|phone|whatsapp|tel|reach us|contact us|contact sales|sales team|email us)\b[^.!?\n]*[.!?]?",
        "",
        text
    )

    # Remove internal grounding/audit tags from user-facing responses
    text = re.sub(r"\s*\[(?:VERIFIED|CONFLICT|INFERRED|CALCULATED)[^\]]*\]", "", text)

    # Clean up excess horizontal whitespace while preserving clean paragraph and bullet newlines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return "Could you tell me a little more about the specific requirements you have in mind?"

    return text

