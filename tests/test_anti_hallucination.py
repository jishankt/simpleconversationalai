"""Regression tests for evidence-only product answering and recommendation."""
from agent.evidence_guard import answer_product_question, numbers_are_grounded
from agent.recommendation_engine import assess_product, rank_products


def test_missing_width_is_not_guessed_from_model_name():
    product = {"name": "Example T5400", "description": "CAD printer"}
    answer = answer_product_question(product, "What is the maximum width?")
    assert "couldn't verify" in answer.lower()
    assert "36" not in answer
    assert "914" not in answer


def test_missing_ink_does_not_default_to_ultrachrome():
    product = {"name": "Example Printer", "description": "Production printer"}
    answer = answer_product_question(product, "What ink technology does it use?")
    assert "couldn't verify" in answer.lower()
    assert "ultrachrome" not in answer.lower()


def test_missing_scanner_is_unknown_not_false():
    product = {"name": "Example Printer", "description": "Technical printer"}
    answer = answer_product_question(product, "Does it have a scanner?")
    assert "can't confirm" in answer.lower()
    assert "without" not in answer.lower()


def test_explicit_scanner_boolean_is_respected():
    product = {"name": "Example MFP", "has_scanner": True}
    answer = answer_product_question(product, "Can it scan?")
    assert "confirms scanning capability" in answer.lower()


def test_verified_width_is_copied_exactly():
    product = {"name": "Verified Plotter", "width": "36 inch / 914 mm"}
    answer = answer_product_question(product, "maximum width?")
    assert "36 inch / 914 mm" in answer


def test_numeric_validator_blocks_new_numbers():
    evidence = "Resolution: 2400 x 1200 dpi. Width: 36 inch."
    assert numbers_are_grounded("Resolution is 2400 x 1200 dpi.", evidence)
    assert not numbers_are_grounded("Resolution is 4800 x 2400 dpi.", evidence)


def test_recommendation_does_not_treat_unknown_scanner_as_match():
    product = {"name": "CAD Printer", "category": "Printer", "width": "36 inch / A0", "description": "CAD technical drawings"}
    result = assess_product(product, "technical_cad", {"print_size": "A0", "scan_required": True})
    assert "print_size" in result.matched
    assert "scan_required" in result.unknown
    assert result.confidence != "HIGH"


def test_verified_requirements_rank_ahead_of_unknown():
    verified = {
        "name": "Verified CAD MFP",
        "category": "Printer",
        "width": "36 inch / A0 / 914 mm",
        "has_scanner": True,
        "description": "CAD technical drawing scanner MFP",
    }
    unknown = {"name": "Unknown Printer", "category": "Printer", "description": "printer"}
    ranked = rank_products([unknown, verified], "technical_cad", {"print_size": "A0", "scan_required": True})
    assert ranked[0].product["name"] == "Verified CAD MFP"
    assert ranked[0].confidence == "HIGH"
