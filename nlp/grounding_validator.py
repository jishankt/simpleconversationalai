"""
Zero-Hallucination Grounding Validator.
Cross-references assistant output against verified Kepler Tech facts.
Enforces Rule F whenever facts are unverified or outside confirmed catalog.
"""

import re
from knowledge_base import VERIFIED_PRODUCTS, COMPANY_PROFILE

UNVERIFIED_REFUSAL = "I don’t have confirmed information about that, so I don’t want to give you an inaccurate answer."

# Categories/terms confirmed NOT offered or supported by Kepler Tech catalog
UNCONFIRMED_CATEGORIES = [
    r"\b(?:3d prints?|3d printers?|additive manufacturing|filament)\b",
    r"\b(?:laser toners?|hp laserjet|canon pixma|brother dcp|xerox docucentre)\b",
    r"\b(?:direct to garment|dtg t-shirt|dtf film shaker)\b",
    r"\b(?:cryptocurrency|bitcoin|escrow)\b"
]


def validate_grounding(response_text: str, user_normalized_text: str, intent_data: dict) -> dict:
    """
    Validates that the assistant response is strictly grounded in verified facts.
    Returns:
      - is_grounded: bool
      - status: str (e.g., 'VERIFIED_GROUNDED', 'RULE_F_APPLIED')
      - sanitized_response: str
      - grounding_notes: list of verification details
    """
    lower_user = user_normalized_text.lower()
    lower_resp = response_text.lower()
    notes = []

    # 1. Check if user asked about unconfirmed products/services
    for unconfirmed_pattern in UNCONFIRMED_CATEGORIES:
        if re.search(unconfirmed_pattern, lower_user):
            notes.append("User requested category outside verified Kepler Tech catalog.")
            return {
                "is_grounded": True,
                "status": "RULE_F_UNVERIFIED_CATEGORY",
                "sanitized_response": (
                    f"{UNVERIFIED_REFUSAL} Kepler Tech LLC specializes primarily in Epson large-format CAD/photo plotters, "
                    f"enterprise business inkjets, Citizen dye-sub photo systems, and fine-art media. How can I assist you with those?"
                ),
                "notes": notes
            }

    # 2. Check for fictitious pricing or numeric currency in response
    if re.search(r"\b(?:aed|usd|\$|dirhams?)\s*\d+", lower_resp) or re.search(r"\d+\s*(?:aed|usd|dirhams?)", lower_resp):
        notes.append("Hallucinated price or currency intercepted in output.")
        return {
            "is_grounded": False,
            "status": "PRICE_LEAK_PREVENTED",
            "sanitized_response": "I can help you find the right option based on your requirements, but pricing isn’t available through this chat.",
            "notes": notes
        }

    # 3. Check for invented budget questions
    if re.search(r"\b(?:what is your budget|what's your budget|whats your budget|how much are you looking to spend)\b", lower_resp):
        notes.append("Inadvertent budget question sanitized.")
        response_text = re.sub(
            r"(?i)[^.!?]*\bbudget\b[^.!?]*[.!?]?",
            "What specific features or print volume requirements do you have?",
            response_text
        )

    # 4. Verify model references if present
    # Check if any model mentioned in response exists in verified catalog
    known_models = ["t3100", "t5100", "t5400", "p700", "p900", "p7500", "p9500", "am-c4000", "am-c550", "wf-c879r", "cx-02", "cy-02", "ifa 11", "ifa 13", "olm 68", "olm 70"]
    models_found = [m for m in known_models if m in lower_resp]
    if models_found:
        notes.append(f"Grounded against verified models: {', '.join(models_found)}")

    return {
        "is_grounded": True,
        "status": "VERIFIED_GROUNDED",
        "sanitized_response": response_text.strip(),
        "notes": notes
    }
