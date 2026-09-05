"""
AI Tool Definitions and Registry for Kepler Tech Conversational Assistant.
Defines dynamic tool specifications for LLM function calling without hardcoding.
"""

from typing import List, Dict, Any

CATALOG_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": (
                "Searches Kepler Tech's live 792-item catalog for printers, scanners, media, "
                "or consumables matching customer requirements, application keywords, or print volume."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords describing the user need, model code, print size (e.g. 'A0 CAD plotter', 'DS-770 II', '4x6 photo booth printer')."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Printer", "Scanner", "Consumables", "Media", "Software", "All"],
                        "description": "Optional category filter to isolate hardware from consumables."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of candidate product cards to return (default 4)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_specs",
            "description": (
                "Retrieves complete technical specifications, dimensions, features, official image, "
                "and page URL for a specific product name or SKU from the verified catalog."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_identifier": {
                        "type": "string",
                        "description": "The exact SKU (e.g. 'C11CF11302A1') or model name (e.g. 'SC-T3100', 'DS-900WN', 'CX-02')."
                    }
                },
                "required": ["product_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_compatible_consumables",
            "description": (
                "Discovers verified compatible inks, maintenance boxes, and media directly from the "
                "catalog relationship graph for a given printer model or SKU."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "printer_identifier": {
                        "type": "string",
                        "description": "The printer model name or SKU (e.g. 'SC-T3100', 'SC-P700', 'WF-C5790', 'SC-F100', 'Citizen CZ-01')."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of consumable cards to retrieve (default 6)."
                    }
                },
                "required": ["printer_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": (
                "Extracts and compares specifications, print width, resolution, speed, and intended usage "
                "between two hardware models from the catalog."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model_a": {
                        "type": "string",
                        "description": "Name or SKU of first product (e.g. 'Epson SC-T3100')."
                    },
                    "model_b": {
                        "type": "string",
                        "description": "Name or SKU of second product (e.g. 'Epson SC-T5400M')."
                    }
                },
                "required": ["model_a", "model_b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_consultative_question",
            "description": (
                "Asks a clarifying consultative question with structured suggestion chips when user requirements "
                "are too broad to make a pinpoint recommendation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The consultative question to prompt the customer."
                    },
                    "suggested_pills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of interactive button choices for the user (e.g. ['A0', 'A1', 'A3+'] or ['High-Speed Document Scanners', 'A3 Large Format Flatbed', 'Business Scanners'])."
                    }
                },
                "required": ["question", "suggested_pills"]
            }
        }
    }
]


def format_tools_for_prompt() -> str:
    """Formats tools documentation into clear JSON schema instructions for the AI model."""
    lines = ["Available Tools (you can call one tool if you need to fetch data or qualify customer):"]
    for t in CATALOG_TOOLS:
        fn = t["function"]
        lines.append(f"- {fn['name']}: {fn['description']}")
        lines.append(f"  Parameters: {fn['parameters']['properties']}")
    return "\n".join(lines)
