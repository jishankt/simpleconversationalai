"""
Support Route for Kepler Tech Conversational AI.
Handles troubleshooting queries with deterministic guidance.
"""

from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState


def handle(understanding: LLMUnderstanding, state: ConversationState) -> RouteResult:
    """Handle troubleshooting queries."""
    return RouteResult(
        reply="For print quality issues, we recommend performing an automated nozzle check and head cleaning through the printer utility menu. If the issue persists, please contact our support team at info@keplertech.ae or +971 4 323 1008.",
        suggested_chips=["Nozzle Check", "Paper Feed Issues", "Contact Support"],
        source="route:support",
        needs_composition=True,
        instruction="Provide troubleshooting guidance based on the customer's specific issue description.",
    )
