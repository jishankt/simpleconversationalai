"""
Requirement Updater & Conversation State Manager.
Updates CanonicalState when user answers, corrects, switches topic, or references items.
"""
from typing import Dict, Any, Optional
from state.conversation_state import CanonicalState
from nlp.dialogue_act import (
    ACT_ANSWERING_QUESTION,
    ACT_CORRECTING_ANSWER,
    ACT_CHANGING_TOPIC,
    ACT_REFERENCING_ITEM,
    ACT_CHANGING_REQUIREMENT
)


class RequirementUpdater:
    def __init__(self, consumables_engine=None):
        self.consumables_engine = consumables_engine

    def update_state(self, state: CanonicalState, act_info: Dict[str, Any], raw_text: str) -> CanonicalState:
        act = act_info.get("act")
        params = act_info.get("params", {})
        state.last_dialogue_act = act

        # 1. Topic Switching (e.g., "actually now I need a photo booth printer")
        if act == ACT_CHANGING_TOPIC:
            new_cat = params.get("target_category")
            if new_cat:
                state.reset_category(new_cat)
            return state

        # 2. Corrections (e.g. "actually A1", "no scanner")
        if act == ACT_CORRECTING_ANSWER:
            field = params.get("field")
            val = params.get("value")
            if field and val is not None:
                state.requirements[field] = val
                # Clear active candidate if requirement fundamentally changed
                state.active_product = None
                state.candidate_products = []
            return state

        # 3. Answering Question (e.g. "A0", "yes", "around 60", "scanner_type")
        if act == ACT_ANSWERING_QUESTION:
            field = params.get("field")
            val = params.get("value")
            if field and val is not None:
                state.requirements[field] = val
                if field == state.awaiting_field:
                    state.awaiting_field = None
                state.active_product = None
                state.candidate_products = []
            return state

        # 4. Item Referencing (e.g., "the first one", "the second one", "T5400M")
        if act == ACT_REFERENCING_ITEM:
            ref_index = params.get("item_ref")
            model_code = params.get("model_code")

            if ref_index is not None and 0 <= ref_index < len(state.candidate_products):
                state.active_product = state.candidate_products[ref_index]
            elif model_code and self.consumables_engine:
                found = [p for p in self.consumables_engine.products if model_code.lower() in p.get("name", "").lower() or model_code.lower() in p.get("sku", "").lower()]
                if found:
                    state.active_product = found[0]

            return state

        # 5. Requirement change / Next option (e.g., "show another one")
        if act == ACT_CHANGING_REQUIREMENT:
            if state.candidate_products and len(state.candidate_products) > 1:
                # Rotate active product to next candidate
                curr_idx = 0
                if state.active_product:
                    for idx, cand in enumerate(state.candidate_products):
                        if cand.get("sku") == state.active_product.get("sku"):
                            curr_idx = idx
                            break
                next_idx = (curr_idx + 1) % len(state.candidate_products)
                state.active_product = state.candidate_products[next_idx]

            return state

        return state
