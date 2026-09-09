"""
Unit tests for Claim Validator (Zero-Hallucination Guardrails).
Tests detection and rejection of hallucinated DPI, print speed, scanner presence,
roll width, and unsupported features, along with fallback reversion.
"""
import unittest
from validation.claim_validator import OutputValidator


class TestClaimValidator(unittest.TestCase):
    def setUp(self):
        self.validator = OutputValidator()
        self.sample_evidence = [
            {
                "name": "Epson SureColor SC-T3100 Desktop Large Format Printer",
                "sku": "C11CF11302A0",
                "specs": {
                    "print_resolution": "2400 x 1200 dpi",
                    "print_speed": "34 sec/A1",
                    "max_print_width": "24-inch (610mm)",
                    "has_scanner": False,
                    "ink_technology": "UltraChrome XD2"
                }
            },
            {
                "name": "Epson SureColor SC-T5400M Multifunction Printer with Scanner",
                "sku": "C11CH65301A0",
                "specs": {
                    "print_resolution": "2400 x 1200 dpi",
                    "print_speed": "22 sec/A1",
                    "max_print_width": "36-inch (914mm)",
                    "has_scanner": True,
                    "scanner_resolution": "600 dpi",
                    "ink_technology": "UltraChrome XD2"
                }
            }
        ]

    def test_resolution_exact_match(self):
        text = "The SC-T3100 delivers crisp lines with a 2400 x 1200 dpi resolution."
        is_valid, reason, violations = self.validator.validate_all(text, self.sample_evidence)
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)

    def test_resolution_hallucination_detected(self):
        text = "The SC-T3100 boasts an ultra-high 4800 x 2400 dpi resolution for CAD blueprints."
        is_valid, reason, violations = self.validator.validate_all(text, self.sample_evidence)
        self.assertFalse(is_valid)
        self.assertTrue(any("resolution" in v.lower() for v in violations))

    def test_scanner_hallucination_on_print_only_device(self):
        # SC-T3100 does not have a scanner
        text = "The SC-T3100 features a built-in integrated CIS scanner for digitizing documents."
        evidence = [self.sample_evidence[0]]  # SC-T3100 only
        is_valid, reason, violations = self.validator.validate_all(text, evidence)
        self.assertFalse(is_valid)
        self.assertTrue(any("scanner" in v.lower() for v in violations))

    def test_scanner_claim_valid_on_multifunction_device(self):
        # SC-T5400M has a scanner
        text = "The SC-T5400M includes an integrated scanner for scanning and copying blueprints."
        evidence = [self.sample_evidence[1]]  # SC-T5400M
        is_valid, reason, violations = self.validator.validate_all(text, evidence)
        self.assertTrue(is_valid)

    def test_speed_hallucination_detected(self):
        # SC-T3100 is 34 sec/A1. Claiming 10 sec/A1 is hallucinated.
        text = "Prints blazing fast CAD sheets in only 10 sec per A1."
        is_valid, reason, violations = self.validator.validate_all(text, [self.sample_evidence[0]])
        self.assertFalse(is_valid)
        self.assertTrue(any("speed" in v.lower() for v in violations))

    def test_speed_valid_match(self):
        text = "The SC-T3100 produces an A1 print in 34 seconds."
        is_valid, reason, violations = self.validator.validate_all(text, [self.sample_evidence[0]])
        self.assertTrue(is_valid)

    def test_width_hallucination_detected(self):
        # SC-T3100 is 24-inch. Claiming 44-inch is hallucinated.
        text = "The SC-T3100 is a 44-inch wide format printer."
        is_valid, reason, violations = self.validator.validate_all(text, [self.sample_evidence[0]])
        self.assertFalse(is_valid)
        self.assertTrue(any("width" in v.lower() for v in violations))

    def test_sanitization_fallback(self):
        text = "The SC-T3100 has 4800 dpi and a built-in scanner."
        fallback = "The SC-T3100 is a 24-inch CAD printer offering 2400 x 1200 dpi."
        sanitized = self.validator.sanitize(text, [self.sample_evidence[0]], fallback=fallback)
        self.assertEqual(sanitized, fallback)


if __name__ == "__main__":
    unittest.main()
