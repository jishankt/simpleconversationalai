"""
Dialogue Act Classifier for Conversational Commerce.
Classifies multi-turn user intent beyond static single-turn keyword regex into
interactive dialogue acts (answering, correcting, referencing, questioning, etc.).
"""
import re
from typing import Dict, Any, Optional

ACT_ANSWERING_QUESTION = "answering_question"
ACT_CORRECTING_ANSWER = "correcting_previous_answer"
ACT_ASKING_PRODUCT_QUESTION = "asking_product_question"
ACT_ASKING_COMPARISON = "asking_comparison"
ACT_ASKING_CONSUMABLES = "asking_consumables"
ACT_CHANGING_REQUIREMENT = "changing_requirement"
ACT_CHANGING_TOPIC = "changing_topic"
ACT_REFERENCING_ITEM = "referencing_item"
ACT_GREETING = "greeting"
ACT_ENDING = "ending"
ACT_CONFIRMING = "confirming"
ACT_REJECTING = "rejecting"
ACT_GENERAL_DISCOVERY = "general_discovery"


def classify_dialogue_act(
    text: str,
    awaiting_field: Optional[str] = None,
    current_category: Optional[str] = None,
    active_product: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classifies user message into a conversational dialogue act with extracted entities.
    """
    if not text:
        return {"act": ACT_GENERAL_DISCOVERY, "params": {}}

    raw = text.strip()
    low = raw.lower()

    # 1. Topic change (e.g. "actually now I need a photo booth printer", "switch to scanners")
    if any(k in low for k in ["actually now i need", "now i need", "switch to", "instead i want", "changed my mind"]):
        target_cat = None
        if any(k in low for k in ["photo booth", "dyesub", "citizen", "event printer"]):
            target_cat = "photo_booth"
        elif any(k in low for k in ["cad", "technical", "plotter", "architect", "blueprint"]):
            target_cat = "technical_cad"
        elif any(k in low for k in ["scanner", "scanners", "flatbed"]):
            target_cat = "scanner"
        elif any(k in low for k in ["fine art", "photo printer", "gallery"]):
            target_cat = "photo_fine_art"
        elif any(k in low for k in ["office", "enterprise", "workforce", "business printer"]):
            target_cat = "office_enterprise"
        elif any(k in low for k in ["ink", "consumable", "cartridge"]):
            target_cat = "consumable"

        if target_cat:
            return {"act": ACT_CHANGING_TOPIC, "params": {"target_category": target_cat}}

    # 2. Corrections (e.g., "actually A1", "no scanner", "actually no scanner")
    if re.search(r"\b(?:actually|no,\s*wait|i\s+meant|change\s+to|change\s+size|make\s+it)\b", low) or \
       (re.search(r"\bno\s+scanner\b", low) and awaiting_field != "scan_required"):
        # Detect what is being corrected
        correction_field = None
        new_val = None

        if "scanner" in low:
            correction_field = "scan_required"
            new_val = False if any(k in low for k in ["no", "without", "dont", "don't"]) else True
        elif re.search(r"\b(?:a0|36\s*inch|36\")\b", low):
            correction_field = "print_size"
            new_val = "A0"
        elif re.search(r"\b(?:a1|24\s*inch|24\")\b", low):
            correction_field = "print_size"
            new_val = "A1"
        elif re.search(r"\b(?:4x6|5x7|6x8)\b", low):
            correction_field = "print_size"
            new_val = re.search(r"\b(?:4x6|5x7|6x8)\b", low).group(0)

        if correction_field:
            return {
                "act": ACT_CORRECTING_ANSWER,
                "params": {"field": correction_field, "value": new_val}
            }

    # 3. Consumable questions (e.g. "what ink does it use?", "what ink does the first one use?", "what inks for it?")
    if re.search(r"\b(?:what\s+ink|which\s+ink|compatible\s+ink|what\s+consumable|maintenance\s+tank|waste\s+box|cartridges?\s+for)\b", low):
        item_ref = None
        if "first" in low or "1st" in low:
            item_ref = 0
        elif "second" in low or "2nd" in low:
            item_ref = 1
        return {"act": ACT_ASKING_CONSUMABLES, "params": {"item_ref": item_ref}}

    # 4. Comparison (e.g., "compare them", "which is better for me?", "difference between")
    if any(k in low for k in ["compare", "which is better", "difference between", "how do they compare", "which one should i choose"]):
        return {"act": ACT_ASKING_COMPARISON, "params": {}}

    # 5. Cycle / Change requirement (e.g., "show another one", "show another", "not that one", "any other")
    if any(k in low for k in ["show another", "show another one", "not that one", "next option", "other options", "alternative"]):
        return {"act": ACT_CHANGING_REQUIREMENT, "params": {"direction": "next"}}

    # 6. Specific item reference / selection (e.g., "the first one", "the second one", "what about the second one?", "show me T5400M")
    model_match = re.search(r"\b(t\d{4}[a-z]*|p\d{3,4}[a-z]*|f\d{3,4}|cx-02|cy-02|am-c\d+|wf-c\d+|ds-\d+[a-z]*)\b", low)
    if any(k in low for k in ["first one", "1st one", "second one", "2nd one", "third one"]) or model_match:
        ref_index = None
        if "first" in low or "1st" in low:
            ref_index = 0
        elif "second" in low or "2nd" in low:
            ref_index = 1
        elif "third" in low:
            ref_index = 2

        model_code = model_match.group(1).upper() if model_match else None

        # Check if asking question about referenced item (e.g. "does it have wifi?", "what size can it print?")
        is_question = any(q in low for q in ["does it", "can it", "has it", "what size", "how fast", "wifi", "network", "scanner"])
        if is_question:
            return {
                "act": ACT_ASKING_PRODUCT_QUESTION,
                "params": {"item_ref": ref_index, "model_code": model_code, "query": raw}
            }

        return {
            "act": ACT_REFERENCING_ITEM,
            "params": {"item_ref": ref_index, "model_code": model_code}
        }

    # 7. Product Question on active product (e.g., "why this one?", "does it have a scanner?", "what size can it print?", "does it have wifi?")
    if any(q in low for q in ["why this", "why this one", "does it have", "is it wireless", "can it scan", "can it print", "what size can", "print speed", "warranty", "tell me about", "tell me more", "how does it work"]):
        return {
            "act": ACT_ASKING_PRODUCT_QUESTION,
            "params": {"query": raw}
        }

    # 7b. Direct Recommendation request (e.g., "recommend now", "show options", "show recommendations")
    if any(k in low for k in ["recommend now", "show options", "show recommendations", "what do you recommend"]):
        return {
            "act": "recommend_now",
            "params": {}
        }

    # 8. Answering current awaiting field
    if awaiting_field:
        if awaiting_field == "print_size":
            if re.search(r"\b(?:a0|36\s*inch|36\"|a0\s*size)\b", low):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "print_size", "value": "A0"}}
            elif re.search(r"\b(?:a1|24\s*inch|24\"|a1\s*size)\b", low):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "print_size", "value": "A1"}}
            elif re.search(r"\b(?:4x6|5x7|6x8)\b", low):
                m = re.search(r"\b(?:4x6|5x7|6x8)\b", low).group(0)
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "print_size", "value": m}}

        elif awaiting_field == "scan_required":
            if any(k in low for k in ["yes", "yeah", "yep", "sure", "need scanner", "scanner needed", "integrated"]):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "scan_required", "value": True}}
            elif any(k in low for k in ["no", "nope", "print only", "not needed", "dont need", "don't need"]):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "scan_required", "value": False}}

        elif awaiting_field == "daily_volume":
            num_match = re.search(r"\b(\d+)\b", low)
            if num_match:
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "daily_volume", "value": int(num_match.group(1))}}
            elif any(k in low for k in ["low", "few", "1-10"]):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "daily_volume", "value": 5}}
            elif any(k in low for k in ["medium", "moderate", "10-50"]):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "daily_volume", "value": 25}}
            elif any(k in low for k in ["high", "heavy", "production", "50+"]):
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "daily_volume", "value": 75}}

        elif awaiting_field == "printer_model":
            m_match = re.search(r"\b(sc-p\d+[a-z0-9]*|sc-t\d+[a-z0-9]*|sc-f\d+[a-z0-9]*|p\d{3,4}|t\d{3,4}|f\d{3,4}|wf-c\d+|am-c\d+)\b", low)
            if m_match:
                return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "printer_model", "value": m_match.group(1).upper()}}

    # 9. Standalone entities that match known requirements even without awaiting_field
    if re.search(r"\b(?:a0|36\s*inch|36\")\b", low) and not any(k in low for k in ["compare", "vs"]):
        return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "print_size", "value": "A0"}}
    if re.search(r"\b(?:a1|24\s*inch|24\")\b", low) and not any(k in low for k in ["compare", "vs"]):
        return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "print_size", "value": "A1"}}
    if re.search(r"\b(?:4x6|5x7|6x8)\b", low):
        m = re.search(r"\b(?:4x6|5x7|6x8)\b", low).group(0)
        return {"act": ACT_ANSWERING_QUESTION, "params": {"field": "print_size", "value": m}}

    # 10. Greetings / Confirmations
    if any(w in low for w in ["hello", "hi", "hey", "good morning"]) and len(low.split()) <= 3:
        return {"act": ACT_GREETING, "params": {}}
    if low in ["yes", "yeah", "yep", "sure", "ok", "okay"]:
        return {"act": ACT_CONFIRMING, "params": {}}
    if low in ["no", "nope", "cancel"]:
        return {"act": ACT_REJECTING, "params": {}}

    return {"act": ACT_GENERAL_DISCOVERY, "params": {}}
