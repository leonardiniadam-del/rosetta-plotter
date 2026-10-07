import math

import pytest

from rosetta.app.paper import CUSTOM, PAPER_SIZES, paper_dimensions
from rosetta.errors import UserProblem


def test_the_spec_presets_are_all_there():
    assert list(PAPER_SIZES) == ["letter", "legal", "tabloid", "a4", "a3", "a2", "a1"]


def test_landscape_runs_the_long_side_along_the_rail():
    assert paper_dimensions("letter", "landscape") == pytest.approx((279.4, 215.9))


def test_portrait_runs_the_long_side_toward_the_student():
    assert paper_dimensions("a4", "portrait") == pytest.approx((210.0, 297.0))


def test_custom_sizes_are_taken_as_typed():
    assert paper_dimensions(CUSTOM, "portrait", 300, 200) == (300.0, 200.0)


@pytest.mark.parametrize("width, height", [
    (0, 100), (-5, 100), (math.nan, 100), (100, math.inf), (5000, 100), (None, 100), (True, 100), ("10", 100),
])
def test_custom_sizes_must_be_usable(width, height):
    with pytest.raises(UserProblem, match="between 0 and 2000 mm"):
        paper_dimensions(CUSTOM, "landscape", width, height)


def test_unknown_size_or_orientation_is_a_programming_error():
    with pytest.raises(ValueError):
        paper_dimensions("b5", "landscape")
    with pytest.raises(ValueError):
        paper_dimensions("a4", "sideways")


def test_user_problem_keeps_its_details():
    problem = UserProblem("The plot stopped.", details="SerialException: gone")
    assert (str(problem), problem.details) == ("The plot stopped.", "SerialException: gone")
    assert UserProblem("Plain.").details == ""
