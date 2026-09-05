"""Evidence-only answer helpers.

This module deliberately treats missing catalog fields as UNKNOWN.  It never
converts an unknown value into a guessed specification or a negative claim.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

UNKNOWN_RESPONSE = "I couldn't verify that detail in our current product data."


def _first_value(product: Dict[str, Any], keys: Iterable[str]) -> Tuple[Optional[str], Any]:
    for key in keys:
        value = product.get(key)
        if value not in (None, "", [], {}):
            return key, value
    return None, None


def _text_evidence(product: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("name", "description", "features", "intended_usage", "tags", "category"):
        value = product.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value not in (None, ""):
            parts.append(str(value))
    return " ".join(parts)


def _has_explicit_scan_evidence(product: Dict[str, Any]) -> Optional[bool]:
    """Return True/False only when the catalog explicitly establishes it.

    Absence of words like scanner/MFP is not evidence that scanning is absent.
    """
    for key in ("has_scanner", "scanner", "scan_capable", "mfp"):
        value = product.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in {"yes", "true", "included", "built-in", "integrated"}:
                return True
            if low in {"no", "false", "not included", "print only"}:
                return False

    evidence = _text_evidence(product).lower()
    if re.search(r"\b(integrated|built[- ]?in)\s+(scanner|scanning)\b", evidence):
        return True
    if re.search(r"\b(scan|scanner|scanning|mfp|copy|copier)\b", evidence):
        # Text establishes some scan capability, but do not infer more than that.
        return True
    return None


def answer_product_question(
    product: Dict[str, Any],
    question: str,
    compatible_consumables: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Create a deterministic answer using catalog evidence only."""
    name = str(product.get("name") or product.get("sku") or "this product")
    q = question.lower()

    if any(k in q for k in ("scanner", "scan", "scanning", "copy", "copier", "mfp")):
        scan = _has_explicit_scan_evidence(product)
        if scan is True:
            return f"The catalog confirms scanning capability for {name}."
        if scan is False:
            return f"The catalog confirms {name} is a print-only configuration without a built-in scanner."
        return f"{UNKNOWN_RESPONSE} I can't confirm whether {name} has a built-in scanner."

    if any(k in q for k in ("size", "width", "maximum", "max width", "media width")):
        _, value = _first_value(product, ("width", "max_width", "max_media_width", "media_width", "print_width"))
        if value is None:
            return f"{UNKNOWN_RESPONSE} The maximum media width for {name} is not verified in the catalog entry."
        return f"The verified maximum media width for {name} is {value}."

    if any(k in q for k in ("speed", "ppm", "print speed", "fast")):
        _, value = _first_value(product, ("speed", "print_speed", "ppm", "throughput"))
        if value is None:
            return f"{UNKNOWN_RESPONSE} I don't have a verified print-speed value for {name}."
        return f"The catalog lists the print speed for {name} as {value}."

    if any(k in q for k in ("resolution", "dpi")):
        _, value = _first_value(product, ("resolution", "print_resolution", "max_resolution", "dpi"))
        if value is None:
            return f"{UNKNOWN_RESPONSE} I don't have a verified resolution value for {name}."
        return f"The catalog lists the resolution for {name} as {value}."

    if any(k in q for k in ("ink", "cartridge", "technology", "consumable")):
        _, value = _first_value(product, ("ink_technology", "ink_type", "ink", "technology"))
        if value is not None:
            return f"The catalog lists {value} for {name}."
        if compatible_consumables:
            names = [str(c.get("name")) for c in compatible_consumables if c.get("name")]
            if names:
                preview = ", ".join(names[:4])
                return f"I couldn't verify a specific ink-technology field for {name}, but these compatible consumables are verified in the catalog: {preview}."
        return f"{UNKNOWN_RESPONSE} I don't have a verified ink-technology value for {name}."

    if any(k in q for k in ("wifi", "wi-fi", "wireless", "ethernet", "usb", "network", "connect")):
        _, value = _first_value(product, ("connectivity", "interfaces", "network", "ports"))
        if value is None:
            text = _text_evidence(product)
            requested = [k for k in ("wi-fi", "wifi", "wireless", "ethernet", "usb") if k in q]
            if requested and any(r in text.lower() for r in requested):
                return f"The catalog entry for {name} mentions {requested[0]} connectivity."
            return f"{UNKNOWN_RESPONSE} Connectivity details for {name} are not fully verified in the catalog entry."
        return f"The catalog lists the connectivity for {name} as {value}."

    description = product.get("description")
    if description:
        return f"According to our catalog, {name}: {description}"

    return f"{UNKNOWN_RESPONSE} I found {name} in the catalog, but its detailed description is incomplete."


def extract_numbers(text: str) -> List[str]:
    """Normalize numeric tokens for simple claim validation."""
    return re.findall(r"(?<!\w)\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?", text or "")


def numbers_are_grounded(answer: str, evidence_text: str) -> bool:
    """Every number in an answer must also appear in the supplied evidence."""
    answer_nums = extract_numbers(answer)
    evidence_nums = set(extract_numbers(evidence_text))
    return all(n in evidence_nums for n in answer_nums)
