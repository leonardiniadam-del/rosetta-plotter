import pytest

from rosetta.units import MM_PER_INCH, length_to_mm, parse_length


def test_parse_length_splits_value_and_unit():
    assert parse_length("12.5mm") == (12.5, "mm")
    assert parse_length(" 100% ") == (100.0, "%")
    assert parse_length("612") == (612.0, "")
    assert parse_length("1e2PX") == (100.0, "px")


def test_parse_length_rejects_junk():
    assert parse_length("abc") == (None, "")
    assert parse_length(None) == (None, "")


def test_length_to_mm_absolute_units():
    assert length_to_mm("1in", 96) == pytest.approx(MM_PER_INCH)
    assert length_to_mm("72pt", 96) == pytest.approx(25.4)
    assert length_to_mm("2cm", 96) == pytest.approx(20.0)
    assert length_to_mm("6pc", 96) == pytest.approx(25.4)


def test_length_to_mm_implicit_units_use_px_per_inch():
    assert length_to_mm("96", 96) == pytest.approx(25.4)
    assert length_to_mm("72px", 72) == pytest.approx(25.4)


def test_length_to_mm_unsupported_returns_none():
    assert length_to_mm("50%", 96) is None
    assert length_to_mm("3em", 96) is None
    assert length_to_mm(None, 96) is None
