"""
Deterministic Next-Question & Clarification Engine.
Decides the next consultative question based on the CanonicalState.
"""
from typing import Optional, Dict, Any
from state.conversation_state import CanonicalState


class NextQuestionEngine:
    def evaluate_next_step(self, state: CanonicalState) -> Optional[Dict[str, Any]]:
        """
        Evaluates state. If requirements are incomplete, returns:
        {
            "field": str,
            "question": str,
            "pills": List[str]
        }
        If requirements are satisfied, returns None (ready for product retrieval).
        """
        cat = state.category
        reqs = state.requirements

        if not cat:
            return None

        # 1. Technical CAD & Blueprint Plotters
        if cat == "technical_cad":
            if "print_size" not in reqs:
                state.awaiting_field = "print_size"
                return {
                    "field": "print_size",
                    "question": "What maximum drawing size do you normally print?",
                    "pills": ["24-inch (A1)", "36-inch (A0)"]
                }

            if "scan_required" not in reqs:
                state.awaiting_field = "scan_required"
                return {
                    "field": "scan_required",
                    "question": "Do you need built-in scanning for blueprints?",
                    "pills": ["Yes, Need Scanner", "No, Print Only"]
                }

            if "daily_volume" not in reqs:
                state.awaiting_field = "daily_volume"
                return {
                    "field": "daily_volume",
                    "question": "Roughly how many drawings do you print per day?",
                    "pills": ["Low (1-10)", "Medium (10-50)", "High Volume (50+)"]
                }

            state.awaiting_field = None
            return None

        # 2. Consumables Flow
        elif cat == "consumable":
            if "printer_model" not in reqs and not state.active_printer_for_consumables:
                state.awaiting_field = "printer_model"
                return {
                    "field": "printer_model",
                    "question": "Which printer or scanner model do you need consumables for? Please select or enter your product name:",
                    "pills": ["SC-P900", "SC-T3100", "SC-F100", "SC-P700", "WF-C20600"]
                }

            state.awaiting_field = None
            return None

        # 3. Photo Booth & Events
        elif cat == "photo_booth":
            if "print_size" not in reqs:
                state.awaiting_field = "print_size"
                return {
                    "field": "print_size",
                    "question": "What photo print size do you primarily require?",
                    "pills": ["4x6\" Standard", "5x7\"", "6x8\" Strips"]
                }

            state.awaiting_field = None
            return None

        # 4. Scanners
        elif cat == "scanner":
            if "scanner_type" not in reqs:
                state.awaiting_field = "scanner_type"
                return {
                    "field": "scanner_type",
                    "question": "What document scanning requirement do you have?",
                    "pills": ["High-Speed Document Scanners", "A3 Large Format Flatbed", "Business Scanners"]
                }

            state.awaiting_field = None
            return None

        return None
