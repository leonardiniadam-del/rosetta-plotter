import logging
import sys
from types import SimpleNamespace

import pytest

from rosetta.engine import options as engine_options
from rosetta.engine.options import (
    MIN_PEN_TRAVEL, Advanced, PlotSettings, advanced_from_dict, apply_settings, make_axidraw,
)


def test_pen_up_follows_pen_down():
    assert PlotSettings(model=1, pen_down=30).pen_up == 60
    assert PlotSettings(model=1, pen_down=55).pen_up == 75
    assert PlotSettings(model=1, pen_down=80).pen_up == 100
    assert PlotSettings(model=1, pen_down=95).pen_up == 100  # the clamp holds even for odd input


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


@pytest.mark.parametrize("pen_down", [81, -1, 30.5, True])
def test_apply_settings_rejects_a_pen_down_height_that_could_never_lift(pen_down):
    ad = SimpleNamespace(options=SimpleNamespace())
    with pytest.raises(ValueError):
        apply_settings(ad, PlotSettings(model=1, pen_down=pen_down))


def test_apply_settings_accepts_the_highest_pen_down_height():
    ad = SimpleNamespace(options=SimpleNamespace())
    apply_settings(ad, PlotSettings(model=1, pen_down=80))
    assert (ad.options.pen_pos_down, ad.options.pen_pos_up) == (80, 100)


@pytest.mark.parametrize("penlift", [0, 4])
def test_apply_settings_rejects_an_unknown_pen_lift(penlift):
    ad = SimpleNamespace(options=SimpleNamespace())
    with pytest.raises(ValueError):
        apply_settings(ad, PlotSettings(model=1, penlift=penlift))


def test_ensure_std_streams_replaces_missing_console_streams(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    try:
        engine_options.ensure_std_streams()
        sys.stdout.write("EMS says hello\n")
        sys.stderr.write("EMS says hello\n")
    finally:
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:
                stream.close()


def test_ensure_std_streams_leaves_real_streams_alone(monkeypatch):
    stream = SimpleNamespace(write=lambda text: None)
    monkeypatch.setattr(sys, "stderr", stream)
    engine_options.ensure_std_streams()
    assert sys.stderr is stream


def test_make_axidraw_works_without_a_console(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    try:
        make_axidraw()
        assert sys.stderr is not None and sys.stdout is not None
    finally:
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:
                stream.close()


def test_make_axidraw_sends_ems_messages_to_the_log(caplog):
    ad = make_axidraw()
    with caplog.at_level(logging.INFO, logger="rosetta.ems"):
        ad.user_message_fun("Plot paused by keyboard interrupt.")
    assert "Plot paused by keyboard interrupt." in caplog.text




def _options_after(settings):
    ad = SimpleNamespace(options=SimpleNamespace())
    apply_settings(ad, settings)
    return ad.options


def test_advanced_options_reach_the_engine():
    advanced = Advanced(
        pen_up=90, speed_pendown=40, speed_penup=60, accel=50, pen_rate_raise=80,
        pen_rate_lower=30, pen_delay_up=100, pen_delay_down=200, reordering=4,
        hiding=True, resolution=2,
    )
    o = _options_after(PlotSettings(model=1, pen_down=30, advanced=advanced))
    assert (o.pen_pos_up, o.speed_pendown, o.speed_penup, o.accel) == (90, 40, 60, 50)
    assert (o.pen_rate_raise, o.pen_rate_lower, o.pen_delay_up, o.pen_delay_down) == (80, 30, 100, 200)
    assert (o.reordering, o.hiding, o.resolution) == (4, True, 2)


def test_without_overrides_the_pen_type_sets_the_speed():
    o = _options_after(PlotSettings(model=1, pen_type="brush"))
    assert (o.speed_pendown, o.speed_penup, o.pen_pos_up, o.accel, o.resolution) == (12, 75, 60, 75, 1)


def test_an_advanced_pen_up_height_overrides_the_automatic_one():
    assert PlotSettings(model=1, pen_down=30, advanced=Advanced(pen_up=45)).pen_up == 45


def test_an_advanced_pen_up_height_must_clear_pen_down():
    settings = PlotSettings(model=1, pen_down=50, advanced=Advanced(pen_up=50 + MIN_PEN_TRAVEL - 1))
    with pytest.raises(ValueError, match="at least 10 above"):
        _options_after(settings)


@pytest.mark.parametrize("values, message", [
    ({"accel": 0}, "Acceleration must be from 1 to 100"),
    ({"reordering": 3}, "Path order must be one of 0, 1, 2, 4"),
    ({"pen_delay_up": -5}, "from 0 to 1000"),
    ({"speed_penup": 50.5}, "whole number"),
    ({"accel": True}, "whole number"),
    ({"hiding": 1}, "on or off"),
    ({"warp": 9}, "Unknown advanced option: warp"),
])
def test_advanced_from_dict_rejects_bad_values(values, message):
    with pytest.raises(ValueError, match=message):
        advanced_from_dict(values)


def test_advanced_from_dict_accepts_none_for_the_automatic_values():
    assert advanced_from_dict({"pen_up": None, "speed_pendown": None, "accel": 60}) == Advanced(accel=60)


def test_apply_settings_checks_advanced_values_too():
    with pytest.raises(ValueError, match="Acceleration"):
        _options_after(PlotSettings(model=1, advanced=Advanced(accel=500)))
