"""
Response Validator for Kepler Tech Conversational AI.
Validates assistant responses before sending to the user.
Catches repetition, multi-question, price leakage, and excessive length.
"""

import re
from difflib import SequenceMatcher
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool = True
    violations: List[str] = field(default_factory=list)
    sanitized_response: str = ""


# Price/discount patterns that should never appear in responses
_PRICE_PATTERNS = [
    re.compile(r"[$₹€£]\s*\d+", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:aed|dirhams|dollars|usd|eur|inr)\b", re.IGNORECASE),
    re.compile(r"\b(?:costs?|priced?\s+at|starting\s+at|from)\s*[$₹€£]?\s*\d+", re.IGNORECASE),
]


def validate_response(
    response: str,
    previous_response: Optional[str] = None,
    context_intent: str = "",
) -> ValidationResult:
    """
    Validate a response before sending it to the user.
    Returns ValidationResult with any violations found.
    """
    result = ValidationResult(sanitized_response=response)

    if not response or not response.strip():
        result.valid = False
        result.violations.append("empty_response")
        result.sanitized_response = "How can I help you today?"
        return result

    text = response.strip()

    # ── 1. Duplicate detection ───────────────────────────────────────────
    if previous_response:
        similarity = SequenceMatcher(
            None,
            _normalize_for_comparison(previous_response),
            _normalize_for_comparison(text),
        ).ratio()

        if similarity >= 0.88 and context_intent != "correction":
            result.violations.append("repeated_response")

    # ── 2. Multi-question detection ──────────────────────────────────────
    question_marks = text.count("?")
    if question_marks > 1:
        result.violations.append("multiple_questions")

    # ── 3. Price leakage ─────────────────────────────────────────────────
    for pattern in _PRICE_PATTERNS:
        if pattern.search(text):
            result.violations.append("price_leakage")
            break

    # ── 4. Excessive length ──────────────────────────────────────────────
    if len(text) > 600:
        result.violations.append("excessive_length")

    # ── 5. Unnecessary greeting in non-greeting context ──────────────────
    if context_intent and context_intent not in ("greeting", "customer_introduction"):
        if re.match(r"^(?:hello|hi|hey|welcome)[\s!,]", text, re.IGNORECASE):
            result.violations.append("unnecessary_greeting")

    # ── 6. Truncated / Cut-off detection ────────────────────────────────
    if len(text) < 15 and not any(text.lower().startswith(w) for w in ["yes", "no", "ok", "hello", "hi"]):
        result.violations.append("truncated_response")
    elif re.search(r"\b(?:could you|would you|and|or|with|the|that|which|to|of|for|is|are|a|an)\s*$", text, re.IGNORECASE):
        result.violations.append("truncated_response")

    # Set valid flag
    result.valid = len(result.violations) == 0
    result.sanitized_response = text

    return result


def _normalize_for_comparison(text: str) -> str:
    """Normalize text for similarity comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text
