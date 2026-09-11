"""
Text and Entity Normalization Module.
Corrects common typos, expands abbreviations, and canonicalizes technical units.
"""

import re
import unicodedata

# Common typo dictionary mapping misspelled terms to standard vocabulary
TYPO_CORRECTIONS = {
    # Common English typos
    r"\bpribter\b": "printer",
    r"\bpriner\b": "printer",
    r"\bpriners\b": "printers",
    r"\bpritner\b": "printer",
    r"\bprinr\b": "printer",
    r"\bprintr\b": "printer",
    r"\bpeinter\b": "printer",
    r"\bprntr\b": "printer",
    r"\bprentr\b": "printer",
    r"\baprinter\b": "a printer",
    r"\bprinters\b": "printers",
    r"\bofice\b": "office",
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
    r"\bcitizon\b": "Citizen",
    r"\bcitizone\b": "Citizen",
    r"\bcitizens\b": "Citizen",
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
    r"\bcxo2\b": "CX02",
    r"\bcxo-2\b": "CX-02",
    r"\bcx02w\b": "CX-02W",
    r"\bf1oo\b": "F100",
    r"\bsc-?f1oo\b": "SC-F100",
    r"\bf5oo\b": "F500",
    r"\bp9oo\b": "P900",
    r"\bp7oo\b": "P700",
    r"\bt31oo\b": "T3100",
    r"\bt51oo\b": "T5100",
    r"\bluster\b": "lustre",
    r"\bmirag\b": "Mirage",
    r"\baircast\b": "AirCastPro",
    r"\bdiscont\b": "discount",
    r"\bdiscout\b": "discount",
    r"\bprce\b": "price",
    r"\bpric\b": "price",
    r"\btiming\b": "hours",
    r"\btimings\b": "hours",
    r"\bbroucher\b": "brochure",
    r"\bbrousher\b": "brochure",
    r"\bbrouchure\b": "brochure",
    r"\bdatashet\b": "datasheet",
    r"\bspecfication\b": "specification",
    r"\bspecfications\b": "specifications",
    r"\brecomandation\b": "recommendation",
    r"\brecomended\b": "recommended",
    r"\brequirment\b": "requirement",
    r"\brequirments\b": "requirements",
    r"\bconsumbles\b": "consumables",
    r"\bconsumebles\b": "consumables",
    r"\bnegosition\b": "negotiation",

    # Malayalam-English (Manglish) composite translations to standard terms
    r"\boru\s+photo\s+(?:printer|peinter)\s+venam\b": "I need a photo printer",
    r"\bphoto\s+(?:printer|peinter)\s+venam\b": "I need a photo printer",
    r"\boru\s+(?:printer|peinter)\s+venam\b": "I need a printer",
    r"\bnamaskaram\b": "hello",
    r"\bsukhamano\b": "hello how are you",
    r"\bnanni\b": "thank you",
    r"\bprinter venam\b": "I need a printer",
    r"\baavashyamund\b": "needed",
    r"\baavashyam\b": "need",
    r"\bvaangan\b": "to buy",
    r"\bedukkan\b": "to take",
    r"\bethra price(?: aakum)?\b": "what is the price",
    r"\bethraya(?:nu)? vila\b": "what is the price",
    r"\bvila ethrayanu\b": "what is the price",
    r"\bethra cost\b": "what is the cost",
    r"\bethra aakum\b": "how much will it cost",
    r"\bnalla photo printer eathaanu\b": "which is the best photo printer",
    r"\bnalla printer eathaanu\b": "which is the best printer",
    r"\beathaanu nallath(?:u)?\b": "which is best",
    r"\bnalla\b": "good",
    r"\bnallath(?:u)?\b": "good",
    r"\bcheyyanulla printer\b": "printer for",
    r"\bcheyyan ulla printer\b": "printer for",
    r"\bcheyyan\b": "to do",
    r"\bprint cheyyan\b": "to print",
    r"\bparayu\b": "tell me",
    r"\bparayamo\b": "can you tell me",
    r"\bparanju tharumo\b": "can you explain",
    r"\bkurachu tharumo\b": "can you give discount",
    r"\bkurakko\b": "reduce price",
    r"\bdiscount kittumo\b": "can I get a discount",
    r"\bdiscount undo\b": "is there a discount",
    r"\bkurakkan pattumo\b": "can you reduce price",
    r"\bkurachu\b": "little less",
    r"\bpaper kittumo\b": "is paper available",
    r"\bpaper kitto\b": "is paper available",
    r"\bink kittumo\b": "is ink available",
    r"\bcartridge undo\b": "is cartridge available",
    r"\bscanner undo\b": "is scanner available",
    r"\bscanner inda\b": "is scanner available",
    r"\bithu nallathano\b": "is this good",
    r"\bith nallathano\b": "is this good",
    r"\binkjet aano\b": "is it inkjet",
    r"\binkjet aano ithu\b": "is this an inkjet",
    r"\bithinte features enthanu\b": "what are its features",
    r"\bfeatures enthokke und\b": "what features does it have",
    r"\benthokke und\b": "what all are there",
    r"\benthanu\b": "what is",
    r"\bentha\b": "what is",
    r"\bithu\b": "this",
    r"\beathaanu\b": "which is",
    r"\bvadiya printer\b": "large format printer",
    r"\bvaliya printer\b": "large format printer",
    r"\bcheriya printer\b": "compact small printer",
    r"\bevideyanu\b": "where is",
    r"\bevidaya\b": "where is",
    r"\beppozhanu open\b": "when is it open",
    r"\bonnude parayamo\b": "can you repeat",
}

# Canonical entity normalization mappings
SIZE_CANONICAL = [
    (r"\b(?:24\s*(?:inch|in|\")|a[\s-]?1)\b", "24-inch (A1)"),
    (r"\b(?:36\s*(?:inch|in|\")|a[\s-]?0)\b", "36-inch (A0)"),
    (r"\b(?:44\s*(?:inch|in|\"))\b", "44-inch"),
    (r"\b(?:a[\s-]?3\+?|13\s*(?:inch|in|\"))\b", "13-inch (A3+)"),
    (r"\b(?:a[\s-]?2\+?|17\s*(?:inch|in|\"))\b", "17-inch (A2+)"),
    (r"\b(?:a[\s-]?4)\b", "A4"),
    (r"\b(?:4\s*(?:x|\*)\s*6)\b", "4x6 inches"),
    (r"\b(?:6\s*(?:x|\*)\s*8)\b", "6x8 inches"),
    (r"\b(?:8\s*(?:x|\*)\s*12)\b", "8x12 inches"),
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
