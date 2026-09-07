"""
Product Identifier Resolver and Normalizer.
Resolves model strings like 'SC-T5400', 'T5400', 'Epson T5400', 'SureColor T5400' to canonical product identifiers.
"""
import re
from typing import Optional, Dict, List


def normalize_model_identifier(raw: str) -> str:
    """
    Cleans and canonicalizes a product model string for exact matching.
    Example: 'Epson SureColor SC-T5400M' -> 't5400m'
             'Citizen CX-02' -> 'cx02'
             'WF-C20600' -> 'wfc20600'
    """
    if not raw:
        return ""
    text = raw.lower().strip()
    # Remove brand prefixes and series
    text = re.sub(r"\b(epson|citizen|surecolor|workforce|pro|enterprise)\b", "", text)
    # Remove 'sc-', 'sc ', 'wf-', 'wf '
    text = re.sub(r"\bsc[-_ ]?", "", text)
    text = re.sub(r"\bwf[-_ ]?", "wf", text)
    text = re.sub(r"\bcx[-_ ]?", "cx", text)
    text = re.sub(r"\bcy[-_ ]?", "cy", text)
    # Remove dashes, slashes, spaces
    text = re.sub(r"[^a-z0-9]", "", text)
    return text.strip()


# Common aliases mapping to canonical catalog IDs
ALIAS_TO_CANONICAL_ID: Dict[str, str] = {
    "t3100": "epson-t3100",
    "t3100n": "epson-t3100",
    "sct3100": "epson-t3100",
    "sct3100n": "epson-t3100",
    "t5100": "epson-t5100",
    "t5100n": "epson-t5100",
    "sct5100": "epson-t5100",
    "t5400m": "epson-t5400m",
    "sct5400m": "epson-t5400m",
    "t5400": "epson-t5400m",
    "t5700d": "epson-t5700d",
    "sct5700d": "epson-t5700d",
    "p700": "epson-p700",
    "scp700": "epson-p700",
    "p900": "epson-p900",
    "scp900": "epson-p900",
    "p5300": "epson-p5300",
    "scp5300": "epson-p5300",
    "p7500": "epson-p7500",
    "scp7500": "epson-p7500",
    "p9500": "epson-p9500",
    "scp9500": "epson-p9500",
    "p20000": "epson-p20000",
    "scp20000": "epson-p20000",
    "f100": "epson-f100",
    "scf100": "epson-f100",
    "f500": "epson-f500",
    "scf500": "epson-f500",
    "amc4000": "epson-am-c4000",
    "amc550": "epson-am-c550",
    "wfc20600": "epson-wf-c20600",
    "c20600": "epson-wf-c20600",
    "wfc21000": "epson-wf-c21000",
    "c21000": "epson-wf-c21000",
    "cx02": "citizen-cx-02",
    "cx02w": "citizen-cx-02w",
    "cy02": "citizen-cy-02",
    "cz01": "citizen-cz-01",
    "op900ii": "citizen-op900ii",
    "ds870": "epson-ds-870",
    "ds970": "epson-ds-970",
    "ds730n": "epson-ds-730n",
    "ds790wn": "epson-ds-790wn",
}


def resolve_canonical_id(text: str) -> Optional[str]:
    """
    Resolves any user mention of a model or SKU to its canonical product id.
    """
    if not text:
        return None
    cleaned = normalize_model_identifier(text)
    if cleaned in ALIAS_TO_CANONICAL_ID:
        return ALIAS_TO_CANONICAL_ID[cleaned]
    
    # Substring check for tokenized parts
    tokens = re.split(r"[\s\-_,]+", text.lower())
    for token in tokens:
        norm_t = normalize_model_identifier(token)
        if norm_t and norm_t in ALIAS_TO_CANONICAL_ID:
            return ALIAS_TO_CANONICAL_ID[norm_t]
            
    return None
