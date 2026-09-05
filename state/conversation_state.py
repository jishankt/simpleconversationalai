"""
Canonical Conversation State definitions for multi-turn structured sales dialogues.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class CanonicalState:
    session_id: str
    category: Optional[str] = None  # technical_cad | photo_fine_art | office_enterprise | photo_booth | scanner | consumable
    requirements: Dict[str, Any] = field(default_factory=dict)
    # requirements keys:
    # - print_size: "A0" | "A1" | "A4" | "A3" | "4x6"
    # - scan_required: bool
    # - daily_volume: int
    # - color_count: int
    # - connectivity: str
    # - printer_model: str
    active_product: Optional[Dict[str, Any]] = None
    candidate_products: List[Dict[str, Any]] = field(default_factory=list)
    active_printer_for_consumables: Optional[str] = None
    awaiting_field: Optional[str] = None  # print_size | scan_required | daily_volume | printer_model | category
    history_turns: List[Dict[str, Any]] = field(default_factory=list)
    last_dialogue_act: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "category": self.category,
            "requirements": self.requirements,
            "active_product": self.active_product,
            "candidate_products": self.candidate_products,
            "active_printer_for_consumables": self.active_printer_for_consumables,
            "awaiting_field": self.awaiting_field,
            "last_dialogue_act": self.last_dialogue_act,
            "turn_count": len(self.history_turns)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalState":
        return cls(
            session_id=data.get("session_id", ""),
            category=data.get("category"),
            requirements=data.get("requirements", {}),
            active_product=data.get("active_product"),
            candidate_products=data.get("candidate_products", []),
            active_printer_for_consumables=data.get("active_printer_for_consumables"),
            awaiting_field=data.get("awaiting_field"),
            history_turns=data.get("history_turns", []),
            last_dialogue_act=data.get("last_dialogue_act")
        )

    def reset_category(self, new_category: str):
        """Resets category-specific requirements when user switches topic."""
        self.category = new_category
        self.requirements = {}
        self.active_product = None
        self.candidate_products = []
        self.awaiting_field = None
