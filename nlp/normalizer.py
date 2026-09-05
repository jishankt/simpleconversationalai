"""
Text and Entity Normalization Module.
Corrects common typos, expands abbreviations, and canonicalizes technical units.
"""

import re
import unicodedata

# Common typo dictionary mapping misspelled terms to standard vocabulary
TYPO_CORRECTIONS = {
    r"\bpeinter\b": "printer",
    r"\bprntr\b": "printer",
    r"\bprentr\b": "printer",
    r"\bprinters\b": "printers",
    r"\bpltter\b": "plotter",
    r"\bploter\b": "plotter",
    r"\bpltr\b": "plotter",
    r"\bcadd\b": "CAD",
    r"\barchitct\b": "architect",
    r"\barchitcture\b": "architecture",
    r"\bblueprints?\b": "blueprint",
    r"\binova\b": "Innova",
    r"\bepsonn\b": "Epson",
    r"\beposn\b": "Epson",
    r"\bcitzen\b": "Citizen",
    r"\bcitizn\b": "Citizen",
    r"\bcartrige\b": "cartridge",
    r"\bcatridge\b": "cartridge",
    r"\bcartidges?\b": "cartridge",
    r"\bmaintenence\b": "maintenance",
    r"\bmaintanance\b": "maintenance",
    r"\bphotoboth\b": "photo booth",
    r"\bphotobooth\b": "photo booth",
    r"\bdyesub\b": "dye-sublimation",
    r"\bdye sub\b": "dye-sublimation",
    r"\bsublimtion\b": "sublimation",
    r"\bcopire\b": "copier",
    r"\benterprize\b": "enterprise",
    r"\bscannr\b": "scanner",
    r"\bscaner\b": "scanner",
    r"\bsacnners?\b": "scanners",
    r"\bsacnner\b": "scanner",
    r"\bcxo2\b": "CX02",
    r"\bcxo-2\b": "CX-02",
    r"\bcx02w\b": "CX-02W",
    r"\bluster\b": "lustre",
    r"\bmirag\b": "Mirage",
    r"\baircast\b": "AirCastPro",
    r"\bdiscont\b": "discount",
    r"\bprce\b": "price",
    r"\bpric\b": "price",
    r"\btiming\b": "hours",
    r"\btimings\b": "hours",
}

# Canonical entity normalization mappings
SIZE_CANONICAL = [
    (r"\b(?:24\s*(?:inch|in|\")|a[\s-]?1)\b", "24-inch (A1)"),
    (r"\b(?:36\s*(?:inch|in|\")|a[\s-]?0)\b", "36-inch (A0)"),
    (r"\b(?:44\s*(?:inch|in|\"))\b", "44-inch"),
    (r"\b(?:a[\s-]?3\+?|13\s*(?:inch|in|\"))\b", "13-inch (A3+)"),
    (r"\b(?:a[\s-]?2\+?|17\s*(?:inch|in|\"))\b", "17-inch (A2+)"),
    (r"\b(?:4\s*(?:x|\*)\s*6)\b", "4x6 inch"),
    (r"\b(?:6\s*(?:x|\*)\s*8)\b", "6x8 inch"),
]


def normalize_text(text: str) -> dict:
    """
    Cleans raw user input:
    1. Unicode NFKC normalization
    2. Typo correction
    3. Canonical entity identification
    Returns dict with 'clean_text', 'normalized_text', and 'corrections_applied'.
    """
    if not text:
        return {"clean_text": "", "normalized_text": "", "corrections_applied": []}

    # Normalize unicode characters
    clean = unicodedata.normalize("NFKC", text.strip())

    # Replace multiple spaces/newlines
    clean = re.sub(r"\s+", " ", clean)

    applied_corrections = []
    normalized = clean

    # Apply typo dictionary
    for pattern, replacement in TYPO_CORRECTIONS.items():
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            match = re.search(pattern, normalized, flags=re.IGNORECASE).group(0)
            if match.lower() != replacement.lower():
                applied_corrections.append(f"{match} -> {replacement}")
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    # Detect canonical sizes
    canonical_sizes = []
    for pattern, canonical_val in SIZE_CANONICAL:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            canonical_sizes.append(canonical_val)

    return {
        "raw_text": text,
        "clean_text": clean,
        "normalized_text": normalized,
        "corrections_applied": applied_corrections,
        "canonical_sizes": canonical_sizes
    }
