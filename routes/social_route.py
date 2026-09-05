"""
Social Route for Kepler Tech Conversational AI.
Handles greetings, name introductions, feedback, frustration, thanks,
and small talk WITHOUT triggering product search or RAG.

Critical rule: social messages must NOT remove product state.
When handling "my name is Jishan" mid-qualification, save the name
and then resume the pending question.
"""

import logging
from domain.conversation_types import Intent, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState

logger = logging.getLogger("route:social")


def handle(understanding: LLMUnderstanding, state: ConversationState) -> RouteResult:
    """Handle social intents. Never touches product state."""
    intent = understanding.intent
    entities = understanding.entities

    # ── Customer introduction ────────────────────────────────────────────
    if intent == Intent.CUSTOMER_INTRODUCTION:
        name = entities.get("customer_name", "").strip()
        if name:
            state.customer_name = name
            logger.info(f"Customer introduced as: {name}")

        # Check if there's a pending question to resume
        pending = state.pending_question
        if pending and name:
            reply = f"Nice to meet you, {name}! {pending}"
            state.consume_pending_question()
        elif name:
            reply = f"Nice to meet you, {name}! How can I help you today?"
        else:
            reply = "Nice to meet you! How can I help you today?"

        return RouteResult(
            reply=reply,
            suggested_chips=[],
            source="route:social",
        )

    # ── Greeting ─────────────────────────────────────────────────────────
    if intent == Intent.GREETING:
        if not state.history_turns or len(state.history_turns) <= 1:
            state.candidate_products = []
            state.active_product = None
            state.requirements = {}
            state.category = None
        if state.customer_name:
            reply = f"Hello, {state.customer_name}! How can I assist you today?"
        else:
            reply = "Hello! Welcome to Kepler Tech LLC. How can I assist you with your printing solutions today?"

        return RouteResult(
            reply=reply,
            suggested_chips=[],
            product_cards=[],
            consumable_cards=[],
            source="route:social",
        )

    # ── Positive feedback ────────────────────────────────────────────────
    if intent == Intent.POSITIVE_FEEDBACK:
        reply = "Thank you for the kind words! Is there anything else I can help you with?"
        return RouteResult(reply=reply, source="route:social")

    # ── Negative feedback ────────────────────────────────────────────────
    if intent == Intent.NEGATIVE_FEEDBACK:
        state.record_frustration()
        pending = state.pending_question

        if state.frustration_count >= 2:
            reply = "I apologize for the experience. Let me be more helpful."
            if pending:
                reply += f" {pending}"
                state.consume_pending_question()
        else:
            reply = "Fair point — I'll try to be more helpful. What would you like to know?"

        return RouteResult(reply=reply, source="route:social")

    # ── Frustration ──────────────────────────────────────────────────────
    if intent == Intent.FRUSTRATION:
        state.record_frustration()

        if state.frustration_count >= 3:
            reply = "I sincerely apologize. Let me get straight to helping you."
        elif "repeat" in (understanding.entities.get("complaint", "") or "").lower() or \
             state.frustration_count >= 2:
            reply = "You're right, I should not have repeated that. Let me continue from what you've already told me."
        else:
            reply = "I understand your frustration. Let me adjust my approach."

        # Don't ask a new question when frustrated — just acknowledge
        return RouteResult(reply=reply, source="route:social")

    # ── Small talk ───────────────────────────────────────────────────────
    if intent == Intent.SMALL_TALK:
        pending = state.pending_question
        if pending:
            reply = f"That's interesting! Now, {pending}"
            state.consume_pending_question()
        else:
            reply = "That's great! Is there anything I can help you with regarding printing equipment?"
        return RouteResult(
            reply=reply,
            suggested_chips=[],
            source="route:social",
        )

    # ── Conversation ending ──────────────────────────────────────────────
    if intent == Intent.CONVERSATION_ENDING:
        name_suffix = f", {state.customer_name}" if state.customer_name else ""
        reply = f"Thank you for contacting Kepler Tech LLC{name_suffix}! Feel free to reach out anytime."
        state.stage = "closing"
        return RouteResult(reply=reply, source="route:social")

    # ── Fallback for any other social intent ─────────────────────────────
    return RouteResult(
        reply="How can I help you today?",
        suggested_chips=[],
        source="route:social",
    )
