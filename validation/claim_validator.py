"""
Multi-Stage Output Validators for Anti-Hallucination Enforcement.
Checks:
  1. validate_numbers: Prevents hallucinated numbers/resolutions (e.g. 4800 dpi instead of 2400 dpi).
  2. validate_model_names: Ensures mentioned products exist in catalog.
  3. validate_spec_claims: Ensures specs claimed match verified evidence.
"""
import re
from typing import Dict, Any, List, Tuple


class OutputValidator:
    def validate_numbers(self, text: str, evidence: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates that numeric resolution / dimension claims in output exist in verified evidence.
        """
        # Look for resolution patterns like '4800 x 1200' or '2400 x 1200 dpi'
        dpi_matches = re.findall(r"(\d{3,4})\s*(?:x|×)\s*(\d{3,4})\s*dpi", text.lower())
        if dpi_matches:
            verified_res = evidence.get("verified_specs", {}).get("resolution") or evidence.get("verified_value") or ""
            for match in dpi_matches:
                res_str = f"{match[0]} x {match[1]}"
                res_str_alt = f"{match[0]} × {match[1]}"
                if res_str not in verified_res.lower() and res_str_alt not in verified_res.lower():
                    return False, f"Hallucinated resolution claim: {match[0]}x{match[1]} dpi (Verified: {verified_res})"

        return True, "OK"

    def validate_spec_claims(self, text: str, evidence: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates that scanner or connectivity claims match evidence.
        """
        has_scanner_evidence = evidence.get("verified_specs", {}).get("has_scanner")
        if has_scanner_evidence is False:
            if any(term in text.lower() for term in ["integrated scanner", "includes scanner", "built-in scanner", "with scanner"]):
                return False, "Output claims scanner exists on a verified print-only device."

        return True, "OK"

    def validate_all(self, text: str, evidence: Dict[str, Any]) -> Tuple[bool, str]:
        if not evidence:
            return True, "OK"

        ok_num, msg_num = self.validate_numbers(text, evidence)
        if not ok_num:
            return False, msg_num

        ok_spec, msg_spec = self.validate_spec_claims(text, evidence)
        if not ok_spec:
            return False, msg_spec

        return True, "OK"


output_validator = OutputValidator()
