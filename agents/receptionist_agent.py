"""
Receptionist & Concierge Agent (Agent 1).
Handles greetings, pleasantries, store hours, Dubai location, contact channels,
and broad printing category orientation.
"""

import logging
from typing import Dict, Any, List, Optional
from domain.conversation_types import Intent, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agents.base_agent import BaseSpecialistAgent
from routes import social_route, business_info_route

logger = logging.getLogger("agent.receptionist")


class ReceptionistAgent(BaseSpecialistAgent):
    def __init__(self):
        super().__init__(
            agent_id="receptionist",
            name="Kepler Concierge",
            role="Front Desk & Reception",
            theme_color="#10b981",
            badge="🌿 Front Desk",
            icon="fas fa-concierge-bell",
        )

    def handle_turn(
        self,
        raw_message: str,
        normalized_message: str,
        understanding: Optional[LLMUnderstanding],
        state: ConversationState,
        **kwargs,
    ) -> RouteResult:
        logger.info(f"Receptionist handling message: {normalized_message[:60]}")
        low = normalized_message.lower()

        # Check if this is a business info request (hours, location, contact, delivery)
        if any(k in low for k in ["hour", "time", "timing", "open", "working", "schedule",
                                  "where", "location", "address", "dubai", "office", "direction",
                                  "deliver", "shipping", "ship", "transport",
                                  "service", "installation", "training", "amc",
                                  "partner", "distributor"]):
            res = business_info_route.handle(understanding, state, raw_message=normalized_message)
            res.source = "agent:receptionist:business_info"
            if not res.suggested_chips:
                res.suggested_chips = ["Explore CAD Plotters", "Photo Printers", "Office MFPs", "Contact Sales"]
            return res

        # Otherwise route through social handler
        res = social_route.handle(understanding, state)
        res.source = "agent:receptionist:social"

        # Provide friendly exploration chips on greetings
        if understanding and understanding.intent == Intent.GREETING:
            res.suggested_chips = [
                "Technical CAD Plotters",
                "Photo & Fine Art Printers",
                "Office Enterprise MFPs",
                "Photo Booth Dye-Sub",
                "Office Hours & Location",
            ]

        return res


receptionist_agent = ReceptionistAgent()
