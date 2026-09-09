"""
Brochure and Datasheet Resolver for Kepler Tech Conversational AI.
Loads verified product data sheets from data/verified_brochures.json
and provides direct PDF links to customers.
"""

import json
import os
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("catalog.brochure_resolver")

BROCHURES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "verified_brochures.json")


class BrochureResolver:
    def __init__(self, json_path: str = BROCHURES_PATH):
        self.json_path = json_path
        self.brochures: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    self.brochures = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {self.json_path}: {e}")

    def get_brochure(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Finds a verified brochure by model code, alias, id, or product name."""
        if not identifier:
            return None
        q = identifier.strip().lower()
        q_norm = re.sub(r"[\s\-_]+", "", q)

        # 1. Exact ID match
        if q in self.brochures:
            return self.brochures[q]

        # 2. Match aliases or normalized ID
        for pid, data in self.brochures.items():
            pid_norm = re.sub(r"[\s\-_]+", "", pid)
            if q_norm == pid_norm or q_norm in pid_norm or pid_norm in q_norm:
                return data
            for alias in data.get("aliases", []):
                alias_norm = re.sub(r"[\s\-_]+", "", alias.lower())
                if q_norm == alias_norm or alias_norm in q_norm or q_norm in alias_norm:
                    return data
            name_norm = re.sub(r"[\s\-_]+", "", data.get("name", "").lower())
            if q_norm in name_norm or name_norm in q_norm:
                return data

        return None

    def find_brochures_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extracts any mentioned products from text and returns their brochures."""
        if not text:
            return []
        text_l = text.lower()
        found = []
        seen_pdfs = set()

        for pid, data in self.brochures.items():
            matched = False
            for alias in data.get("aliases", []):
                # Word boundary match for alias
                pattern = r"(?:\b|_|-)" + re.escape(alias.lower()) + r"(?:\b|_|-)"
                if re.search(pattern, text_l):
                    matched = True
                    break
            if not matched and pid.lower() in text_l:
                matched = True

            if matched:
                pdf = data.get("pdf")
                if pdf and pdf not in seen_pdfs:
                    seen_pdfs.add(pdf)
                    found.append(data)

        return found

    def resolve_for_conversation(self, state, raw_message: str = "") -> List[Dict[str, Any]]:
        """
        Determines the relevant brochures based on user message, recent comparison,
        candidate products, or active product in state.
        """
        # 1. Check if user explicitly mentioned models in raw_message
        found = self.find_brochures_from_text(raw_message)
        if found:
            return found

        # 2. Check recent compared products
        if hasattr(state, "compared_product_ids") and state.compared_product_ids:
            compared_brochures = []
            for cid in state.compared_product_ids:
                b = self.get_brochure(cid)
                if b and b.get("pdf") not in [x.get("pdf") for x in compared_brochures]:
                    compared_brochures.append(b)
            if compared_brochures:
                return compared_brochures

        # 3. Check candidate products from current or previous turn
        if state.candidate_products:
            cand_brochures = []
            for p in state.candidate_products:
                name = p.get("name") or p.get("title") or p.get("id") or ""
                b = self.get_brochure(name) or self.get_brochure(p.get("id", "")) or self.get_brochure(p.get("sku", ""))
                if b and b.get("pdf") not in [x.get("pdf") for x in cand_brochures]:
                    cand_brochures.append(b)
            if cand_brochures:
                return cand_brochures

        # 4. Check active product
        if state.active_product:
            act_name = state.active_product.get("name") or state.active_product.get("id") or ""
            b = self.get_brochure(act_name) or self.get_brochure(state.active_product.get("id", ""))
            if b:
                return [b]

        # 5. Check recent assistant turn for mentioned models
        if state.history_turns:
            for turn in reversed(state.history_turns[-3:]):
                content = turn.get("content", "")
                found = self.find_brochures_from_text(content)
                if found:
                    return found

        return []


brochure_resolver = BrochureResolver()
