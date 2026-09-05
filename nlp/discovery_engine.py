"""
Consultative Needs Discovery & Multi-Factor Satisfaction Scoring Engine for Kepler Tech LLC.
Intercepts broad/ambiguous requests (e.g. "I want ink", "need a printer", "paper", "scanners")
and engages the customer with consultative qualification questions matching the salesai conversational flow.
"""
import re
from typing import Tuple, Optional, Dict, Any, List

BROAD_CATEGORY_PATTERNS = {
    "ink": [
        r"^(?:no\s+)?(?:do\s+you\s+have\s+|i\s+need\s+|i\s+want\s+|show\s+me\s+|give\s+me\s+|wanna\s+)?(?:some\s+)?(?:inks?|cartridges?|bottles?|toners?)\s*\??$",
    ],
    "printer": [
        r"(?:new\s+printing\s+shop|new\s+shop|printing\s+business|new\s+business|event\s+setup|my\s+business)",
        r"(?:recommend|need|want|looking\s+for|trying\s+to\s+buy|buy|purchase|get|show\s+me|check).*(?:new\s+|large\s+format\s+)?(?:printers?|plotters?|machines?)",
        r"^(?:printers?|plotters?|machines?)$",
        r"^(?:i\s+want\s+printers?|need\s+printers?|looking\s+for\s+printers?)$"
    ],
    "paper": [
        r"^(?:no\s+)?(?:do\s+you\s+have\s+|i\s+need\s+|i\s+want\s+|show\s+me\s+|give\s+me\s+|wanna\s+)?(?:some\s+)?(?:papers?|canvas|canvas\s+rolls?|rolls?|media)\s*\??$",
    ],
    "scanner": [
        r"(?:buy|purchase|need|want|looking\s+for|trying\s+to\s+buy|show\s+me|get|check|have)?.*(?:scanners?)\s*\??$",
    ]
}

SPECIFIC_EXCLUSIONS = [
    # If the user mentioned a specific model name/code or specific ink color, it's NOT a broad query
    r"\b(?:sc-p\d+[a-z0-9]*|sc-t\d+[a-z0-9]*|sc-f\d+[a-z0-9]*|p\d{3,5}[a-z0-9]*|t\d{3,5}[a-z0-9]*|f\d{3,4}[a-z0-9]*|cx-02[a-z0-9]*|cz-01|cy-02|wf-[a-z0-9]+|am-[a-z0-9]+|em-[a-z0-9]+|ds-[a-z0-9]+|es-[a-z0-9]+|12000xl|c13t\d+|t800\d+|photo\s+black|matte\s+black|cyan|magenta|yellow|700ml|350ml|110ml|1\.6l)\b",
    # Do not intercept specific pill choices from discovery prompts
    r"(?:a4\s+business|a3\s+large\s+format|high-speed\s+document|flatbed|artistic\s+canvas|fine\s+art\s+smooth|photo\s+gloss)"
]

CATEGORY_DISCOVERY_PROMPTS = {
    "ink": (
        "Sure! We carry the complete range of genuine Epson UltraChrome and WorkForce inks. 🖨️\n\n"
        "What printer model do you have? Which color(s) or cartridge size are you looking for?\n\n"
        "[Options: SureColor SC-P Inks | WorkForce Pro Inks | EcoTank / Dye-Sub | Maintenance Box]"
    ),
    "printer": (
        "Welcome to Kepler Tech! 🖨️ We distribute Epson Large Format & Citizen Photo Printers across the UAE.\n\n"
        "Which printing category best fits your requirement?\n\n"
        "• 📐 **Technical & CAD/GIS** (Epson SC-T series — 24\" to 44\" for architectural drawings)\n"
        "• 🏢 **Office & Enterprise** (Epson WorkForce A4/A3 high-speed business MFPs)\n"
        "• 📸 **Photo Booth & Events** (Citizen compact dye-sub photo printers)\n"
        "• 🎨 **Fine Art & Photography** (Epson SC-P series — 12-color 99% Pantone)\n\n"
        "[Options: Technical / CAD | Office & Enterprise | Photo Booth | Fine Art & Photo]"
    ),
    "paper": (
        "We stock genuine Innova fine art papers and Korejet canvas rolls! 🎨\n\n"
        "What media type are you looking for?\n\n"
        "[Options: Artistic Canvas Rolls | Fine Art Smooth Paper | Photo Gloss / Luster]"
    ),
    "scanner": (
        "We carry high-speed Epson business and flatbed scanners. 📄\n\n"
        "What document size do you need to scan?\n\n"
        "[Options: A4 Business Scanner | A3 Large Format Flatbed | High-Speed Document Scanner]"
    )
}

def is_broad_query(query: str) -> Tuple[bool, Optional[str]]:
    """Checks if a user query is a broad/unspecified category request."""
    if not query:
        return False, None
    q = query.strip().lower()
    
    # If specific model or SKU is present, do not intercept as broad
    for excl in SPECIFIC_EXCLUSIONS:
        if re.search(excl, q):
            return False, None

    # Strip greeting prefix if attached to the sentence
    q_norm = re.sub(r'^(?:hi|hello|hey|greetings|good\s+morning|good\s+afternoon|good\s+evening)[,\s!\-]+', '', q).strip()

    for cat, patterns in BROAD_CATEGORY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q_norm):
                return True, cat
    return False, None

def get_discovery_question(category: str) -> str:
    """Returns the consultative qualification question for a broad category."""
    return CATEGORY_DISCOVERY_PROMPTS.get(category, "Could you specify the model or specifications you are looking for?")
