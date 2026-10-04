import pytest
from axidrawinternal import axidraw_conf

from rosetta.models import MODELS, PEN_TYPES, PEN_UP_SPEED, get_model

EMS_SUFFIXES = {1: "default", 2: "V3A3", 3: "V3XLX", 4: "MiniKit", 5: "SEA1", 6: "SEA2", 7: "V3B6"}


def test_all_seven_ems_models_present():
    assert sorted(MODELS) == [1, 2, 3, 4, 5, 6, 7]


def test_travel_matches_ems_inches_times_25_4():
    x, y = get_model(5).travel_mm  # SE/A1: 34.02 x 23.39 in
    assert x == pytest.approx(864.108)
    assert y == pytest.approx(594.106)
    assert get_model(1).travel_mm == pytest.approx((299.974, 217.932))


def test_travel_table_matches_installed_ems_config():
    for number, suffix in EMS_SUFFIXES.items():
        model = get_model(number)
        assert model.travel_x_in == getattr(axidraw_conf, f"x_travel_{suffix}")
        assert model.travel_y_in == getattr(axidraw_conf, f"y_travel_{suffix}")


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        get_model(9)


def test_pen_types():
    assert PEN_TYPES["fineliner"].speed_pendown == 25
    assert PEN_TYPES["marker"].speed_pendown == 35
    assert PEN_TYPES["brush"].speed_pendown == 12
    assert PEN_UP_SPEED == 75
