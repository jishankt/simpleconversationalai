"""Regression tests for requirement extraction loopholes."""
from routes.qualification_route import (
    _explicit_daily_volume,
    _explicit_scan_requirement,
    _explicit_print_size,
)


def test_bare_yes_only_answers_scanner_when_scanner_is_awaited():
    assert _explicit_scan_requirement("yes", None) is None
    assert _explicit_scan_requirement("yes", "print_size") is None
    assert _explicit_scan_requirement("yes", "scan_required") is True


def test_no_scanner_is_explicit_false():
    assert _explicit_scan_requirement("i need a0 but no scanner", None) is False


def test_model_number_is_not_daily_volume():
    assert _explicit_daily_volume("i am looking at the t5400", "daily_volume") is None
    assert _explicit_daily_volume("a0 36 inch", "daily_volume") is None


def test_bare_number_can_answer_daily_volume_when_awaited():
    assert _explicit_daily_volume("25", "daily_volume") == 25


def test_explicit_daily_phrase_is_volume():
    assert _explicit_daily_volume("around 40 drawings per day", None) == 40


def test_size_extraction_is_explicit():
    assert _explicit_print_size("i normally need a0 drawings") == "A0"
    assert _explicit_print_size("i need 24 inch output") == "A1"
