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
    "t5100m": "epson-t5400m",
    "sct5100m": "epson-t5400m",
    "t5400m": "epson-t5400m",
    "sct5400m": "epson-t5400m",
    "t5400": "epson-t5400m",
    "sct5400": "epson-t5400m",
    "t5700d": "epson-t5700d",
    "sct5700d": "epson-t5700d",
    "p700": "epson-p700",
    "scp700": "epson-p700",
    "p900": "epson-p900",
    "scp900": "epson-p900",
    "p5300": "epson-p5300",
    "scp5300": "epson-p5300",
    "p7500": "epson-p7500-p9500",
    "scp7500": "epson-p7500-p9500",
    "p9500": "epson-p7500-p9500",
    "scp9500": "epson-p7500-p9500",
    "p20000": "epson-p20000",
    "scp20000": "epson-p20000",
    "f100": "epson-sc-f100",
    "scf100": "epson-sc-f100",
    "f500": "epson-sc-f500",
    "scf500": "epson-sc-f500",
    "amc4000": "epson-am-c4000",
    "amc550": "epson-am-c550",
    "wfc20600": "epson-wf-c20600",
    "c20600": "epson-wf-c20600",
    "wfc21000": "epson-wf-c21000",
    "c21000": "epson-wf-c21000",
    "cx02": "citizen-cx-02",
    "cx02s": "citizen-cx-02",
    "cx02w": "citizen-cx-02w",
    "cy02": "citizen-cy-02",
    "cz01": "citizen-cz-01",
    "op900ii": "citizen-op900ii",
    "ds530": "epson-ds-530ii",
    "ds530ii": "epson-ds-530ii",
    "ds800": "epson-ds-800wn",
    "ds800wn": "epson-ds-800wn",
    "ds900": "epson-ds-900wn",
    "ds900wn": "epson-ds-900wn",
    "12000xl": "epson-expression-12000xl",
    "expression12000xl": "epson-expression-12000xl",
    "ds70": "epson-b11b252402",
    "ds80w": "epson-b11b253402",
    "ds80": "epson-b11b253402",
    "ds1630": "epson-b11b239402bb",
    "ds1660w": "epson-b11b244402bb",
    "ds310": "epson-b11b241401by",
    "ds360w": "epson-b11b242401by",
    "ds410": "epson-b11b249401bb",
    "ds730n": "epson-b11b259401bb",
    "ds770": "epson-b11b262401bb",
    "ds770ii": "epson-b11b262401bb",
    "ds790wn": "epson-b11b265401bb",
    "ds790": "epson-b11b265401bb",
    "ds870": "epson-b11b250401bb",
    "ds970": "epson-b11b251401bb",
    "ds30000": "epson-b11b256401bb",
    "ds32000": "epson-b11b255401bb",
    "ds60000": "epson-b11b204231by",
    "ds70000": "epson-b11b204331by",
    "ds6500": "epson-b11b205231by",
    "ds7500": "epson-b11b205331by",
    "es500w": "epson-b11b263401bb",
    "es500wii": "epson-b11b263401bb",
    "es580w": "epson-b11b258401bb",
    "es580": "epson-b11b258401bb",
    "ifa11": "innova-ifa11",
    "ifa13": "innova-ifa13",
    "olm70": "olmec-olm70",
    "aircastpro": "aircastpro",
    "mirage": "mirage-dinax",
}


def resolve_canonical_id(text: str) -> Optional[str]:
    """
    Resolves any user mention of a model or SKU to its canonical product id.
    Handles compound identifiers like 'Epson DS-530II', 'Citizen CX-02', 'SC-T5400M', 'AM-C4000'.
    """
    if not text:
        return None

    cleaned = normalize_model_identifier(text)
    if cleaned in ALIAS_TO_CANONICAL_ID:
        return ALIAS_TO_CANONICAL_ID[cleaned]

    # Extract all alphanumeric words from the text
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    if not words:
        return None

    # Check 3-gram, 2-gram, and 1-gram combinations (longest first)
    for n in [3, 2, 1]:
        for i in range(len(words) - n + 1):
            candidate = "".join(words[i:i+n])
            norm_c = normalize_model_identifier(candidate)
            if norm_c and norm_c in ALIAS_TO_CANONICAL_ID:
                return ALIAS_TO_CANONICAL_ID[norm_c]

    return None
