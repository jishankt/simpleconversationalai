"""
Domain Types for Kepler Tech Conversational AI.
Defines canonical enums, dataclasses, and type contracts used across the system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


# ---------------------------------------------------------------------------
# Intent Taxonomy
# ---------------------------------------------------------------------------
class Intent(str, Enum):
    """All recognized customer intents. The LLM must return one of these."""
    GREETING = "greeting"
    CUSTOMER_INTRODUCTION = "customer_introduction"
    SMALL_TALK = "small_talk"
    POSITIVE_FEEDBACK = "positive_feedback"
    NEGATIVE_FEEDBACK = "negative_feedback"
    FRUSTRATION = "frustration"
    CORRECTION = "correction"
    CONFIRMATION = "confirmation"
    REJECTION = "rejection"
    CONVERSATION_ENDING = "conversation_ending"
    LANGUAGE_CHANGE = "language_change"
    PRODUCT_DISCOVERY = "product_discovery"
    PRODUCT_QUESTION = "product_question"
    PRODUCT_COMPARISON = "product_comparison"
    CONSUMABLES_QUERY = "consumables_query"
    BUSINESS_INFORMATION = "business_information"
    TROUBLESHOOTING = "troubleshooting"
    UNCLEAR = "unclear"
    OUT_OF_SCOPE = "out_of_scope"


# Grouped intent sets for decision engine routing
SOCIAL_INTENTS = frozenset({
    Intent.GREETING,
    Intent.CUSTOMER_INTRODUCTION,
    Intent.SMALL_TALK,
    Intent.POSITIVE_FEEDBACK,
    Intent.NEGATIVE_FEEDBACK,
    Intent.FRUSTRATION,
    Intent.CONVERSATION_ENDING,
})

PRODUCT_INTENTS = frozenset({
    Intent.PRODUCT_DISCOVERY,
    Intent.PRODUCT_QUESTION,
    Intent.PRODUCT_COMPARISON,
    Intent.CONSUMABLES_QUERY,
})


# ---------------------------------------------------------------------------
# Dialogue Act (what the user is doing in the conversation)
# ---------------------------------------------------------------------------
class DialogueAct(str, Enum):
    INFORMING = "informing"
    REQUESTING = "requesting"
    QUESTIONING = "questioning"
    CORRECTING = "correcting"
    CONFIRMING = "confirming"
    REJECTING = "rejecting"
    GREETING = "greeting"
    THANKING = "thanking"
    COMPLAINING = "complaining"
    CLARIFYING = "clarifying"


# ---------------------------------------------------------------------------
# Conversation Stage
# ---------------------------------------------------------------------------
class ConversationStage(str, Enum):
    OPEN = "open"
    QUALIFYING = "qualifying"
    RECOMMENDING = "recommending"
    COMPARING = "comparing"
    CONSUMABLES = "consumables"
    SUPPORTING = "supporting"
    CLOSING = "closing"


# ---------------------------------------------------------------------------
# Route Names (used by decision engine)
# ---------------------------------------------------------------------------
class RouteName(str, Enum):
    SOCIAL = "social"
    QUALIFICATION = "qualification"
    PRODUCT = "product"
    COMPARISON = "comparison"
    CONSUMABLES = "consumables"
    SUPPORT = "support"
    BUSINESS_INFO = "business_info"
    CLARIFICATION = "clarification"


# ---------------------------------------------------------------------------
# Intercept Result (from deterministic interceptor)
# ---------------------------------------------------------------------------
@dataclass
class InterceptResult:
    """Result from the deterministic interceptor that runs before any LLM call."""
    matched: bool
    intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    response: Optional[str] = None
    should_continue: bool = True  # False = stop here, True = pass to LLM
    suggested_chips: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM Understanding Result
# ---------------------------------------------------------------------------
@dataclass
class LLMUnderstanding:
    """Structured output from the local LLM understanding module."""
    intent: Intent = Intent.UNCLEAR
    dialogue_act: DialogueAct = DialogueAct.INFORMING
    product_related: bool = False
    confidence: float = 0.0
    sentiment: str = "neutral"
    language: str = "en"
    entities: Dict[str, Any] = field(default_factory=dict)
    requirement_updates: Dict[str, Any] = field(default_factory=dict)
    requested_action: str = "ask_clarification"
    tool_request: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMUnderstanding":
        """Parse from LLM JSON output with fallback for invalid values."""
        try:
            intent = Intent(data.get("intent", "unclear"))
        except ValueError:
            intent = Intent.UNCLEAR

        try:
            dialogue_act = DialogueAct(data.get("dialogue_act", "informing"))
        except ValueError:
            dialogue_act = DialogueAct.INFORMING

        entities = dict(data.get("entities") or {})
        if entities.get("daily_volume") is not None:
            try:
                if int(entities["daily_volume"]) <= 0:
                    del entities["daily_volume"]
            except (ValueError, TypeError):
                del entities["daily_volume"]

        return cls(
            intent=intent,
            dialogue_act=dialogue_act,
            product_related=bool(data.get("product_related", False)),
            confidence=float(data.get("confidence", 0.0)),
            sentiment=str(data.get("sentiment", "neutral")),
            language=str(data.get("language", "en")),
            entities=entities,
            requirement_updates=data.get("requirement_updates") or {},
            requested_action=str(data.get("requested_action", "ask_clarification")),
            tool_request=data.get("tool_request"),
        )


# ---------------------------------------------------------------------------
# Route Decision (from decision engine)
# ---------------------------------------------------------------------------
@dataclass
class RouteDecision:
    """Decision made by the decision engine about which route to execute."""
    route: RouteName
    tool: Optional[str] = None
    tool_arguments: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


# ---------------------------------------------------------------------------
# Route Result (returned by route handlers)
# ---------------------------------------------------------------------------
@dataclass
class RouteResult:
    """Result returned by a route handler after processing."""
    reply: str = ""
    product_cards: List[Dict[str, Any]] = field(default_factory=list)
    consumable_cards: List[Dict[str, Any]] = field(default_factory=list)
    suggested_chips: List[str] = field(default_factory=list)
    source: str = "ai_agent"
    needs_composition: bool = False  # True = send to LLM composer for natural language
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    instruction: str = ""  # Instruction for the response composer
