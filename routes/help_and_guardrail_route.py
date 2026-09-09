"""
Handler for Conversation Help and Guardrail Rejections.
Ensures process questions and pricing requests never produce product cards.
"""

from domain.conversation_types import RouteResult, LLMUnderstanding
from domain.conversation_state import ConversationState


class ConversationHelpHandler:
    @staticmethod
    def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
        reply = (
            "I can help you find printers, compare verified specifications and identify compatible consumables. "
            "What will you primarily print?"
        )
        return RouteResult(
            reply=reply,
            product_cards=[],
            consumable_cards=[],
            suggested_chips=["Technical CAD Plotters", "Photo Printers", "Office Enterprise MFPs", "Document Scanners"],
            source="route:conversation_help",
            needs_composition=False,
        )


class GuardrailHandler:
    @staticmethod
    def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
        from guardrails import PRICE_REFUSAL
        return RouteResult(
            reply=PRICE_REFUSAL,
            product_cards=[],
            consumable_cards=[],
            suggested_chips=["View Large Format Plotters", "Photo Printers", "Office MFPs", "Contact Sales"],
            source="guardrail_rule",
            needs_composition=False,
        )


conversation_help_route = ConversationHelpHandler()
guardrail_route = GuardrailHandler()
