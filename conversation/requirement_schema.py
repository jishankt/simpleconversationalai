"""
Category-Specific Requirement Schemas.
Enforces hierarchical requirement collection:
  - critical: Must-have gates (cannot recommend without matching)
  - important: Key differentiator fields
  - optional: Nice-to-have features
"""
from typing import Dict, List, Any

REQUIREMENT_SCHEMAS: Dict[str, Dict[str, List[str]]] = {
    "technical_cad": {
        "critical": [
            "print_size",
            "scan_required",
        ],
        "important": [
            "daily_volume",
        ],
        "optional": [
            "connectivity",
            "ink_capacity",
        ]
    },
    "photo_booth": {
        "critical": [
            "print_size",
        ],
        "important": [
            "portability_or_capacity",
        ],
        "optional": [
            "print_volume",
        ]
    },
    "photo_fine_art": {
        "critical": [
            "print_size",
        ],
        "important": [
            "application",
        ],
        "optional": [
            "color_gamut",
            "roll_support",
        ]
    },
    "office_enterprise": {
        "critical": [
            "daily_volume",
        ],
        "important": [
            "speed",
            "multifunction",
        ],
        "optional": [
            "duplex",
            "network",
        ]
    },
    "scanner": {
        "critical": [
            "scanner_type",
        ],
        "important": [
            "document_size",
            "daily_volume",
        ],
        "optional": [
            "duplex",
            "network",
        ]
    },
    "consumable": {
        "critical": [
            "printer_model",
        ],
        "important": [
            "consumable_type",
        ],
        "optional": []
    }
}

QUESTIONS_BY_FIELD: Dict[str, Dict[str, Any]] = {
    "print_size": {
        "question": "What maximum drawing or print size do you need?",
        "pills": ["24-inch (A1)", "36-inch (A0)"]
    },
    "scan_required": {
        "question": "Do you need scanning and copying built in, or printing only?",
        "pills": ["Yes, Need Scanner", "No, Print Only"]
    },
    "daily_volume": {
        "question": "Approximately how many pages or drawings do you produce per day?",
        "pills": ["Low (under 20)", "Medium (20–60)", "High Production (60+)"]
    },
    "portability_or_capacity": {
        "question": "Which is more important for your events—lightweight portability or maximum roll capacity?",
        "pills": ["Portability (under 12 kg)", "High Roll Capacity (700 prints)"]
    },
    "application": {
        "question": "What will you primarily print—exhibition gallery prints, studio portraits, or fine-art canvas?",
        "pills": ["Gallery & Exhibition", "Studio Portraits", "Canvas & Fine Art"]
    },
    "speed": {
        "question": "What print speed does your workgroup require?",
        "pills": ["40 ppm", "55 ppm", "60+ ppm"]
    },
    "multifunction": {
        "question": "Do you require full multifunction (printing, copying, scanning) or dedicated printing only?",
        "pills": ["Full Multifunction (Print/Copy/Scan)", "Print Only"]
    },
    "scanner_type": {
        "question": "Do you need a high-speed sheetfed document scanner or an A3 flatbed scanner?",
        "pills": ["Sheetfed Document Scanner", "A3 Flatbed Scanner"]
    },
    "document_size": {
        "question": "What is your maximum required document size?",
        "pills": ["Standard A4/Legal", "A3 Large Format"]
    },
    "printer_model": {
        "question": "Which printer or scanner model do you need consumables for?",
        "pills": ["Citizen CX-02", "Citizen CY-02", "Epson SC-T3100", "Epson SC-P900", "Epson AM-C4000"]
    },
    "consumable_type": {
        "question": "Which consumable do you need—ink cartridges, maintenance tank, or media roll?",
        "pills": ["Ink Cartridges", "Maintenance Tank", "Paper / Ribbon Roll"]
    }
}

