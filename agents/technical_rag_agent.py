"""
Technical RAG & Comparison Specialist Agent (Agent 3).
Handles technical specifications, deep RAG retrieval, multi-model comparisons,
superlatives, and brochure/datasheet downloads.
"""

import logging
from typing import Dict, Any, List, Optional
from domain.conversation_types import RouteName, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agents.base_agent import BaseSpecialistAgent
from routes import comparison_route

logger = logging.getLogger("agent.technical_rag")


class TechnicalRagAgent(BaseSpecialistAgent):
    def __init__(self):
        super().__init__(
            agent_id="technical_rag",
            name="Technical & Comparison Specialist",
            role="Technical RAG & Comparison",
            theme_color="#8b5cf6",
            badge="⚡ Tech & Comparison",
            icon="fas fa-microchip",
        )

    def handle_turn(
        self,
        raw_message: str,
        normalized_message: str,
        understanding: Optional[LLMUnderstanding],
        state: ConversationState,
        **kwargs,
    ) -> RouteResult:
        logger.info(f"TechnicalRagAgent handling message: {normalized_message[:60]}")
        res = comparison_route.handle(understanding, state, raw_message=normalized_message)
        res.source = "agent:technical_rag:comparison"
        return res


technical_rag_agent = TechnicalRagAgent()
