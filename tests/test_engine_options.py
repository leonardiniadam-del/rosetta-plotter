from types import SimpleNamespace

import pytest

from rosetta.engine.options import PlotSettings, apply_settings


def test_pen_up_follows_pen_down():
    assert PlotSettings(model=1, pen_down=30).pen_up == 60
    assert PlotSettings(model=1, pen_down=55).pen_up == 75
    assert PlotSettings(model=1, pen_down=95).pen_up == 100


def test_apply_settings_sets_ems_options():
    ad = SimpleNamespace(options=SimpleNamespace())
    apply_settings(ad, PlotSettings(model=5, penlift=3, pen_down=40, pen_type="brush"))
    o = ad.options
    assert (o.model, o.penlift) == (5, 3)
    assert (o.pen_pos_down, o.pen_pos_up) == (40, 60)
    assert (o.speed_pendown, o.speed_penup) == (12, 75)
    assert o.auto_rotate is False
    assert (o.reordering, o.hiding) == (2, False)


def test_apply_settings_rejects_unknown_values():
    ad = SimpleNamespace(options=SimpleNamespace())
    with pytest.raises(ValueError):
        apply_settings(ad, PlotSettings(model=9))
    with pytest.raises(ValueError):
        apply_settings(ad, PlotSettings(model=1, pen_type="crayon"))
