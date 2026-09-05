"""
Tool Executor Module for Kepler Tech Conversational AI.
Executes dynamic catalog tools and formats zero-hallucination cards and context.
Zero hardcoding: all data is resolved dynamically from data/products.json.
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from rag.retriever import rag_retriever

PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "products.json")


class CatalogToolExecutor:
    def __init__(self, products_path: str = PRODUCTS_PATH):
        self.products_path = products_path
        self.products = []
        self.sku_map: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.products_path):
            with open(self.products_path, "r", encoding="utf-8") as f:
                self.products = json.load(f)
            self.sku_map = {str(p.get("sku", "")).upper(): p for p in self.products if p.get("sku")}

    def format_card(self, prod: Dict[str, Any], card_type: str = "hardware") -> Dict[str, Any]:
        """Formats a catalog product into a clean card for frontend display."""
        name = prod.get("name", "")
        sku = prod.get("sku", "VERIFIED-KEPLER")
        image_url = prod.get("image_url") or prod.get("image")
        if not image_url and prod.get("images"):
            image_url = prod["images"][0]
        if not image_url:
            image_url = "https://www.keplertechllc.com/wp-content/uploads/2023/05/Kepler-Logo-.png"

        product_url = prod.get("website_url") or prod.get("web_url") or prod.get("url") or prod.get("source_url")
        if not product_url:
            slug = re.sub(r"[^\w\s-]", "", name.lower()).strip()
            slug = re.sub(r"[\s_]+", "-", slug)
            product_url = f"https://www.keplertechllc.com/product/{slug}/"

        tags = prod.get("tags", [])
        badge = "Hardware" if card_type == "hardware" else "Consumable"
        if any("Ink" in t for t in tags):
            badge = "UltraChrome Ink"
        elif any("Maintenance" in t for t in tags):
            badge = "Maintenance Tank"
        elif any("Media" in t for t in tags) or "media" in name.lower():
            badge = "Print Media"

        return {
            "id": prod.get("_id") or prod.get("sku"),
            "name": name,
            "sku": sku,
            "image": image_url,
            "image_url": image_url,
            "url": product_url,
            "source_url": product_url,
            "badge": badge,
            "card_type": card_type,
            "description": prod.get("description") or f"Official verified {badge.lower()} from Kepler Tech LLC.",
            "category": prod.get("category", "Hardware"),
            "has_consumables": (card_type == "hardware")
        }

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches and executes the designated tool dynamically."""
        if tool_name == "search_catalog":
            return self._search_catalog(
                query=arguments.get("query", ""),
                category=arguments.get("category"),
                limit=arguments.get("limit", 4)
            )
        elif tool_name == "get_product_specs":
            return self._get_product_specs(
                identifier=arguments.get("product_identifier", "")
            )
        elif tool_name == "get_compatible_consumables":
            return self._get_compatible_consumables(
                printer_identifier=arguments.get("printer_identifier", ""),
                limit=arguments.get("limit", 6)
            )
        elif tool_name == "compare_products":
            return self._compare_products(
                model_a=arguments.get("model_a", ""),
                model_b=arguments.get("model_b", "")
            )
        elif tool_name == "ask_consultative_question":
            return {
                "success": True,
                "action": "consultative_question",
                "question": arguments.get("question", ""),
                "suggested_pills": arguments.get("suggested_pills", []),
                "product_cards": [],
                "consumable_cards": []
            }
        else:
            return {"success": False, "error": f"Unknown tool '{tool_name}'"}

    def _search_catalog(self, query: str, category: Optional[str] = None, limit: int = 4) -> Dict[str, Any]:
        """Searches catalog using hybrid search and returns clean cards."""
        cat_filter = None if category in (None, "All") else category
        raw_results = rag_retriever.search(query=query, category=cat_filter, limit=limit)

        cards = []
        for r in raw_results:
            card_type = "consumable" if r.get("category") in ["Consumables", "Ink Cartridge", "Media"] else "hardware"
            cards.append(self.format_card(r, card_type=card_type))

        return {
            "success": True,
            "count": len(cards),
            "results": raw_results,
            "product_cards": cards if any(c["card_type"] == "hardware" for c in cards) else [],
            "consumable_cards": cards if any(c["card_type"] == "consumable" for c in cards) else []
        }

    def _get_product_specs(self, identifier: str) -> Dict[str, Any]:
        """Finds a product and extracts detailed specs."""
        prod = rag_retriever.get_by_sku(identifier) or rag_retriever.get_by_name(identifier)
        if not prod:
            # Fallback search top match
            s = rag_retriever.search(identifier, limit=1)
            if s:
                prod = s[0]

        if not prod:
            return {"success": False, "error": f"Product '{identifier}' not found in catalog."}

        card = self.format_card(prod, card_type="hardware")
        return {
            "success": True,
            "product": prod,
            "product_cards": [card],
            "specs_text": (
                f"Model: {prod.get('name')}\n"
                f"SKU: {prod.get('sku')}\n"
                f"Category: {prod.get('category')}\n"
                f"Description: {prod.get('description')}\n"
                f"Print Width: {prod.get('width', 'N/A')}\n"
                f"Print Speed: {prod.get('speed', 'N/A')}\n"
                f"Technology: {prod.get('ink_technology', 'N/A')}\n"
                f"Intended Application: {prod.get('intended_usage', 'N/A')}\n"
                f"Official URL: {card.get('url')}"
            )
        }

    def _get_compatible_consumables(self, printer_identifier: str, limit: int = 6) -> Dict[str, Any]:
        """Finds genuine consumables dynamically linked to a printer model."""
        target_printer = None
        q_raw = printer_identifier.strip()
        q_clean = q_raw.lower()

        # Reject explicitly unverified / competitor brands
        if any(unv in q_clean for unv in ["canon", "hp", "designjet", "brother", "xerox", "ricoh"]):
            return {
                "success": True,
                "printer_name": q_raw,
                "count": 0,
                "consumable_cards": [],
                "consumables_summary": ""
            }

        # 1. Exact SKU
        if q_raw.upper() in self.sku_map:
            target_printer = self.sku_map[q_raw.upper()]

        # 2. Match by specific model token
        if not target_printer:
            GENERIC_WORDS = {"epson", "surecolor", "workforce", "printer", "scanner", "series", "large", "format", "color", "pro", "the", "for", "with"}
            specific_tokens = [t for t in re.findall(r"[a-z0-9]+", q_clean) if len(t) >= 3 and t not in GENERIC_WORDS]
            
            # Prioritize matching printer category products
            candidate_printers = [p for p in self.products if "printer" in p.get("category", "").lower()]
            if not candidate_printers:
                candidate_printers = self.products

            for t in sorted(specific_tokens, key=lambda x: len(x), reverse=True):
                pattern = r'(?:\b|_|-)' + re.escape(t) + r'(?:\b|_|-|\s|$)(?!\d)'
                for p in candidate_printers:
                    p_name = p.get("name", "").lower().replace("\u200b", " ")
                    p_sku = str(p.get("sku", "")).lower()
                    if re.search(pattern, p_name) or t == p_sku:
                        target_printer = p
                        break
                if target_printer:
                    break

        # If no target printer recognized from Kepler Tech catalog, return empty to prevent hallucination
        if not target_printer:
            return {
                "success": True,
                "printer_name": q_raw,
                "count": 0,
                "consumable_cards": [],
                "consumables_summary": ""
            }

        consumable_items = []
        seen = set()

        # Look up explicit consumables SKU links from printer metadata
        if target_printer.get("consumables"):
            raw_skus = target_printer["consumables"]
            # Separate inks and maintenance tanks so customer sees both
            mbox_skus = [s for s in raw_skus if any(s.upper().startswith(pfx) for pfx in ["C12C", "C13S", "C13T671"])]
            ink_skus = [s for s in raw_skus if s not in mbox_skus]
            
            # Include maintenance box first or alongside inks
            ordered_skus = (mbox_skus[:1] + ink_skus) if mbox_skus else raw_skus

            for c_sku in ordered_skus:
                c_sku_up = str(c_sku).upper()
                if c_sku_up in self.sku_map and c_sku_up not in seen:
                    seen.add(c_sku_up)
                    consumable_items.append(self.sku_map[c_sku_up])
                    if len(consumable_items) >= limit:
                        break

        # Dynamic token match over catalog if more needed
        if len(consumable_items) < limit:
            q_name = target_printer.get("name", q_raw).lower()
            tokens = [t for t in re.findall(r"[a-z0-9]+", q_name) if len(t) >= 3]
            clean_tokens = [t for t in tokens if t not in ["epson", "surecolor", "printer", "workforce", "color", "scanner", "plotter", "large", "format"]]

            for p in self.products:
                sku_up = str(p.get("sku", "")).upper()
                if sku_up in seen:
                    continue
                p_name_norm = re.sub(r"[\s\-_\u200b]", "", p.get("name", "").lower())
                p_desc_norm = re.sub(r"[\s\-_\u200b]", "", p.get("description", "").lower())
                p_tags_norm = re.sub(r"[\s\-_\u200b]", "", " ".join(p.get("tags", [])).lower())

                is_cons = any(k in p_name_norm or k in p_desc_norm for k in ["ink", "cartridge", "tank", "maintenance", "ribbon", "media", "paper"])
                if is_cons and any(t in p_name_norm or t in p_desc_norm or t in p_tags_norm for t in clean_tokens):
                    seen.add(sku_up)
                    consumable_items.append(p)
                    if len(consumable_items) >= limit:
                        break

        consumable_cards = [self.format_card(c, card_type="consumable") for c in consumable_items]
        p_name = target_printer.get("name") if target_printer else q_raw

        return {
            "success": True,
            "printer_name": p_name,
            "count": len(consumable_cards),
            "consumable_cards": consumable_cards,
            "consumables_summary": ", ".join([c["name"] for c in consumable_cards])
        }

    def _compare_products(self, model_a: str, model_b: str) -> Dict[str, Any]:
        """Compares two models from the live catalog."""
        prod_a = rag_retriever.get_by_name(model_a) or rag_retriever.get_by_sku(model_a)
        if not prod_a:
            s_a = rag_retriever.search(model_a, limit=1)
            prod_a = s_a[0] if s_a else None

        prod_b = rag_retriever.get_by_name(model_b) or rag_retriever.get_by_sku(model_b)
        if not prod_b:
            s_b = rag_retriever.search(model_b, limit=1)
            prod_b = s_b[0] if s_b else None

        if not prod_a or not prod_b:
            return {"success": False, "error": f"Could not find both products for comparison ({model_a}, {model_b})."}

        cards = [self.format_card(prod_a, card_type="hardware"), self.format_card(prod_b, card_type="hardware")]
        return {
            "success": True,
            "product_a": prod_a,
            "product_b": prod_b,
            "product_cards": cards,
            "comparison_data": {
                "model_a": {
                    "name": prod_a.get("name"),
                    "category": prod_a.get("category"),
                    "width": prod_a.get("width", "Standard"),
                    "speed": prod_a.get("speed", "N/A"),
                    "intended": prod_a.get("intended_usage", "Professional production")
                },
                "model_b": {
                    "name": prod_b.get("name"),
                    "category": prod_b.get("category"),
                    "width": prod_b.get("width", "Standard"),
                    "speed": prod_b.get("speed", "N/A"),
                    "intended": prod_b.get("intended_usage", "Professional production")
                }
            }
        }


# Global singleton instance
catalog_tool_executor = CatalogToolExecutor()
