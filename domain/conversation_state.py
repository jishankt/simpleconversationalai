"""
Enhanced Conversation State for Kepler Tech Conversational AI.
Extends the original CanonicalState with customer memory, frustration tracking,
pending question resumption, and richer conversation control fields.

Backward-compatible with the existing CanonicalState.to_dict() / from_dict() API.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class ConversationState:
    """Complete conversation state that preserves customer memory across social interruptions."""
    session_id: str

    # ── Customer Memory ──────────────────────────────────────────────────
    customer_name: Optional[str] = None
    preferred_language: str = "en"

    # ── Conversation Control ─────────────────────────────────────────────
    stage: str = "open"  # open | qualifying | recommending | comparing | consumables | supporting | closing
    active_route: Optional[str] = None
    last_intent: Optional[str] = None
    last_dialogue_act: Optional[str] = None
    last_assistant_response: Optional[str] = None
    pending_question: Optional[str] = None  # Question to resume after social interruption
    pending_field: Optional[str] = None  # Field the pending question was asking about
    interrupted_field: Optional[str] = None  # Field that was being asked when user interrupted
    frustration_count: int = 0

    # ── Product Memory ───────────────────────────────────────────────────
    category: Optional[str] = None  # technical_cad | photo_fine_art | office_enterprise | photo_booth | scanner | consumable
    requirements: Dict[str, Any] = field(default_factory=dict)
    candidate_products: List[Dict[str, Any]] = field(default_factory=list)
    active_product: Optional[Dict[str, Any]] = None
    active_product_id: Optional[str] = None
    compared_product_ids: List[str] = field(default_factory=list)
    active_printer_for_consumables: Optional[str] = None

    # ── Operational ──────────────────────────────────────────────────────
    awaiting_field: Optional[str] = None  # print_size | scan_required | daily_volume | printer_model | scanner_type
    history_turns: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    state_version: int = 2  # Version 2 = enhanced state

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict. Backward-compatible with original CanonicalState."""
        return {
            "session_id": self.session_id,
            # Customer
            "customer_name": self.customer_name,
            "preferred_language": self.preferred_language,
            # Control
            "stage": self.stage,
            "active_route": self.active_route,
            "last_intent": self.last_intent,
            "last_dialogue_act": self.last_dialogue_act,
            "last_assistant_response": self.last_assistant_response,
            "pending_question": self.pending_question,
            "pending_field": self.pending_field,
            "frustrated": self.frustration_count,
            # Product
            "category": self.category,
            "requirements": self.requirements,
            "active_product": self.active_product,
            "active_product_id": self.active_product_id,
            "candidate_products": self.candidate_products,
            "active_printer_for_consumables": self.active_printer_for_consumables,
            # Operational
            "awaiting_field": self.awaiting_field,
            "turn_count": self.turn_count or len(self.history_turns),
            "state_version": self.state_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Deserialize from dict. Handles both v1 (CanonicalState) and v2 formats."""
        return cls(
            session_id=data.get("session_id", ""),
            # Customer
            customer_name=data.get("customer_name"),
            preferred_language=data.get("preferred_language", "en"),
            # Control
            stage=data.get("stage", "open"),
            active_route=data.get("active_route"),
            last_intent=data.get("last_intent"),
            last_dialogue_act=data.get("last_dialogue_act"),
            last_assistant_response=data.get("last_assistant_response"),
            pending_question=data.get("pending_question"),
            pending_field=data.get("pending_field"),
            frustration_count=data.get("frustrated", data.get("frustration_count", 0)),
            # Product
            category=data.get("category"),
            requirements=data.get("requirements", {}),
            active_product=data.get("active_product"),
            active_product_id=data.get("active_product_id"),
            candidate_products=data.get("candidate_products", []),
            active_printer_for_consumables=data.get("active_printer_for_consumables"),
            # Operational
            awaiting_field=data.get("awaiting_field"),
            history_turns=data.get("history_turns", []),
            turn_count=data.get("turn_count", 0),
            state_version=data.get("state_version", 2),
        )

    # ── State Mutations ──────────────────────────────────────────────────

    def reset_category(self, new_category: str):
        """Resets category-specific requirements when user switches topic."""
        self.category = new_category
        self.requirements = {}
        self.active_product = None
        self.active_product_id = None
        self.candidate_products = []
        self.compared_product_ids = []
        self.awaiting_field = None
        self.pending_question = None
        self.pending_field = None

    def save_pending_question(self, question: str, field_name: str):
        """Save the current question so it can be resumed after a social interruption."""
        self.pending_question = question
        self.pending_field = field_name

    def consume_pending_question(self) -> Optional[str]:
        """Return and clear the pending question (used after handling a social interruption)."""
        q = self.pending_question
        self.pending_question = None
        self.pending_field = None
        return q

    def record_frustration(self):
        """Increment frustration counter when user expresses annoyance."""
        self.frustration_count += 1

    def increment_turn(self):
        """Increment turn counter."""
        self.turn_count += 1
