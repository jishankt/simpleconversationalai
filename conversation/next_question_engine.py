"""
Deterministic Next-Question Engine.
Evaluates category schemas and conversation state to ask strictly ONE question at a time.
Never asks for already known fields.
"""
from typing import Optional, Dict, Any
from domain.conversation_state import ConversationState
from conversation.requirement_schema import REQUIREMENT_SCHEMAS, QUESTIONS_BY_FIELD


class NextQuestionEngine:
    def evaluate_next_step(self, state: ConversationState) -> Optional[Dict[str, Any]]:
        """
        Evaluates current requirements against the category schema.
        Returns the next question dictionary if missing requirements exist, or None if ready.
        """
        cat = state.category
        turn_count = getattr(state, "turn_count", 0)

        if not cat:
            state.awaiting_field = "category"
            last_resp = (state.last_assistant_response or "").lower()
            has_welcomed = bool(
                state.last_assistant_response
                or getattr(state, "turn_count", 0) > 0
                or (hasattr(state, "history_turns") and len(state.history_turns) > 0)
            )
            already_asked_cat = "printing or scanning solution" in last_resp or "type of print" in last_resp

            if already_asked_cat:
                q_text = "We offer four specialized printing categories. What will you primarily be printing?"
                pills = [
                    "Office & Business Documents",
                    "CAD & Technical Blueprints",
                    "Photo & Fine Art",
                    "Photo Booth / Events"
                ]
            elif has_welcomed:
                q_text = "What type of printing or scanning solution are you looking for?"
                pills = [
                    "Office Enterprise Printers",
                    "Photo & Fine Art",
                    "CAD & Technical Plotters",
                    "Photo Booth / Dye-Sub",
                    "Document Scanners"
                ]
            else:
                q_text = "Welcome to Kepler Tech! What type of printing or scanning solution are you looking for?"
                pills = [
                    "Office Enterprise Printers",
                    "Photo & Fine Art",
                    "CAD & Technical Plotters",
                    "Photo Booth / Dye-Sub",
                    "Document Scanners"
                ]

            return {
                "field": "category",
                "question": q_text,
                "pills": pills
            }

        schema = REQUIREMENT_SCHEMAS.get(cat)
        if not schema:
            return None

        reqs = state.requirements or {}

        # 1. Critical fields (Must be collected first)
        for field in schema.get("critical", []):
            if field not in reqs or reqs[field] is None:
                state.awaiting_field = field
                q_info = self._get_tailored_question(field, cat)
                return {
                    "field": field,
                    "question": q_info["question"],
                    "pills": q_info.get("pills", [])
                }

        # 2. Important fields (Secondary qualification)
        for field in schema.get("important", []):
            if field not in reqs or reqs[field] is None:
                state.awaiting_field = field
                q_info = self._get_tailored_question(field, cat)
                return {
                    "field": field,
                    "question": q_info["question"],
                    "pills": q_info.get("pills", [])
                }

    def _get_tailored_question(self, field: str, category: str) -> Dict[str, Any]:
        """Returns questions and pills customized for the specific product category."""
        if field == "daily_volume":
            if category == "office_enterprise":
                return {
                    "question": "Approximately how many pages or documents do you print per day?",
                    "pills": ["Low (under 50 pages)", "Medium (50–200 pages)", "High (200+ pages)"]
                }
            elif category == "technical_cad":
                return {
                    "question": "Approximately how many drawings or pages do you print per day?",
                    "pills": ["Low (1–10 drawings)", "Medium (10–50 drawings)", "High Volume (50+)"]
                }
            elif category in ("photo_fine_art", "photo_booth"):
                return {
                    "question": "Approximately how many photos or prints do you produce per day?",
                    "pills": ["Occasional / Studio", "High volume batch printing"]
                }
            return {
                "question": "Approximately how many pages do you print per day?",
                "pills": ["Low (1-10)", "Medium (10-50)", "High Volume (50+)"]
            }

        if field == "print_size":
            if category == "office_enterprise":
                return {
                    "question": "What paper sizes do you need (e.g., standard A4 or up to A3)?",
                    "pills": ["Standard A4", "A3 / Tabloid", "Both A4 and A3"]
                }
            elif category == "photo_fine_art":
                return {
                    "question": "What print size do you need — compact desktop or large-format?",
                    "pills": ["Small (Desktop A3+)", "Medium (17-inch A2)", "Large (24-inch)", "Production (44-inch)"]
                }
            elif category == "photo_booth":
                return {
                    "question": "What photo print sizes do you need (e.g., 4x6, 6x8, or 8x12 inches)?",
                    "pills": ["Small (4x6 inches)", "Medium (6x8 inches)", "Large (8x12 inches)"]
                }
            elif category == "technical_cad":
                return {
                    "question": "What maximum drawing or print size do you need?",
                    "pills": ["Small (24-inch / A1)", "Large (36-inch / A0)"]
                }

        if field == "scan_required":
            if category == "office_enterprise":
                return {
                    "question": "Do you need built-in scanning and copying, or print-only?",
                    "pills": ["Multifunction (Print/Scan/Copy)", "Print Only"]
                }
            return {
                "question": "Do you need scanning as well, or printing only?",
                "pills": ["Yes, Need Scanner", "No, Print Only"]
            }

        return QUESTIONS_BY_FIELD.get(field, {
            "question": f"What are your requirements for {field.replace('_', ' ')}?",
            "pills": []
        })

        # All critical and important requirements collected
        state.awaiting_field = None
        return None
