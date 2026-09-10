"""
Comprehensive test suite for DeterministicResponseValidator and the 11 factual grounding fixes.
"""

import unittest
from validation.deterministic_validator import (
    DeterministicResponseValidator,
    deterministic_validator,
    KNOWN_VALID_SKUS,
    SLUG_TO_PRODUCT_RULE,
)
from validation.claim_validator import (
    claim_validator,
    VERIFIED_PRODUCT_SLUGS,
)
from catalog.repository import catalog_repository


class TestDeterministicResponseValidator(unittest.TestCase):

    def test_epson_t5100m_source_url_matching(self):
        """Fix 1: Replace SC-T5400M with SC-T5100M when using the /epson-surecolor-sc-t5100m-plotter-printer/ source."""
        validator = DeterministicResponseValidator()

        # Invalid: SC-T5400M linked to sc-t5100m URL
        bad_reply = (
            "Check out the [Epson SureColor SC-T5400M](https://www.keplertechllc.com/product/epson-surecolor-sc-t5100m-plotter-printer/) "
            "for technical CAD drawings."
        )
        is_valid, violations = validator.validate(bad_reply, context={"source": "epson-surecolor-sc-t5100m-plotter-printer"})
        assert not is_valid
        assert any("Product name / URL mismatch" in v or "Product ID mismatch" in v for v in violations)

        # Valid: SC-T5100M linked to sc-t5100m URL
        good_reply = (
            "Check out the [Epson SureColor SC-T5100M](https://www.keplertechllc.com/product/epson-surecolor-sc-t5100m-plotter-printer/) "
            "which features an integrated 36-inch scanner and 34 sec/A1 print speed."
        )
        is_valid, violations = validator.validate(good_reply, context={"source": "epson-surecolor-sc-t5100m-plotter-printer"})
        assert is_valid
        assert len(violations) == 0

    def test_no_mismatched_product_name_url_spec(self):
        """Fix 2: Never allow a product name, URL and specification record belonging to different product IDs in the same answer."""
        validator = DeterministicResponseValidator()

        # Mismatched name and URL
        mismatched_reply = (
            "We recommend the [Epson SureColor SC-T5400M](https://www.keplertechllc.com/product/epson-surecolor-sc-t5100m-plotter-printer/) "
            "with 22 sec/A1 speed."
        )
        is_valid, violations = validator.validate(mismatched_reply)
        assert not is_valid
        assert len(violations) > 0

    def test_cx02_4x6_media_sku_and_model(self):
        """Fix 3 & 5: CX-02 4x6 media model_number = CX2-MS46-2PC, sku = CX2.4x6. Never reject CX2.4x6."""
        validator = DeterministicResponseValidator()

        assert "CX2.4X6" in KNOWN_VALID_SKUS
        assert KNOWN_VALID_SKUS["CX2.4X6"] == "citizen-cx-02"

        # Valid answer mentioning the correct SKU
        valid_reply = (
            "The approved 4×6″ media for the Citizen CX-02 is the **CX2-MS46-2PC** (catalogue SKU: **CX2.4x6**). "
            "It delivers 800 prints per box."
        )
        is_valid, violations = validator.validate(valid_reply, context={"product_id": "citizen-cx-02"})
        assert is_valid

        # Invalid answer falsely claiming CX2.4x6 is invalid or does not exist
        rejecting_reply = (
            "CX2.4x6 is not a valid catalogue SKU for our printers."
        )
        is_valid, violations = validator.validate(rejecting_reply)
        assert not is_valid
        assert any("Valid SKU falsely rejected" in v for v in violations)

    def test_cx02w_8x12_media_sku_and_model(self):
        """Fix 4: CX-02W 8x12 media model_number = CX2W 812, sku = CX2W 812."""
        validator = DeterministicResponseValidator()

        assert "CX2W 812" in KNOWN_VALID_SKUS
        assert KNOWN_VALID_SKUS["CX2W 812"] == "citizen-cx-02w"

        valid_reply = (
            "For the Citizen CX-02W 8-inch wide printer, the verified media pack is **CX2W 812** "
            "(SKU: **CX2W 812**), producing 220 prints per box (2 rolls of 110 prints)."
        )
        is_valid, violations = validator.validate(valid_reply, context={"product_id": "citizen-cx-02w"})
        assert is_valid

    def test_cx02w_rejects_cx24x6_linkage(self):
        """Cannot claim CX2.4x6 works in CX-02W."""
        validator = DeterministicResponseValidator()

        bad_reply = "You can use CX2.4x6 media for your CX-02W printer."
        is_valid, violations = validator.validate(bad_reply, context={"product_id": "citizen-cx-02w"})
        assert not is_valid
        assert any("Consumable linkage violation" in v for v in violations)

    def test_cx02_verified_sizes_include_6x9(self):
        """Fix 6: Include 6x9 among verified CX-02 sizes."""
        cx02 = catalog_repository.get_by_id("citizen-cx-02")
        assert cx02 is not None
        # Check structured specs print_speed and max_width
        assert "6x9" in cx02.structured_specs.get("print_speed", {})
        assert "6x9" in cx02.structured_specs.get("max_width", {}).get("note", "")
        # Check deterministic validator metrics
        from validation.deterministic_validator import VERIFIED_METRICS
        assert "6x9" in VERIFIED_METRICS["citizen-cx-02"]["sizes"]

    def test_cx02_6x8_speed_is_15_6_seconds(self):
        """Fix 7: Correct CX-02 6x8 speed to the catalogue value of 15.6 seconds (fail on 21.8s)."""
        validator = DeterministicResponseValidator()

        # Reject 21.8 seconds
        bad_reply = (
            "The Citizen CX-02 prints 4x6 photos in 9.8 seconds and 6x8 in 21.8 sec."
        )
        is_valid, violations = validator.validate(bad_reply, context={"product_id": "citizen-cx-02"})
        assert not is_valid
        assert any("CX-02 6x8 speed is 15.6 seconds" in v for v in violations)

        # Accept 15.6 seconds
        good_reply = (
            "The Citizen CX-02 prints 4x6 photos in 9.8 seconds and 6x8 in 15.6 seconds."
        )
        is_valid, violations = validator.validate(good_reply, context={"product_id": "citizen-cx-02"})
        assert is_valid

    def test_cy02_weight_is_13_8_kg_product_16_5_kg_package(self):
        """Fix 8: CY-02 product weight is 13.8 kg and package weight is 16.5 kg. Remove '18 kg loaded'."""
        validator = DeterministicResponseValidator()

        # Reject unverified 18 kg
        bad_reply = (
            "The Citizen CY-02 has a robust chassis weighing 18 kg loaded for kiosks."
        )
        is_valid, violations = validator.validate(bad_reply, context={"product_id": "citizen-cy-02"})
        assert not is_valid
        assert any("18 kg" in v for v in violations)

        # Accept 13.8 kg product / 16.5 kg package
        good_reply = (
            "The Citizen CY-02 features a robust chassis weighing 13.8 kg (package weight: 16.5 kg)."
        )
        is_valid, violations = validator.validate(good_reply, context={"product_id": "citizen-cy-02"})
        assert is_valid

    def test_never_say_100_percent_guaranteed(self):
        """Fix 9: Never say '100% guaranteed'."""
        validator = DeterministicResponseValidator()

        bad_reply = "Compatibility is 100% guaranteed with our original media."
        is_valid, violations = validator.validate(bad_reply)
        assert not is_valid
        assert any("Absolute guarantee violation" in v for v in violations)

    def test_unsupported_chassis_spool_claims_blocked(self):
        """Fix 10: Remove unsupported claims about chassis fit, spool construction, printhead damage and warranty invalidation."""
        bad_claims = [
            "Using this paper will void your manufacturer warranty immediately.",
            "Third party ribbons can cause permanent thermal printhead damage.",
            "The custom spool construction prevents proper chassis fit inside the bay.",
            "The media bay fit is too tight for non-OEM spools.",
        ]
        for claim in bad_claims:
            assert claim_validator.contains_unsupported_consumable_claim(claim), f"Expected claim to be flagged: {claim}"
            unsupported = claim_validator.get_unsupported_claims(claim)
            assert len(unsupported) > 0

    def test_unknown_models_use_approved_catalogue_phrase(self):
        """Fix 11: For unknown models, say 'not found in our approved catalogue', not 'does not exist'."""
        validator = DeterministicResponseValidator()

        bad_reply = "The Citizen CX-02S does not exist and was never manufactured."
        is_valid, violations = validator.validate(bad_reply)
        assert not is_valid
        assert any("Global absence claim violation" in v for v in violations)

        good_reply = "The Citizen CX-02S is not found in our approved catalogue. We offer the verified Citizen CX-02 and CX-02W."
        is_valid, violations = validator.validate(good_reply)
        assert is_valid
