"""
Qualification Route (Retired / Passthrough).
The multi-turn qualification and question-asking flow has been removed in preparation
for the new implementation plan. Requests pass directly to product_route.
"""
import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from routes import product_route

logger = logging.getLogger("route:qualification")


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    """Pass directly to product search / catalog handling without qualification questions."""
    logger.info("Qualification flow bypassed — forwarding to product route.")
    return product_route.handle(understanding, state, raw_message=raw_message)
